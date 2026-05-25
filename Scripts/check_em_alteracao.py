#!/usr/bin/env python3
"""
Script para identificar tarefas com status "em alteração" no histórico
"""
import os
import requests
import json
from typing import List, Dict

CLICKUP_API_TOKEN = os.getenv('CLICKUP_API_TOKEN')
CLICKUP_API_URL = "https://api.clickup.com/api/v2"

# Task IDs extraídos da lista fornecida
TASK_IDS = [
    "86ahe25wy", "86ahe25x6", "86ahe25xv", "86ahe25y3", "86ahe25tz",
    "86ahe25um", "86ahe25vg", "86ahe25vw", "86ahe25zb", "86ahe25zt",
    "86ahe2609", "86ahhpmvd", "86ahhktqx", "86ahhpjmf", "86ahhpjyz",
    "86ahhpkcd", "86ahhpm9v", "86ahhpnce", "86ahkatzm", "86ahkau2c",
    "86ah8t8pr", "86ahj90am", "86ahjnqgx", "86ahhpp7d", "86ah8t85n",
    "86ahhr6z3", "86ahhrz9v", "86ahhpq71", "86ahgqxj7", "86ahgqxy0",
    "86ahdcp2a", "86ahetxn3", "86ahfmp4d", "86ahgcm6z", "86ahhpqmd"
]

HEADERS = {
    "Authorization": CLICKUP_API_TOKEN
}

def get_task_details(task_id: str) -> Dict:
    """Obtém detalhes da tarefa incluindo nome e status atual"""
    url = f"{CLICKUP_API_URL}/task/{task_id}"
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar tarefa {task_id}: {e}")
        return None

def get_task_history(task_id: str) -> List[Dict]:
    """Obtém histórico de atividades da tarefa via activity endpoint"""
    # Tenta o endpoint de activities
    url = f"{CLICKUP_API_URL}/task/{task_id}/activity"
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.json().get('activity', [])
    except requests.exceptions.RequestException:
        # Tenta alternativa: pegar detalhes com histórico
        try:
            url = f"{CLICKUP_API_URL}/task/{task_id}?include_subtasks=false"
            response = requests.get(url, headers=HEADERS)
            response.raise_for_status()
            data = response.json()
            # Verifica se há algum campo de histórico ou status_history
            return data.get('status_history', []) or data.get('history', [])
        except requests.exceptions.RequestException as e:
            print(f"Erro ao buscar histórico de {task_id}: {e}")
            return []

def check_em_alteracao_status(histories: List[Dict]) -> bool:
    """Verifica se há "em alteração" no histórico de status"""
    for history in histories:
        if history.get('field') == 'status':
            # Verifica tanto 'after' quanto 'before' para status changes
            after = history.get('after', '').lower()
            before = history.get('before', '').lower()

            if 'em alteração' in after or 'em alteração' in before:
                return True
            # Tenta também variações
            if 'alteração' in after or 'alteração' in before:
                return True
    return False

def main():
    print(f"Verificando {len(TASK_IDS)} tarefas para status 'em alteração'...\n")

    tasks_em_alteracao = []
    all_tasks = []

    for i, task_id in enumerate(TASK_IDS, 1):
        print(f"[{i}/{len(TASK_IDS)}] Verificando {task_id}...", end=" ")

        # Obtém detalhes da tarefa
        task_details = get_task_details(task_id)
        if not task_details:
            print("❌ Erro ao buscar")
            continue

        task_name = task_details.get('name', 'N/A')
        current_status = task_details.get('status', {}).get('status', 'N/A')

        # Obtém histórico
        histories = get_task_history(task_id)

        # Verifica se tem "em alteração"
        has_em_alteracao = check_em_alteracao_status(histories)

        task_info = {
            'task_id': task_id,
            'name': task_name,
            'current_status': current_status,
            'histories': histories
        }
        all_tasks.append(task_info)

        if has_em_alteracao:
            print(f"✅ ENCONTRADO")
            tasks_em_alteracao.append(task_info)
        else:
            # Verifica se o status atual é "em alteração"
            if current_status and 'alteração' in current_status.lower():
                print(f"⚠️  STATUS ATUAL = 'em alteração'")
                tasks_em_alteracao.append(task_info)
            else:
                print(f"⭕ Não encontrado (Status: {current_status})")

    # Exibe resultados
    print("\n" + "="*80)
    print(f"RESULTADO: {len(tasks_em_alteracao)} tarefa(s) com 'em alteração' encontrada(s)\n")

    if tasks_em_alteracao:
        for task in tasks_em_alteracao:
            print(f"Task ID: {task['task_id']}")
            print(f"Nome: {task['name']}")
            print(f"Status atual: {task['current_status']}")
            print(f"URL: https://app.clickup.com/t/{task['task_id']}")
            print("-" * 80)
    else:
        print("Nenhuma tarefa com status 'em alteração' foi encontrada no histórico.")

if __name__ == "__main__":
    if not CLICKUP_API_TOKEN:
        print("❌ Erro: CLICKUP_API_TOKEN não está configurado")
        exit(1)

    main()
