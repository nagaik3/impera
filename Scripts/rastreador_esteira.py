#!/usr/bin/env python3
"""
Rastreador de Esteira IMPERA v2.0
- Webhook: status changes em tempo real (porta 5001, taskStatusUpdated events)
- Polling: rastreia mudanças de status das tarefas ClickUp (crontab */120 agora, era */30)
- Alerta: envia alertas de SLA via Telegram (crontab 11h e 16h)
- Bot: responde comandos no Telegram em tempo real
- Activity: posta comentário no ClickUp quando tarefa conclui uma fase

Uso:
  python3 rastreador_esteira.py poll          # Atualiza tracking de status
  python3 rastreador_esteira.py alert         # Envia alertas Telegram
  python3 rastreador_esteira.py status        # Visão geral no terminal
  python3 rastreador_esteira.py atrasos       # Principais atrasos
  python3 rastreador_esteira.py copy          # Setor: Escrevendo - Copy
  python3 rastreador_esteira.py preprod       # Setor: Pré-Produção
  python3 rastreador_esteira.py producao      # Setor: Produção
  python3 rastreador_esteira.py alteracao     # Setor: Produção de Alteração
  python3 rastreador_esteira.py avaliacao     # Setor: Avaliação
  python3 rastreador_esteira.py freelancer    # Setor: Freelancer
  python3 rastreador_esteira.py bot           # Bot Telegram interativo
  python3 rastreador_esteira.py chatid        # Descobrir chat_id do Telegram
  python3 rastreador_esteira.py --server      # Inicia webhook receiver (porta 5001)
"""

import os
import sys
import json
import re
import requests
import time as _time
from datetime import datetime, timedelta
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

sys.path.insert(0, os.path.expanduser("~/Scripts"))
from impera_utils import get_cf_value, extract_ld_mld_range, normalize_person_name
from retry_helper import retry_api_call
from rastreador_resilience import (
    record_heartbeat, check_heartbeat, queue_dead_letter,
    process_dead_letter_queue, record_circuit_breaker_failure,
    record_circuit_breaker_success, is_circuit_breaker_tripped,
    health_check_http
)
from rastreador_notificacao_strategy import (
    is_critical_issue, build_consolidated_alert, should_consolidate_now,
    log_notification, analyze_by_sector
)

# === DATA LAKE: persistir transicoes no PostgreSQL ===
try:
    from database.impera_db import inserir_transicao_esteira
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

# === CONFIG ===
CLICKUP_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

COPY_LIST = "901324556390"
# Lista unificada — EDIÇÃO agora na COPY

# ClickUp Chat para alertas (v2.0 — centralizando notificações)
# Canal: https://app.clickup.com/9013620875/chat/r/8cm1w4b-9853
CHAT_VIEW_ID = "8cm1w4b-9853"

TRACKING_FILE = os.path.expanduser("~/Scripts/data/esteira_tracking.json")
LOG_FILE = os.path.expanduser("~/Scripts/data/esteira_log.jsonl")
OFFSET_FILE = os.path.expanduser("~/Scripts/data/esteira_bot_offset.txt")

# Webhook configuration (v2.0)
# Note: Port 5001 is used by rastreador_health_server, using 5002 instead
ESTEIRA_WEBHOOK_PORT = int(os.environ.get("ESTEIRA_WEBHOOK_PORT", "5002"))

HEADERS = {"Authorization": CLICKUP_TOKEN, "Content-Type": "application/json"}

# === SETORES ===
SETORES = [
    "Escrevendo - Copy",
    "Pré-Produção",
    "Produção",
    "Alteração",
    "Avaliação - Pós Edição",
    "Avaliação - Pós Alteração",
    "Freelancer",
]

SETOR_CMD_MAP = {
    "copy": ["Escrevendo - Copy"],
    "preprod": ["Pré-Produção"],
    "producao": ["Produção"],
    "alteracao": ["Alteração"],
    "avaliacao": ["Avaliação - Pós Edição", "Avaliação - Pós Alteração"],
    "freelancer": ["Freelancer"],
}

# === SLA POR STATUS (em horas) ===
# Tipos: "criativo", "lead", "vsl"
# Para fases agrupadas (Escrevendo-Copy), agrupa lista de statuses cujo SLA
# conta desde o primeiro até sair do último.

FASES_SLA = {
    # --- ESCREVENDO - COPY (agrupado: escrevendo → encaminhado para edição) ---
    "escrevendo": {
        "setor": "Escrevendo - Copy",
        "sla": {"criativo": 24, "lead": 48, "vsl": 168},
        "agrupa": [
            "escrevendo",
            "aguardando review head",
            "alteração copy",
            "avaliação - alteração copy",
            "encaminhado para edição",
        ],
    },
    "aguardando review head": {
        "setor": "Escrevendo - Copy",
        "sla": {"criativo": 24, "lead": 48, "vsl": 168},
        "fase_pai": "escrevendo",
    },
    "alteração copy": {
        "setor": "Escrevendo - Copy",
        "sla": {"criativo": 24, "lead": 48, "vsl": 168},
        "fase_pai": "escrevendo",
    },
    "avaliação - alteração copy": {
        "setor": "Escrevendo - Copy",
        "sla": {"criativo": 24, "lead": 48, "vsl": 168},
        "fase_pai": "escrevendo",
    },
    "encaminhado para edição": {
        "setor": "Escrevendo - Copy",
        "sla": {"criativo": 24, "lead": 48, "vsl": 168},
        "fase_pai": "escrevendo",
    },
    # --- PRÉ-PRODUÇÃO (apenas pré produção) ---
    "pré produção": {
        "setor": "Pré-Produção",
        "sla": {"criativo": 24, "lead": 48, "vsl": 72},
    },
    # --- PRODUÇÃO (apenas em edição) ---
    "em edição": {
        "setor": "Produção",
        "sla": {"criativo": 24, "lead": 48, "vsl": 216},
    },
    # --- ALTERAÇÃO (apenas em alteração) ---
    "em alteração": {
        "setor": "Alteração",
        "sla": {"criativo": 24, "lead": 24, "vsl": 48},
    },
    # --- AVALIAÇÃO - PÓS EDIÇÃO ---
    "avaliação - pós edição": {
        "setor": "Avaliação - Pós Edição",
        "sla": {"criativo": 24, "lead": 24, "vsl": 24},
    },
    # --- AVALIAÇÃO - PÓS ALTERAÇÃO ---
    "avaliação - pós alteração": {
        "setor": "Avaliação - Pós Alteração",
        "sla": {"criativo": 24, "lead": 24, "vsl": 24},
    },
    # --- FREELANCER ---
    "freelancer - editando": {
        "setor": "Freelancer",
        "sla": {"criativo": 24, "lead": 48, "vsl": 216},
        "sub": "Editando",
    },
    "freelancer - em revisão": {
        "setor": "Freelancer",
        "sla": {"criativo": 24, "lead": 24, "vsl": 24},
        "sub": "Em Revisão",
    },
    "freelancer - alterando": {
        "setor": "Freelancer",
        "sla": {"criativo": 24, "lead": 24, "vsl": 48},
        "sub": "Alterando",
    },
}

