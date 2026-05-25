#!/usr/bin/env python3
"""
Auto Envio ao Tráfego — IMPERA
Substitui a automação nativa do ClickUp que copiava tarefas da lista COPY
para a GESTÃO DE TRÁFEGO quando o status mudava para "enviado para tráfego".

A automação nativa falhou silenciosamente em ~23% das tarefas em abril/2026.
Este script é confiável: tem log, retry, alerta Telegram e anti-duplicidade.

Anti-duplicidade (3 camadas):
  1. State file: task_id da COPY já processado → pula
  2. Custom field: "Parent Task ID" na GT vincula por ID (não por nome)
  3. Match por nome: fallback normalizado (remove tags [TOP], [CS], etc)

Modos:
  --preview     Mostra o que seria copiado (sem alterar nada)
  --execute     Cria as cópias na Gestão de Tráfego
  --monitor     Roda em loop para crontab (*/10)
  --chat        Envia resumo consolidado no Chat (16h)

Crontab:
  */10 * * * 1-6 . ~/.impera_env && /usr/bin/python3 ~/Scripts/auto_envio_trafego.py --monitor >> ~/Scripts/logs/auto_envio_trafego.log 2>&1
  0 16 * * 1-6 . ~/.impera_env && /usr/bin/python3 ~/Scripts/auto_envio_trafego.py --chat >> ~/Scripts/logs/auto_envio_trafego.log 2>&1

GPDR — Iago Almeida | Assistido por Claude — Anthropic
"""

import fcntl
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime

sys.path.insert(0, os.path.expanduser("~/Scripts"))

API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

LIST_COPY = "901324556390"
LIST_TRAFEGO = "901324476398"
CHAT_VIEW_ID = "6-901324556390-8"

# Status que dispara a cópia
TRIGGER_STATUS = "enviado para trafego"

# Arquivo de controle — tarefas já copiadas (evita duplicidade)
STATE_FILE = os.path.expanduser("~/Scripts/data/enviados_trafego.json")
LOCK_FILE = os.path.expanduser("~/Scripts/data/auto_envio_trafego.lock")

# Custom field "Parent Task ID" na GT — vincula cópia ao original
CF_PARENT_TASK_ID = "e437be35-6ae3-4a6b-ac8d-46a7e9fbadeb"

# Campos a copiar da tarefa original
FIELDS_TO_COPY = [
    "eeb64866-df57-4dbf-8338-5d4fb58837aa",  # Copywriter
    "6002b1b9-e8c5-49ad-9e3d-3d8c314a1c91",  # Editor de Video
    "796e4880-13f0-4d30-9d3b-1ee72c6df14c",  # Fonte de Tráfego
    "1149425c-f3c9-478e-af23-37677d5f7eb3",  # Oferta
    "f61bfe77-933f-4637-828a-c9d8ef400d60",  # Nicho
    "deaa7741-15a9-4368-a88c-7ed4603cff1a",  # Mês Referente
    "c32f509c-b990-4a36-aa0f-78242640bef7",  # Link do material
]

LOG_DIR = os.path.expanduser("~/Scripts/logs")


# =============================================================================
# File lock (previne execuções simultâneas)
# =============================================================================

_lock_fd = None

def acquire_lock():
    """Tenta adquirir lock exclusivo. Retorna False se já há execução ativa."""
    global _lock_fd
    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
    _lock_fd = open(LOCK_FILE, "w")
    try:
        fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lock_fd.write(str(os.getpid()))
        _lock_fd.flush()
        return True
    except IOError:
        _lock_fd.close()
        _lock_fd = None
        return False


def release_lock():
    """Libera o lock."""
    global _lock_fd
    if _lock_fd:
        fcntl.flock(_lock_fd, fcntl.LOCK_UN)
        _lock_fd.close()
        _lock_fd = None


# =============================================================================
# API helpers
# =============================================================================

def api_request(method, endpoint, data=None, retries=3):
    """ClickUp API request com retry automático."""
    url = f"https://api.clickup.com/api/v2/{endpoint}"
    headers = {"Authorization": API_TOKEN, "Content-Type": "application/json"}

    for attempt in range(retries):
        try:
            body = json.dumps(data).encode() if data else None
            req = urllib.request.Request(url, data=body, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            log(f"ERRO API {method} {endpoint}: {e}")
            return None


def log(msg):
    """Log com timestamp."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def telegram_send(msg):
    """Envia alerta ao Telegram."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = json.dumps({
            "chat_id": TELEGRAM_CHAT,
            "text": msg,
            "parse_mode": "HTML"
        }).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        log(f"Erro Telegram: {e}")


# =============================================================================
# Estado (anti-duplicidade camada 1)
# =============================================================================

def load_state():
    """Carrega IDs de tarefas já copiadas."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_state(state):
    """Salva estado atualizado."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


# =============================================================================
# Anti-duplicidade camada 2: buscar por Parent Task ID na GT
# =============================================================================

_gt_parent_ids = None
_gt_parent_ids_time = 0


