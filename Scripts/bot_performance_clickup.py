#!/usr/bin/env python3
"""
Bot Performance → ClickUp Chat View
Migração do Telegram bot para ClickUp.

Modos:
  python3 bot_performance_clickup.py morning   # Report 08:30
  python3 bot_performance_clickup.py afternoon # Report 16:00
  python3 bot_performance_clickup.py check     # Alertas horários

Posts para ClickUp Chat View: 8cm1w4b-9893

GPDR — Iago Almeida | Assistido por Claude — Anthropic
"""

import os
import sys
import json
import subprocess
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.expanduser("~/Scripts"))
from cruzamento_clickup_redtrack import (
    parse_campaign_name, fetch_redtrack_campaigns, fetch_redtrack_adgroups,
    build_clickup_data, build_redtrack_data,
    OFERTA_PADRAO, NICHO_KEYWORDS, GESTOR_MAP,
)
from impera_utils import get_cf_value, detect_nicho

API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
REDTRACK_KEY = os.environ.get("REDTRACK_API_KEY", "")
CLICKUP_CHAT_VIEW = "8cm1w4b-9893"

LOG_DIR = os.path.expanduser("~/Scripts/logs")
STATE_FILE = os.path.expanduser("~/Scripts/data/bot_perf_state.json")

PERIODOS = {
    "24h": 1,
    "48h": 2,
    "7d": 7,
    "15d": 15,
}

CONFIG = {
    "MIN_COST_DISPLAY": 10,
    "MIN_COST_ALERT": 100,
    "MIN_COST_CRITICAL": 500,
    "ROAS_FRONT_MIN": 1.8,
    "ROAS_WARNING": 1.5,
    "ROAS_CRITICAL": 1.0,
    "ROAS_GOOD": 2.0,
    "CPA_META": 180,
}


# === HELPERS ===

