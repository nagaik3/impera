#!/usr/bin/env python3
"""
Gate Finalizado — IMPERA
Validação automática de tarefas ao atingir status "aguardando validação".
Verifica nomenclatura e compliance do Drive antes de liberar para tráfego.
@menciona copywriter (nomenclatura) e editor (Drive) nos problemas.
Aguarda "CORRIGIDO" e revalida antes de liberar.
Resumo diário no Chat da lista Copy/Edição.

Uso:
  python3 gate_finalizado.py          # Executa validação
  python3 gate_finalizado.py --dry    # Mostra sem comentar/enviar
  python3 gate_finalizado.py --poll   # Checa respostas "CORRIGIDO"
  python3 gate_finalizado.py --chat   # Resumo no Chat (16h)

Crontab:
  */30 * * * * cd ~/Scripts && python3 gate_finalizado.py
  15 */2 * * * cd ~/Scripts && python3 gate_finalizado.py --poll
  0 16 * * 1-6 cd ~/Scripts && python3 gate_finalizado.py --chat
"""

import json
import os
import sys
import urllib.request
import urllib.parse
import threading
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from retry_helper import retry_api_call

# === CONFIG ===
API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

LIST_COPY = "901324556390"
CHAT_VIEW_ID = "6-901324556390-8"
BOT_USER_ID = 176404277
STATE_FILE = os.path.expanduser("~/Scripts/data/gate_finalizado_state.json")
MOVES_LOG = os.path.expanduser("~/Scripts/data/gate_finalizado_moves.jsonl")
STATUS_CACHE_FILE = os.path.expanduser("~/Scripts/data/gate_status_ids.json")

DRY = "--dry" in sys.argv

# === PONTUAÇÃO EDITORES ===
CF_PONTUACAO = "fb840b35-65cf-4f31-8456-bcdf5fcde651"
CF_TIPO_EDICAO = None  # <<<< PREENCHER COM ID REAL APÓS CRIAR DROPDOWN
CF_COPYWRITER = "eeb64866-df57-4dbf-8338-5d4fb58837aa"
CF_EDITOR = "6002b1b9-e8c5-49ad-9e3d-3d8c314a1c91"

PONTOS_POR_TIPO = {
    "Imagem": 1, "Variação Imagem": 1,
    "Full UGC": 2, "Variação Hook": 2, "Empilhamento Hook": 2,
    "Troca de Avatar": 3, "Tela Dividida": 3,
    "Edição Otimizações VSL/min": 5, "Edição AD até 90seg": 5,
    "Edição AD até 180seg": 7, "Edição AD até 240seg": 10,
}

# === MAPEAMENTO PESSOAS ===
COPY_NAME_TO_USER = {
    "YAN": 81970243, "REAPER": 18922946, "CRISPIM": 118015162,
    "ANA": 118024166, "ELIAS": 84627549, "CAROL": 118051219,
}
EDITOR_NAME_TO_USER = {
    "IGOR OLIVEIRA": 118039482, "IGOR PAIVA": 200616743,
    "WELL": 118039481, "NICOLAS": 118039483, "MURYLLO": 118039480,
}

# === IMPORTS DOS SCRIPTS IMPERA ===
sys.path.insert(0, os.path.expanduser("~/Scripts"))
from auditoria_nomenclatura import validate_task_name
from compliance_drive import check_compliance
from impera_utils import classify_task

_drive_service = None


def get_drive_svc():
    global _drive_service
    if _drive_service is not None:
        return _drive_service
    try:
        from compliance_drive import get_drive_service
        _drive_service = get_drive_service()
        return _drive_service
    except Exception as e:
        print(f"[WARN] Drive service indisponível: {e}")
        return None


# === API ===

def api_get(endpoint):
    url = f"https://api.clickup.com/api/v2{endpoint}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", API_TOKEN)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def api_post(endpoint, payload):
    url = f"https://api.clickup.com/api/v2{endpoint}"
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, method="POST")
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


def fetch_status_ids():
    """Fetch and cache status IDs from ClickUp."""
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
        print(f"Erro ao buscar status IDs: {e}")
        # Try to load from cache
        try:
            with open(STATUS_CACHE_FILE) as f:
                return json.load(f)
        except:
            return {}

