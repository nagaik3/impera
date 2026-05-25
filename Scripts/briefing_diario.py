#!/usr/bin/env python3
"""
Briefing Diário IMPERA — 10h seg-sáb
Panorama operacional das últimas 48h: RedTrack, ClickUp, Esteira, Automações.
Envia via Telegram e salva .txt para referência no Claude Code.

Crontab: 0 10 * * 1-6
"""

import os
import json
import time
import re
from datetime import datetime, timedelta
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from collections import Counter, defaultdict
from pathlib import Path
from impera_cache import rt_rate_limit

# === CONFIG ===
CLICKUP_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
REDTRACK_KEY = os.environ.get("REDTRACK_API_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
SCRIPTS_DIR = Path.home() / "Scripts"
DOCS_DIR = Path.home() / "Documents"
DATA_DIR = SCRIPTS_DIR / "data"

CLICKUP_LISTS = {
    "COPY": "901324556390",
    # Lista unificada — EDIÇÃO agora na COPY
    "TRÁFEGO": "901324476398",
    "SOLICITAÇÕES": "901324763465",
}

# Campaign name parser (simplified)
NICHO_MAP = {
    "DB": "Diabetes", "EM": "Emagrecimento", "DA": "Dor Articular",
    "PR": "Próstata", "CL": "Colesterol", "HT": "Hipertensão",
    "MM": "Memória", "QC": "Queda Capilar", "AN": "Ansiedade",
    "VC": "Visão", "FG": "Fígado", "IM": "Imunidade",
}

GESTOR_MAP = {
    "DC": "Douglas", "GF": "Gabriel Fraza", "LC": "Lucas Cavalcanti",
    "LD": "Ludson", "IG": "Iago",
}


def fmt(val):
    """Formata valor monetário."""
    if val >= 1_000_000:
        return f"R${val/1_000_000:.2f}M"
    if val >= 1_000:
        return f"R${val/1_000:.1f}k"
    return f"R${val:.0f}"


def arrow(cur, prev):
    """Seta de comparação."""
    if prev == 0:
        return ""
    pct = ((cur - prev) / prev) * 100
    if pct > 2:
        return f"↑{pct:.0f}%"
    elif pct < -2:
        return f"↓{abs(pct):.0f}%"
    return "→"


# === REDTRACK ===
def fetch_redtrack_day(date_str):
    """Busca dados RedTrack de um dia."""
    try:
        url = (f"https://api.redtrack.io/report?api_key={REDTRACK_KEY}"
               f"&date_from={date_str}&date_to={date_str}"
               f"&columns=revenue,revenuetype2,revenuetype3,convtype1,convtype4,cost,clicks,lp_clicks")
        rt_rate_limit()
        data = json.loads(urlopen(url, timeout=15).read())
        front = sum(float(c.get("revenuetype2", 0)) + float(c.get("revenuetype3", 0)) for c in data)
        cost = sum(float(c.get("cost", 0)) for c in data)
        vendas = sum(int(c.get("convtype1", 0)) for c in data)
        vendas_cc = sum(int(c.get("convtype4", 0)) for c in data)
        clicks = sum(int(c.get("clicks", 0)) for c in data)
        lp_clicks = sum(int(c.get("lp_clicks", 0)) for c in data)
        roas = front / cost if cost > 0 else 0
        return {
            "date": date_str, "front": front, "cost": cost,
            "vendas": vendas, "vendas_cc": vendas_cc,
            "clicks": clicks, "lp_clicks": lp_clicks, "roas": roas,
        }
    except Exception as e:
        return {"date": date_str, "error": str(e)}


def fetch_redtrack_top_campaigns(date_from, date_to):
    """Top campanhas por faturamento."""
    try:
        url = (f"https://api.redtrack.io/report?api_key={REDTRACK_KEY}"
               f"&group=campaign&date_from={date_from}&date_to={date_to}"
               f"&columns=revenuetype2,revenuetype3,convtype1,convtype4,cost,clicks")
        rt_rate_limit()
        data = json.loads(urlopen(url, timeout=15).read())
        campaigns = []
        for c in data:
            cost = float(c.get("cost", 0))
            front = float(c.get("revenuetype2", 0)) + float(c.get("revenuetype3", 0))
            if cost < 100:
                continue
            campaigns.append({
                "name": c.get("campaign", "") or c.get("sub1", "") or "?",
                "front": front, "cost": cost,
                "roas": front / cost if cost > 0 else 0,
                "vendas": int(c.get("convtype1", 0)),
            })
        campaigns.sort(key=lambda x: x["front"], reverse=True)
        return campaigns[:5]
    except Exception:
        return []


def fetch_redtrack_gestores(date_from, date_to):
    """Breakdown por gestor de tráfego (parseado do nome da campanha)."""
    try:
        url = (f"https://api.redtrack.io/report?api_key={REDTRACK_KEY}"
               f"&group=campaign&date_from={date_from}&date_to={date_to}"
               f"&columns=revenuetype2,revenuetype3,convtype1,convtype4,cost,clicks")
        rt_rate_limit()
        data = json.loads(urlopen(url, timeout=15).read())

        gestores = defaultdict(lambda: {"front": 0, "cost": 0, "vendas": 0, "vendas_cc": 0, "campaigns": 0})
        for c in data:
            name = c.get("campaign", "")
            cost = float(c.get("cost", 0))
            front = float(c.get("revenuetype2", 0)) + float(c.get("revenuetype3", 0))
            vendas = int(c.get("convtype1", 0))
            vendas_cc = int(c.get("convtype4", 0))

            m = re.search(r"G\.\s*(\w+)", name)
            gestor = m.group(1).title() if m else "Sem gestor"

            gestores[gestor]["front"] += front
            gestores[gestor]["cost"] += cost
            gestores[gestor]["vendas"] += vendas
            gestores[gestor]["vendas_cc"] += vendas_cc
            gestores[gestor]["campaigns"] += 1

        return dict(sorted(gestores.items(), key=lambda x: x[1]["front"], reverse=True))
    except Exception:
        return {}


def fetch_redtrack_top_ads(date_from, date_to, limit=5):
    """Top ads por faturamento (sub5 = nome do criativo no RedTrack)."""
    try:
        url = (f"https://api.redtrack.io/report?api_key={REDTRACK_KEY}"
               f"&group=sub5&date_from={date_from}&date_to={date_to}"
               f"&columns=revenuetype2,revenuetype3,convtype1,convtype4,cost,clicks")
        rt_rate_limit()
        data = json.loads(urlopen(url, timeout=15).read())

        ads = []
        for c in data:
            cost = float(c.get("cost", 0))
            front = float(c.get("revenuetype2", 0)) + float(c.get("revenuetype3", 0))
            if cost < 50:
                continue
            ads.append({
                "name": c.get("sub5", "?") or "?",
                "front": front, "cost": cost,
                "roas": front / cost if cost > 0 else 0,
                "vendas": int(c.get("convtype1", 0)),
                "clicks": int(c.get("clicks", 0)),
            })
        ads.sort(key=lambda x: x["front"], reverse=True)
        return ads[:limit]
    except Exception:
        return []


# === CLICKUP ===
def fetch_clickup_list_activity(list_id, hours=48):
    """Tarefas atualizadas nas últimas N horas."""
    try:
        cutoff = int((time.time() - hours * 3600) * 1000)
        url = (f"https://api.clickup.com/api/v2/list/{list_id}/task"
               f"?order_by=updated&reverse=true&include_closed=true&subtasks=true&page=0")
        req = Request(url, headers={"Authorization": CLICKUP_TOKEN})
        resp = json.loads(urlopen(req, timeout=15).read())
        tasks = resp.get("tasks", [])
        recent = [t for t in tasks if int(t.get("date_updated", 0)) >= cutoff]
        statuses = Counter(t.get("status", {}).get("status", "?") for t in recent)
        return {"total": len(tasks), "recent": len(recent), "statuses": dict(statuses.most_common())}
    except Exception as e:
        return {"error": str(e)}


# === ESTEIRA ===
def parse_esteira_alerts():
    """Lê alertas de atraso do rastreador_esteira.log."""
    log_path = SCRIPTS_DIR / "rastreador_esteira.log"
    if not log_path.exists():
        return []

    alerts = []
    lines = log_path.read_text(errors="replace").splitlines()[-100:]
    for line in lines:
        m = re.search(r"atraso:\s*(\S+)\s*\|\s*Resp:\s*(\S+)", line)
        if m:
            alerts.append({"atraso": m.group(1), "resp": m.group(2)})

    # Aggregate by responsável
    by_resp = defaultdict(list)
    for a in alerts:
        by_resp[a["resp"]].append(a["atraso"])

    return dict(by_resp)


# === AUTOMAÇÕES ===
def check_automations_health():
    """Verifica saúde das automações pelos logs."""
    checks = {
        "sync_responsavel.log": {"name": "Sync Responsável", "max_h": 0.5},
        "automacao_drive.log": {"name": "Automação Drive", "max_h": 0.5},
        "rastreador_esteira.log": {"name": "Rastreador Esteira", "max_h": 1.5},
        "auditoria_nomenclatura.log": {"name": "Auditoria Nomenclatura", "max_h": 4},
        "gpdr_bot_cron.log": {"name": "Bot GPDR", "max_h": 7},
        "perf_bot_cron.log": {"name": "Bot Performance", "max_h": 2},
        "roas_diario.log": {"name": "ROAS Diário", "max_h": 25},
        "rotina_diaria.log": {"name": "Rotina Diária", "max_h": 13},
    }

    now = time.time()
    results = []
    for log_name, cfg in checks.items():
        log_path = SCRIPTS_DIR / log_name
        if not log_path.exists():
            results.append({"name": cfg["name"], "status": "❌", "detail": "log ausente"})
            continue

        mtime = log_path.stat().st_mtime
        hours_ago = (now - mtime) / 3600

        # Check for errors in last lines
        last_lines = log_path.read_text(errors="replace").splitlines()[-5:]
        has_error = any(re.search(r"ERRO|Traceback|HTTPError|401|403|500", l, re.I) for l in last_lines)

        if has_error:
            results.append({"name": cfg["name"], "status": "⚠️", "detail": "erros recentes"})
        elif hours_ago > cfg["max_h"] * 2:
            results.append({"name": cfg["name"], "status": "⚠️", "detail": f"inativo há {hours_ago:.0f}h"})
        else:
            results.append({"name": cfg["name"], "status": "✅", "detail": "OK"})

    return results


# === BUILD BRIEFING ===
def build_briefing():
    """Monta o briefing completo."""
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    day_before = (now - timedelta(days=2)).strftime("%Y-%m-%d")

    lines = []
    lines.append(f"📊 <b>BRIEFING DIÁRIO IMPERA</b>")
    lines.append(f"📅 {now.strftime('%d/%m/%Y %H:%M')}")
    lines.append("")

    # --- REDTRACK ---
    d1 = fetch_redtrack_day(yesterday)
    d2 = fetch_redtrack_day(day_before)

    lines.append("<b>💰 PERFORMANCE (RedTrack)</b>")
    if "error" not in d1 and "error" not in d2:
        lines.append(f"")
        lines.append(f"Ontem ({yesterday}):")
        lines.append(f"  Custo: {fmt(d1['cost'])} | Front: {fmt(d1['front'])} | ROAS: {d1['roas']:.2f}")
        lines.append(f"  Vendas: {d1['vendas']} (CC: {d1['vendas_cc']}) | Clicks: {d1['clicks']:,}")
        lines.append(f"")
        lines.append(f"Anteontem ({day_before}):")
        lines.append(f"  Custo: {fmt(d2['cost'])} | Front: {fmt(d2['front'])} | ROAS: {d2['roas']:.2f}")
        lines.append(f"  Vendas: {d2['vendas']} (CC: {d2['vendas_cc']}) | Clicks: {d2['clicks']:,}")
        lines.append(f"")

        # Comparativo
        rev_arrow = arrow(d1["front"], d2["front"])
        cost_arrow = arrow(d1["cost"], d2["cost"])
        roas_arrow = arrow(d1["roas"], d2["roas"])
        lines.append(f"  Tendência: Front {rev_arrow} | Custo {cost_arrow} | ROAS {roas_arrow}")
    else:
        err = d1.get("error", d2.get("error", "?"))
        lines.append(f"  ⚠️ Erro ao buscar dados: {err[:60]}")

    # Gestores
    gestores = fetch_redtrack_gestores(yesterday, yesterday)
    if gestores:
        lines.append("")
        lines.append("<b>👤 POR GESTOR (ontem)</b>")
        for g, d in gestores.items():
            roas = d["front"] / d["cost"] if d["cost"] > 0 else 0
            lines.append(f"  {g}: {fmt(d['front'])} | Custo {fmt(d['cost'])} | ROAS {roas:.2f} | {d['vendas']} vendas | {d['campaigns']} camp.")

    # Top campanhas
    top = fetch_redtrack_top_campaigns(yesterday, yesterday)
    if top:
        lines.append("")
        lines.append("<b>🏆 TOP 5 CAMPANHAS (ontem)</b>")
        for i, c in enumerate(top, 1):
            name_short = c["name"][:40] if c["name"] else "?"
            lines.append(f"  {i}. {name_short}")
            lines.append(f"     {fmt(c['front'])} | ROAS {c['roas']:.2f} | {c['vendas']} vendas")

    # Top ads
    top_ads = fetch_redtrack_top_ads(yesterday, yesterday)
    if top_ads:
        lines.append("")
        lines.append("<b>🎯 TOP 5 ADS (ontem)</b>")
        for i, a in enumerate(top_ads, 1):
            name_short = a["name"][:40] if a["name"] else "?"
            lines.append(f"  {i}. {name_short}")
            lines.append(f"     {fmt(a['front'])} | ROAS {a['roas']:.2f} | {a['vendas']} vendas | {a['clicks']:,} clicks")

    lines.append("")

    # --- CLICKUP ---
    lines.append("<b>📋 CLICKUP (últimas 48h)</b>")
    for list_name, list_id in CLICKUP_LISTS.items():
        data = fetch_clickup_list_activity(list_id)
        if "error" in data:
            lines.append(f"  {list_name}: ⚠️ {data['error'][:40]}")
        elif data["recent"] == 0:
            lines.append(f"  {list_name}: sem movimentação ({data['total']} tarefas)")
        else:
            status_str = ", ".join(f"{k}: {v}" for k, v in list(data["statuses"].items())[:4])
            lines.append(f"  {list_name}: {data['recent']} atualizadas")
            lines.append(f"    → {status_str}")

    lines.append("")

    # --- ESTEIRA ---
    esteira = parse_esteira_alerts()
    if esteira:
        lines.append("<b>⏰ ATRASOS ESTEIRA</b>")
        for resp, atrasos in sorted(esteira.items(), key=lambda x: len(x[1]), reverse=True):
            lines.append(f"  {resp}: {len(atrasos)} tarefa(s) — {', '.join(atrasos[-3:])}")
    else:
        lines.append("<b>⏰ ESTEIRA</b>: Sem atrasos detectados ✅")

    lines.append("")

    # --- AUTOMAÇÕES ---
    auto_health = check_automations_health()
    ok_count = sum(1 for a in auto_health if a["status"] == "✅")
    warn_count = sum(1 for a in auto_health if a["status"] != "✅")

    lines.append(f"<b>⚙️ AUTOMAÇÕES</b>: {ok_count} OK | {warn_count} alertas")
    for a in auto_health:
        if a["status"] != "✅":
            lines.append(f"  {a['status']} {a['name']}: {a['detail']}")

    lines.append("")
    lines.append("<i>GPDR — Iago Almeida, assistido por Claude</i>")

    return "\n".join(lines)


# === TELEGRAM ===
def send_to_clickup_chat(message):
    """Envia para ClickUp Chat View 8cm1w4b-9913."""
    if not CLICKUP_TOKEN:
        return False

    chat_view_id = "8cm1w4b-9913"
    # Remove HTML tags para ClickUp
    clean_msg = re.sub(r"</?[^>]+>", "", message)

    try:
        url = f"https://api.clickup.com/api/v2/view/{chat_view_id}/chat"
        data = json.dumps({"content": clean_msg}).encode()
        req = Request(url, data=data, headers={
            "Authorization": CLICKUP_TOKEN,
            "Content-Type": "application/json"
        })
        urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"Erro ClickUp Chat: {e}")
        return False


