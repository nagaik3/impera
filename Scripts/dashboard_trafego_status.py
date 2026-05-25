#!/usr/bin/env python3
"""
Dashboard de Status de Criativos — GESTÃO DE TRÁFEGO
Lista todos os criativos agrupados por status com copywriter responsável.
Uso:
  python3 dashboard_trafego_status.py              # todos os statuses
  python3 dashboard_trafego_status.py --json       # exporta JSON
  python3 dashboard_trafego_status.py --status="em teste"  # filtra 1 status
"""

import json
import os
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.expanduser("~/Scripts"))
from impera_utils import normalize_person_name

# === CONFIG ===
API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
LIST_TRAFEGO = "901324476398"

# Ordem de statuses no workflow
STATUSES_ORDER = [
    "aguardando teste", "em teste", "testes concluídos",
    "pré-escala", "validado", "escala",
    "em risco", "negativo", "pausado",
    "vturb", "reprovado", "cemitério"
]

# Cores para visualização (ANSI)
STATUS_COLORS = {
    "aguardando teste": "\033[90m",      # Gray
    "em teste": "\033[90m",              # Gray
    "testes concluídos": "\033[90m",     # Gray
    "pré-escala": "\033[92m",            # Green
    "validado": "\033[94m",              # Blue
    "escala": "\033[32m",                # Dark Green
    "em risco": "\033[93m",              # Yellow/Orange
    "negativo": "\033[91m",              # Red
    "pausado": "\033[93m",               # Orange
    "vturb": "\033[94m",                 # Blue
    "reprovado": "\033[91m",             # Red
    "cemitério": "\033[32m",             # Dark Green
}
RESET = "\033[0m"


def api_get(endpoint):
    """Chamada GET para API ClickUp."""
    url = f"https://api.clickup.com/api/v2{endpoint}"
    req = urllib.request.Request(url, headers={"Authorization": API_TOKEN})
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"❌ Erro na API: {e}")
        return {"tasks": []}


def fetch_trafego_tasks():
    """Busca todas as tarefas da lista GESTÃO DE TRÁFEGO com paginação."""
    tasks = []
    page = 0
    while True:
        params = f"subtasks=true&include_closed=true&page={page}"
        data = api_get(f"/list/{LIST_TRAFEGO}/task?{params}")
        batch = data.get("tasks", [])
        tasks.extend(batch)
        if data.get("last_page", True) or not batch:
            break
        page += 1
    return tasks


def get_cf_copywriter(task):
    """Extrai o copywriter responsável da tarefa."""
    for cf in task.get("custom_fields", []):
        if "copywritter" in cf.get("name", "").lower():
            opts = cf.get("type_config", {}).get("options", [])
            val = cf.get("value")
            if val is not None:
                for o in opts:
                    if o.get("orderindex") == val:
                        return normalize_person_name(o["name"]) or "NÃO ATRIBUÍDO"
    return "NÃO ATRIBUÍDO"


def days_in_status(task):
    """Calcula quantos dias a tarefa está no status atual."""
    date_updated = task.get("date_updated")
    if not date_updated:
        return "?"
    try:
        updated_ts = int(date_updated) / 1000  # ClickUp retorna em ms
        updated_dt = datetime.fromtimestamp(updated_ts)
        delta = datetime.now() - updated_dt
        return delta.days
    except:
        return "?"


def classify_by_status(tasks):
    """Agrupa tarefas por status."""
    grouped = defaultdict(list)
    for task in tasks:
        status = task.get("status", {}).get("status", "desconhecido")
        grouped[status].append(task)
    return grouped


def format_task_display(task):
    """Formata uma tarefa para exibição."""
    name = task.get("name", "sem nome")
    copywriter = get_cf_copywriter(task)
    dias = days_in_status(task)

    # Limita o nome a 60 caracteres
    if len(name) > 60:
        name = name[:57] + "..."

    return {
        "name": name,
        "copywriter": copywriter,
        "dias_no_status": dias,
        "task_id": task.get("id", "?"),
        "status": task.get("status", {}).get("status", "?"),
    }


def print_dashboard(grouped, filter_status=None):
    """Imprime o dashboard no terminal."""
    print("\n" + "="*120)
    print("📊 DASHBOARD DE TESTES — GESTÃO DE TRÁFEGO")
    print("="*120 + "\n")

    total_tarefas = sum(len(tasks) for tasks in grouped.values())
    print(f"📦 Total de criativos em teste: {total_tarefas}\n")

    for status in STATUSES_ORDER:
        if filter_status and status != filter_status:
            continue

        tasks = grouped.get(status, [])
        count = len(tasks)

        if count == 0:
            continue

        color = STATUS_COLORS.get(status, "")
        print(f"{color}{'─' * 120}{RESET}")
        print(f"{color}▶ {status.upper()} ({count} criativo{'s' if count != 1 else ''})  {RESET}")
        print(f"{color}{'─' * 120}{RESET}")

        # Header da tabela
        print(f"{'Nome':<65} {'Copywriter':<20} {'Dias':<8} {'ID':<20}")
        print(f"{'-'*120}")

        # Linhas da tabela
        for task in sorted(tasks, key=lambda t: t.get("name", "")):
            fmt = format_task_display(task)
            print(f"{fmt['name']:<65} {fmt['copywriter']:<20} {str(fmt['dias_no_status']):<8} {fmt['task_id']:<20}")

        print()


def export_json(grouped, output_path):
    """Exporta dashboard em JSON."""
    data = {}
    for status in STATUSES_ORDER:
        tasks = grouped.get(status, [])
        data[status] = [format_task_display(t) for t in tasks]

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"✅ Dashboard exportado para: {output_path}")


def main():
    # Parsear argumentos
    filter_status = None
    export_json_path = None

    for arg in sys.argv[1:]:
        if arg == "--json":
            export_json_path = os.path.expanduser("~/Documents/dashboard_trafego.json")
        elif arg.startswith("--status="):
            filter_status = arg.split("=", 1)[1]

    # Buscar tarefas
    print("🔄 Buscando tarefas da GESTÃO DE TRÁFEGO...")
    tasks = fetch_trafego_tasks()
    print(f"✅ {len(tasks)} tarefas carregadas\n")

    # Agrupar por status
    grouped = classify_by_status(tasks)

    # Exibir dashboard
    if filter_status:
        print(f"🔍 Filtrando por status: {filter_status}\n")

    print_dashboard(grouped, filter_status=filter_status)

    # Exportar JSON se solicitado
    if export_json_path:
        export_json(grouped, export_json_path)

    print("✨ Dashboard completo!")


if __name__ == "__main__":
    main()