def get_status_id(status_name):
    """Get status ID by name, using cache or fetching fresh."""
    try:
        with open(STATUS_CACHE_FILE) as f:
            cache = json.load(f)
    except:
        cache = fetch_status_ids()

    status_key = status_name.lower()
    if status_key in cache:
        return cache[status_key]

    # Cache miss, fetch fresh
    cache = fetch_status_ids()
    return cache.get(status_key)

def fetch_finalizado():
    tasks = []
    page = 0
    status_encoded = urllib.parse.quote("aguardando validação")
    while True:
        data = api_get(
            f"/list/{LIST_COPY}/task"
            f"?statuses%5B%5D={status_encoded}&subtasks=false&include_closed=false&page={page}"
        )
        tasks.extend(data.get("tasks", []))
        if data.get("last_page", True):
            break
        page += 1
    return tasks


def get_task_comments(task_id):
    try:
        data = api_get(f"/task/{task_id}/comment")
        return data.get("comments", [])
    except Exception:
        return []


def post_comment(task_id, text, assignee_id=None, notify_all=False):
    if DRY:
        print(f"  [DRY] Comentário em {task_id}: {text[:80]}...")
        return
    payload = {"comment_text": text, "notify_all": notify_all}
    if assignee_id:
        payload["assignee"] = assignee_id
    try:
        api_post(f"/task/{task_id}/comment", payload)
    except Exception as e:
        print(f"  [ERRO] Falha ao comentar em {task_id}: {e}")


def post_chat_view(text):
    if DRY:
        print(f"[DRY] Chat: {text[:100]}...")
        return
    url = f"https://api.clickup.com/api/v2/view/{CHAT_VIEW_ID}/comment"
    payload = json.dumps({"comment_text": text}).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Authorization", API_TOKEN)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return True
    except Exception as e:
        print(f"  [ERRO] Chat View: {e}")
        return False


def send_telegram(msg):
    if DRY:
        print(f"[DRY] Telegram: {msg}")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    body = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID, "text": msg,
        "parse_mode": "HTML", "disable_web_page_preview": True
    }).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        urllib.request.urlopen(req, timeout=15)
    except Exception as e:
        print(f"[ERRO] Telegram: {e}")


# === PERSON LOOKUP ===

def get_copywriter_from_task(task):
    for cf in task.get("custom_fields", []):
        if cf.get("id") == CF_COPYWRITER and cf.get("value") is not None:
            opts = cf.get("type_config", {}).get("options", [])
            for o in opts:
                if o.get("orderindex") == cf["value"]:
                    name = o.get("name", "").upper()
                    return name, COPY_NAME_TO_USER.get(name)
    return None, None


def get_editor_from_task(task):
    for cf in task.get("custom_fields", []):
        if cf.get("id") == CF_EDITOR and cf.get("value") is not None:
            opts = cf.get("type_config", {}).get("options", [])
            for o in opts:
                if o.get("orderindex") == cf["value"]:
                    name = o.get("name", "").upper()
                    return name, EDITOR_NAME_TO_USER.get(name)
    return None, None


# === STATE ===

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def clean_old_entries(state):
    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    to_remove = [tid for tid, info in state.items()
                 if isinstance(info, dict) and info.get("date", "") < cutoff]
    for tid in to_remove:
        del state[tid]
    return state


# === VALIDAÇÃO ===

def validate_nomenclature(task_name):
    if not task_name.strip().startswith("["):
        return ["Nome não começa com '[' — padrão esperado: [NICHO][OFERTA]..."]
    return validate_task_name(task_name)


def validate_drive(task):
    svc = get_drive_svc()
    if svc is None:
        return True, "Drive indisponível (auth) — validação ignorada"
    try:
        result = check_compliance(task, svc)
    except Exception as e:
        return False, f"Erro ao verificar Drive: {e}"
    if result is None:
        return True, None
    status = result.get("status", "")
    detail = result.get("detail", "")
    if status in ("OK", "ALT_STRUCTURE"):
        return True, None
    elif status == "VAZIO":
        if "sem subpastas" in detail.lower():
            return True, None
        return True, None
    elif status in ("DIVERGENTE", "ERRO"):
        return False, f"{status}: {detail}"
    return False, f"{status}: {detail}"


