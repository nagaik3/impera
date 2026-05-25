#!/usr/bin/env python3
"""
Integrador de URLs Trackable no ClickUp
Salva a URL trackable em um custom field específico da tarefa.

Uso:
  # Descobrir ID do custom field primeiro:
  python3 integrar_tracking_url.py --find-field "URL Trackable"

  # Depois, salvar URL em uma tarefa:
  python3 integrar_tracking_url.py \
    --task-id "86ahe2609" \
    --field-id "xxxxx-xxxxx-xxxxx" \
    --url "https://seu-dominio.com/?utm_source=facebook&utm_content=AD116_V1"
"""

import json
import os
import sys
import urllib.request
import re

sys.path.insert(0, os.path.expanduser("~/Scripts"))
from gerar_tracking_url import gerar_tracking_url, parse_nomenclatura

API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")


def find_custom_field(list_id, field_name):
    """
    Encontra um custom field pelo nome em uma lista.

    Retorna: field_id ou None se não encontrado
    """
    url = f"https://api.clickup.com/api/v2/list/{list_id}"
    headers = {"Authorization": API_TOKEN}

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        for cf in data.get("custom_fields", []):
            if field_name.lower() in cf.get("name", "").lower():
                return cf.get("id"), cf.get("name")

        return None, None
    except Exception as e:
        print(f"❌ Erro ao buscar campo: {e}")
        return None, None


def get_task_details(task_id):
    """Retorna detalhes da tarefa incluindo custom fields."""
    url = f"https://api.clickup.com/api/v2/task/{task_id}"
    headers = {"Authorization": API_TOKEN}

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"❌ Erro ao buscar tarefa: {e}")
        return None


def update_custom_field(task_id, field_id, value):
    """
    Atualiza um custom field em uma tarefa.

    task_id: ID da tarefa no ClickUp
    field_id: ID do custom field (descoberto via find_custom_field)
    value: Novo valor para o campo
    """
    url = f"https://api.clickup.com/api/v2/task/{task_id}"
    headers = {
        "Authorization": API_TOKEN,
        "Content-Type": "application/json"
    }

    payload = {
        "custom_fields": [
            {
                "id": field_id,
                "value": value
            }
        ]
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method='PUT'
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            return result
    except Exception as e:
        print(f"❌ Erro ao atualizar field: {e}")
        return None


def main():
    if "--find-field" in sys.argv:
        # Modo: Encontrar ID de um campo
        idx = sys.argv.index("--find-field")
        field_name = sys.argv[idx + 1]

        print(f"🔍 Procurando campo '{field_name}' em GESTÃO DE TRÁFEGO...\n")

        field_id, field_full_name = find_custom_field("901324476398", field_name)

        if field_id:
            print(f"✅ Campo encontrado!")
            print(f"\nNome: {field_full_name}")
            print(f"ID:   {field_id}\n")
            print(f"Use este ID ao chamar --task-id:")
            print(f"  --field-id \"{field_id}\"")
        else:
            print(f"❌ Campo '{field_name}' não encontrado")
            print(f"\nCampos disponíveis com 'url' ou 'track':")

            # Listar campos que contêm url/track
            url = f"https://api.clickup.com/api/v2/list/901324476398"
            headers = {"Authorization": API_TOKEN}
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read())
                for cf in data.get("custom_fields", []):
                    name = cf.get("name", "")
                    if any(t in name.lower() for t in ["url", "track", "link"]):
                        print(f"  - {name} (ID: {cf.get('id')})")
            except:
                pass

    elif "--task-id" in sys.argv:
        # Modo: Atualizar tarefa com URL
        task_id = sys.argv[sys.argv.index("--task-id") + 1]
        field_id = sys.argv[sys.argv.index("--field-id") + 1] if "--field-id" in sys.argv else None
        url_value = sys.argv[sys.argv.index("--url") + 1] if "--url" in sys.argv else None

        if not all([task_id, field_id, url_value]):
            print("❌ Uso: --task-id <id> --field-id <id> --url <url>")
            sys.exit(1)

        print(f"📝 Atualizando tarefa {task_id}...")
        result = update_custom_field(task_id, field_id, url_value)

        if result:
            print(f"✅ Campo atualizado com sucesso!")
            print(f"\nURL salva: {url_value}")
        else:
            print(f"❌ Erro ao atualizar")

    elif "--auto" in sys.argv and len(sys.argv) > 2:
        # Modo: Auto - gera URL e salva tudo
        task_name = sys.argv[sys.argv.index("--auto") + 1]
        task_id = sys.argv[sys.argv.index("--task-id") + 1] if "--task-id" in sys.argv else None
        field_id = sys.argv[sys.argv.index("--field-id") + 1] if "--field-id" in sys.argv else None

        if not task_id or not field_id:
            print("❌ Modo --auto requer: --task-id <id> --field-id <id>")
            sys.exit(1)

        print(f"🔗 Gerando URL para {task_name}...")
        result = gerar_tracking_url(task_name)

        if result:
            print(f"✅ URL gerada: {result['url_completa']}")
            print(f"\n📝 Salvando no ClickUp...")

            update_result = update_custom_field(task_id, field_id, result['url_completa'])
            if update_result:
                print(f"✅ Salvo com sucesso!")
            else:
                print(f"❌ Erro ao salvar")
        else:
            print(f"❌ Nomenclatura inválida: {task_name}")

    else:
        print("Uso:")
        print()
        print("  # 1. Encontrar ID do custom field:")
        print("  python3 integrar_tracking_url.py --find-field 'URL Trackable'")
        print()
        print("  # 2. Atualizar tarefa com URL manualmente:")
        print("  python3 integrar_tracking_url.py \\")
        print("    --task-id '86ahe2609' \\")
        print("    --field-id 'xxxxx-xxxxx-xxxxx' \\")
        print("    --url 'https://seu-dominio.com/?utm_content=AD116_V1'")
        print()
        print("  # 3. Gerar URL + Salvar automaticamente:")
        print("  python3 integrar_tracking_url.py \\")
        print("    --auto '[EM][BR][OF02][FB][AD116][V1]' \\")
        print("    --task-id '86ahe2609' \\")
        print("    --field-id 'xxxxx-xxxxx-xxxxx'")


if __name__ == "__main__":
    main()
