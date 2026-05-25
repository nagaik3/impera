#!/usr/bin/env python3
"""
Script para debugar e exibir detalhes completos do histórico de uma tarefa
"""
import os
import requests
import json

CLICKUP_API_TOKEN = os.getenv('CLICKUP_API_TOKEN')
CLICKUP_API_URL = "https://api.clickup.com/api/v2"

HEADERS = {
    "Authorization": CLICKUP_API_TOKEN
}

def get_task_details(task_id: str):
    """Obtém detalhes completos da tarefa"""
    url = f"{CLICKUP_API_URL}/task/{task_id}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()

def main():
    task_id = "86ahdcp2a"

    print(f"=== Buscando detalhes da tarefa {task_id} ===\n")

    try:
        task_data = get_task_details(task_id)

        print("INFORMAÇÕES BÁSICAS:")
        print(f"  Nome: {task_data.get('name')}")
        print(f"  Status: {task_data.get('status', {}).get('status')}")
        print(f"  Status ID: {task_data.get('status', {}).get('id')}")
        print()

        # Exibe a estrutura JSON completa para análise
        print("DADOS COMPLETOS DA TAREFA (JSON):")
        print(json.dumps(task_data, indent=2, ensure_ascii=False)[:5000])

        # Procura por campos de histórico
        print("\n\nCAMPOS COM 'HISTORY' OU 'ACTIVITY':")
        for key in task_data.keys():
            if 'history' in key.lower() or 'activity' in key.lower() or 'status_history' in key.lower():
                print(f"  {key}: {task_data[key]}")

    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    if not CLICKUP_API_TOKEN:
        print("❌ Erro: CLICKUP_API_TOKEN não está configurado")
        exit(1)

    main()
