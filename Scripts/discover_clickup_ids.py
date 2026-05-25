#!/usr/bin/env python3
"""
Descobrir IDs de Custom Fields e Statuses no ClickUp — IMPERA
Ajuda a configurar expandir_range_tasks.py com os IDs corretos.

Uso:
  python3 discover_clickup_ids.py --list-fields     # mostra custom fields da lista
  python3 discover_clickup_ids.py --list-statuses   # mostra statuses da lista
"""

import json
import os
import sys
import urllib.request

API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
LIST_TRAFEGO = "901324476398"  # GESTÃO TRÁFEGO

def api_get(endpoint):
    """GET request to ClickUp API."""
    url = f"https://api.clickup.com/api/v2{endpoint}"
    req = urllib.request.Request(url, headers={"Authorization": API_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def list_custom_fields():
    """Lista custom fields da GESTÃO TRÁFEGO."""
    print("📋 Custom Fields em GESTÃO TRÁFEGO:")
    print("=" * 80)

    list_data = api_get(f"/list/{LIST_TRAFEGO}")
    if not list_data:
        print("❌ Não conseguiu fetch lista")
        return

    custom_fields = list_data.get("custom_fields", [])
    if not custom_fields:
        print("❌ Nenhum custom field encontrado")
        return

    for field in custom_fields:
        field_id = field.get("id")
        field_name = field.get("name")
        field_type = field.get("type")
        print(f"  ID: {field_id}")
        print(f"  Nome: {field_name}")
        print(f"  Tipo: {field_type}")
        print()

    print("\n💡 Para usar parent_task_id, copie o ID acima para:")
    print("   export CU_FIELD_PARENT_TASK_ID='<ID>'")

def list_statuses():
    """Lista statuses da GESTÃO TRÁFEGO."""
    print("🔴 Statuses em GESTÃO TRÁFEGO:")
    print("=" * 80)

    list_data = api_get(f"/list/{LIST_TRAFEGO}")
    if not list_data:
        print("❌ Não conseguiu fetch lista")
        return

    statuses = list_data.get("statuses", [])
    if not statuses:
        print("❌ Nenhum status encontrado")
        return

    for status in statuses:
        status_id = status.get("id")
        status_name = status.get("status")
        print(f"  ID: {status_id}")
        print(f"  Nome: {status_name}")

    print("\n💡 Para usar 'Testes Concluídos', procure o status e copie o ID:")
    print("   export CU_STATUS_TESTES_CONCLUIDOS='<ID>'")

if __name__ == "__main__":
    if not API_TOKEN:
        print("❌ CLICKUP_API_TOKEN não configurado")
        sys.exit(1)

    if "--list-fields" in sys.argv:
        list_custom_fields()
    elif "--list-statuses" in sys.argv:
        list_statuses()
    else:
        print(__doc__)
        list_custom_fields()
        print("\n")
        list_statuses()
