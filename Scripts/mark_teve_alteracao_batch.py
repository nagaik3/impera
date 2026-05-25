#!/usr/bin/env python3
"""
Script para marcar retrospectivamente tarefas como "Teve alteração?"

Uso:
  python3 mark_teve_alteracao_batch.py --task-ids 86ahdcp2a 86ahe25wy 86ahe25x6

Ou marcar todas as tarefas de uma lista:
  python3 mark_teve_alteracao_batch.py --all
"""

import os
import sys
import argparse
import requests
from datetime import datetime

CLICKUP_API_TOKEN = os.getenv('CLICKUP_API_TOKEN')
CLICKUP_API_URL = "https://api.clickup.com/api/v2"

# IDs importantes
FIELD_TEVE_ALTERACAO = "3617b249-06e2-4d2e-9ba0-c48da305e42a"
LIST_ID = "901324556390"

HEADERS = {
    "Authorization": CLICKUP_API_TOKEN,
    "Content-Type": "application/json"
}

def get_all_tasks_from_list(list_id: str):
    """Obtém todas as tarefas da lista"""
    url = f"{CLICKUP_API_URL}/list/{list_id}/task"
    params = {
        'limit': 1000,
        'include_subtasks': False
    }

    try:
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        return response.json().get('tasks', [])
    except Exception as e:
        print(f"❌ Erro ao buscar tarefas: {e}")
        return []

def get_task_details(task_id: str):
    """Obtém detalhes de uma tarefa"""
    url = f"{CLICKUP_API_URL}/task/{task_id}"

    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Erro ao buscar tarefa {task_id}: {e}")
        return None

def mark_teve_alteracao(task_id: str, mark: bool = True):
    """Marca ou desmarca uma tarefa como 'Teve alteração?'"""
    url = f"{CLICKUP_API_URL}/task/{task_id}/field/{FIELD_TEVE_ALTERACAO}"

    payload = {
        "value": mark
    }

    try:
        response = requests.post(url, headers=HEADERS, json=payload)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"❌ Erro ao marcar {task_id}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Marca tarefas como 'Teve alteração?'"
    )
    parser.add_argument(
        '--task-ids',
        nargs='+',
        help='IDs das tarefas a marcar'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Marca TODAS as tarefas da lista'
    )
    parser.add_argument(
        '--unmark',
        action='store_true',
        help='Desmarcar ao invés de marcar'
    )

    args = parser.parse_args()

    if not CLICKUP_API_TOKEN:
        print("❌ Erro: CLICKUP_API_TOKEN não está configurado")
        sys.exit(1)

    print("=" * 80)
    print("📌 MARCAR TAREFAS COMO 'TEVE ALTERAÇÃO?'")
    print("=" * 80)
    print()

    task_ids_to_mark = []

    if args.task_ids:
        task_ids_to_mark = args.task_ids
        print(f"📋 Tarefas especificadas: {len(task_ids_to_mark)}")

    elif args.all:
        print("🔍 Buscando todas as tarefas da lista...")
        tasks = get_all_tasks_from_list(LIST_ID)
        task_ids_to_mark = [t.get('id') for t in tasks]
        print(f"✅ {len(task_ids_to_mark)} tarefas encontradas")

    else:
        parser.print_help()
        sys.exit(0)

    if not task_ids_to_mark:
        print("❌ Nenhuma tarefa especificada")
        sys.exit(1)

    # Confirma ação
    action = "desmarcar" if args.unmark else "marcar"
    print()
    print(f"⚠️  Você está prestes a {action} {len(task_ids_to_mark)} tarefa(s).")
    confirm = input("Deseja continuar? (s/n): ").lower()

    if confirm != 's':
        print("❌ Operação cancelada")
        sys.exit(0)

    print()
    print("-" * 80)

    success_count = 0
    failed_count = 0

    for i, task_id in enumerate(task_ids_to_mark, 1):
        task = get_task_details(task_id)

        if not task:
            failed_count += 1
            print(f"[{i}/{len(task_ids_to_mark)}] ❌ {task_id} - Erro ao buscar detalhes")
            continue

        task_name = task.get('name', 'N/A')
        status = task.get('status', {}).get('status', 'N/A')

        print(f"[{i}/{len(task_ids_to_mark)}] Processando: {task_name}")
        print(f"            Status: {status}")

        if mark_teve_alteracao(task_id, not args.unmark):
            status_msg = "desmarcado" if args.unmark else "marcado"
            print(f"            ✅ {status_msg.upper()}")
            success_count += 1
        else:
            failed_count += 1
            print(f"            ❌ FALHA")

        print()

    print("-" * 80)
    print()
    print("📊 RESULTADO:")
    print(f"   ✅ Sucesso: {success_count}")
    print(f"   ❌ Falha: {failed_count}")
    print(f"   📅 Timestamp: {datetime.now()}")

if __name__ == "__main__":
    main()
