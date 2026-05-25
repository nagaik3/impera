#!/usr/bin/env python3
"""
Relatório de Pontuação de Editores — IMPERA PRODUTOS NATURAIS
Calcula pontos, faixa e bônus estimado por editor.

Uso:
  python3 relatorio_pontuacao_editores.py             # Mês até agora (MTD)
  python3 relatorio_pontuacao_editores.py --semanal    # Semana atual (seg-dom)
  python3 relatorio_pontuacao_editores.py --mensal     # Mês completo anterior
  python3 relatorio_pontuacao_editores.py --dry        # Mostra sem enviar Telegram

Crontab:
  0 9 * * 1 cd ~/Scripts && python3 relatorio_pontuacao_editores.py --semanal
  0 9 1 * * cd ~/Scripts && python3 relatorio_pontuacao_editores.py --mensal
"""

import json
import os
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta

sys.path.insert(0, os.path.expanduser("~/Scripts"))
from impera_utils import normalize_person_name

# === CONFIG ===
API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

LIST_COPY = "901324556390"
TEAM_ID = "9013620875"

# Custom field IDs
CF_EDITOR = "6002b1b9-e8c5-49ad-9e3d-3d8c314a1c91"
CF_PONTUACAO = "fb840b35-65cf-4f31-8456-bcdf5fcde651"

DRY = "--dry" in sys.argv
SEMANAL = "--semanal" in sys.argv
MENSAL = "--mensal" in sys.argv

# Salários base dos editores (ajustar conforme necessário)
SALARIO_EDITORES = {
    "WELL": 2500,
    "NICOLAS": 2500,
    "IGOR OLIVEIRA": 2500,
    "IGOR PAIVA": 1500,
    "MURYLLO": 1500,
    "MINEIRO": 1500,
}

# Faixas de bônus: (min_pts, max_pts, pct_por_ponto)
FAIXAS = [
    (0,    799,  0.0),
    (800,  999,  0.0),
    (1000, 1149, 0.0001),   # 0.01%
    (1150, 1499, 0.0003),   # 0.03%
    (1500, 1999, 0.0004),   # 0.04%
    (2000, 99999, 0.0005),  # 0.05%
]


def faixa_label(pts):
    """Retorna label da faixa de pontos."""
    if pts < 800:
        return "0-799 (0%)"
    elif pts < 1000:
        return "800-999 (0%)"
    elif pts < 1150:
        return "1000-1149 (0.01%)"
    elif pts < 1500:
        return "1150-1499 (0.03%)"
    elif pts < 2000:
        return "1500-1999 (0.04%)"
    else:
        return "2000+ (0.05%)"


def calcular_bonus(pts, salario):
    """Calcula bônus = pontos x pct x salário."""
    for min_pts, max_pts, pct in FAIXAS:
        if min_pts <= pts <= max_pts:
            return round(pts * pct * salario, 2)
    return 0.0


# === PERÍODO ===

def get_periodo():
    """Retorna (date_from_ms, date_to_ms, label)."""
    now = datetime.now()

    if SEMANAL:
        # Segunda a domingo da semana passada
        today = now.date()
        # Última segunda-feira
        last_monday = today - timedelta(days=today.weekday() + 7)
        last_sunday = last_monday + timedelta(days=6)
        label = f"Semana {last_monday.strftime('%d/%m')} - {last_sunday.strftime('%d/%m/%Y')}"
        d_from = datetime(last_monday.year, last_monday.month, last_monday.day)
        d_to = datetime(last_sunday.year, last_sunday.month, last_sunday.day, 23, 59, 59)

    elif MENSAL:
        # Mês anterior completo
        first_this = now.replace(day=1)
        last_day = first_this - timedelta(days=1)
        first_prev = last_day.replace(day=1)
        label = f"Mês {first_prev.strftime('%m/%Y')}"
        d_from = datetime(first_prev.year, first_prev.month, first_prev.day)
        d_to = datetime(last_day.year, last_day.month, last_day.day, 23, 59, 59)

    else:
        # MTD — mês até agora
        first = now.replace(day=1)
        label = f"MTD {first.strftime('%d/%m')} - {now.strftime('%d/%m/%Y')}"
        d_from = datetime(first.year, first.month, first.day)
        d_to = now

    from_ms = int(d_from.timestamp() * 1000)
    to_ms = int(d_to.timestamp() * 1000)
    return from_ms, to_ms, label


