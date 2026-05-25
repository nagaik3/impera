#!/usr/bin/env python3
"""
Auto Etiqueta — IMPERA
Adiciona tags automáticas a tarefas do ClickUp com base na nomenclatura.

Analisa o nome da tarefa e aplica tags como: criativo-novo, variação, imagem,
microlead, lead, vsl, otimização, upsell, pressell, ripagem.

Modos:
  --dry       Mostra o que seria alterado (sem modificar nada)
  --server    Inicia webhook server para tagging real-time
  (sem flag)  Aplica as tags (polling)

Webhook: Porta 5006 (real-time tagging na criação/atualização de tasks)
Crontab (1x a cada 2 horas): 0 */2 * * * cd ~/Scripts && /usr/bin/python3 auto_etiqueta.py >> ~/Scripts/logs/auto_etiqueta.log 2>&1

GPDR — Iago Almeida | Assistido por Claude — Anthropic
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

sys.path.insert(0, os.path.expanduser("~/Scripts"))
try:
    from auto_etiqueta_cache import (
        get_cached_analysis, cache_analysis, build_consolidated_alert,
        should_alert_today, mark_alerted_today, clear_cache
    )
except:
    pass

API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
CLICKUP_CHAT_VIEW = "8cm1w4b-9873"

LIST_COPY = "901324556390"
STATE_FILE = os.path.expanduser("~/Scripts/data/etiqueta_state.json")
LOG_DIR = os.path.expanduser("~/Scripts/logs")
WEBHOOK_PORT = 5006

DRY_RUN = "--dry" in sys.argv
SERVER_MODE = "--server" in sys.argv


# =============================================================================
# Helpers
# =============================================================================

def log(msg):
    """Log com timestamp."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def api_request(method, endpoint, data=None, retries=3):
    """ClickUp API request com retry automático."""
    url = f"https://api.clickup.com/api/v2/{endpoint}"
    headers = {"Authorization": API_TOKEN, "Content-Type": "application/json"}

    for attempt in range(retries):
        try:
            body = json.dumps(data).encode() if data else None
            req = urllib.request.Request(url, data=body, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode()
                return json.loads(raw) if raw.strip() else {}
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            log(f"ERRO API {method} {endpoint}: {e}")
            return None


def post_clickup_alert(message):
    """Posta alerta no ClickUp Chat View."""
    if not message or not CLICKUP_CHAT_VIEW:
        return
    try:
        import subprocess
        cmd = [
            "curl", "-s", "-X", "POST",
            f"https://api.clickup.com/api/v2/view/{CLICKUP_CHAT_VIEW}/chat",
            "-H", f"Authorization: {API_TOKEN}",
            "-H", "Content-Type: application/json",
            "-d", json.dumps({"content": message})
        ]
        subprocess.run(cmd, timeout=10, capture_output=True)
    except Exception as e:
        log(f"Erro ao postar no ClickUp: {e}")


# =============================================================================
# Estado (evita reprocessamento)
# =============================================================================

def load_state():
    """Carrega estado: {task_id: [tags já aplicadas]}."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_state(state):
    """Salva estado atualizado."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


# =============================================================================
# Tag detection — analisa nomenclatura
# =============================================================================

def detect_tags(name):
    """Analisa o nome da tarefa e retorna set de tags esperadas."""
    tags = set()
    upper = name.upper()

    # --- Criativo novo vs Variação ---
    # Regras:
    #   - V1 ou V1-V2 até V1-V5 = criativo-novo (poucos hooks, teste inicial)
    #   - V1-V6+ = variação (volume = derivado de algo que já performou)
    #   - V2+, V3+, etc. = variação (range não começa em V1)
    #   - AD com versão no nome (AD08V2, AD76V10) = variação (derivado)
    #   - CE/CY/CC com versão (CE15 V12, CE15][V22) = variação (trabalho em cima de ripagem)
    #   - CE/CY/CC sem versão (CE15, CY01-CY08) = ripagem pura (tag separada)
    has_ad_version = bool(re.search(r'\[AD\d+V\d+', upper))  # AD08V2, AD76V10

    # Detectar se é ripagem PURA (CE/CY/CC/C## trazendo criativos ripados, sem variação)
    # Ripagem pura: [CY01-CY08], [CE66-CE72], [C36] — sem grupo [V##] na tarefa
    # Variação de rip: [CE15][V22-V36], [CE15 V12][V1-V20] — tem [V##]
    # C## (sem E/Y/C) = Douglas tráfego, mesmo tratamento que ripagem
    rip_ceyc = re.search(r'\[C[EYC]\d+', upper)  # CE15, CY01, CC05
    rip_c_plain = re.search(r'\[C(\d+)', upper)   # C36, C123
    # Garantir que C plain não é parte de AD (ex: ADCE34 não conta)
    is_c_plain = bool(rip_c_plain) and not bool(re.search(r'\[AD.*C\d+', upper))
    has_rip_prefix = bool(rip_ceyc) or is_c_plain
    has_any_version_group = bool(re.search(r'\[V\d+', upper))
    is_pure_ripagem = has_rip_prefix and not has_any_version_group
    is_rip_derived = has_rip_prefix and has_any_version_group

    ad_pattern = r'\[AD\w*\d+(?:\s*-\s*(?:AD\w*\d+|IMG))?\]'
    rip_pattern = r'\[C[EYC]?\d+(?:\s*V\d+)?(?:\s*-\s*C[EYC]?\d+)?\]'
    creative_pattern = f'(?:{ad_pattern}|{rip_pattern})'
    ver_match = re.search(creative_pattern + r'\s*\[V(\d+)(?:-V(\d+))?\]', upper)
    if ver_match:
        v_start = int(ver_match.group(1))
        v_end = int(ver_match.group(2)) if ver_match.group(2) else v_start
        v_range = v_end - v_start + 1

        if is_pure_ripagem or has_ad_version or is_rip_derived:
            tags.add("variação")
        elif v_start == 1 and v_range <= 5:
            tags.add("criativo-novo")
        else:
            tags.add("variação")

    # --- Imagem ---
    if "[IMG]" in upper or re.search(r'\[AD\d+\s*IMG', upper) or "IMG" in upper:
        tags.add("imagem")

    # --- Microlead (antes de lead, pois MLD contém LD) ---
    if "[MLD]" in upper or re.search(r'\[MLD\d*\]', upper) or "[MLD" in upper:
        tags.add("microlead")
    # --- Lead (não MLD) ---
    elif "[LD]" in upper or re.search(r'\[LD\d*\]', upper) or "[LD" in upper:
        tags.add("lead")

    # --- VSL ---
    if "[VSL]" in upper:
        tags.add("vsl")

    # --- Otimização ---
    if "[OTMZ]" in upper:
        tags.add("otimização")

    # --- Upsell ---
    if "[UP]" in upper:
        tags.add("upsell")

    # --- Pressell ---
    if "[PRESSELL" in upper or "[PSL" in upper:
        tags.add("pressell")

    # --- Ripagem (CE##, CY##, CC##, C##) — só quando é ripagem pura, sem variação ---
    # [CY01-CY08] = ripagem. [CE15 V12][V1-V20] = variação (alguém trabalhando em cima)
    # [C36] = ripagem Douglas. [C123V3][V16-V35] = variação de C123
    if is_pure_ripagem:
        tags.add("ripagem")

    return tags


# =============================================================================
# Core: buscar tarefas e aplicar tags
# =============================================================================

def fetch_open_tasks():
    """Busca todas as tarefas abertas da lista COPY."""
    tasks = []
    page = 0
    while True:
        data = api_request("GET",
            f"list/{LIST_COPY}/task?page={page}&include_closed=false"
            f"&subtasks=true")
        if not data or not data.get("tasks"):
            break
        tasks.extend(data["tasks"])
        page += 1
        if len(data["tasks"]) < 100:
            break
        time.sleep(0.3)
    return tasks


def get_existing_tags(task):
    """Retorna set de nomes de tags já presentes na tarefa."""
    return {t["name"].lower() for t in task.get("tags", [])}


def add_tag(task_id, tag_name):
    """Adiciona uma tag a uma tarefa."""
    encoded = urllib.parse.quote(tag_name)
    return api_request("POST", f"task/{task_id}/tag/{encoded}")


def process_tasks():
    """Lógica principal: detecta e aplica tags."""
    state = load_state()
    tasks = fetch_open_tasks()

    if not tasks:
        log("Nenhuma tarefa aberta encontrada.")
        return

    log(f"Encontradas {len(tasks)} tarefas abertas.")

    added_count = 0
    skipped = 0
    errors = 0
    changes = []  # para resumo ClickUp

    for task in tasks:
        name = task.get("name", "")
        task_id = task["id"]

        # Só processar tarefas cuja nomenclatura começa com "["
        if not name.startswith("["):
            skipped += 1
            continue

        # Checar cache de análise
        cached = get_cached_analysis(task_id)
        if cached:
            expected_tags = set(cached.get("tags", []))
            log(f"[CACHE HIT] {name[:60]}")
        else:
            expected_tags = detect_tags(name)
            # Armazenar análise em cache
            cache_analysis(task_id, {"tags": list(expected_tags), "name": name})

        if not expected_tags:
            continue

        existing_tags = get_existing_tags(task)

        # Checar estado — tags já aplicadas por nós anteriormente
        state_tags = set(state.get(task_id, []))

        # Tags que precisam ser adicionadas
        missing = expected_tags - existing_tags

        # Filtrar tags que já tentamos aplicar (estão no state mas não na tarefa =
        # pode ter sido removida manualmente, não reaplicar)
        to_add = missing - state_tags

        if not to_add:
            continue

        if DRY_RUN:
            log(f"[DRY] {name[:80]} → +{', '.join(sorted(to_add))}")
            added_count += len(to_add)
            continue

        task_ok = True
        for tag in sorted(to_add):
            result = add_tag(task_id, tag)
            if result is not None:
                log(f"TAG +{tag} → {name[:80]}")
                added_count += 1
                state_tags.add(tag)
                time.sleep(0.2)  # rate limit
            else:
                log(f"ERRO ao adicionar tag '{tag}' em {name[:60]}")
                errors += 1
                task_ok = False

        if task_ok and to_add:
            changes.append(f"• {name[:60]} → +{', '.join(sorted(to_add))}")

        # Atualizar state com todas as tags aplicadas (existentes + novas)
        state[task_id] = sorted(state_tags | (expected_tags & existing_tags))

    if not DRY_RUN:
        save_state(state)

    # Resumo
    mode = "[DRY RUN] " if DRY_RUN else ""
    log(f"{mode}Concluído: {added_count} tags adicionadas, {skipped} ignoradas, {errors} erros")

    # ClickUp Chat — só se houve alterações reais
    if changes and not DRY_RUN:
        changes_by_time = {"main": changes}
        msg = build_consolidated_alert(changes_by_time, len(tasks))
        if msg:
            post_clickup_alert(msg)
            state = mark_alerted_today(state)
            save_state(state)


# =============================================================================
# Webhook Server — Real-time tagging
# =============================================================================

class WebhookHandler(BaseHTTPRequestHandler):
    """Handler para webhook do ClickUp."""

    def do_POST(self):
        """Recebe eventos do ClickUp."""
        if self.path != "/webhook/etiqueta":
            self.send_response(404)
            self.end_headers()
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode()
            event_data = json.loads(body)

            # Evento de criação/atualização de task
            if event_data.get("event") in ["taskCreated", "taskUpdated"]:
                task = event_data.get("task", {})
                name = task.get("name", "")
                task_id = task.get("id", "")

                if name and task_id and name.startswith("["):
                    log(f"[WEBHOOK] Evento: {event_data.get('event')} → {name[:60]}")
                    self.process_single_task(task_id, name)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')

        except Exception as e:
            log(f"Erro no webhook: {e}")
            self.send_response(500)
            self.end_headers()

    def process_single_task(self, task_id, name):
        """Processa uma única tarefa (para webhook)."""
        try:
            state = load_state()

            expected_tags = detect_tags(name)
            if not expected_tags:
                return

            # Buscar tarefa
            task_data = api_request("GET", f"task/{task_id}")
            if not task_data:
                return

            existing_tags = get_existing_tags(task_data)
            state_tags = set(state.get(task_id, []))
            missing = expected_tags - existing_tags
            to_add = missing - state_tags

            if not to_add:
                return

            # Aplicar tags
            for tag in sorted(to_add):
                result = add_tag(task_id, tag)
                if result is not None:
                    log(f"[WEBHOOK TAG] +{tag} → {name[:60]}")
                    state_tags.add(tag)
                    time.sleep(0.2)

            state[task_id] = sorted(state_tags | (expected_tags & existing_tags))
            save_state(state)

        except Exception as e:
            log(f"Erro ao processar webhook task: {e}")

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def start_webhook_server():
    """Inicia servidor webhook na porta 5006."""
    server = HTTPServer(("localhost", WEBHOOK_PORT), WebhookHandler)
    log(f"🚀 Webhook server iniciado na porta {WEBHOOK_PORT}")
    server.serve_forever()


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    os.makedirs(LOG_DIR, exist_ok=True)

    if not API_TOKEN:
        log("ERRO: CLICKUP_API_TOKEN não definido.")
        sys.exit(1)

    if SERVER_MODE:
        log("Iniciando Auto Etiqueta [WEBHOOK SERVER]")
        try:
            start_webhook_server()
        except Exception as e:
            log(f"ERRO FATAL no webhook: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    else:
        log(f"Iniciando Auto Etiqueta {'[DRY RUN]' if DRY_RUN else '[POLLING]'}")
        try:
            process_tasks()
        except Exception as e:
            log(f"ERRO FATAL: {e}")
            import traceback
            traceback.print_exc()
            post_clickup_alert(f"❌ Auto Etiqueta ERRO\n{e}")
            sys.exit(1)