# === PONTUAÇÃO ===

def set_pontuacao(task_id, valor):
    if DRY:
        print(f"  [DRY] Pontuação de {task_id} = {valor}")
        return
    url = f"https://api.clickup.com/api/v2/task/{task_id}/field/{CF_PONTUACAO}"
    body = json.dumps({"value": valor}).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", API_TOKEN)
    req.add_header("Content-Type", "application/json")
    try:
        urllib.request.urlopen(req, timeout=15)
    except Exception as e:
        print(f"  [ERRO] Falha ao setar pontuação em {task_id}: {e}")


def calcular_pontuacao(task):
    if not CF_TIPO_EDICAO:
        return None, "Campo 'Tipo de Edição' não configurado (CF_TIPO_EDICAO = None)"

    tipo_nome = get_tipo_edicao(task)
    if tipo_nome is None:
        return None, "Campo 'Tipo de Edição' não preenchido"

    tipo_pts = PONTOS_POR_TIPO.get(tipo_nome, 0)
    if tipo_pts == 0:
        return None, f"Tipo de edição '{tipo_nome}' sem pontuação configurada"

    name = task["name"].strip()
    _cat, qtd, _nicho, _mercado, _rp = classify_task(name)
    pontos = tipo_pts * qtd
    return pontos, f"{tipo_nome} ({tipo_pts}pts) x {qtd} criativos = {pontos}pts"


# === RUN: VALIDAÇÃO ===

# === AUTO-MOVE FUNCTIONS ===

def load_status_cache():
    """Carrega cache de status IDs do ClickUp."""
    if not os.path.exists(STATUS_CACHE_FILE):
        return {}
    try:
        with open(STATUS_CACHE_FILE) as f:
            return json.load(f)
    except:
        return {}

def save_status_cache(cache):
    """Salva cache de status IDs."""
    os.makedirs(os.path.dirname(STATUS_CACHE_FILE), exist_ok=True)
    with open(STATUS_CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)

@retry_api_call(max_retries=3)
def fetch_status_ids():
    """
    Busca todos os status IDs da COPY list.
    Cacheia por 24h para não sobrecarregar ClickUp API.
    """
    cache = load_status_cache()

    # Usar cache se recente
    if cache.get("_timestamp"):
        try:
            age = (datetime.now() - datetime.fromisoformat(cache["_timestamp"])).total_seconds()
            if age < 86400:  # 24 horas
                return cache
        except:
            pass

    print("  🔄 Buscando status IDs do ClickUp...")
    try:
        list_data = api_get(f"/list/{LIST_COPY}")
        statuses = list_data.get("statuses", [])
        for status in statuses:
            status_name = status.get("status", "").lower()
            status_id = status.get("id", "")
            if status_id:
                cache[status_name] = status_id

        cache["_timestamp"] = datetime.now().isoformat()
        if not DRY:
            save_status_cache(cache)
        return cache
    except Exception as e:
        print(f"  ❌ Erro ao buscar status IDs: {e}")
        return cache

def get_tipo_edicao(task):
    """Extrai tipo de edição da tarefa."""
    if not CF_TIPO_EDICAO:
        return None

    for cf in task.get("custom_fields", []):
        if cf.get("id") == CF_TIPO_EDICAO:
            value = cf.get("value", "")
            if isinstance(value, dict):
                return value.get("label", "")
            return value
    return None

def determine_target_status(task):
    """
    Determina status alvo (intermediário) baseado em tipo de edição ou nome da tarefa.
    Tipos especiais (Microlead, Upsell, Downsell, Otmz, VSL) → "aprovado-vturb"
    Criativos regulares → "aprovado-trafego"

    Esses status intermediários (tipo custom) são movidos por aprova_para_trafego.py
    para os status finais (tipo done): "enviado para trafego" / "enviado para vturb"
    """
    TIPOS_VTURB = ["Microlead", "Upsell", "Downsell", "Otmz", "VSL"]
    PADROES_VTURB = ["[MLD", "[ML", "UPSELL", "DOWNSELL", "OTMZ", "[VSL", "VTURB"]

    # Verificar custom field Tipo de Edição
    tipo = get_tipo_edicao(task)
    if tipo and any(t.lower() in tipo.lower() for t in TIPOS_VTURB):
        return "aprovado-vturb"

    # Verificar padrões no nome da tarefa
    task_name = task.get("name", "").upper()
    if any(padrao in task_name for padrao in PADROES_VTURB):
        return "aprovado-vturb"

    return "aprovado-trafego"