def send_telegram(message):
    """Envia mensagem via Telegram (split se necessário)."""
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Telegram não configurado")
        return False

    # Split if too long (Telegram limit ~4096)
    chunks = []
    if len(message) <= 4000:
        chunks = [message]
    else:
        current = ""
        for line in message.split("\n"):
            if len(current) + len(line) + 1 > 4000:
                chunks.append(current)
                current = line
            else:
                current += "\n" + line if current else line
        if current:
            chunks.append(current)

    for chunk in chunks:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = json.dumps({
            "chat_id": CHAT_ID,
            "text": chunk,
            "parse_mode": "HTML",
        }).encode()
        req = Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            urlopen(req, timeout=10)
        except Exception as e:
            print(f"Erro Telegram: {e}")
            return False

    return True


def save_txt(briefing_text):
    """Salva versão .txt para referência."""
    clean = re.sub(r"</?[^>]+>", "", briefing_text)
    path = SCRIPTS_DIR / "data" / "briefing_diario_latest.txt"
    path.write_text(clean)
    return path


def save_obsidian_daily(briefing_text):
    """Salva Daily Note no vault Obsidian."""
    vault_dir = Path.home() / "Obsidian" / "IMPERA" / "Daily Notes"
    vault_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now()
    filename = today.strftime("%Y-%m-%d") + ".md"
    filepath = vault_dir / filename

    clean = re.sub(r"</?[^>]+>", "", briefing_text)

    # Se já existe, append (pode rodar mais de 1x)
    if filepath.exists():
        existing = filepath.read_text()
        if "Briefing Diário" in existing:
            return filepath  # Já tem briefing hoje

    note = f"""---
tipo: daily
data: {today.strftime('%Y-%m-%d')}
dia_semana: {today.strftime('%A')}
tags: [daily, briefing]
---

# {today.strftime('%d/%m/%Y')} — {today.strftime('%A')}

## Briefing Diário (gerado às {today.strftime('%H:%M')})

{clean}

---

## Notas do dia
_Adicione aqui observações, decisões ou contexto que o Claude precisa saber._

"""
    filepath.write_text(note)
    return filepath


def main():
    timestamp = datetime.now().isoformat()
    print(f"[{timestamp}] Gerando briefing diário...")

    briefing = build_briefing()

    # Save txt
    txt_path = save_txt(briefing)
    print(f"  Salvo em: {txt_path}")

    # Save Obsidian Daily Note
    obs_path = save_obsidian_daily(briefing)
    print(f"  Obsidian: {obs_path}")

    # Send ClickUp Chat
    if send_to_clickup_chat(briefing):
        print("  ✅ Enviado para ClickUp Chat")
    else:
        print("  ⚠️ Falha no envio ClickUp Chat")

    # Send Telegram
    if send_telegram(briefing):
        print("  ✅ Enviado via Telegram")
    else:
        print("  ⚠️ Falha no envio Telegram")

    # Print clean version
    clean = re.sub(r"</?[^>]+>", "", briefing)
    print()
    print(clean)


if __name__ == "__main__":
    main()