def _load_gt_parent_ids():
    """Carrega todos os Parent Task IDs da GT com cache de 5 min."""
    global _gt_parent_ids, _gt_parent_ids_time
    now = time.time()
    if _gt_parent_ids is not None and (now - _gt_parent_ids_time) < 300:
        return _gt_parent_ids

    parent_ids = set()
    page = 0
    while True:
        data = api_request("GET",
            f"list/{LIST_TRAFEGO}/task?page={page}&include_closed=true")
        if not data or not data.get("tasks"):
            break
        for t in data["tasks"]:
            for cf in t.get("custom_fields", []):
                if cf.get("id") == CF_PARENT_TASK_ID and cf.get("value"):
                    parent_ids.add(cf["value"].strip())
        page += 1
        if len(data["tasks"]) < 100:
            break
        time.sleep(0.3)

    _gt_parent_ids = parent_ids
    _gt_parent_ids_time = now
    log(f"  Cache GT Parent IDs carregado: {len(parent_ids)} tarefas vinculadas")
    return parent_ids


def check_exists_by_parent_id(task_id):
    """Verifica se já existe tarefa na GT vinculada a este task_id."""
    parent_ids = _load_gt_parent_ids()
    return task_id in parent_ids


# =============================================================================
# Anti-duplicidade camada 3: fallback por nome
# =============================================================================

_gt_names = None
_gt_names_time = 0


def _load_gt_names():
    """Carrega todos os nomes de tarefas da GT com cache de 5 minutos."""
    global _gt_names, _gt_names_time
    now = time.time()
    if _gt_names is not None and (now - _gt_names_time) < 300:
        return _gt_names

    names = set()
    page = 0
    while True:
        data = api_request("GET",
            f"list/{LIST_TRAFEGO}/task?page={page}&include_closed=true")
        if not data or not data.get("tasks"):
            break
        for t in data["tasks"]:
            n = _norm_name(t["name"])
            names.add(n)
        page += 1
        if len(data["tasks"]) < 100:
            break
        time.sleep(0.3)

    _gt_names = names
    _gt_names_time = now
    return names


def _norm_name(s):
    """Normaliza nome para comparação."""
    s = re.sub(r'\s*\[(TOP|CS|PRE-V)\]', '', s)
    return re.sub(r'\s+', ' ', s).strip().lower()


def check_exists_by_name(task_name):
    """Verifica se já existe tarefa com nome similar na GT."""
    names = _load_gt_names()
    return _norm_name(task_name) in names


# =============================================================================
# Core: buscar tarefas pendentes e criar cópias
# =============================================================================

def get_pending_tasks():
    """Busca tarefas na lista COPY com status 'enviado para tráfego'."""
    tasks = []
    page = 0
    while True:
        encoded_status = urllib.parse.quote(TRIGGER_STATUS)
        data = api_request("GET",
            f"list/{LIST_COPY}/task?page={page}&statuses[]={encoded_status}"
            f"&include_closed=true")
        if not data or not data.get("tasks"):
            break
        tasks.extend(data["tasks"])
        page += 1
        if len(data["tasks"]) < 100:
            break
        time.sleep(0.3)
    return tasks


