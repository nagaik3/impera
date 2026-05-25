#!/usr/bin/env python3
"""
Auto Fill Start Date — ClickUp Automation
Usa date_created nativo do ClickUp como referência de start_date.

Uso:
  python3 auto_fill_start_date.py --validate   # Valida tarefas com start_date preenchida
  python3 auto_fill_start_date.py --report     # Relatório de datas

GPDR — Iago Almeida | Assistido por Claude — Anthropic
"""

import os
import sys
import json
import subprocess
from datetime import datetime

API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
COPY_LIST = "901324556390"
TRAFEGO_LIST = "901324476398"


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def fetch_tasks(list_id):
    """Busca todas as tarefas da lista."""
    try:
        cmd = [
            "curl", "-s",
            f"https://api.clickup.com/api/v2/list/{list_id}/task?limit=100&archived=false",
            "-H", f"Authorization: {API_TOKEN}",
        ]
        result = subprocess.run(cmd, timeout=10, capture_output=True, text=True)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get("tasks", [])
    except Exception as e:
        log(f"Erro ao buscar tarefas: {e}")
    return []


def validate_start_dates(list_id):
    """Valida tarefas que têm start_date com base em date_created."""
    log(f"Validando tarefas em {list_id}...")
    tasks = fetch_tasks(list_id)

    total = 0
    with_date = 0

    for task in tasks:
        total += 1
        date_ts = task.get("date_created")
        if date_ts:
            with_date += 1
            date_str = datetime.fromtimestamp(int(date_ts) / 1000).strftime("%Y-%m-%d")
            log(f"✓ {task.get('name', 'Task')[:40]}: {date_str}")

    log(f"\n✓ {with_date}/{total} tarefas com date_created")
    return with_date, total


def report_start_dates(list_id):
    """Gera relatório de datas."""
    log(f"Relatório de datas - {list_id}")
    tasks = fetch_tasks(list_id)

    by_date = {}
    for task in tasks:
        date_ts = task.get("date_created")
        if date_ts:
            date_str = datetime.fromtimestamp(int(date_ts) / 1000).strftime("%Y-%m-%d")
            by_date[date_str] = by_date.get(date_str, 0) + 1

    for date, count in sorted(by_date.items(), reverse=True)[:20]:
        log(f"{date}: {count} tarefas")


if __name__ == "__main__":
    if not API_TOKEN:
        log("ERRO: CLICKUP_API_TOKEN não definido")
        sys.exit(1)

    cmd = sys.argv[1] if len(sys.argv) > 1 else "--help"

    if cmd == "--validate":
        log("=== COPY ===")
        validate_start_dates(COPY_LIST)
        log("\n=== TRAFEGO ===")
        validate_start_dates(TRAFEGO_LIST)

    elif cmd == "--report":
        log("=== COPY ===")
        report_start_dates(COPY_LIST)
        log("\n=== TRAFEGO ===")
        report_start_dates(TRAFEGO_LIST)

    else:
        print(__doc__)
