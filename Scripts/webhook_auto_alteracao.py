#!/usr/bin/env python3
"""
Webhook Automático: Marca "Teve alteração?" quando tarefa vai para "em alteração"

Fluxo:
1. Tarefa é movida para status "em alteração"
2. Webhook recebe a mudança
3. Campo "Teve alteração?" é automaticamente marcado ✅
4. Registro é salvo para auditoria

Para configurar no ClickUp:
- Webhook URL: http://seu-servidor:5001/webhook/auto-alteracao
- Events: taskStatusUpdated
- Team ID: 2640127
"""

import os
import json
from datetime import datetime
from flask import Flask, request
import requests

app = Flask(__name__)

CLICKUP_API_TOKEN = os.getenv('CLICKUP_API_TOKEN')
CLICKUP_API_URL = "https://api.clickup.com/api/v2"

# IDs importantes
FIELD_TEVE_ALTERACAO = "3617b249-06e2-4d2e-9ba0-c48da305e42a"
STATUS_EM_ALTERACAO = "em alteração"
TRACKING_FILE = os.path.expanduser("~/Scripts/data/auto_alteracao_log.json")

# Criar diretório se não existir
os.makedirs(os.path.dirname(TRACKING_FILE), exist_ok=True)

HEADERS = {
    "Authorization": CLICKUP_API_TOKEN,
    "Content-Type": "application/json"
}

def update_task_field(task_id: str, field_id: str, value: bool):
    """Atualiza um campo customizado da tarefa"""
    url = f"{CLICKUP_API_URL}/task/{task_id}/field/{field_id}"

    payload = {
        "value": value  # True para marcar, False para desmarcar
    }

    try:
        response = requests.post(url, headers=HEADERS, json=payload)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro ao atualizar campo: {e}")
        return False

def log_event(event_data: dict):
    """Registra o evento em arquivo JSON para auditoria"""
    try:
        if os.path.exists(TRACKING_FILE):
            with open(TRACKING_FILE, 'r') as f:
                logs = json.load(f)
        else:
            logs = {"events": []}

        logs["events"].append(event_data)

        with open(TRACKING_FILE, 'w') as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Erro ao registrar log: {e}")

@app.route('/webhook/auto-alteracao', methods=['POST'])
def webhook_auto_alteracao():
    """
    Recebe webhook quando tarefa muda de status
    Se status é "em alteração", marca o campo automaticamente
    """
    try:
        payload = request.json

        # Extrai informações do webhook
        event = payload.get('event', '')
        task_data = payload.get('task', {})
        task_id = task_data.get('id')
        task_name = task_data.get('name')
        status = task_data.get('status', {}).get('status', '').lower()

        timestamp = datetime.now().isoformat()

        print(f"\n📬 [{timestamp}] Webhook recebido")
        print(f"   Event: {event}")
        print(f"   Task: {task_name} ({task_id})")
        print(f"   Status: {status}")

        # Se mudou para "em alteração", marca o campo
        if status and 'em alteração' in status:
            print(f"\n   🔄 Status é 'em alteração'...")
            print(f"   ✏️  Marcando campo 'Teve alteração?'...")

            # Atualiza o campo para True (marcado)
            success = update_task_field(task_id, FIELD_TEVE_ALTERACAO, True)

            if success:
                print(f"   ✅ Campo atualizado com sucesso!")

                # Registra o evento
                log_event({
                    "timestamp": timestamp,
                    "task_id": task_id,
                    "task_name": task_name,
                    "event": "AUTO_MARKED_TEVE_ALTERACAO",
                    "status": status,
                    "field_id": FIELD_TEVE_ALTERACAO,
                    "action": "marked"
                })

                return {
                    "status": "success",
                    "message": "Campo marcado automaticamente",
                    "task_id": task_id
                }, 200
            else:
                print(f"   ❌ Falha ao atualizar campo")
                return {
                    "status": "error",
                    "message": "Falha ao atualizar campo"
                }, 500
        else:
            # Status não é "em alteração", apenas registra
            log_event({
                "timestamp": timestamp,
                "task_id": task_id,
                "task_name": task_name,
                "event": "STATUS_CHANGED_OTHER",
                "status": status,
                "action": "no_action"
            })

            return {
                "status": "received",
                "message": "Status não é 'em alteração', nenhuma ação tomada",
                "task_id": task_id
            }, 200

    except Exception as e:
        print(f"\n❌ Erro ao processar webhook: {e}")
        return {
            "status": "error",
            "message": str(e)
        }, 400

@app.route('/webhook/logs', methods=['GET'])
def get_logs():
    """Retorna todos os eventos registrados"""
    try:
        if os.path.exists(TRACKING_FILE):
            with open(TRACKING_FILE, 'r') as f:
                logs = json.load(f)
            return logs, 200
        else:
            return {"events": []}, 200
    except Exception as e:
        return {"error": str(e)}, 400

@app.route('/webhook/status', methods=['GET'])
def status():
    """Verifica se o webhook está ativo"""
    return {
        "status": "active",
        "service": "webhook_auto_alteracao",
        "field": "🔄 Teve alteração?",
        "field_id": FIELD_TEVE_ALTERACAO,
        "trigger": "Status → em alteração"
    }, 200

if __name__ == '__main__':
    print("=" * 80)
    print("⚙️  WEBHOOK AUTO-ALTERACAO")
    print("=" * 80)
    print()
    print("📋 Configuração:")
    print(f"   Campo: 🔄 Teve alteração?")
    print(f"   Field ID: {FIELD_TEVE_ALTERACAO}")
    print(f"   Acionador: Tarefa movida para 'em alteração'")
    print(f"   Ação: Marca o checkbox automaticamente ✅")
    print()
    print("🔗 Endpoints disponíveis:")
    print(f"   POST   http://localhost:5001/webhook/auto-alteracao")
    print(f"   GET    http://localhost:5001/webhook/logs")
    print(f"   GET    http://localhost:5001/webhook/status")
    print()
    print("📝 Para configurar no ClickUp:")
    print("   1. Vá para: Settings → Integrations → Webhooks")
    print("   2. Clique em 'Create Webhook'")
    print("   3. Configure:")
    print(f"      - URL: http://localhost:5001/webhook/auto-alteracao")
    print(f"      - Event: Task Status Updated")
    print(f"      - Workspace/Team: IMPERA PRODUTOS NATURAIS")
    print()
    print("🚀 Iniciando servidor na porta 5001...")
    print("=" * 80)
    print()

    app.run(host='0.0.0.0', port=5001, debug=False)