# Status que não contam SLA (filas, terminais)
STATUS_IGNORADOS = {
    "backlog copy",
    "backlog edição",
    "pre produção finalizada",
    "enviado para trafego",
    "aguardando validação",
    "aprovado-trafego",
    "aprovado-vturb",
    "arquivo morto",
    "enviado para vturb",
}

# Status que, ao serem atingidos, encerram a fase anterior e geram activity
PHASE_EXIT_TRIGGERS = {
    # Quando entra em backlog edição (lista EDIÇÃO), encerrou "Escrevendo - Copy"
    "backlog edição": "Escrevendo - Copy",
    # Quando entra em pre produção finalizada ou em edição, encerrou "Pré-Produção"
    "pre produção finalizada": "Pré-Produção",
    "em edição": "Pré-Produção",
    # Quando sai de em edição para qualquer outro, encerrou "Produção"
    # (tratado por lógica de saída, não de entrada)
    # Quando entra em avaliação - pós edição, encerrou "Produção"
    "avaliação - pós edição": "Produção",
    # Quando entra em em alteração, encerrou "Avaliação - Pós Edição"
    # (pode não ser sempre, mas é o fluxo principal)
    "em alteração": "Avaliação - Pós Edição",
    # Quando entra em avaliação - pós alteração, encerrou "Alteração"
    "avaliação - pós alteração": "Alteração",
    # Quando entra em enviado para trafego/aguardando validação, encerrou a avaliação
    "enviado para trafego": "Avaliação",
    "aguardando validação": "Avaliação",
}


# === UTILS ===

def classify_task_type(name):
    """Classifica tarefa: vsl, lead, criativo."""
    upper = name.upper()
    if "VSL" in upper:
        return "vsl"
    ld_type, _, _ = extract_ld_mld_range(name)
    if ld_type:
        return "lead"
    return "criativo"


def is_creative_task(name):
    return bool(re.match(r"\s*\[", name))


NOME_MAP = {
    "reaper": "CÁSSIO",
    "yan da silva rangel": "YAN",
    "ana ramos": "ANA",
    "igor oliveira": "IGOR OLIVEIRA",
    "igor paiva": "IGOR PAIVA",
}


def normalize_name(name):
    if not name or name == "N/A":
        return "N/A"
    lower = name.strip().lower()
    if lower in NOME_MAP:
        return NOME_MAP[lower]
    if name.isupper():
        return name
    return name.split()[0].upper() if name else "N/A"


def get_responsible(task):
    list_id = task.get("list", {}).get("id", "")
    resp = None
    if list_id == COPY_LIST:
        resp = get_cf_value(task, "copywriter") or get_cf_value(task, "editor")
    if not resp:
        assignees = task.get("assignees", [])
        if assignees:
            resp = assignees[0].get("username", assignees[0].get("email", "N/A"))
    return normalize_name(resp or "N/A")


def format_time(hours):
    if abs(hours) < 1:
        m = int(abs(hours) * 60)
        return f"{m}min"
    if abs(hours) < 24:
        return f"{hours:.0f}h"
    days = hours / 24
    return f"{days:.1f}d"


def format_delay(delay_hours):
    if delay_hours <= 0:
        return None
    return format_time(delay_hours)


def format_remaining(hours, sla_hours):
    remaining = sla_hours - hours
    if remaining <= 0:
        return None
    return format_time(remaining)


# === API ===

@retry_api_call(max_retries=3)
def fetch_all_tasks(list_id):
    tasks = []
    page = 0
    while True:
        url = f"https://api.clickup.com/api/v2/list/{list_id}/task"
        params = {"page": page, "limit": 100, "include_closed": "false", "subtasks": "true"}
        resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
        if resp.status_code != 200:
            print(f"Erro API list {list_id} page {page}: {resp.status_code}")
            break
        data = resp.json()
        batch = data.get("tasks", [])
        tasks.extend(batch)
        if not batch or data.get("last_page", True):
            break
        page += 1
    return tasks


@retry_api_call(max_retries=3)
def post_clickup_comment(task_id, comment_text):
    """Posta comentário no activity da tarefa no ClickUp."""
    url = f"https://api.clickup.com/api/v2/task/{task_id}/comment"
    payload = {"comment_text": comment_text}
    try:
        resp = requests.post(url, headers=HEADERS, json=payload, timeout=30)
        if resp.status_code == 200:
            print(f"  💬 Comentário postado em {task_id}")
        else:
            print(f"  ❌ Erro comentário {task_id}: {resp.status_code}")
    except Exception as e:
        print(f"  ❌ Erro comentário {task_id}: {e}")


# === TRACKING ===

def load_tracking():
    if os.path.exists(TRACKING_FILE):
        with open(TRACKING_FILE, "r") as f:
            return json.load(f)
    return {}