# === API ===

def api_get(endpoint):
    url = f"https://api.clickup.com/api/v2{endpoint}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", API_TOKEN)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def fetch_tasks_done(from_ms, to_ms):
    """Busca tarefas concluídas no período (date_done entre from_ms e to_ms)."""
    tasks = []
    page = 0
    while True:
        params = (
            f"subtasks=false&include_closed=true"
            f"&date_done_gt={from_ms}&date_done_lt={to_ms}"
            f"&page={page}"
        )
        data = api_get(f"/list/{LIST_COPY}/task?{params}")
        batch = data.get("tasks", [])
        tasks.extend(batch)
        if data.get("last_page", True) or not batch:
            break
        page += 1
    return tasks


def get_editor(task):
    """Retorna nome normalizado do editor ou None."""
    for cf in task.get("custom_fields", []):
        if cf.get("id") == CF_EDITOR:
            val = cf.get("value")
            if val is None:
                return None
            opts = cf.get("type_config", {}).get("options", [])
            for o in opts:
                if o.get("orderindex") == val:
                    return normalize_person_name(o.get("name", ""))
    return None


def get_pontuacao(task):
    """Retorna valor do campo Pontuação ou 0."""
    for cf in task.get("custom_fields", []):
        if cf.get("id") == CF_PONTUACAO:
            val = cf.get("value")
            if val is not None:
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return 0
    return 0


def send_telegram(msg):
    if DRY:
        print(f"[DRY] Telegram:\n{msg}")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    body = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        urllib.request.urlopen(req, timeout=15)
    except Exception as e:
        print(f"[ERRO] Telegram: {e}")


# === MAIN ===

def run():
    from_ms, to_ms, label = get_periodo()
    print(f"=== Relatório Pontuação Editores — {label} ===")

    tasks = fetch_tasks_done(from_ms, to_ms)
    print(f"Tarefas concluídas no período: {len(tasks)}")

    # Agrupar por editor
    editor_data = defaultdict(lambda: {"pontos": 0, "tarefas": 0, "nomes": []})

    for task in tasks:
        editor = get_editor(task)
        if not editor or editor == "NÃO ATRIBUÍDO":
            continue

        pts = get_pontuacao(task)
        editor_data[editor]["pontos"] += pts
        editor_data[editor]["tarefas"] += 1
        if pts > 0:
            editor_data[editor]["nomes"].append(
                f"  {task['name'].strip()[:50]} ({int(pts)}pts)"
            )

    if not editor_data:
        print("Nenhum editor com tarefas concluídas no período.")
        return

    # Ordenar por pontos desc
    ranking = sorted(editor_data.items(), key=lambda x: x[1]["pontos"], reverse=True)

    # Montar mensagem Telegram
    lines = [f"📊 <b>Pontuação Editores — {label}</b>\n"]

    for i, (editor, data) in enumerate(ranking, 1):
        pts = int(data["pontos"])
        tarefas = data["tarefas"]
        faixa = faixa_label(pts)
        salario = SALARIO_EDITORES.get(editor, 1500)
        bonus = calcular_bonus(pts, salario)

        lines.append(
            f"<b>{i}. {editor}</b>\n"
            f"   Pontos: <b>{pts}</b> | Tarefas: {tarefas}\n"
            f"   Faixa: {faixa}\n"
            f"   Bônus estimado: R$ {bonus:,.2f} (base R$ {salario:,})"
        )

    # Total
    total_pts = sum(d["pontos"] for d in editor_data.values())
    total_tasks = sum(d["tarefas"] for d in editor_data.values())
    lines.append(f"\n<b>Total:</b> {int(total_pts)} pts | {total_tasks} tarefas")

    # Editores sem pontuação
    sem_pts = [e for e, d in ranking if d["pontos"] == 0 and d["tarefas"] > 0]
    if sem_pts:
        lines.append(f"\n⚠️ Editores com tarefas mas sem pontuação: {', '.join(sem_pts)}")
        lines.append("(Campo 'Tipo de Edição' pode estar vazio)")

    msg = "\n".join(lines)
    print(msg.replace("<b>", "").replace("</b>", ""))

    send_telegram(msg)
    print("\nRelatório enviado.")


if __name__ == "__main__":
    run()
