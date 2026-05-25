#!/usr/bin/env python3
"""
Script para explorar e encontrar o endpoint correto de histórico no ClickUp
"""
import os
import requests
import json

CLICKUP_API_TOKEN = os.getenv('CLICKUP_API_TOKEN')
CLICKUP_API_URL = "https://api.clickup.com/api/v2"

HEADERS = {
    "Authorization": CLICKUP_API_TOKEN
}

def test_endpoint(url: str, description: str):
    """Testa um endpoint e retorna o resultado"""
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ {description}")
            print(f"   URL: {url}")
            print(f"   Resposta: {str(data)[:200]}...")
            return True
        elif response.status_code == 404:
            print(f"⭕ {description} — 404 Not Found")
            return False
        else:
            print(f"❌ {description} — Status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ {description} — Erro: {str(e)[:50]}")
        return False

def main():
    task_id = "86ahdcp2a"

    print("=" * 80)
    print("EXPLORANDO ENDPOINTS DE HISTÓRICO DO CLICKUP")
    print("=" * 80)
    print()

    # Primeiro, tenta obter o workspace/team ID
    print("1️⃣  Buscando Team ID...")

    # Obtém detalhes da task para descobrir o team_id indiretamente
    try:
        resp = requests.get(f"{CLICKUP_API_URL}/task/{task_id}", headers=HEADERS)
        task_data = resp.json()
        print(f"   Task encontrada: {task_data.get('name')}")

        # Extrai informações úteis
        workspace_id = task_data.get('workspace', {}).get('id')
        space_id = task_data.get('space', {}).get('id')
        folder_id = task_data.get('folder', {}).get('id')
        list_id = task_data.get('list', {}).get('id')

        print(f"   Workspace ID: {workspace_id}")
        print(f"   Space ID: {space_id}")
        print(f"   Folder ID: {folder_id}")
        print(f"   List ID: {list_id}")
    except Exception as e:
        print(f"   ❌ Erro ao obter task: {e}")
        return

    print()
    print("2️⃣  Testando diferentes endpoints de histórico...")
    print()

    # Lista de endpoints para tentar
    endpoints_to_test = [
        # Endpoints diretos da task
        (f"{CLICKUP_API_URL}/task/{task_id}/history", "GET /task/{task_id}/history"),
        (f"{CLICKUP_API_URL}/task/{task_id}/activity", "GET /task/{task_id}/activity"),
        (f"{CLICKUP_API_URL}/task/{task_id}/comments", "GET /task/{task_id}/comments"),
        (f"{CLICKUP_API_URL}/task/{task_id}/status_history", "GET /task/{task_id}/status_history"),

        # Endpoints da list
        (f"{CLICKUP_API_URL}/list/{list_id}/activity", "GET /list/{list_id}/activity") if list_id else None,

        # Endpoints da workspace/team
        (f"{CLICKUP_API_URL}/team/2640127/activity", "GET /team/2640127/activity"),
        (f"{CLICKUP_API_URL}/team/2640127/audit", "GET /team/2640127/audit"),

        # Endpoints de espaço
        (f"{CLICKUP_API_URL}/space/{space_id}/activity", "GET /space/{space_id}/activity") if space_id else None,
    ]

    # Remove None entries
    endpoints_to_test = [e for e in endpoints_to_test if e is not None]

    for url, desc in endpoints_to_test:
        test_endpoint(url, desc)
        print()

    print("=" * 80)
    print("ℹ️  Se nenhum endpoint funcionou, a ClickUp API pode não expor histórico completo.")
    print("   Você pode verificar manualmente em: https://app.clickup.com/t/86ahdcp2a")

if __name__ == "__main__":
    if not CLICKUP_API_TOKEN:
        print("❌ Erro: CLICKUP_API_TOKEN não está configurado")
        exit(1)

    main()