# Mapeamento: status intermediário (custom) → status final (done)
TRAMPOLIM = {
    "aprovado-trafego": "enviado para trafego",
    "aprovado-vturb": "enviado para vturb",
}


@retry_api_call(max_retries=3)
def auto_move_task(task_id, target_status_name, reason):
    """
    Auto-move task via trampolim: custom → done.
    ClickUp bloqueia API moves direto para status tipo "done",
    então movemos primeiro para o intermediário (custom) e depois
    para o final (done). O date_done é preenchido automaticamente.
    """
    debug = lambda msg: open("/tmp/gate_webhook_debug.log", "a").write(msg + "\n")
    debug(f"[AUTO_MOVE] task_id={task_id}, target={target_status_name}")

    # Step 1: Mover para status intermediário (custom)
    # Usa "status" (nome) em vez de "status_id" — mais confiável,
    # não depende de cache e é o que funcionou nos testes manuais.
    try:
        debug(f"[AUTO_MOVE] Step 1: movendo para {target_status_name}")
        result = api_put(f"/task/{task_id}", {"status": target_status_name})
        actual = result.get("status", {}).get("status", "?")
        debug(f"[AUTO_MOVE] Step 1 resultado: status={actual}")
        if actual.lower() != target_status_name.lower():
            debug(f"[AUTO_MOVE] Step 1 FALHOU: status não mudou (ainda {actual})")
            print(f"  ❌ Move silencioso: esperava {target_status_name}, obteve {actual}")
            return False
    except Exception as e:
        debug(f"[AUTO_MOVE] Step 1 FALHOU: {e}")
        print(f"  ❌ Erro ao mover para {target_status_name}: {e}")
        return False

    # Step 2: Mover para status final (done) — trampolim
    final_status = TRAMPOLIM.get(target_status_name)
    if final_status:
        try:
            debug(f"[AUTO_MOVE] Step 2: trampolim → {final_status}")
            result = api_put(f"/task/{task_id}", {"status": final_status})
            actual = result.get("status", {}).get("status", "?")
            has_done = result.get("date_done") is not None
            debug(f"[AUTO_MOVE] Step 2 resultado: status={actual}, date_done={'sim' if has_done else 'não'}")
            if actual.lower() != final_status.lower():
                debug(f"[AUTO_MOVE] Step 2 FALHOU: status não mudou (ainda {actual})")
                print(f"  ⚠️ Intermediário OK, mas final falhou: {actual}")
        except Exception as e:
            debug(f"[AUTO_MOVE] Step 2 FALHOU: {e}")
            print(f"  ⚠️ Intermediário OK, mas falha no final: {e}")

    # Log move
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "task_id": task_id,
        "target_status": final_status or target_status_name,
        "reason": reason,
        "success": True,
    }

    os.makedirs(os.path.dirname(MOVES_LOG), exist_ok=True)
    with open(MOVES_LOG, 'a') as f:
        f.write(json.dumps(log_entry) + '\n')

    return True

