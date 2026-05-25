#!/usr/bin/env python3
"""
Script avançado para encontrar status "em alteração" usando múltiplos endpoints
"""
import os
import requests
import json
from datetime import datetime

CLICKUP_API_TOKEN = os.getenv('CLICKUP_API_TOKEN')
CLICKUP_API_URL = "https://api.clickup.com/api/v2"

HEADERS = {
    "Authorization": CLICKUP_API_TOKEN
}

def get_task_details(task_id: str):
    """Obtém detalhes da tarefa"""
    url = f"{CLICKUP_API_URL}/task/{task_id}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()

def get_task_comments(task_id: str):
    """Obtém comentários da tarefa que podem conter histórico"""
    url = f"{CLICKUP_API_URL}/task/{task_id}/comment"
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.json().get('comments', [])
    except:
        return []

def check_for_em_alteracao(task_id: str):
    """Verifica múltiplos pontos para encontrar 'em alteração'"""

    print(f"\n📋 Verificando tarefa: {task_id}")
    print("-" * 80)

    try:
        task = get_task_details(task_id)
        task_name = task.get('name')
        current_status = task.get('status', {}).get('status')
        date_updated = task.get('date_updated')

        print(f"  Nome: {task_name}")
        print(f"  Status atual: {current_status}")

        if date_updated:
            from_epoch = datetime.fromtimestamp(int(date_updated) / 1000)
            print(f"  Última atualização: {from_epoch}")

        # Tenta buscar comentários que possam conter histórico
        print(f"\n  Buscando comentários do sistema...")
        comments = get_task_comments(task_id)

        em_alteracao_found = False

        if comments:
            for i, comment in enumerate(comments, 1):
                comment_text = comment.get('comment_text', '')
                username = comment.get('user', {}).get('username', 'Sistema')

                # Procura por menções a "em alteração"
                if 'em alteração' in comment_text.lower() or 'alteração' in comment_text.lower():
                    print(f"    ✅ Comentário {i}: {username}")
                    print(f"       {comment_text[:100]}...")
                    em_alteracao_found = True

                # Procura por mudanças de status nos comentários
                if 'status' in comment_text.lower() or 'movido' in comment_text.lower():
                    if 'alteração' in comment_text.lower():
                        print(f"    ⚠️  Comentário {i}: {username}")
                        print(f"       {comment_text[:150]}...")
                        em_alteracao_found = True
        else:
            print(f"    ℹ️  Nenhum comentário encontrado")

        # Tenta endpoint de atividades direto (Team/Space level)
        print(f"\n  Tentando obter histórico via API avançada...")

        # Busca o ID do espaço (space_id) para consultar auditoria
        try:
            # O task_id contém informações, vamos tentar um endpoint diferente
            url_history = f"{CLICKUP_API_URL}/task/{task_id}/audit"
            resp = requests.get(url_history, headers=HEADERS)
            if resp.status_code == 200:
                audit = resp.json()
                print(f"    ✅ Auditoria encontrada: {json.dumps(audit, indent=2)[:500]}")
                em_alteracao_found = True
        except Exception as e:
            print(f"    ℹ️  Endpoint de auditoria não disponível: {str(e)[:50]}")

        # Exibe a resposta com toda a estrutura JSON
        print(f"\n  Estrutura completa dos dados da task:")
        print(f"    Data de criação: {task.get('date_created')}")
        print(f"    Data de atualização: {task.get('date_updated')}")
        print(f"    Data done: {task.get('date_done')}")

        return em_alteracao_found

    except Exception as e:
        print(f"  ❌ Erro: {str(e)}")
        return False

if __name__ == "__main__":
    if not CLICKUP_API_TOKEN:
        print("❌ Erro: CLICKUP_API_TOKEN não está configurado")
        exit(1)

    # Verifica a tarefa específica que o usuário mencionou
    task_id = "86ahdcp2a"

    print("=" * 80)
    print(f"BUSCA AVANÇADA POR 'EM ALTERAÇÃO'")
    print("=" * 80)

    found = check_for_em_alteracao(task_id)

    print("\n" + "=" * 80)
    if found:
        print("✅ Status 'em alteração' foi encontrado!")
    else:
        print("⭕ Não foi possível encontrar 'em alteração' nos dados acessíveis via API")
        print("\nℹ️  NOTA: O ClickUp API pode não expor o histórico completo de status.")
        print("   Para verificar manualmente, acesse: https://app.clickup.com/t/86ahdcp2a")
        print("   E verifique o histórico de atividades/comentários na tarefa.")
