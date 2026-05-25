#!/usr/bin/env python3
"""
Aprova Para Trafego — IMPERA
Move tarefas de status "aprovado-trafego" e "aprovado-vturb" (custom)
para "enviado para trafego" e "enviado para vturb" (done type).

Substitui automação nativa do ClickUp quando crédito é limitado.

Uso:
  python3 aprova_para_trafego.py

Crontab:
  */5 * * * * cd ~/Scripts && python3 aprova_para_trafego.py
"""

import json
import os
import sys
import urllib.request
from datetime import datetime
from retry_helper import retry_api_call

API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
LIST_COPY = "901324556390"
STATUS_CACHE_FILE = os.path.expanduser("~/Scripts/data/gate_status_ids.json")
MOVES_LOG = os.path.expanduser("~/Scripts/data/aprova_trafego_moves.jsonl")

# === API ===
def api_get(endpoint):
    url = f"https://api.clickup.com/api/v2{endpoint}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", API_TOKEN)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())

def api_put(endpoint, payload):
    url = f"https://api.clickup.com/api/v2{endpoint}"
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, method="PUT")
    req.add_header("Authorization", API_TOKEN)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())

# === FETCH STATUS IDS ===
def fetch_status_ids():
    try:
        list_data = api_get(f"/list/{LIST_COPY}")
        statuses = list_data.get("statuses", [])
        cache = {}
        for status in statuses:
            status_name = status.get("status", "").lower()
            status_id = status.get("id", "")
            if status_id:
                cache[status_name] = status_id

        cache["_timestamp"] = datetime.now().isoformat()
        os.makedirs(os.path.dirname(STATUS_CACHE_FILE), exist_ok=True)
        with open(STATUS_CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=2)
        return cache
    except Exception as e:
        print(f"❌ Erro ao buscar status IDs: {e}")
        return {}

# === MAIN ===
@retry_api_call(max_retries=3)
def move_task(task_id, task_name, source_status, target_status):
    status_ids = fetch_status_ids()
    target_status_id = status_ids.get(target_status.lower())

    if not target_status_id:
        print(f"  ❌ Status '{target_status}' não encontrado")
        return False

    try:
        result = api_put(f"/task/{task_id}", {"status_id": target_status_id})
        new_status = result.get("status", {}).get("status", "unknown")

        if new_status.lower() == target_status.lower():
            print(f"  ✅ {task_name[:50]}")
            print(f"     {source_status} → {target_status}")

            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "task_id": task_id,
                "task_name": task_name,
                "source_status": source_status,
                "target_status": target_status,
                "success": True
            }
            os.makedirs(os.path.dirname(MOVES_LOG), exist_ok=True)
            with open(MOVES_LOG, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
            return True
        else:
            print(f"  ⚠️  {task_name[:50]} — status ainda {new_status}")
            return False
    except Exception as e:
        print(f"  ❌ Erro ao mover {task_id}: {e}")
        return False

def run():
    print(f"=== Aprova Para Trafego — {datetime.now().strftime('%Y-%m-%d %H:%M')} ===")

    moved_count = 0

    for source_status, target_status in [
        ("aprovado-trafego", "enviado para trafego"),
        ("aprovado-vturb", "enviado para vturb")
    ]:
        try:
            data = api_get(f"/list/{LIST_COPY}/task?statuses%5B%5D={source_status}&subtasks=false")
            tasks = data.get("tasks", [])

            if not tasks:
                print(f"  (nenhuma tarefa em '{source_status}')")
                continue

            print(f"\n  [{source_status}] {len(tasks)} tarefa(s)")
            for task in tasks:
                task_id = task.get("id", "")
                task_name = task.get("name", "")
                if move_task(task_id, task_name, source_status, target_status):
                    moved_count += 1
        except Exception as e:
            print(f"  ❌ Erro ao processar '{source_status}': {e}")

    print(f"\n  Total movidas: {moved_count}")

if __name__ == "__main__":
    run()