def run():
    print(f"=== Gate Finalizado — {datetime.now().strftime('%Y-%m-%d %H:%M')} ===")

    tasks = fetch_finalizado()
    print(f"Tarefas com status 'aguardando validação': {len(tasks)}")

    if not tasks:
        print("Nenhuma tarefa para validar.")
        return

    state = load_state()
    state = clean_old_entries(state)

    validated_count = 0
    problem_count = 0
    processed = 0
    blocked_tasks = []

    for task in tasks:
        tid = task["id"]
        if tid not in state:
            process_single_task(task)
            processed += 1
            # Reload state after processing to get updated counts
            state = load_state()
            if tid in state:
                if state[tid].get("validated"):
                    validated_count += 1
                else:
                    problem_count += 1
                    if state[tid].get("copywriter") or state[tid].get("editor"):
                        blocked_tasks.append({
                            "name": task.get("name", ""),
                            "copy": state[tid].get("copywriter"),
                            "editor": state[tid].get("editor")
                        })

    if not DRY:
        save_state(state)

    # Telegram summary (keep as backup for Iago)
    if processed > 0 and not DRY:
        msg = (
            f"🚦 <b>Gate Finalizado</b>: "
            f"{validated_count} tarefa(s) validada(s), "
            f"{problem_count} com problemas"
        )
        send_telegram(msg)
        print(f"\nResumo: {validated_count} OK, {problem_count} com problemas")
    else:
        print("Nenhuma tarefa nova para processar.")


# === RUN: POLL CORRIGIDO ===

def run_poll():
    """Checa se responsáveis responderam 'CORRIGIDO' e revalida."""
    now = datetime.now()
    print(f"[{now.strftime('%Y-%m-%d %H:%M')}] Poll CORRIGIDO — Gate Finalizado")

    state = load_state()
    pending = {tid: info for tid, info in state.items()
               if isinstance(info, dict) and info.get("pending_corrigido")}

    if not pending:
        print("  Nenhuma tarefa pendente de CORRIGIDO.")
        return

    print(f"  {len(pending)} tarefa(s) pendente(s)")

    for tid, info in pending.items():
        alerted_at = info.get("date", "")
        try:
            alerted_ts = int(datetime.fromisoformat(alerted_at).timestamp() * 1000)
        except ValueError:
            continue

        comments = get_task_comments(tid)

        found_corrigido = False
        responder = None
        for c in comments:
            comment_ts = int(c.get("date", 0))
            user_id = c.get("user", {}).get("id")
            if comment_ts > alerted_ts and user_id != BOT_USER_ID:
                text = (c.get("comment_text", "") or "").upper()
                if "CORRIGIDO" in text or "PRONTO" in text or "CORRIGI" in text:
                    found_corrigido = True
                    responder = c.get("user", {}).get("username", "?")
                    break

        if found_corrigido:
            print(f"  ✅ Resposta de {responder} em {tid}")

            # Revalidar
            try:
                task_data = api_get(f"/task/{tid}")
            except Exception:
                continue

            new_nom = validate_nomenclature(task_data["name"].strip())
            drive_ok, drive_detail = validate_drive(task_data)
            still_bad = []
            if new_nom:
                still_bad.extend([f"Nomenclatura: {p}" for p in new_nom])
            if not drive_ok:
                still_bad.append(f"Drive: {drive_detail}")

            if not still_bad:
                # Tudo OK — liberar
                pontos, pont_msg = calcular_pontuacao(task_data)
                if pontos is not None:
                    set_pontuacao(tid, pontos)
                pont_line = f"\n📊 Pontuação: {pont_msg}" if pontos else ""
                post_comment(tid, (
                    f"✅ REVALIDAÇÃO OK\n\n"
                    f"Problemas corrigidos por @{responder}.\n"
                    f"Tarefa liberada para envio ao tráfego.{pont_line}\n\n"
                    f"— GPDR Gate Automático"
                ), notify_all=True)
                info["validated"] = True
                info["pending_corrigido"] = False
                info["resolved_date"] = now.isoformat()
                info["resolved_by"] = responder
                print(f"    → Liberada ✅")
            else:
                # Ainda tem problemas
                copy_name = info.get("copywriter")
                copy_id = info.get("copywriter_id")
                editor_name = info.get("editor")
                editor_id = info.get("editor_id")
                lines = ["⚠️ REVALIDAÇÃO — Ainda com problemas:\n"]
                for p in still_bad:
                    lines.append(f"- {p}")
                lines.append("\nCorrijam novamente e respondam \"CORRIGIDO\".\n")
                lines.append("— GPDR Gate Automático")
                primary_id = copy_id or editor_id
                post_comment(tid, "\n".join(lines), assignee_id=primary_id)
                info["date"] = now.isoformat()  # Reset timer
                info["problems"] = still_bad
                print(f"    → Ainda com {len(still_bad)} problema(s)")

    if not DRY:
        save_state(state)


