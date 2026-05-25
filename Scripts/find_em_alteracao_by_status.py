#!/usr/bin/env python3
"""
Script para encontrar tarefas com status 'em alteração' usando a API do ClickUp
"""
import os
import requests
import json

CLICKUP_API_TOKEN = os.getenv('CLICKUP_API_TOKEN')
CLICKUP_API_URL = "https://api.clickup.com/api/v2"

HEADERS = {
    "Authorization": CLICKUP_API_TOKEN
}

# IDs da lista COPY
LIST_ID = "901324556390"

def get_list_status_options(list_id: str):
    """Obtém todos os status disponíveis para uma lista"""
    url = f"{CLICKUP_API_URL}/list/{list_id}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    data = response.json()

    statuses = data.get('statuses', [])
    return statuses

def search_tasks_by_status(list_id: str, status_name: str):
    """Busca tarefas com um status específico"""

    # Primeiro, obtém o ID do status
    statuses = get_list_status_options(list_id)

    target_status_id = None
    for status in statuses:
        if status.get('status', '').lower() == status_name.lower():
            target_status_id = status.get('id')
            break

    if not target_status_id:
        print(f"❌ Status '{status_name}' não encontrado na lista.")
        print(f"\nStatus disponíveis:")
        for status in statuses:
            print(f"  - {status.get('status')} (ID: {status.get('id')})")
        return []

    print(f"✅ Status encontrado: '{status_name}' (ID: {target_status_id})")

    # Busca tarefas com esse status
    url = f"{CLICKUP_API_URL}/list/{list_id}/task"
    params = {
        'statuses[]': target_status_id,
        'limit': 1000,
        'include_subtasks': False
    }

    print(f"\n🔍 Buscando tarefas com status '{status_name}'...")

    response = requests.get(url, headers=HEADERS, params=params)
    response.raise_for_status()
    data = response.json()

    tasks = data.get('tasks', [])
    return tasks

def main():
    print("=" * 80)
    print("BUSCAR TAREFAS COM STATUS 'EM ALTERAÇÃO'")
    print("=" * 80)
    print()

    # Tenta buscar tarefas com status "em alteração"
    tasks = search_tasks_by_status(LIST_ID, "em alteração")

    print()
    print("=" * 80)

    if tasks:
        print(f"✅ ENCONTRADO: {len(tasks)} tarefa(s) com status 'em alteração'")
        print()

        for i, task in enumerate(tasks, 1):
            task_id = task.get('id')
            task_name = task.get('name')
            status = task.get('status', {}).get('status')
            assignees = [a.get('username') for a in task.get('assignees', [])]

            print(f"{i}. {task_name}")
            print(f"   Task ID: {task_id}")
            print(f"   Status: {status}")
            print(f"   Responsáveis: {', '.join(assignees) if assignees else 'Ninguém'}")
            print(f"   Link: https://app.clickup.com/t/{task_id}")
            print()
    else:
        print("⭕ Nenhuma tarefa encontrada com status 'em alteração' ATUALMENTE")
        print()
        print("ℹ️  NOTA IMPORTANTE:")
        print("   A ClickUp API não expõe o histórico de mudanças de status.")
        print("   Isso significa que as tarefas que FORAM movidas para 'em alteração'")
        print("   no passado não podem ser encontradas programaticamente.")
        print()
        print("   Para encontrar tarefas que JÁ estiveram em 'em alteração':")
        print("   1. Use a busca avançada do ClickUp (Filter/View)")
        print("   2. Procure em atividades/comentários manualmente")
        print("   3. Ou crie um webhook para rastrear mudanças em tempo real")

if __name__ == "__main__":
    if not CLICKUP_API_TOKEN:
        print("❌ Erro: CLICKUP_API_TOKEN não está configurado")
        exit(1)

    main()
