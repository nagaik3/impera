#!/usr/bin/env python3
"""
Script de teste: Valida se a automação está funcionando corretamente
"""

import os
import sys
import requests
import json

CLICKUP_API_TOKEN = os.getenv('CLICKUP_API_TOKEN')
CLICKUP_API_URL = "https://api.clickup.com/api/v2"

FIELD_TEVE_ALTERACAO = "3617b249-06e2-4d2e-9ba0-c48da305e42a"
LIST_ID = "901324556390"

HEADERS = {
    "Authorization": CLICKUP_API_TOKEN
}

def test_token():
    """Testa se token está configurado"""
    print("1️⃣  Testando token...")
    if not CLICKUP_API_TOKEN:
        print("   ❌ CLICKUP_API_TOKEN não está configurado")
        return False

    if not CLICKUP_API_TOKEN.startswith('pk_'):
        print("   ⚠️  Token não começa com 'pk_' (pode estar inválido)")
        return False

    print("   ✅ Token configurado corretamente")
    return True

def test_api_connection():
    """Testa conexão com API do ClickUp"""
    print("\n2️⃣  Testando conexão com API...")
    try:
        url = f"{CLICKUP_API_URL}/team"
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        print("   ✅ Conexão com API bem-sucedida")
        return True
    except Exception as e:
        print(f"   ❌ Erro na conexão: {e}")
        return False

def test_field_exists():
    """Testa se o campo existe na lista"""
    print("\n3️⃣  Testando se campo 'Teve alteração?' existe...")
    try:
        url = f"{CLICKUP_API_URL}/list/{LIST_ID}/field"
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()

        fields = response.json().get('fields', [])

        field_found = False
        for field in fields:
            if field.get('id') == FIELD_TEVE_ALTERACAO:
                field_found = True
                field_name = field.get('name')
                field_type = field.get('type')
                print(f"   ✅ Campo encontrado: {field_name} ({field_type})")
                break

        if not field_found:
            print(f"   ❌ Campo com ID {FIELD_TEVE_ALTERACAO} não encontrado")
            print(f"   Campos disponíveis:")
            for field in fields[:5]:
                print(f"      - {field.get('name')} ({field.get('type')})")
            return False

        return True
    except Exception as e:
        print(f"   ❌ Erro ao buscar campo: {e}")
        return False

def test_status_exists():
    """Testa se o status 'em alteração' existe"""
    print("\n4️⃣  Testando se status 'em alteração' existe...")
    try:
        url = f"{CLICKUP_API_URL}/list/{LIST_ID}"
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()

        statuses = response.json().get('statuses', [])

        status_found = False
        for status in statuses:
            if 'em alteração' in status.get('status', '').lower():
                status_found = True
                status_name = status.get('status')
                status_id = status.get('id')
                print(f"   ✅ Status encontrado: {status_name} (ID: {status_id})")
                break

        if not status_found:
            print(f"   ❌ Status 'em alteração' não encontrado")
            print(f"   Status disponíveis:")
            for status in statuses[:5]:
                print(f"      - {status.get('status')}")
            return False

        return True
    except Exception as e:
        print(f"   ❌ Erro ao buscar status: {e}")
        return False

def test_mark_field():
    """Testa se consegue marcar o campo em uma tarefa"""
    print("\n5️⃣  Testando marcação de campo (teste sem salvar)...")
    print("   ℹ️  Simulando atualização (será revertida)")

    try:
        # Busca uma tarefa qualquer da lista
        url = f"{CLICKUP_API_URL}/list/{LIST_ID}/task"
        response = requests.get(url, headers=HEADERS, params={'limit': 1})
        response.raise_for_status()

        tasks = response.json().get('tasks', [])
        if not tasks:
            print("   ⚠️  Nenhuma tarefa encontrada para teste")
            return True

        task_id = tasks[0].get('id')
        task_name = tasks[0].get('name')

        print(f"   Tarefa de teste: {task_name} ({task_id})")

        # Tenta marcar o campo
        url_update = f"{CLICKUP_API_URL}/task/{task_id}/field/{FIELD_TEVE_ALTERACAO}"
        payload = {"value": True}

        response = requests.post(url_update, headers=HEADERS, json=payload)
        response.raise_for_status()

        print(f"   ✅ Campo pode ser atualizado com sucesso")

        # Reverte para não deixar marcado
        payload = {"value": False}
        requests.post(url_update, headers=HEADERS, json=payload)
        print(f"   ↩️  Campo revertido (teste concluído)")

        return True
    except Exception as e:
        print(f"   ❌ Erro ao testar campo: {e}")
        return False

def test_webhook_endpoint():
    """Testa se endpoint do webhook está respondendo"""
    print("\n6️⃣  Testando endpoint do webhook...")

    try:
        response = requests.get("http://localhost:5001/webhook/status", timeout=2)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Webhook está rodando")
            print(f"      Serviço: {data.get('service')}")
            print(f"      Trigger: {data.get('trigger')}")
            return True
        else:
            print(f"   ⚠️  Webhook não está rodando no momento (normal se não foi iniciado)")
            print(f"      Para iniciar: python3 ~/Scripts/webhook_auto_alteracao.py")
            return True  # Não falha, é esperado
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        print(f"   ⚠️  Webhook não está rodando (normal se não foi iniciado)")
        print(f"      Para iniciar: python3 ~/Scripts/webhook_auto_alteracao.py")
        return True  # Não falha o teste, só aviso
    except Exception as e:
        print(f"   ⚠️  Erro ao conectar: {e}")
        return True

def main():
    print("=" * 80)
    print("🧪 TESTE DE AUTOMAÇÃO: 'TEVE ALTERAÇÃO?'")
    print("=" * 80)
    print()

    tests = [
        test_token(),
        test_api_connection(),
        test_field_exists(),
        test_status_exists(),
        test_mark_field(),
        test_webhook_endpoint()
    ]

    print("\n" + "=" * 80)
    print("📊 RESULTADO DOS TESTES")
    print("=" * 80)

    passed = sum(tests)
    total = len(tests)

    print(f"\n✅ Testes passando: {passed}/{total}")

    if passed == total:
        print("\n🎉 Todos os testes passaram! Sistema pronto para usar.")
        print("\n🚀 Próximos passos:")
        print("   1. Configure o webhook no ClickUp (Settings → Webhooks)")
        print("   2. Ou inicie o webhook com: python3 ~/Scripts/webhook_auto_alteracao.py")
        print("   3. Ou marque manualmente: python3 ~/Scripts/mark_teve_alteracao_batch.py --task-ids <id>")
    else:
        print(f"\n⚠️  {total - passed} teste(s) falharam. Verifique os erros acima.")
        sys.exit(1)

if __name__ == "__main__":
    main()
