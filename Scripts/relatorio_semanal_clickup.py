#!/usr/bin/env python3
"""
Relatório Semanal Produção → ClickUp Chat View
Migração de .docx para posts consolidados em ClickUp.

Análise semanal: produção por copywriter, editor e nicho.
Crontab: domingo 12:03

GPDR — Iago Almeida | Assistido por Claude — Anthropic
"""

import json
import os
import re
import subprocess
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta

sys.path.insert(0, os.path.expanduser("~/Scripts"))
try:
    from impera_utils import normalize_person_name
except:
    def normalize_person_name(name):
        return name

API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
LIST_COPY = "901324556390"
CLICKUP_CHAT_VIEW = "8cm1w4b-9953"  # Chat View dedicado para Relatório Semanal

LOG_DIR = os.path.expanduser("~/Scripts/logs")

NICHOS = {
    "DA": "Dores Articulares", "DB": "Diabetes", "ED": "Adulto/ED",
    "EM": "Emagrecimento", "MM": "Memória", "NE": "Neuropatia",
    "PT": "Próstata", "ZB": "Zumbido", "ME": "Memória EUA",
}
CATS = ["img_novo", "img_otim", "vid_novo", "vid_otim", "lead", "microlead", "vsl", "rp"]
CAT_LABELS = ["Img N", "Img O", "Víd N", "Víd O", "Lead", "MLD", "VSL", "RP"]


