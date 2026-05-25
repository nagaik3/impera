#!/usr/bin/env python3
"""
Webhook Receiver: Expandir Ranges de Tarefas — IMPERA
Recebe POST do dashboard atribuidor-impera.onrender.com quando gestor move subtarefas.

Fluxo:
1. Dashboard cria 6 subtarefas em ClickUp (ex: AD116V1, AD117V1, ..., AD120V1)
2. Dashboard envia POST /webhook/expand-range com parent_task_id + created_tasks
3. Script recebe webhook:
   - Adiciona parent_task_id a cada subtarefa
   - Marca tarefa PAI com [EXPANDIDA] - Variações: V##,V##,... na descrição
   - Move tarefa PAI para status "Testes Concluídos"
   - Retorna 200 OK

Uso:
  python3 expandir_range_tasks.py --server         # inicia webhook server (porta 5000)
  python3 expandir_range_tasks.py --test           # envia webhook mock
"""

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

sys.path.insert(0, os.path.expanduser("~/Scripts"))

# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════

CLICKUP_API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
LIST_TRAFEGO = "901324476398"  # GESTÃO TRÁFEGO

# Custom field IDs (via ClickUp API — precisam ser descobertos)
CUSTOM_FIELD_PARENT_TASK_ID = os.environ.get("CU_FIELD_PARENT_TASK_ID", "")

# Status IDs (precisam ser descobertos via ClickUp API)
STATUS_TESTES_CONCLUIDOS = os.environ.get("CU_STATUS_TESTES_CONCLUIDOS", "")

WEBHOOK_PORT = int(os.environ.get("WEBHOOK_PORT", "5000"))
LOG_FILE = os.path.expanduser("~/Scripts/data/expand_range_webhook.log")

# ═══════════════════════════════════════════════════════════════
# API HELPERS
# ═══════════════════════════════════════════════════════════════