def copy_task_to_gt(task, dry_run=False):
    """Cria cópia da tarefa na Gestão de Tráfego com vínculo por ID."""

    name = task["name"]
    task_id = task["id"]

    # Extrair custom fields com valor
    cf_values = {}
    for cf in task.get("custom_fields", []):
        if cf["id"] in FIELDS_TO_COPY and cf.get("value") is not None:
            cf_values[cf["id"]] = cf["value"]

    if dry_run:
        log(f"  [PREVIEW] Copiaria: {name} (ID: {task_id})")
        log(f"            Campos: {len(cf_values)} custom fields")
        return {"id": "preview", "name": name}

    # Criar tarefa na GT
    payload = {
        "name": name,
        "status": "aguardando teste",
        "description": f"Cópia automática da lista COPY.\nTarefa original: {task_id}\nData: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    }

    result = api_request("POST", f"list/{LIST_TRAFEGO}/task", payload)
    if not result or "id" not in result:
        log(f"  ERRO ao criar tarefa: {name}")
        return None

    new_id = result["id"]
    log(f"  ✅ Criada: {name} → GT ID: {new_id}")

    # Setar Parent Task ID (vínculo por ID)
    api_request("POST", f"task/{new_id}/field/{CF_PARENT_TASK_ID}",
                {"value": task_id})

    # Setar demais custom fields
    for field_id, value in cf_values.items():
        api_request("POST", f"task/{new_id}/field/{field_id}", {"value": value})
        time.sleep(0.1)

    # Comentário na tarefa original (COPY)
    comment = (
        f"✅ Cópia enviada automaticamente para Gestão de Tráfego.\n"
        f"Nova tarefa: {new_id}\n"
        f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"— Auto Envio ao Tráfego (GPDR)"
    )
    api_request("POST", f"task/{task_id}/comment", {
        "comment_text": comment,
        "notify_all": False
    })

    return result


# =============================================================================
# Modos de execução
# =============================================================================

def run(dry_run=False):
    """Execução principal."""
    state = load_state()
    tasks = get_pending_tasks()

    if not tasks:
        log("Nenhuma tarefa pendente em 'enviado para tráfego'.")
        return 0

    log(f"Encontradas {len(tasks)} tarefas em 'enviado para tráfego'.")

    created = 0
    skipped = 0
    errors = 0

    for task in tasks:
        task_id = task["id"]
        name = task["name"]

        # Camada 1: State file
        if task_id in state:
            skipped += 1
            continue

        # Camada 2: Parent Task ID na GT
        if not dry_run and check_exists_by_parent_id(task_id):
            log(f"  ⏭️  Já vinculada na GT (Parent ID): {name}")
            state[task_id] = {
                "name": name,
                "status": "já existia (parent_id)",
                "date": datetime.now().isoformat()
            }
            skipped += 1
            continue

        # Camada 3: Match por nome (fallback)
        if not dry_run and check_exists_by_name(name):
            log(f"  ⏭️  Já existe na GT (nome): {name}")
            state[task_id] = {
                "name": name,
                "status": "já existia (nome)",
                "date": datetime.now().isoformat()
            }
            skipped += 1
            continue

        # Criar cópia
        result = copy_task_to_gt(task, dry_run=dry_run)

        if result:
            created += 1
            if not dry_run:
                state[task_id] = {
                    "name": name,
                    "gt_id": result.get("id", "?"),
                    "date": datetime.now().isoformat()
                }
        else:
            errors += 1

        time.sleep(0.3)

    if not dry_run:
        save_state(state)

    # Resumo
    log(f"Resumo: {created} criadas | {skipped} já existiam | {errors} erros")

    # Alerta Telegram
    if created > 0 and not dry_run:
        telegram_send(
            f"📋 <b>Auto Envio ao Tráfego</b>\n\n"
            f"✅ {created} tarefa(s) copiada(s) para Gestão de Tráfego\n"
            f"⏭️ {skipped} já existiam\n"
            f"❌ {errors} erro(s)\n\n"
            f"<i>{datetime.now().strftime('%d/%m/%Y %H:%M')}</i>"
        )

    if errors > 0 and not dry_run:
        telegram_send(
            f"🔴 <b>ALERTA — Auto Envio ao Tráfego</b>\n\n"
            f"❌ {errors} tarefa(s) falharam ao copiar para GT.\n"
            f"Verificar log: ~/Scripts/logs/auto_envio_trafego.log\n\n"
            f"<i>{datetime.now().strftime('%d/%m/%Y %H:%M')}</i>"
        )

    return created


# =============================================================================
# Chat Summary
# =============================================================================

def post_chat_view(text):
    """Posta mensagem no Chat da lista Copy/Edição."""
    url = f"https://api.clickup.com/api/v2/view/{CHAT_VIEW_ID}/comment"
    payload = json.dumps({"comment_text": text}).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Authorization", API_TOKEN)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return True
    except Exception as e:
        log(f"[ERRO] Chat View: {e}")
        return False


def run_chat_summary():
    """Envia resumo consolidado do dia no Chat da lista."""
    now = datetime.now()
    log(f"Chat Summary — Auto Envio ao Tráfego")

    state = load_state()

    # Contar envios de hoje
    today = now.strftime("%Y-%m-%d")
    created_today = []
    skipped_today = 0

    for tid, info in state.items():
        date_str = info.get("date", "")
        if not date_str.startswith(today):
            continue
        status = info.get("status", "")
        if "já existia" in status:
            skipped_today += 1
        elif info.get("gt_id"):
            created_today.append(info)

    total = len(created_today) + skipped_today
    if total == 0:
        log("  Nenhum envio hoje.")
        return

    lines = [f"📋 Auto Envio ao Tráfego — {now.strftime('%d/%m')} (consolidado)"]
    lines.append("")
    lines.append(f"✅ {len(created_today)} tarefa(s) enviadas para GT hoje")
    if skipped_today:
        lines.append(f"⏭️ {skipped_today} já existiam (ignoradas)")
    lines.append("")

    if created_today:
        lines.append("Enviadas:")
        for info in created_today[:10]:
            name = info.get("name", "?")[:55]
            lines.append(f"  • {name}")
        if len(created_today) > 10:
            lines.append(f"  ... e mais {len(created_today) - 10}")
        lines.append("")

    lines.append("— GPDR Auto Envio")

    text = "\n".join(lines)
    if post_chat_view(text):
        log("  Resumo postado no Chat da lista")


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    os.makedirs(LOG_DIR, exist_ok=True)

    if "--chat" in sys.argv:
        log("=== CHAT SUMMARY ===")
        run_chat_summary()
        sys.exit(0)

    if "--preview" in sys.argv:
        log("=== MODO PREVIEW ===")
        run(dry_run=True)
        sys.exit(0)

    # Modos que modificam dados — precisam de lock
    if not acquire_lock():
        log("⏭️  Outra instância já está rodando. Saindo.")
        sys.exit(0)

    try:
        if "--execute" in sys.argv:
            log("=== MODO EXECUÇÃO ===")
            run(dry_run=False)
        elif "--monitor" in sys.argv:
            log("=== MODO MONITOR (crontab) ===")
            run(dry_run=False)
        else:
            print(__doc__)
    finally:
        release_lock()