# === RUN: CHAT SUMMARY ===

def run_chat_summary():
    """Resumo diário no Chat da lista Copy/Edição."""
    now = datetime.now()
    print(f"[{now.strftime('%Y-%m-%d %H:%M')}] Chat Summary — Gate Finalizado")

    state = load_state()

    # Contadores do dia
    today = now.strftime("%Y-%m-%d")
    validated_today = []
    blocked_today = []
    resolved_today = []

    for tid, info in state.items():
        if not isinstance(info, dict):
            continue
        date_str = info.get("date", "")
        if not date_str.startswith(today):
            # Check resolved_date too
            if info.get("resolved_date", "").startswith(today):
                resolved_today.append(info)
            continue
        if info.get("validated"):
            validated_today.append(info)
        elif info.get("pending_corrigido"):
            blocked_today.append(info)

    total = len(validated_today) + len(blocked_today) + len(resolved_today)
    if total == 0:
        print("  Nada para reportar hoje.")
        return

    lines = [f"🚦 Gate Finalizado — {now.strftime('%d/%m')} (consolidado)"]
    lines.append("")
    lines.append(f"Processadas hoje: {len(validated_today) + len(blocked_today) + len(resolved_today)} tarefas")
    lines.append(f"  ✅ {len(validated_today) + len(resolved_today)} validadas/liberadas")
    if blocked_today:
        lines.append(f"  ⚠️ {len(blocked_today)} bloqueadas (aguardando correção)")
    lines.append("")

    if blocked_today:
        lines.append("Bloqueadas:")
        for info in blocked_today[:10]:
            name = info.get("name", "?") if "name" in info else "?"
            copy = info.get("copywriter", "")
            editor = info.get("editor", "")
            probs = info.get("problems", [])
            prob_type = "nomenclatura" if info.get("needs_nom") else "Drive"
            mentions = []
            if copy:
                mentions.append(f"@{copy}")
            if editor:
                mentions.append(f"@{editor}")
            mention_str = " + ".join(mentions) if mentions else "?"
            lines.append(f"  • {prob_type} → {mention_str}")
        lines.append("")

    if resolved_today:
        lines.append(f"Corrigidas hoje:")
        for info in resolved_today[:5]:
            by = info.get("resolved_by", "?")
            lines.append(f"  • Corrigido por @{by}")
        lines.append("")

    lines.append("— GPDR Gate Automático")

    text = "\n".join(lines)
    post_chat_view(text)
    print("  Resumo postado no Chat da lista")


# === WEBHOOK SERVER ===

GATE_WEBHOOK_PORT = int(os.environ.get("GATE_WEBHOOK_PORT", "5004"))
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "5"))
BATCH_TIMEOUT = 5  # segundos para acumular tarefas antes de processar
WEBHOOK_LOG = os.path.expanduser("~/Scripts/logs/gate_webhook.log")
LOGGING_MODE = os.environ.get("LOGGING_MODE", "resumido")  # resumido ou detalhado

# Batch processing
_batch_tasks = []
_batch_timer = None