def log(msg):
    """Log com timestamp."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def post_clickup(message):
    """Posta mensagem no ClickUp Chat View."""
    if not message or not CLICKUP_CHAT_VIEW:
        return
    try:
        cmd = [
            "curl", "-s", "-X", "POST",
            f"https://api.clickup.com/api/v2/view/{CLICKUP_CHAT_VIEW}/comment",
            "-H", f"Authorization: {API_TOKEN}",
            "-H", "Content-Type: application/json",
            "-d", json.dumps({"comment_text": message})
        ]
        subprocess.run(cmd, timeout=10, capture_output=True)
        log(f"✓ Mensagem postada em ClickUp")
    except Exception as e:
        log(f"✗ Erro ao postar: {e}")


def calc_roas(revenue, cost):
    """Calcula ROAS."""
    return revenue / cost if cost > 0 else 0


def calc_cpa(cost, vendas):
    """Calcula CPA."""
    return cost / vendas if vendas > 0 else 0


def fmt(val):
    """Formata número."""
    if val >= 1000:
        return f"R${val:,.0f}"
    return f"R${val:.0f}"


def roas_icon(roas):
    """Retorna ícone baseado em ROAS."""
    if roas >= CONFIG["ROAS_GOOD"]:
        return "✅"
    if roas >= CONFIG["ROAS_WARNING"]:
        return "⚠️"
    if roas >= CONFIG["ROAS_CRITICAL"]:
        return "🔴"
    return "❌"


def get_dates(period_key, live=False):
    """Retorna (date_from, date_to) como strings YYYY-MM-DD."""
    if "_" in period_key and len(period_key) == 17:
        d1 = datetime.strptime(period_key[:8], "%Y%m%d")
        d2 = datetime.strptime(period_key[9:], "%Y%m%d")
        return d1.strftime("%Y-%m-%d"), d2.strftime("%Y-%m-%d")

    days = PERIODOS.get(period_key, 7)
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    if live:
        date_to = today.strftime("%Y-%m-%d")
        date_from = (today - timedelta(days=days)).strftime("%Y-%m-%d")
    else:
        yesterday = today - timedelta(days=1)
        date_to = yesterday.strftime("%Y-%m-%d")
        date_from = (yesterday - timedelta(days=days - 1)).strftime("%Y-%m-%d")

    return date_from, date_to


def fetch_campaigns(period_key, live=False):
    """Busca campanhas do RedTrack."""
    date_from, date_to = get_dates(period_key, live=live)
    raw = fetch_redtrack_campaigns(date_from, date_to)
    campaigns = []
    for r in raw:
        name = r.get("campaign", "")
        cost = float(r.get("cost", 0))
        rev = float(r.get("revenuetype2", 0)) + float(r.get("revenuetype3", 0))
        vendas = int(r.get("convtype1", 0))
        clicks = int(r.get("clicks", 0))
        parsed = parse_campaign_name(name)
        campaigns.append({
            "name": name,
            "campaign_id": r.get("campaign_id", ""),
            "cost": cost,
            "revenue": rev,
            "roas": rev / cost if cost > 0 else 0,
            "vendas": vendas,
            "clicks": clicks,
            **parsed,
        })
    return campaigns


# === REPORT BUILDERS ===

def build_performance_report(period_key="24h", live=True):
    """Build relatório de performance por oferta."""
    campaigns = fetch_campaigns(period_key, live=live)
    ofertas = defaultdict(lambda: {"cost": 0, "revenue": 0, "vendas": 0, "campanhas": 0})

    for c in campaigns:
        if not c.get("nicho") or not c.get("oferta"):
            continue
        key = f"{c['nicho']} | {c['oferta']}"
        if c.get("mercado") == "EUA":
            key += " (EUA)"
        ofertas[key]["cost"] += c["cost"]
        ofertas[key]["revenue"] += c["revenue"]
        ofertas[key]["vendas"] += c["vendas"]
        ofertas[key]["campanhas"] += 1

    total_rev = sum(d["revenue"] for d in ofertas.values())
    total_cost = sum(d["cost"] for d in ofertas.values())
    total_roas = calc_roas(total_rev, total_cost)

    lines = [
        f"📊 PERFORMANCE — {datetime.now().strftime('%d/%m %H:%M')}",
        f"",
        f"💰 Receita: {fmt(total_rev)} | Custo: {fmt(total_cost)} | ROAS: {total_roas:.2f}",
        f"",
    ]

    sorted_of = sorted(ofertas.items(), key=lambda x: x[1]["revenue"], reverse=True)
    for key, d in sorted_of:
        if d["cost"] < CONFIG["MIN_COST_DISPLAY"]:
            continue
        roas = calc_roas(d["revenue"], d["cost"])
        cpa = calc_cpa(d["cost"], d["vendas"])
        icon = roas_icon(roas)
        lines.append(f"{icon} {key}")
        lines.append(f"  • R$: {fmt(d['revenue'])} | Custo: {fmt(d['cost'])} | ROAS: {roas:.2f}")
        lines.append(f"  • Vendas: {d['vendas']} | CPA: {fmt(cpa)} | Camps: {d['campanhas']}")
        lines.append("")

    return "\n".join(lines)


def build_gestores_report(period_key="24h", live=True):
    """Build ranking de gestores de tráfego."""
    campaigns = fetch_campaigns(period_key, live=live)
    gestores = defaultdict(lambda: {"cost": 0, "revenue": 0, "vendas": 0, "campanhas": 0, "nichos": set()})

    for c in campaigns:
        g = c.get("gestor")
        if not g:
            continue
        gestores[g]["cost"] += c["cost"]
        gestores[g]["revenue"] += c["revenue"]
        gestores[g]["vendas"] += c["vendas"]
        gestores[g]["campanhas"] += 1
        if c.get("nicho"):
            gestores[g]["nichos"].add(c["nicho"])

    lines = [
        f"👥 GESTORES DE TRÁFEGO — {datetime.now().strftime('%d/%m %H:%M')}",
        f"",
    ]

    sorted_g = sorted(gestores.items(), key=lambda x: x[1]["revenue"], reverse=True)
    for i, (g, d) in enumerate(sorted_g, 1):
        if d["cost"] < CONFIG["MIN_COST_DISPLAY"]:
            continue
        roas = calc_roas(d["revenue"], d["cost"])
        cpa = calc_cpa(d["cost"], d["vendas"])
        icon = roas_icon(roas)
        nichos = ", ".join(sorted(d["nichos"]))[:40]
        lines.append(f"{i}. {icon} {g} ({d['campanhas']} campaigns)")
        lines.append(f"   R$: {fmt(d['revenue'])} | Custo: {fmt(d['cost'])} | ROAS: {roas:.2f}")
        lines.append(f"   Vendas: {d['vendas']} | CPA: {fmt(cpa)} | Nichos: {nichos}")
        lines.append("")

    return "\n".join(lines)


def build_alerts_report(period_key="24h", live=True):
    """Build alertas de problemas (ROAS baixo, gasto sem venda, CPA alto)."""
    campaigns = fetch_campaigns(period_key, live=live)

    alerts = []

    # Alertar ofertas com ROAS crítico
    ofertas_roas = defaultdict(lambda: {"cost": 0, "revenue": 0, "vendas": 0})
    for c in campaigns:
        if not c.get("nicho") or not c.get("oferta"):
            continue
        key = f"{c['nicho']} | {c['oferta']}"
        ofertas_roas[key]["cost"] += c["cost"]
        ofertas_roas[key]["revenue"] += c["revenue"]
        ofertas_roas[key]["vendas"] += c["vendas"]

    for key, d in ofertas_roas.items():
        if d["cost"] < CONFIG["MIN_COST_CRITICAL"]:
            continue
        roas = calc_roas(d["revenue"], d["cost"])
        if roas < CONFIG["ROAS_CRITICAL"]:
            alerts.append(f"❌ {key}: ROAS {roas:.2f} (crítico!) | Gasto: {fmt(d['cost'])}")
        elif roas < CONFIG["ROAS_WARNING"]:
            alerts.append(f"⚠️ {key}: ROAS {roas:.2f} (atenção) | Gasto: {fmt(d['cost'])}")

    # Alertar campanhas com gasto alto sem venda
    for c in campaigns:
        if c["cost"] < CONFIG["MIN_COST_CRITICAL"]:
            continue
        if c["vendas"] == 0 and c["cost"] > CONFIG["MIN_COST_CRITICAL"]:
            alerts.append(f"🚨 {c['name'][:50]}: Gastou {fmt(c['cost'])} sem venda!")

    if not alerts:
        return None

    lines = [
        f"⚠️ ALERTAS — {datetime.now().strftime('%d/%m %H:%M')}",
        f"",
    ]
    lines.extend(alerts[:10])
    if len(alerts) > 10:
        lines.append(f"\n... e mais {len(alerts) - 10} alertas")

    return "\n".join(lines)


# === AUTO REPORTS ===

def report_morning():
    """Auto report 08:30."""
    log("Gerando relatório da manhã...")
    msg = build_performance_report("24h", live=True)
    msg += "\n\n"
    msg += build_gestores_report("24h", live=True)

    alerts = build_alerts_report("24h", live=True)
    if alerts:
        msg += "\n\n"
        msg += alerts

    post_clickup(msg)
    save_last_report("morning", msg)


def report_afternoon():
    """Auto report 16:00."""
    log("Gerando relatório da tarde...")
    msg = build_performance_report("24h", live=True)
    msg += "\n\n"
    msg += build_gestores_report("24h", live=True)

    alerts = build_alerts_report("24h", live=True)
    if alerts:
        msg += "\n\n"
        msg += alerts

    post_clickup(msg)
    save_last_report("afternoon", msg)


def hourly_check():
    """Checagem horária de alertas."""
    log("Checagem horária...")
    alerts = build_alerts_report("24h", live=True)
    if alerts:
        post_clickup(alerts)
        save_last_report("hourly", alerts)
    else:
        log("Sem alertas")


# === STATE ===

def load_state():
    """Carrega estado."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_state(state):
    """Salva estado."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def save_last_report(cmd, content):
    """Salva último relatório."""
    state = load_state()
    if "reports" not in state:
        state["reports"] = {}
    state["reports"][cmd] = {
        "timestamp": datetime.now().isoformat(),
        "preview": content[:200] + ("..." if len(content) > 200 else "")
    }
    save_state(state)


# === MAIN ===

if __name__ == "__main__":
    os.makedirs(LOG_DIR, exist_ok=True)

    if not API_TOKEN:
        log("ERRO: CLICKUP_API_TOKEN não definido.")
        sys.exit(1)

    cmd = sys.argv[1] if len(sys.argv) > 1 else "morning"

    try:
        if cmd == "morning":
            report_morning()
        elif cmd == "afternoon":
            report_afternoon()
        elif cmd == "check":
            hourly_check()
        else:
            print(__doc__)
    except Exception as e:
        log(f"ERRO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    log("✓ Concluído")
