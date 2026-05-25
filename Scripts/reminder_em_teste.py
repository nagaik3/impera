#!/usr/bin/env python3
"""
Reminder Em Teste — IMPERA
Posta lembrete no ClickUp para tarefas em "em teste" há >= 3 dias.
Notifica o copywriter para acompanhar resultados com o gestor.

Crontab: 0 10 * * * cd ~/Scripts && python3 reminder_em_teste.py
"""

import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta

sys.path.insert(0, os.path.expanduser("~/Scripts"))
from impera_cache import cached_cu_tasks

API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
LIST_TRAFEGO = "901324476398"
STATE_FILE = os.path.expanduser("~/Scripts/data/reminder_em_teste.json")

CF_COPYWRITER = "eeb64866-df57-4dbf-8338-5d4fb58837aa"
REMINDER_DAYS = 3

# Mapeamento copywriter dropdown → ClickUp user ID (para @mention)
COPYWRITER_USER_MAP = {
    "YAN": 81970243,
    "REAPER": 18922946,
    "CRISPIM": 118015162,
    "ANA": 118024166,
    "ELIAS": 84627549,
    "CAROL": 118051219,
}


def api_post(endpoint, data):
    url = f"https://api.clickup.com/api/v2{endpoint}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Authorization": API_TOKEN,
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def get_cf_value(task, field_id):
    for cf in task.get("custom_fields", []):
        if cf["id"] != field_id:
            continue
        val = cf.get("value")
        if val is None:
            return None
        if cf.get("type") == "drop_down" and "type_config" in cf:
            for opt in cf["type_config"].get("options", []):
                if opt.get("orderindex") == val or opt.get("id") == str(val):
                    return opt.get("name")
            if isinstance(val, int) and val < len(cf["type_config"].get("options", [])):
                return cf["type_config"]["options"][val].get("name")
        return str(val)
    return None


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def main():
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] Reminder em teste — verificando...")

    tasks = cached_cu_tasks(LIST_TRAFEGO, ttl=1800)
    em_teste = [t for t in tasks if t["status"]["status"].lower() == "em teste" and not t.get("parent")]

    state = load_state()
    now = datetime.now()
    cutoff = now - timedelta(days=REMINDER_DAYS)
    reminded = 0

    for t in em_teste:
        tid = t["id"]
        name = t.get("name", "")

        # Skip if already reminded
        if tid in state:
            continue

        # Check task age (date_updated as proxy for when it entered "em teste")
        date_updated = int(t.get("date_updated", "0"))
        if date_updated == 0:
            continue

        task_date = datetime.fromtimestamp(date_updated / 1000)
        if task_date > cutoff:
            continue  # Not old enough yet

        # Get copywriter
        copywriter = get_cf_value(t, CF_COPYWRITER) or "Copywriter"

        # Get gestor
        assignees = t.get("assignees", [])
        gestor = assignees[0].get("username", "Gestor") if assignees else "Gestor"

        comment = (
            f"Lembrete automatico: esta tarefa esta em teste ha {REMINDER_DAYS}+ dias.\n"
            f"{copywriter}, verifique os resultados com {gestor}."
        )

        copywriter_upper = copywriter.upper().strip()
        copywriter_cu_id = COPYWRITER_USER_MAP.get(copywriter_upper)

        comment_data = {"comment_text": comment, "notify_all": False}
        if copywriter_cu_id:
            comment_data["assignee"] = copywriter_cu_id
        else:
            comment_data["notify_all"] = True

        try:
            api_post(f"/task/{tid}/comment", comment_data)
            state[tid] = {
                "name": name,
                "reminded_at": now.isoformat(),
                "copywriter": copywriter,
            }
            reminded += 1
            print(f"  Lembrete: {name} ({copywriter})")
            time.sleep(0.5)
        except Exception as e:
            print(f"  ERRO: {name} — {e}")

    save_state(state)
    print(f"  Total: {reminded} lembretes enviados | {len(em_teste)} tarefas em teste")


if __name__ == "__main__":
    main()