class GateWebhookHandler(BaseHTTPRequestHandler):
    """Recebe eventos do ClickUp quando status muda para 'aguardando validação'."""

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len)

        try:
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        log_msg = f"[WEBHOOK] Recebido: event={payload.get('event')}, task_id={payload.get('task_id')}"
        print(log_msg, flush=True)
        with open("/tmp/gate_webhook_debug.log", "a") as f:
            f.write(log_msg + "\n")

        # ClickUp webhook verification (retorna challenge)
        if "challenge" in payload:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"challenge": payload["challenge"]}).encode())
            print(f"[WEBHOOK] Challenge respondido: {payload['challenge']}")
            return

        # Filtrar: só processar taskStatusUpdated
        event = payload.get("event", "")
        print(f"[WEBHOOK] Event: {event}")
        if event != "taskStatusUpdated":
            self.send_response(200)
            self.end_headers()
            return

        # Extrair task_id e novo status
        task_id = payload.get("task_id", "")
        history = payload.get("history_items", [])
        new_status = ""
        for h in history:
            if h.get("field") == "status":
                new_status = h.get("after", {}).get("status", "").lower()
                break

        # Só processar "aguardando validação". Ignorar moves do próprio trampolim.
        IGNORE_STATUSES = {"aprovado-trafego", "aprovado-vturb", "enviado para trafego", "enviado para vturb"}
        if new_status in IGNORE_STATUSES or new_status != "aguardando validação" or not task_id:
            self.send_response(200)
            self.end_headers()
            return

        log_webhook(f"📝 Recebido: {task_id}")

        # Batch Processing: acumula tarefa
        try:
            task_data = api_get(f"/task/{task_id}")
            _batch_tasks.append(task_data)
            log_webhook(f"📦 Acumulado: {len(_batch_tasks)}/{BATCH_SIZE} tarefas")

            # Se atingiu batch size, processa imediatamente
            if len(_batch_tasks) >= BATCH_SIZE:
                process_batch()
            else:
                # Caso contrário, agenda timeout
                schedule_batch()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "queued", "batch_size": len(_batch_tasks)}).encode())
        except Exception as e:
            log_webhook(f"❌ Erro em {task_id}: {str(e)}", level="ERROR")
            self.send_response(500)
            self.end_headers()

    def log_message(self, format, *args):
        pass


def process_single_task(task):
    """Valida uma única tarefa (usado tanto pelo polling quanto pelo webhook)."""
    msg = f"[PROCESS] Iniciando validação de {task.get('id')}"
    print(msg, flush=True)
    with open("/tmp/gate_webhook_debug.log", "a") as f:
        f.write(msg + "\n")
    tid = task["id"]
    name = task["name"].strip()
    state = load_state()

    if tid in state:
        print(f"  ⏭️  {name} — já processada")
        return

    problems = []

    # Validação 1: Nomenclatura
    nom_problems = validate_nomenclature(name)
    if nom_problems:
        problems.append(("Nomenclatura", nom_problems))

    # Validação 2: Drive
    drive_ok, drive_detail = validate_drive(task)
    if not drive_ok:
        problems.append(("Drive", [drive_detail]))

    # Validação 3: Pontuação
    pontos, pont_msg = calcular_pontuacao(task)
    if pontos is not None:
        set_pontuacao(tid, pontos)
        print(f"  📊 Pontuação: {pont_msg}")
    elif CF_TIPO_EDICAO and "não preenchido" in pont_msg:
        editor_name, editor_id = get_editor_from_task(task)
        post_comment(tid,
            "⚠️ Campo 'Tipo de Edição' não preenchido. "
            "Preencha para calcular a pontuação do editor.",
            assignee_id=editor_id)

    if not problems:
        # APROVADO
        msg = f"[PROCESS] Validação OK para {tid}"
        print(msg, flush=True)
        with open("/tmp/gate_webhook_debug.log", "a") as f:
            f.write(msg + "\n")

        pont_line = f"\n📊 Pontuação: {pont_msg}" if pontos else ""
        post_comment(tid,
            f"✅ VALIDAÇÃO OK — Nomenclatura e material conferidos. "
            f"Tarefa liberada para envio.{pont_line}",
            notify_all=True)

        # Auto-move para tráfego ou vturb
        target = determine_target_status(task)
        msg = f"[PROCESS] Target status: {target}, chamando auto_move..."
        print(msg, flush=True)
        with open("/tmp/gate_webhook_debug.log", "a") as f:
            f.write(msg + "\n")

        moved = auto_move_task(tid, target, "Gate validação aprovada")
        msg = f"[PROCESS] auto_move resultado: {moved}"
        print(msg, flush=True)
        with open("/tmp/gate_webhook_debug.log", "a") as f:
            f.write(msg + "\n")

        if moved:
            print(f"  ✅ {name} → {target}")
        else:
            print(f"  ✅ {name} (validada, move manual necessário)")

        state[tid] = {
            "validated": True,
            "date": datetime.now().isoformat(),
            "problems": [],
            "pontos": pontos,
            "auto_moved": moved,
            "target_status": target,
        }
    else:
        # REPROVADO
        copy_name, copy_id = get_copywriter_from_task(task)
        editor_name, editor_id = get_editor_from_task(task)

        lines = ["⚠️ VALIDAÇÃO — Problemas encontrados:\n"]
        mention_ids = []

        for category, items in problems:
            responsible = ""
            resp_id = None
            if category == "Nomenclatura" and copy_name:
                responsible = f" → @{copy_name}"
                resp_id = copy_id
            elif category == "Drive" and editor_name:
                responsible = f" → @{editor_name}"
                resp_id = editor_id

            for item in items:
                lines.append(f"- {category}: {item}{responsible}")

            if resp_id and resp_id not in mention_ids:
                mention_ids.append(resp_id)

        lines.append("\n👉 Corrijam e respondam \"CORRIGIDO\" neste comentário.")
        lines.append("A tarefa só será liberada após revalidação.\n")
        lines.append("— GPDR Gate Automático")

        primary_id = mention_ids[0] if mention_ids else None
        post_comment(tid, "\n".join(lines), assignee_id=primary_id)

        flat_problems = [f"{cat}: {item}" for cat, items in problems for item in items]

        state[tid] = {
            "validated": False,
            "date": datetime.now().isoformat(),
            "problems": flat_problems,
            "pending_corrigido": True,
            "copywriter": copy_name,
            "copywriter_id": copy_id,
            "editor": editor_name,
            "editor_id": editor_id,
            "needs_nom": bool(nom_problems),
            "needs_drive": not drive_ok,
        }
        print(f"  ⚠️ {name} — {len(flat_problems)} problema(s)")

    save_state(state)


