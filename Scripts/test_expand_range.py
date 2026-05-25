#!/usr/bin/env python3
"""
Teste da lógica de expandir_range_tasks.py
Simula o webhook e executa a lógica diretamente.
"""

import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime

API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
CUSTOM_FIELD_PARENT_TASK_ID = os.environ.get("CU_FIELD_PARENT_TASK_ID", "")
STATUS_TESTES_CONCLUIDOS = os.environ.get("CU_STATUS_TESTES_CONCLUIDOS", "")

def api_get(endpoint):
    """GET request to ClickUp API."""
    url = f"https://api.clickup.com/api/v2{endpoint}"
    req = urllib.request.Request(url, headers={"Authorization": API_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"❌ api_get({endpoint}) error: {e}")
        return None

def api_put(endpoint, data):
    """PUT request to ClickUp API."""
    url = f"https://api.clickup.com/api/v2{endpoint}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method="PUT")
    req.add_header("Authorization", API_TOKEN)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"❌ api_put({endpoint}) error: {e}")
        return None

def extract_variations(task_name):
    """Extract variation numbers from task name."""
    # Try [V##-V##] pattern first (variations)
    match = re.search(r'\[V(\d+)-V(\d+)\]', task_name)
    if match:
        start, end = int(match.group(1)), int(match.group(2))
        return [f"V{i}" for i in range(start, end + 1)]

    # Try [AD###-AD###] pattern (creative ranges)
    match = re.search(r'\[AD(\d+)-AD(\d+)\]', task_name)
    if match:
        start, end = int(match.group(1)), int(match.group(2))
        return [f"AD{i}" for i in range(start, end + 1)]

    return []

print("=" * 80)
print("🧪 TEST: expandir_range_tasks.py")
print("=" * 80)

# Check config
print(f"\n📋 Configuração:")
print(f"  CUSTOM_FIELD_PARENT_TASK_ID: {CUSTOM_FIELD_PARENT_TASK_ID[:20]}...")
print(f"  STATUS_TESTES_CONCLUIDOS: {STATUS_TESTES_CONCLUIDOS}")

if not CUSTOM_FIELD_PARENT_TASK_ID or not STATUS_TESTES_CONCLUIDOS:
    print("\n❌ Variáveis de ambiente não configuradas")
    sys.exit(1)

# Test 1: Extract variations
print(f"\n✅ Test 1: Extract variations")
test_names = [
    "[NE][OF03][FB][AD06V1][V16-V21]",
    "[MM][BR][OF01][FB][AD116-AD120][V1]",
    "[EM][OF02][FB][AD644V9]",
]
for name in test_names:
    vars = extract_variations(name)
    print(f"  {name} → {vars}")

# Test 2: Update parent task (use real task from ClickUp)
print(f"\n✅ Test 2: Update real parent task")
parent_task_id = "868r3vhg8"  # [NE][OF03][FB][AD06V1] — use uma tarefa real para teste

task_data = api_get(f"/task/{parent_task_id}")
if task_data:
    task_name = task_data.get("name", "")
    print(f"  Parent Task: {task_name}")

    variations = extract_variations(task_name)
    if variations:
        print(f"  Variações encontradas: {variations}")

        # Update description
        current_desc = task_data.get("description", "") or ""
        variations_str = ", ".join(variations)
        expanded_line = f"[EXPANDIDA] - Variações: {variations_str}"

        new_desc = expanded_line
        if current_desc.strip():
            new_desc = expanded_line + "\n\n" + current_desc

        print(f"\n  Nova descrição:")
        print(f"  {new_desc[:100]}...")

        result = api_put(f"/task/{parent_task_id}", {"description": new_desc})
        if result:
            print(f"  ✅ Descrição atualizada")
        else:
            print(f"  ❌ Falha ao atualizar descrição")
    else:
        print(f"  ⚠️  Nenhuma variação encontrada no nome")
else:
    print(f"  ❌ Task não encontrada: {parent_task_id}")

# Test 3: Update custom field
print(f"\n✅ Test 3: Update custom field parent_task_id")
test_task_id = "868r3vhgg"  # Use uma tarefa filha real
payload = {
    "custom_fields": {
        CUSTOM_FIELD_PARENT_TASK_ID: parent_task_id
    }
}
result = api_put(f"/task/{test_task_id}", payload)
if result:
    print(f"  ✅ Custom field atualizado: {test_task_id}")
else:
    print(f"  ❌ Falha ao atualizar custom field")

# Test 4: Update status
print(f"\n✅ Test 4: Update task status")
payload = {"status": STATUS_TESTES_CONCLUIDOS}
result = api_put(f"/task/{parent_task_id}", payload)
if result:
    print(f"  ✅ Status atualizado: {parent_task_id}")
else:
    print(f"  ❌ Falha ao atualizar status")

print(f"\n{'=' * 80}")
print("✅ Testes completos!")
print(f"{'=' * 80}\n")
