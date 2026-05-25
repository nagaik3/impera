#!/usr/bin/env python3
"""
Webhook para rastrear tarefas movidas para 'em alteração'
Registra em um arquivo JSON para consultas posteriores
"""
import os
import json
from datetime import datetime
from flask import Flask, request
import requests

app = Flask(__name__)

CLICKUP_API_TOKEN = os.getenv('CLICKUP_API_TOKEN')
TRACKING_FILE = os.path.expanduser("~/Scripts/data/em_alteracao_history.json")

# Criar diretório se não existir
os.makedirs(os.path.dirname(TRACKING_FILE), exist_ok=True)

def load_history():
    """Carrega histórico de tarefas em alteração"""
    if os.path.exists(TRACKING_FILE):
        with open(TRACKING_FILE, 'r') as f:
            return json.load(f)
    return {"tasks": []}

def save_history(history):
    """Salva histórico de tarefas em alteração"""
    with open(TRACKING_FILE, 'w') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

@app.route('/webhook/task-status-change', methods=['POST'])
def webhook_status_change():
    """Recebe webhooks de mudança de status do ClickUp"""

    try:
        payload = request.json

        # Extrai informações do webhook
        event = payload.get('event', '')
        task_data = payload.get('task', {})
        task_id = task_data.get('id')
        task_name = task_data.get('name')
        status = task_data.get('status', {}).get('status')

        print(f"[{datetime.now()}] Webhook recebido: {event}")
        print(f"  Task: {task_name} ({task_id})")
        print(f"  Status: {status}")

        # Se foi movido para "em alteração", registra
        if status and 'em alteração' in status.lower():
            history = load_history()

            task_entry = {
                "task_id": task_id,
                "task_name": task_name,
                "status": status,
                "timestamp": datetime.now().isoformat(),
                "event": event
            }

            # Verifica se já não existe
            if not any(t['task_id'] == task_id for t in history['tasks']):
                history['tasks'].append(task_entry)
                save_history(history)

                print(f"  ✅ Registrado em {TRACKING_FILE}")

        return {"status": "received"}, 200

    except Exception as e:
        print(f"❌ Erro ao processar webhook: {e}")
        return {"error": str(e)}, 400

@app.route('/webhook/tracked-tasks', methods=['GET'])
def get_tracked_tasks():
    """Retorna lista de todas as tarefas registradas em 'em alteração'"""
    history = load_history()
    return history, 200

if __name__ == '__main__':
    print("=" * 80)
    print("WEBHOOK TRACKER - EM ALTERAÇÃO")
    print("=" * 80)
    print()
    print("Para configurar no ClickUp:")
    print("1. Acesse: https://app.clickup.com/settings/integrations/webhooks")
    print("2. Crie um novo webhook com:")
    print(f"   URL: http://localhost:5001/webhook/task-status-change")
    print("   Events: taskStatusUpdated")
    print()
    print("Iniciando servidor...")
    print()

    app.run(port=5001, debug=False)