def log_webhook(msg, level="INFO"):
    """Log com modo resumido ou detalhado."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    if LOGGING_MODE == "detalhado":
        # Logging detalhado (full stack trace)
        log_line = f"[{timestamp}] [{level}] {msg}"
    else:
        # Logging resumido (apenas essencial)
        log_line = f"[{timestamp}] {msg}"

    print(log_line, flush=True)
    os.makedirs(os.path.dirname(WEBHOOK_LOG), exist_ok=True)
    with open(WEBHOOK_LOG, "a") as f:
        f.write(log_line + "\n")


def process_batch():
    """Processa todas as tarefas acumuladas (batch processing)."""
    global _batch_tasks, _batch_timer

    if not _batch_tasks:
        return

    batch_to_process = _batch_tasks.copy()
    _batch_tasks = []
    _batch_timer = None

    log_webhook(f"🔄 Batch iniciado: {len(batch_to_process)} tarefas")

    success_count = 0
    error_count = 0

    for task in batch_to_process:
        try:
            process_single_task(task)
            success_count += 1
        except Exception as e:
            error_count += 1
            log_webhook(f"❌ Erro em {task.get('id')}: {str(e)}", level="ERROR")

    log_webhook(f"✅ Batch concluído: {success_count} OK | {error_count} erros")


def schedule_batch():
    """Agenda o processamento do batch com timeout."""
    global _batch_timer

    if _batch_timer:
        _batch_timer.cancel()

    _batch_timer = threading.Timer(BATCH_TIMEOUT, process_batch)
    _batch_timer.daemon = True
    _batch_timer.start()


def start_gate_server():
    print(f"🚀 Gate Finalizado webhook server na porta {GATE_WEBHOOK_PORT}")
    print(f"   Endpoint: POST http://0.0.0.0:{GATE_WEBHOOK_PORT}/")
    print(f"   Batch Size: {BATCH_SIZE} tarefas")
    print(f"   Logging: {LOGGING_MODE}")
    print(f"   Escutando eventos: taskStatusUpdated → aguardando validação")
    server = HTTPServer(("0.0.0.0", GATE_WEBHOOK_PORT), GateWebhookHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹️  Gate webhook server interrompido")
        if _batch_timer:
            _batch_timer.cancel()
        server.shutdown()


# === MAIN ===

if __name__ == "__main__":
    if "--server" in sys.argv:
        start_gate_server()
    elif "--chat" in sys.argv:
        run_chat_summary()
    elif "--poll" in sys.argv:
        run_poll()
    else:
        run()