def save_tracking(data):
    os.makedirs(os.path.dirname(TRACKING_FILE), exist_ok=True)
    with open(TRACKING_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def log_transition(task_id, task_name, old_status, new_status, timestamp):
    # Legado: manter JSONL para compatibilidade (sera removido em v2)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    entry = {
        "timestamp": timestamp,
        "task_id": task_id,
        "task_name": task_name,
        "from": old_status,
        "to": new_status,
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def get_phase_start(task_id, current_status, tracking):
    """Para fases agrupadas, retorna quando entrou no primeiro status do grupo."""
    task_data = tracking.get(task_id, {})
    history = task_data.get("history", [])

    fase_config = FASES_SLA.get(current_status)
    if not fase_config:
        return task_data.get("status_entered_at")

    pai = fase_config.get("fase_pai", current_status)
    pai_config = FASES_SLA.get(pai, {})
    group_statuses = pai_config.get("agrupa", [current_status])

    earliest = task_data.get("status_entered_at")
    for entry in reversed(history):
        if entry["status"] in group_statuses:
            earliest = entry["entered"]
        else:
            break
    return earliest


def format_dt(iso_str):
    """Formata ISO string para dd/mm HH:MM."""
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%d/%m %H:%M")
    except (ValueError, TypeError):
        return "?"


# Mapa de nomes de destino para exibição
DESTINO_LABELS = {
    "backlog edição": "Backlog Edição",
    "pre produção finalizada": "Pré-Produção Finalizada",
    "em edição": "Em Edição",
    "avaliação - pós edição": "Avaliação - Pós Edição",
    "em alteração": "Em Alteração",
    "avaliação - pós alteração": "Avaliação - Pós Alteração",
    "enviado para trafego": "Enviado para Tráfego",
    "aguardando validação": "Aguardando Validação",
    "aprovado-trafego": "Aprovado - Tráfego",
    "aprovado-vturb": "Aprovado - Vturb",
    "enviado para vturb": "Enviado para Vturb",
}


def build_activity_comment(setor, responsible, hours_spent, sla_hours, task_type, entry_time, exit_time, destino):
    """Constrói mensagem de activity para o ClickUp."""
    type_tag = f" [{task_type.upper()}]"

    destino_label = DESTINO_LABELS.get(destino, destino.title())

    if hours_spent <= sla_hours:
        status_icon = "✅"
        status_text = "DENTRO DO PRAZO"
        detail = f"Duração: {format_time(hours_spent)} (SLA: {format_time(sla_hours)})"
    else:
        status_icon = "🔴"
        status_text = "ATRASO"
        delay = hours_spent - sla_hours
        detail = f"Duração: {format_time(hours_spent)} (SLA: {format_time(sla_hours)}) — atraso de {format_time(delay)}"

    return (
        f"{status_icon} {setor}{type_tag} — {status_text}\n"
        f"Responsável: {responsible}\n"
        f"Entrada: {format_dt(entry_time)} → Saída: {format_dt(exit_time)}\n"
        f"{detail}\n"
        f"Destino: {destino_label}\n"
        f"— Rastreador de Esteira IMPERA"
    )


def build_journey_summary(task_data):
    """Constrói resumo completo da jornada da tarefa na esteira."""
    history = task_data.get("history", [])
    task_type = task_data.get("task_type", "criativo")
    type_tag = f" [{task_type.upper()}]"

    # Mapeia cada entrada do histórico ao seu setor e calcula duração
    phases_seen = []
    first_entry = None
    last_exit = None

    for entry in history:
        status = entry["status"]
        config = FASES_SLA.get(status)
        if not config:
            continue

        setor = config["setor"]
        # Para fases agrupadas, checa se é continuação da mesma fase
        pai = config.get("fase_pai", status)

        entered = entry["entered"]
        exited = entry["exited"]

        if not first_entry:
            first_entry = entered

        last_exit = exited

        try:
            dt_in = datetime.fromisoformat(entered)
            dt_out = datetime.fromisoformat(exited)
            hours = (dt_out - dt_in).total_seconds() / 3600
        except (ValueError, TypeError):
            hours = 0

        sla_hours = config["sla"].get(task_type, config["sla"]["criativo"])

        # Agrupa com a fase anterior se for o mesmo setor (fase agrupada)
        if phases_seen and phases_seen[-1]["setor"] == setor:
            phases_seen[-1]["hours"] += hours
            phases_seen[-1]["exit"] = exited
        else:
            phases_seen.append({
                "setor": setor,
                "hours": hours,
                "sla_hours": sla_hours,
                "entry": entered,
                "exit": exited,
                "responsible": task_data.get("responsible", "N/A"),
            })

    if not phases_seen:
        return None

    # Calcula total
    total_hours = sum(p["hours"] for p in phases_seen)

    lines = [f"📋 RESUMO DA ESTEIRA{type_tag}\n"]
    for p in phases_seen:
        if p["hours"] <= p["sla_hours"]:
            icon = "✅"
            extra = ""
        else:
            icon = "🔴"
            delay = p["hours"] - p["sla_hours"]
            extra = f" — atraso: {format_time(delay)}"
        lines.append(
            f"{icon} {p['setor']}: {format_time(p['hours'])} "
            f"(SLA: {format_time(p['sla_hours'])}){extra}"
        )

    lines.append(f"\nTempo total na esteira: {format_time(total_hours)}")
    if first_entry and last_exit:
        lines.append(f"Início: {format_dt(first_entry)} → Fim: {format_dt(last_exit)}")
    lines.append(f"— Rastreador de Esteira IMPERA")

    return "\n".join(lines)


def check_phase_completion(task_id, old_status, new_status, tracking):
    """Verifica se a transição encerrou uma fase e posta activity no ClickUp."""
    task_data = tracking.get(task_id, {})
    if not task_data:
        return

    old_config = FASES_SLA.get(old_status)
    if not old_config:
        return

    old_setor = old_config["setor"]

    new_config = FASES_SLA.get(new_status)
    new_setor = new_config["setor"] if new_config else None

    # Se ainda na mesma fase, não faz nada
    if new_setor == old_setor:
        return

    # Calcula tempo na fase que acabou de sair
    phase_start = get_phase_start(task_id, old_status, tracking)
    if not phase_start:
        return

    try:
        entered = datetime.fromisoformat(phase_start)
    except (ValueError, TypeError):
        return

    now = datetime.now()
    exit_time = now.isoformat()
    hours_spent = (now - entered).total_seconds() / 3600
    task_type = task_data.get("task_type", "criativo")
    sla_hours = old_config["sla"].get(task_type, old_config["sla"]["criativo"])
    responsible = task_data.get("responsible", "N/A")

    # 0. DATA LAKE: Persistir transicao na fact_slas_esteira
    if DB_AVAILABLE and os.getenv("DATABASE_URL"):
        try:
            inserir_transicao_esteira(
                task_id=task_id,
                setor_fase=old_setor,
                data_entrada=entered,
                data_saida=now,
                sla_horas=sla_hours,
            )
        except Exception as e:
            print(f"  ⚠️ Data Lake SLA: {e}")
            # Dead Letter Queue: persiste para sincronizar depois
            queue_dead_letter({
                "task_id": task_id,
                "setor_fase": old_setor,
                "data_entrada": entered,
                "data_saida": now,
                "sla_horas": sla_hours,
            })

    # 1. Posta comentário da fase concluída
    comment = build_activity_comment(
        old_setor, responsible, hours_spent, sla_hours, task_type,
        phase_start, exit_time, new_status
    )
    post_clickup_comment(task_id, comment)

    # 2. Se a tarefa está saindo para um status terminal, posta resumo da jornada
    TERMINAL_STATUSES = {"enviado para trafego", "enviado para vturb", "arquivo morto"}
    if new_status in TERMINAL_STATUSES:
        # Adiciona a fase que acabou de sair ao histórico temporariamente para o resumo
        temp_history = list(task_data.get("history", []))
        temp_history.append({
            "status": old_status,
            "entered": phase_start,
            "exited": exit_time,
        })
        temp_data = dict(task_data)
        temp_data["history"] = temp_history

        summary = build_journey_summary(temp_data)
        if summary:
            post_clickup_comment(task_id, summary)


# === POLLING ===

def poll():
    """Faz polling das tarefas e atualiza tracking.
    Fora do horário comercial (20h-8h), pula execução para economizar API calls.
    O crontab roda */30 mas só executa de fato entre 8h-20h.
    """
    # Circuit breaker: se muitas falhas consecutivas, aguarda reset
    if is_circuit_breaker_tripped():
        print("⚠️ Circuit breaker TRIPPED — aguardando reset (5 min)...")
        return

    hora_atual = datetime.now().hour
    if hora_atual < 8 or hora_atual >= 20:
        return  # Fora do horário comercial — pula silenciosamente

    now = datetime.now().isoformat()
    tracking = load_tracking()

    try:
        all_tasks = []
        all_tasks.extend(fetch_all_tasks(COPY_LIST))
    except Exception as e:
        print(f"❌ Erro ao buscar tarefas: {e}")
        record_circuit_breaker_failure()
        raise

    changes = 0
    for task in all_tasks:
        tid = task["id"]
        name = task["name"]
        status = task.get("status", {}).get("status", "unknown").lower()
        list_id = task.get("list", {}).get("id", "")
        responsible = get_responsible(task)

        if not is_creative_task(name):
            continue

        if tid in tracking:
            old_status = tracking[tid]["current_status"]
            if old_status != status:
                # Verifica se copywriter está vazio
                copy_field = None
                if old_status == "backlog copy":
                    copy_field = get_cf_value(task, "✍️ Copywritter")

                # Determina se é crítico (usa estratégia)
                is_critical, reason = is_critical_issue(
                    old_status, status,
                    task_data=task,
                    missing_copywriter=(not copy_field if old_status == "backlog copy" else False)
                )

                # Notifica apenas se crítico (evita spam)
                if is_critical:
                    msg = f"🚨 CRÍTICO: {name}\n→ {reason.upper()}"
                    post_clickup_alert(msg)
                    log_notification("critical", tid, msg, posted=True)

                # Verifica se encerrou uma fase (posta activity no ClickUp)
                check_phase_completion(tid, old_status, status, tracking)

                log_transition(tid, name, old_status, status, now)
                history_entry = {
                    "status": old_status,
                    "entered": tracking[tid]["status_entered_at"],
                    "exited": now,
                }
                if "history" not in tracking[tid]:
                    tracking[tid]["history"] = []
                tracking[tid]["history"].append(history_entry)
                tracking[tid]["current_status"] = status
                tracking[tid]["status_entered_at"] = now
                tracking[tid]["responsible"] = responsible
                tracking[tid]["list_id"] = list_id
                changes += 1
            else:
                tracking[tid]["responsible"] = responsible
                tracking[tid]["list_id"] = list_id
        else:
            # Seed inteligente para tarefas novas
            date_created = task.get("date_created")
            date_updated = task.get("date_updated")

            # Para status rastreados, usa date_updated como melhor estimativa
            if status in FASES_SLA and date_updated:
                seed_ts = datetime.fromtimestamp(int(date_updated) / 1000).isoformat()
            elif date_created:
                seed_ts = datetime.fromtimestamp(int(date_created) / 1000).isoformat()
            else:
                seed_ts = now

            tracking[tid] = {
                "name": name,
                "current_status": status,
                "status_entered_at": seed_ts,
                "responsible": responsible,
                "list_id": list_id,
                "task_type": classify_task_type(name),
                "history": [],
                "seeded": True,
            }
            changes += 1

    for tid, data in tracking.items():
        if "task_type" not in data:
            data["task_type"] = classify_task_type(data.get("name", ""))

    save_tracking(tracking)
    print(f"[{now}] Poll concluído. {len(all_tasks)} tarefas, {changes} mudanças.")

    # Sucesso: reset circuit breaker e registra heartbeat
    record_circuit_breaker_success()
    record_heartbeat(status="ok", error=None)

    # Process DLQ se houver (transições pendentes)
    if DB_AVAILABLE:
        try:
            processed = process_dead_letter_queue(inserir_transicao_esteira)
            if processed > 0:
                print(f"  ✅ DLQ: Sincronizadas {processed} transições")
        except Exception as e:
            print(f"  ⚠️ DLQ: Erro ao processar: {e}")


# === ANÁLISE ===

def analyze_tasks(tracking, setor_filter=None):
    """Analisa tarefas. Retorna dict por setor com atrasadas/em_risco/no_prazo."""
    now = datetime.now()
    result = {s: {"atrasadas": [], "em_risco": [], "no_prazo": []} for s in SETORES}

    for tid, data in tracking.items():
        status = data["current_status"]
        if status in STATUS_IGNORADOS:
            continue

        fase_config = FASES_SLA.get(status)
        if not fase_config:
            continue

        setor = fase_config["setor"]
        if setor_filter and setor not in (setor_filter if isinstance(setor_filter, list) else [setor_filter]):
            continue

        phase_start = get_phase_start(tid, status, tracking)
        if not phase_start:
            continue
        try:
            entered = datetime.fromisoformat(phase_start)
        except (ValueError, TypeError):
            continue

        hours_in_phase = (now - entered).total_seconds() / 3600
        task_type = data.get("task_type", "criativo")
        sla_hours = fase_config["sla"].get(task_type, fase_config["sla"]["criativo"])
        delay_hours = hours_in_phase - sla_hours
        pct = (hours_in_phase / sla_hours * 100) if sla_hours > 0 else 0

        # Sub-label para freelancer
        sub = fase_config.get("sub", "")

        info = {
            "task_id": tid,
            "name": data["name"],
            "setor": setor,
            "sub": sub,
            "responsible": data.get("responsible", "N/A"),
            "hours": round(hours_in_phase, 1),
            "sla_hours": sla_hours,
            "delay_hours": round(delay_hours, 1),
            "pct": round(pct),
            "task_type": task_type,
            "status": status,
        }

        if pct >= 100:
            result[setor]["atrasadas"].append(info)
        elif pct >= 80:
            result[setor]["em_risco"].append(info)
        else:
            result[setor]["no_prazo"].append(info)

    for setor in SETORES:
        result[setor]["atrasadas"].sort(key=lambda x: x["delay_hours"], reverse=True)
        result[setor]["em_risco"].sort(key=lambda x: x["pct"], reverse=True)
        result[setor]["no_prazo"].sort(key=lambda x: x["pct"], reverse=True)

    return result


# === FORMATAÇÃO ===

def _task_line(t, show_setor=False):
    type_tag = ""
    if t["task_type"] != "criativo":
        type_tag = f" [{t['task_type'].upper()}]"

    sub_tag = f" ({t['sub']})" if t.get("sub") else ""
    setor_tag = f" | {t['setor']}{sub_tag}" if show_setor else (sub_tag if sub_tag else "")

    if t["delay_hours"] > 0:
        delay = format_delay(t["delay_hours"])
        return (
            f"  {t['name'][:55]}{type_tag}\n"
            f"    → {format_time(t['hours'])} na fase (SLA: {format_time(t['sla_hours'])}) "
            f"| atraso: {delay}{setor_tag}\n"
            f"    → Resp: {t['responsible']}"
        )
    else:
        remaining = format_remaining(t["hours"], t["sla_hours"])
        return (
            f"  {t['name'][:55]}{type_tag}\n"
            f"    → {format_time(t['hours'])} na fase (SLA: {format_time(t['sla_hours'])}) "
            f"| restam: {remaining}{setor_tag}\n"
            f"    → Resp: {t['responsible']}"
        )


def build_setor_block(setor, data, limit=None):
    atrasadas = data["atrasadas"]
    em_risco = data["em_risco"]
    no_prazo = data["no_prazo"]
    total = len(atrasadas) + len(em_risco) + len(no_prazo)

    if total == 0:
        return None

    lines = [f"\n{'='*40}", f"📂 {setor.upper()} ({total} tarefas)"]

    if atrasadas:
        show = atrasadas[:limit] if limit else atrasadas
        lines.append(f"\n🔴 Atrasadas ({len(atrasadas)}):")
        for t in show:
            lines.append(_task_line(t))
        if limit and len(atrasadas) > limit:
            lines.append(f"  ... +{len(atrasadas) - limit} tarefas atrasadas")

    if em_risco:
        show = em_risco[:limit] if limit else em_risco
        lines.append(f"\n🟡 Em risco ({len(em_risco)}):")
        for t in show:
            lines.append(_task_line(t))
        if limit and len(em_risco) > limit:
            lines.append(f"  ... +{len(em_risco) - limit} tarefas em risco")

    if no_prazo:
        show = no_prazo[:limit] if limit else no_prazo
        lines.append(f"\n✅ No prazo ({len(no_prazo)}):")
        for t in show:
            lines.append(_task_line(t))
        if limit and len(no_prazo) > limit:
            lines.append(f"  ... +{len(no_prazo) - limit} tarefas no prazo")

    return "\n".join(lines)


def build_alert_message(analysis):
    """Mensagem de alerta para Telegram (dividida por setor)."""
    now = datetime.now()
    period = "manhã" if now.hour < 14 else "tarde"
    lines = [f"📊 ESTEIRA IMPERA — {now.strftime('%d/%m %H:%M')} ({period})"]

    total_atrasadas = sum(len(d["atrasadas"]) for d in analysis.values())
    total_risco = sum(len(d["em_risco"]) for d in analysis.values())
    total_prazo = sum(len(d["no_prazo"]) for d in analysis.values())

    lines.append(f"🔴 {total_atrasadas} atrasadas | 🟡 {total_risco} em risco | ✅ {total_prazo} no prazo\n")

    if total_atrasadas == 0 and total_risco == 0:
        lines.append("✅ Nenhuma tarefa com SLA estourado ou em risco.")
        return "\n".join(lines)

    for setor in SETORES:
        data = analysis[setor]
        atrasadas = data["atrasadas"]
        em_risco = data["em_risco"]

        if not atrasadas and not em_risco:
            continue

        lines.append(f"━━ {setor.upper()} ━━")

        if atrasadas:
            lines.append(f"🔴 Atrasadas ({len(atrasadas)}):")
            for t in atrasadas[:5]:
                type_tag = f" [{t['task_type'].upper()}]" if t["task_type"] != "criativo" else ""
                sub_tag = f" ({t['sub']})" if t.get("sub") else ""
                delay = format_delay(t["delay_hours"])
                lines.append(
                    f"  {t['name'][:50]}{type_tag}{sub_tag}\n"
                    f"    atraso: {delay} | Resp: {t['responsible']}"
                )
            if len(atrasadas) > 5:
                lines.append(f"  +{len(atrasadas) - 5} mais...")

        if em_risco:
            lines.append(f"🟡 Em risco ({len(em_risco)}):")
            for t in em_risco[:3]:
                type_tag = f" [{t['task_type'].upper()}]" if t["task_type"] != "criativo" else ""
                remaining = format_remaining(t["hours"], t["sla_hours"])
                lines.append(
                    f"  {t['name'][:50]}{type_tag}\n"
                    f"    restam: {remaining} | Resp: {t['responsible']}"
                )
            if len(em_risco) > 3:
                lines.append(f"  +{len(em_risco) - 3} mais...")

        lines.append("")

    return "\n".join(lines)


def build_atrasos_message(analysis):
    now = datetime.now()
    lines = [f"📊 PRINCIPAIS ATRASOS — {now.strftime('%d/%m %H:%M')}\n"]

    any_delay = False
    for setor in SETORES:
        atrasadas = analysis[setor]["atrasadas"]
        if not atrasadas:
            continue
        any_delay = True
        lines.append(f"━━ {setor.upper()} ({len(atrasadas)} atrasadas) ━━")
        for t in atrasadas[:10]:
            type_tag = f" [{t['task_type'].upper()}]" if t["task_type"] != "criativo" else ""
            delay = format_delay(t["delay_hours"])
            lines.append(
                f"  {t['name'][:50]}{type_tag}\n"
                f"    atraso: {delay} | Resp: {t['responsible']}"
            )
        if len(atrasadas) > 10:
            lines.append(f"  +{len(atrasadas) - 10} mais...")
        lines.append("")

    if not any_delay:
        lines.append("✅ Nenhuma tarefa atrasada!")

    return "\n".join(lines)


# === CLICKUP CHAT VIEW (v2.0 — centralizando notificações) ===

def post_clickup_alert(message):
    """Posta alerta no ClickUp Chat View em vez de Telegram."""
    url = f"https://api.clickup.com/api/v2/view/{CHAT_VIEW_ID}/comment"
    payload = {"comment_text": message}
    try:
        resp = requests.post(url, headers=HEADERS, json=payload, timeout=30)
        if resp.status_code == 200:
            print("✅ Alerta postado no ClickUp Chat View.")
            return True
        else:
            print(f"❌ Erro ClickUp {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"❌ Erro ao postar no ClickUp: {e}")
        return False


# === TELEGRAM ===

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️  TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não configurado.")
        print(message)
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    chunks = []
    if len(message) <= 4000:
        chunks = [message]
    else:
        lines = message.split("\n")
        current = ""
        for line in lines:
            if len(current) + len(line) + 1 > 4000:
                chunks.append(current)
                current = line
            else:
                current += ("\n" + line) if current else line
        if current:
            chunks.append(current)

    ok = True
    for chunk in chunks:
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": chunk, "disable_web_page_preview": True}
        resp = requests.post(url, json=payload)
        if resp.status_code != 200:
            print(f"❌ Erro Telegram: {resp.status_code} - {resp.text}")
            ok = False
    if ok:
        print(f"✅ Alerta enviado via Telegram ({len(chunks)} msg).")
    return ok


def send_telegram_to(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    chunks = []
    if len(message) <= 4000:
        chunks = [message]
    else:
        lines = message.split("\n")
        current = ""
        for line in lines:
            if len(current) + len(line) + 1 > 4000:
                chunks.append(current)
                current = line
            else:
                current += ("\n" + line) if current else line
        if current:
            chunks.append(current)
    for chunk in chunks:
        payload = {"chat_id": chat_id, "text": chunk, "disable_web_page_preview": True}
        requests.post(url, json=payload)


# === BOT TELEGRAM ===

def build_setor_message(setores_list, limit=None):
    tracking = load_tracking()
    if not tracking:
        return "Nenhum dado de tracking disponível."
    blocks = []
    for setor_nome in setores_list:
        analysis = analyze_tasks(tracking, setor_filter=setor_nome)
        data = analysis[setor_nome]
        total = len(data["atrasadas"]) + len(data["em_risco"]) + len(data["no_prazo"])
        if total == 0:
            blocks.append(f"📂 {setor_nome.upper()} — Nenhuma tarefa neste setor.")
        else:
            block = build_setor_block(setor_nome, data, limit=limit)
            if block:
                blocks.append(block)
    return "\n".join(blocks) if blocks else "Nenhum dado."


def handle_bot_command(text):
    text = text.strip().lower().lstrip("/")

    if text in ("status", "start"):
        tracking = load_tracking()
        analysis = analyze_tasks(tracking)
        return build_alert_message(analysis)
    elif text == "atrasos":
        tracking = load_tracking()
        analysis = analyze_tasks(tracking)
        return build_atrasos_message(analysis)
    elif text in SETOR_CMD_MAP:
        return build_setor_message(SETOR_CMD_MAP[text])
    elif text == "help":
        return (
            "📋 Comandos disponíveis:\n\n"
            "/status — Visão geral da esteira\n"
            "/atrasos — Principais atrasos por setor\n"
            "/copy — Escrevendo - Copy\n"
            "/preprod — Pré-Produção\n"
            "/producao — Produção\n"
            "/alteracao — Produção de Alteração\n"
            "/avaliacao — Avaliação (Pós Edição + Pós Alteração)\n"
            "/freelancer — Freelancer\n"
            "/help — Esta mensagem"
        )
    return None


def load_offset():
    if os.path.exists(OFFSET_FILE):
        with open(OFFSET_FILE, "r") as f:
            return int(f.read().strip())
    return 0


def save_offset(offset):
    os.makedirs(os.path.dirname(OFFSET_FILE), exist_ok=True)
    with open(OFFSET_FILE, "w") as f:
        f.write(str(offset))


def bot_poll_once():
    offset = load_offset()
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"offset": offset + 1, "timeout": 30}
    try:
        resp = requests.get(url, params=params, timeout=35)
    except requests.exceptions.Timeout:
        return
    except requests.exceptions.ConnectionError:
        print(f"[{datetime.now().isoformat()}] Erro de conexão.")
        return

    if resp.status_code != 200:
        return

    for update in resp.json().get("result", []):
        update_id = update["update_id"]
        msg = update.get("message", {})
        chat_id = msg.get("chat", {}).get("id")
        text = msg.get("text", "")

        if chat_id and text:
            # Poll fresco antes de responder
            poll()
            response = handle_bot_command(text)
            if response:
                send_telegram_to(chat_id, response)

        save_offset(update_id)


def cmd_health():
    """Verifica saúde do rastreador (heartbeat, circuit breaker, DLQ)."""
    health = health_check_http()
    print(f"🏥 RASTREADOR HEALTH CHECK")
    print(f"  Status: {health['status'].upper()}")
    print(f"  Heartbeat: {health['heartbeat']}")
    print(f"  Circuit Breaker: {health['circuit_breaker']}")
    print(f"  DLQ Pendentes: {health['dlq_pending']}")
    print(f"  Timestamp: {health['timestamp']}")


def cmd_bot():
    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN não configurado.")
        sys.exit(1)

    print(f"[{datetime.now().isoformat()}] Bot IMPERA Esteira iniciado.")

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setMyCommands"
    cmds = [
        {"command": "status", "description": "Visão geral da esteira"},
        {"command": "atrasos", "description": "Principais atrasos por setor"},
        {"command": "copy", "description": "Escrevendo - Copy"},
        {"command": "preprod", "description": "Pré-Produção"},
        {"command": "producao", "description": "Produção"},
        {"command": "alteracao", "description": "Produção de Alteração"},
        {"command": "avaliacao", "description": "Avaliação (Pós Edição + Pós Alteração)"},
        {"command": "freelancer", "description": "Freelancer"},
        {"command": "health", "description": "Saúde do rastreador"},
        {"command": "help", "description": "Lista de comandos"},
    ]
    requests.post(url, json={"commands": cmds})
    print("✅ Comandos registrados no Telegram.")

    while True:
        try:
            bot_poll_once()
        except KeyboardInterrupt:
            print("\nBot encerrado.")
            break
        except Exception as e:
            print(f"[{datetime.now().isoformat()}] Erro: {e}")
            _time.sleep(5)


# === CLI COMMANDS ===

def cmd_poll():
    poll()


def cmd_alert():
    """Envia alerta consolidado (11h e 16h)."""
    poll()
    tracking = load_tracking()

    # Coleta críticos não resolvidos (tarefas atrasadas demais)
    critical_issues = []
    now = datetime.now()
    for tid, task_data in tracking.items():
        status = task_data.get("current_status", "").lower()
        entered_at = task_data.get("status_entered_at", "")

        # Verifica se excedeu SLA de forma crítica (3+ dias depois)
        from rastreador_notificacao_strategy import task_exceeds_sla_critical
        exceeds, days = task_exceeds_sla_critical(status, entered_at, days_threshold=3)

        if exceeds:
            critical_issues.append({
                "task_name": task_data.get("name", "?"),
                "reason": f"Atrasada {days}d (SLA+3d)",
                "days": days,
            })

    # Constrói mensagem consolidada
    message = build_consolidated_alert(tracking, critical_issues=critical_issues)

    if message:
        post_clickup_alert(message)
        log_notification("consolidated", "alert_daily", message, posted=True)
    else:
        print("✅ Nada crítico para alertar hoje.")


def analyze_paused_tasks(tracking, days_threshold=7):
    """
    Analisa tarefas pausadas na esteira.
    Retorna tarefas que estão pausadas > threshold dias.
    """
    now = datetime.now()
    pausados = []

    for tid, data in tracking.items():
        current_status = data.get("current_status", "").lower()
        if "pausado" not in current_status:
            continue

        status_entered = data.get("status_entered_at", "")
        try:
            entered_dt = datetime.fromisoformat(status_entered)
            days_paused = (now - entered_dt).days
            if days_paused >= days_threshold:
                pausados.append({
                    "id": tid,
                    "name": data.get("name", "?"),
                    "responsible": data.get("responsible", "?"),
                    "days_paused": days_paused,
                    "entered": status_entered,
                })
        except:
            pass

    pausados.sort(key=lambda x: x["days_paused"], reverse=True)
    return pausados


def cmd_status():
    tracking = load_tracking()
    if not tracking:
        print("Nenhum dado de tracking. Execute 'poll' primeiro.")
        return
    analysis = analyze_tasks(tracking)
    now = datetime.now()
    total_a = sum(len(d["atrasadas"]) for d in analysis.values())
    total_r = sum(len(d["em_risco"]) for d in analysis.values())
    total_p = sum(len(d["no_prazo"]) for d in analysis.values())
    print(f"📊 ESTEIRA IMPERA — {now.strftime('%d/%m %H:%M')}")
    print(f"🔴 {total_a} atrasadas | 🟡 {total_r} em risco | ✅ {total_p} no prazo")
    print(f"Total rastreado: {len(tracking)} tarefas")
    for setor in SETORES:
        block = build_setor_block(setor, analysis[setor], limit=5)
        if block:
            print(block)

    # Mostrar pausados > 7 dias
    pausados = analyze_paused_tasks(tracking, days_threshold=7)
    if pausados:
        print(f"\n⏸️  PAUSADOS >7 DIAS ({len(pausados)}):")
        for p in pausados[:10]:
            print(f"  • {p['name'][:40]} — {p['days_paused']}d (→ {p['responsible']})")
        if len(pausados) > 10:
            print(f"  ... +{len(pausados) - 10} tarefas pausadas")


def cmd_atrasos():
    tracking = load_tracking()
    if not tracking:
        print("Nenhum dado de tracking. Execute 'poll' primeiro.")
        return
    analysis = analyze_tasks(tracking)
    print(build_atrasos_message(analysis))


def cmd_paused():
    """Lista tarefas pausadas > 7 dias."""
    tracking = load_tracking()
    if not tracking:
        print("Nenhum dado de tracking. Execute 'poll' primeiro.")
        return
    pausados = analyze_paused_tasks(tracking, days_threshold=7)
    if not pausados:
        print("✅ Nenhuma tarefa pausada > 7 dias")
        return

    print(f"⏸️  TAREFAS PAUSADAS >7 DIAS ({len(pausados)})")
    print("=" * 80)
    for p in pausados:
        print(f"  {p['name'][:60]}")
        print(f"    ID: {p['id']} | {p['days_paused']}d paused | Responsável: {p['responsible']}")
    print()


def cmd_setor(setores_list):
    tracking = load_tracking()
    if not tracking:
        print("Nenhum dado de tracking. Execute 'poll' primeiro.")
        return
    for setor_nome in setores_list:
        analysis = analyze_tasks(tracking, setor_filter=setor_nome)
        data = analysis[setor_nome]
        total = len(data["atrasadas"]) + len(data["em_risco"]) + len(data["no_prazo"])
        if total == 0:
            print(f"📂 {setor_nome.upper()} — Nenhuma tarefa neste setor.")
        else:
            block = build_setor_block(setor_nome, data, limit=None)
            if block:
                print(block)


def discover_chat_id():
    if not TELEGRAM_TOKEN:
        print("Configure TELEGRAM_BOT_TOKEN primeiro.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    resp = requests.get(url)
    if resp.status_code != 200:
        print(f"Erro: {resp.status_code}")
        return
    updates = resp.json().get("result", [])
    if not updates:
        print("Nenhuma mensagem recebida.")
        return
    seen = set()
    for u in updates:
        chat = u.get("message", {}).get("chat", {})
        cid = chat.get("id")
        name = (chat.get("first_name", "") + " " + chat.get("last_name", "")).strip()
        if cid and cid not in seen:
            seen.add(cid)
            print(f"Chat ID: {cid} | Nome: {name}")


# === WEBHOOK: Real-time status updates (v2.0) ===

class EsteirWebhookHandler(BaseHTTPRequestHandler):
    """Handles ClickUp webhook events for task status changes."""

    def do_POST(self):
        if self.path == "/webhook/esteira":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)

            try:
                event = json.loads(body)
                event_type = event.get("event")

                if event_type == "taskStatusUpdated":
                    task = event.get("task", {})
                    task_id = task.get("id")
                    task_name = task.get("name", "").strip()
                    status = task.get("status", {}).get("status", "unknown").lower()

                    if task_id and is_creative_task(task_name):
                        print(f"  [WEBHOOK] {task_name[:50]} → {status}")
                        tracking = load_tracking()

                        if task_id in tracking:
                            old_status = tracking[task_id].get("current_status", "unknown")
                            if old_status != status:
                                responsible = task.get("assignees", [])
                                now = datetime.now().isoformat()

                                # Verifica se copywriter está vazio
                                copy_field = None
                                if old_status == "backlog copy":
                                    copy_field = get_cf_value(task, "✍️ Copywritter")

                                # Determina se é crítico
                                is_critical, reason = is_critical_issue(
                                    old_status, status,
                                    task_data=task,
                                    missing_copywriter=(not copy_field if old_status == "backlog copy" else False)
                                )

                                # Notifica apenas se crítico (evita spam)
                                if is_critical:
                                    msg = f"🚨 CRÍTICO: {task_name}\n→ {reason.upper()}"
                                    post_clickup_alert(msg)
                                    log_notification("critical", task_id, msg, posted=True)
                                    print(f"    🚨 CRÍTICO: {reason}")
                                else:
                                    # Não é crítico, apenas loga
                                    log_notification("normal", task_id, f"{old_status} → {status}", posted=False)
                                    print(f"    ℹ️  Normal: {old_status} → {status}")

                                # Log transition (sempre)
                                check_phase_completion(task_id, old_status, status, tracking)
                                log_transition(task_id, task_name, old_status, status, now)

                                # Update tracking
                                tracking[task_id]["current_status"] = status
                                tracking[task_id]["status_entered_at"] = now
                                save_tracking(tracking)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True}).encode())

            except Exception as e:
                print(f"  [WEBHOOK ERROR] {e}")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress default logging


def start_webhook_server():
    """Starts webhook server in background thread."""
    server = HTTPServer(("127.0.0.1", ESTEIRA_WEBHOOK_PORT), EsteirWebhookHandler)
    print(f"[WEBHOOK] Listening on port {ESTEIRA_WEBHOOK_PORT}...")

    server_thread = Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    return server


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "--server":
        print(f"[{datetime.now().strftime('%d/%m/%Y %H:%M')}] 🎯 Rastreador Esteira Webhook Server v2.0")
        server = start_webhook_server()
        try:
            while True:
                _time.sleep(1)
        except KeyboardInterrupt:
            print("\n[WEBHOOK] Encerrado.")
            server.shutdown()
    else:
        commands = {
            "poll": cmd_poll,
            "alert": cmd_alert,
            "status": cmd_status,
            "atrasos": cmd_atrasos,
            "paused": cmd_paused,
            "health": cmd_health,
            "bot": cmd_bot,
            "chatid": discover_chat_id,
        }

        if cmd in commands:
            commands[cmd]()
        elif cmd in SETOR_CMD_MAP:
            cmd_setor(SETOR_CMD_MAP[cmd])
        else:
            print(f"Comando desconhecido: {cmd}")
            print(__doc__)
            sys.exit(1)