def log(msg):
    """Log com timestamp."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def post_clickup(message):
    """Posta mensagem no ClickUp Chat View."""
    if not message or not CLICKUP_CHAT_VIEW:
        return False

    try:
        cmd = [
            "curl", "-s", "-X", "POST",
            f"https://api.clickup.com/api/v2/view/{CLICKUP_CHAT_VIEW}/comment",
            "-H", f"Authorization: {API_TOKEN}",
            "-H", "Content-Type: application/json",
            "-d", json.dumps({"comment_text": message})
        ]
        result = subprocess.run(cmd, timeout=10, capture_output=True, text=True)
        if result.returncode == 0:
            log("✓ Relatório postado em ClickUp")
            return True
        else:
            log(f"✗ Erro ao postar: {result.stderr}")
            return False
    except Exception as e:
        log(f"✗ Erro: {e}")
        return False


def api_get(endpoint):
    """ClickUp API request."""
    url = f"https://api.clickup.com/api/v2{endpoint}"
    req = urllib.request.Request(url, headers={"Authorization": API_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        log(f"Erro API: {e}")
        return {}


def fetch_all_tasks(list_id):
    """Busca todas as tarefas."""
    tasks = []
    page = 0
    while True:
        params = f"subtasks=true&include_closed=true&page={page}"
        data = api_get(f"/list/{list_id}/task?{params}")
        batch = data.get("tasks", [])
        tasks.extend(batch)
        if data.get("last_page", True) or not batch:
            break
        page += 1
    return tasks


def get_cf(task, field_name):
    """Extrai custom field."""
    for cf in task.get("custom_fields", []):
        if field_name.lower() in cf.get("name", "").lower():
            opts = cf.get("type_config", {}).get("options", [])
            val = cf.get("value")
            if val is not None:
                for o in opts:
                    if o.get("orderindex") == val:
                        return normalize_person_name(o["name"]) or "?"
    return "?"


def extract_version_range(text):
    """Extrai versão (V1-V5, etc)."""
    m = re.search(r"\[V(\d+)\s*-\s*V?(\d+)\]", text)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"\[V(\d+)\]", text)
    if m:
        return int(m.group(1)), int(m.group(1))
    return None, None


def classify(task):
    """Classifica tarefa."""
    name = task["name"]
    info = {"name": name, "status": task["status"]["status"]}

    # Nicho
    NICHOS_VALIDOS = {"DA", "DB", "ED", "EM", "ME", "MM", "NE", "PT", "ZB"}
    nicho = "?"
    for nm in re.findall(r"\[([A-Z]{2,3})\]", name):
        if nm in NICHOS_VALIDOS:
            nicho = nm
            break
    info["nicho"] = nicho

    # Data início
    sd = task.get("start_date")
    info["start_date"] = datetime.fromtimestamp(int(sd) / 1000) if sd else None

    # Ripagem
    upper = name.upper()
    info["is_rp"] = "[RP]" in upper or "RIPAGEM" in upper

    # Categoria
    is_img = "IMG" in upper
    v_low, v_high = extract_version_range(name)

    if info["is_rp"]:
        info["categoria"] = "rp"
        info["qtd"] = 1
    elif "[OTMZ]" in upper or "OTIM" in upper:
        info["categoria"] = "img_otim" if is_img else "vid_otim"
        info["qtd"] = (v_high - v_low + 1) if v_low else 1
    elif "[VSL]" in upper:
        info["categoria"] = "vsl"
        info["qtd"] = 1
    elif "[LD]" in upper or "[MLD]" in upper:
        info["categoria"] = "microlead" if "[MLD]" in upper else "lead"
        info["qtd"] = 1
    else:
        info["categoria"] = "img_novo" if is_img else "vid_novo"
        info["qtd"] = (v_high - v_low + 1) if v_low else 1

    # Pessoas
    info["copywriter"] = get_cf(task, "copywriter")
    info["editor"] = get_cf(task, "editor")

    return info


def get_week_range():
    """Período semanal (últimos 9 dias)."""
    end = datetime.now() - timedelta(days=1)
    start = end - timedelta(days=8)
    return start, end


def build_report(tasks):
    """Constrói relatório consolidado."""
    classified = [classify(t) for t in tasks]

    # Períodos
    week_start, week_end = get_week_range()
    prev_start = week_start - timedelta(days=7)
    prev_end = week_end - timedelta(days=7)

    def make_stats():
        return {c: 0 for c in CATS}

    # Copywriters - semana atual
    cw_weekly = defaultdict(make_stats)
    nicho_count = defaultdict(int)

    for r in classified:
        sd = r.get("start_date")
        if sd and week_start <= sd <= week_end:
            cw_weekly[r["copywriter"]][r["categoria"]] += r["qtd"]
            nicho_count[r["nicho"]] += r["qtd"]

    # Copywriters - semana anterior
    cw_prev = defaultdict(make_stats)
    for r in classified:
        sd = r.get("start_date")
        if sd and prev_start <= sd <= prev_end:
            cw_prev[r["copywriter"]][r["categoria"]] += r["qtd"]

    # Editores
    ed_status = ["avaliação - pós edição", "avaliação - pós alteração", "enviado para trafego"]
    ed_snapshot = defaultdict(make_stats)
    for r in classified:
        if r["status"] in ed_status and not r.get("is_rp", False):
            ed_snapshot[r["editor"]][r["categoria"]] += r["qtd"]

    # Build message
    week_start_fmt = week_start.strftime("%d/%m")
    week_end_fmt = week_end.strftime("%d/%m")

    lines = [
        f"📋 RELATÓRIO SEMANAL PRODUÇÃO — {week_start_fmt} a {week_end_fmt}",
        f"",
    ]

    # Copywriters
    if cw_weekly:
        lines.append("✍️ COPYWRITERS (últimos 9 dias)")
        sorted_cw = sorted(cw_weekly.items(), key=lambda x: sum(x[1].values()), reverse=True)
        for cw, stats in sorted_cw:
            total = sum(stats.values())
            if total == 0:
                continue
            prev_total = sum(cw_prev[cw].values())
            delta = total - prev_total
            delta_str = f" ({delta:+d} vs semana anterior)" if prev_total > 0 else ""
            lines.append(f"  • {cw}: <b>{total}</b> criativos{delta_str}")
            detail = " | ".join(f"{CAT_LABELS[i]}: {stats[CATS[i]]}" for i in range(len(CATS)) if stats[CATS[i]] > 0)
            lines.append(f"    {detail}")
        lines.append("")

    # Nichos
    if nicho_count:
        lines.append("🎯 POR NICHO")
        sorted_nichos = sorted(nicho_count.items(), key=lambda x: -x[1])
        for nicho, count in sorted_nichos[:5]:
            name = NICHOS.get(nicho, "?")
            lines.append(f"  • {nicho} ({name}): {count}")
        lines.append("")

    # Editores
    if ed_snapshot:
        lines.append("🎬 EDITORES (em avaliação + entregues)")
        sorted_ed = sorted(ed_snapshot.items(), key=lambda x: sum(x[1].values()), reverse=True)
        for ed, stats in sorted_ed:
            total = sum(stats.values())
            if total == 0:
                continue
            lines.append(f"  • {ed}: {total} criativos")
        lines.append("")

    # Resumo
    total_criados = sum(sum(s.values()) for s in cw_weekly.values())
    lines.append(f"📊 RESUMO: {total_criados} criativos criados na semana")

    return "\n".join(lines)


def main():
    """Executa relatório semanal."""
    log("Iniciando relatório semanal...")

    tasks = fetch_all_tasks(LIST_COPY)
    log(f"Fetched {len(tasks)} tasks")

    if not tasks:
        log("Nenhuma tarefa encontrada")
        return False

    report = build_report(tasks)
    success = post_clickup(report)

    if success:
        log("✓ Relatório postado com sucesso")
        return True
    else:
        log("✗ Erro ao postar relatório")
        return False


if __name__ == "__main__":
    os.makedirs(LOG_DIR, exist_ok=True)

    if not API_TOKEN:
        log("ERRO: CLICKUP_API_TOKEN não definido.")
        sys.exit(1)

    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        log(f"ERRO FATAL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