def api_get(endpoint):
    """GET request to ClickUp API."""
    url = f"https://api.clickup.com/api/v2{endpoint}"
    req = urllib.request.Request(url, headers={"Authorization": CLICKUP_API_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        log(f"❌ api_get({endpoint}) error: {e}")
        return None

def api_put(endpoint, data):
    """PUT request to ClickUp API."""
    url = f"https://api.clickup.com/api/v2{endpoint}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method="PUT")
    req.add_header("Authorization", CLICKUP_API_TOKEN)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        log(f"❌ api_put({endpoint}) error: {e}")
        return None

def log(msg):
    """Log to file and stdout."""
    timestamp = datetime.now().isoformat()
    full_msg = f"[{timestamp}] {msg}"
    print(full_msg)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(full_msg + "\n")

# ═══════════════════════════════════════════════════════════════
# TASK UPDATES
# ═══════════════════════════════════════════════════════════════

def extract_variations(task_name):
    """
    Extract variation numbers from task name.
    Ex: [NE][OF03][FB][AD06V1][V16-V21] → ['V16', 'V17', ..., 'V21']
    Ex: [MM][BR][OF01][FB][AD116-AD120][V1] → ['AD116', 'AD117', ..., 'AD120']
    """
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

def update_subtask_parent_id(task_id, parent_task_id):
    """
    Adiciona parent_task_id na subtarefa.
    Opção A: Campo custom parent_task_id
    """
    if not CUSTOM_FIELD_PARENT_TASK_ID:
        log(f"⚠️  CUSTOM_FIELD_PARENT_TASK_ID não configurado. Skipando parent_task_id para {task_id}")
        return True

    payload = {
        "custom_fields": {
            CUSTOM_FIELD_PARENT_TASK_ID: parent_task_id
        }
    }

    result = api_put(f"/task/{task_id}", payload)
    if result:
        log(f"  ✅ parent_task_id adicionado: {task_id}")
        return True
    else:
        log(f"  ❌ Falha ao adicionar parent_task_id: {task_id}")
        return False

def update_parent_task_description(parent_task_id, variations):
    """
    Adiciona flag [EXPANDIDA] na descrição da tarefa PAI.
    Opção B: Descrição (primeira linha)

    Formato:
    [EXPANDIDA] - Variações: V16, V17, V18, V19, V20, V21
    [... resto da descrição original ...]
    """
    # Fetch tarefa PAI para pegar descrição atual
    task = api_get(f"/task/{parent_task_id}")
    if not task:
        log(f"  ❌ Não conseguiu fetch tarefa PAI: {parent_task_id}")
        return False

    current_desc = task.get("description", "") or ""
    variations_str = ", ".join(variations)

    # Montar descrição nova
    expanded_line = f"[EXPANDIDA] - Variações: {variations_str}"

    # Checar se já tem [EXPANDIDA] (evitar duplicação)
    if "[EXPANDIDA]" in current_desc:
        log(f"  ℹ️  Tarefa PAI já estava marcada [EXPANDIDA]: {parent_task_id}")
        return True

    # Prepend expanded_line ao description
    new_desc = expanded_line
    if current_desc.strip():
        new_desc = expanded_line + "\n\n" + current_desc

    payload = {"description": new_desc}
    result = api_put(f"/task/{parent_task_id}", payload)
    if result:
        log(f"  ✅ Descrição atualizada (PAI): {parent_task_id}")
        return True
    else:
        log(f"  ❌ Falha ao atualizar descrição: {parent_task_id}")
        return False

def move_parent_to_testes_concluidos(parent_task_id):
    """
    Move tarefa PAI para status "Testes Concluídos".
    """
    if not STATUS_TESTES_CONCLUIDOS:
        log(f"⚠️  CU_STATUS_TESTES_CONCLUIDOS não configurado. Skipando status move para {parent_task_id}")
        return True

    payload = {"status": STATUS_TESTES_CONCLUIDOS}
    result = api_put(f"/task/{parent_task_id}", payload)
    if result:
        log(f"  ✅ Status atualizado (PAI → Testes Concluídos): {parent_task_id}")
        return True
    else:
        log(f"  ❌ Falha ao atualizar status: {parent_task_id}")
        return False

# ═══════════════════════════════════════════════════════════════
# WEBHOOK HANDLER
# ═══════════════════════════════════════════════════════════════

class ExpandRangeHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler para webhook."""

    def do_POST(self):
        """Handle POST /webhook/expand-range"""
        if self.path != "/webhook/expand-range":
            self.send_response(404)
            self.end_headers()
            return

        # Parse JSON payload
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            payload = json.loads(body.decode())
        except Exception as e:
            log(f"❌ Webhook payload inválido: {e}")
            self.send_response(400)
            self.end_headers()
            return

        # Extract fields
        parent_task_id = payload.get("parent_task_id")
        created_tasks = payload.get("created_tasks", [])  # [{id, name}, ...]
        target_status = payload.get("target_status")

        log(f"🎯 Webhook recebido: parent_task_id={parent_task_id}, {len(created_tasks)} subtarefas")

        if not parent_task_id or not created_tasks:
            log(f"❌ Payload incompleto: parent_task_id={parent_task_id}, created_tasks={created_tasks}")
            self.send_response(400)
            self.end_headers()
            return

        # Process
        try:
            # 1. Extract variations from parent task name
            parent_task = api_get(f"/task/{parent_task_id}")
            if not parent_task:
                raise Exception(f"Não conseguiu fetch tarefa PAI: {parent_task_id}")

            parent_name = parent_task.get("name", "")
            variations = extract_variations(parent_name)

            if not variations:
                log(f"⚠️  Nenhuma variação detectada no nome: {parent_name}")
                variations = [f"V{i}" for i in range(len(created_tasks))]

            log(f"  Variações detectadas: {variations}")

            # 2. Update each subtask with parent_task_id
            for i, subtask_obj in enumerate(created_tasks):
                task_id = subtask_obj.get("id")
                task_name = subtask_obj.get("name", "")

                if not task_id:
                    log(f"  ⚠️  Subtarefa {i} sem ID, skipando")
                    continue

                log(f"  Atualizando subtarefa: {task_name}")
                update_subtask_parent_id(task_id, parent_task_id)
                time.sleep(0.5)  # Rate limit

            # 3. Update parent task description
            if variations:
                update_parent_task_description(parent_task_id, variations)

            # 4. Move parent task to "Testes Concluídos"
            move_parent_to_testes_concluidos(parent_task_id)

            # 5. Return success
            log(f"✅ Expansão completa: {parent_task_id}")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())

        except Exception as e:
            log(f"❌ Erro ao processar webhook: {e}")
            self.send_response(500)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default HTTP logging."""
        pass

# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def start_server():
    """Inicia webhook server."""
    log(f"🚀 Iniciando webhook server na porta {WEBHOOK_PORT}")
    server = HTTPServer(("0.0.0.0", WEBHOOK_PORT), ExpandRangeHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("⏹️  Webhook server interrompido")
        server.shutdown()

def test_webhook():
    """Envia webhook mock para testar."""
    payload = {
        "parent_task_id": "86ah8t9ac",  # mock
        "created_tasks": [
            {"id": "task_1", "name": "[NE][OF03][FB][AD116][V1]"},
            {"id": "task_2", "name": "[NE][OF03][FB][AD117][V1]"},
            {"id": "task_3", "name": "[NE][OF03][FB][AD118][V1]"},
            {"id": "task_4", "name": "[NE][OF03][FB][AD119][V1]"},
            {"id": "task_5", "name": "[NE][OF03][FB][AD120][V1]"},
        ],
        "target_status": "aguardando teste"
    }

    url = f"http://localhost:{WEBHOOK_PORT}/webhook/expand-range"
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            log(f"✅ Test webhook enviado: {result}")
    except Exception as e:
        log(f"❌ Erro ao enviar test webhook: {e}")

if __name__ == "__main__":
    if not CLICKUP_API_TOKEN:
        print("❌ CLICKUP_API_TOKEN não configurado")
        sys.exit(1)

    if "--server" in sys.argv:
        start_server()
    elif "--test" in sys.argv:
        test_webhook()
    else:
        print(__doc__)
