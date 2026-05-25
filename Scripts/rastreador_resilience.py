#!/usr/bin/env python3
"""
Resiliência para rastreador_esteira.py
- Heartbeat: ping Telegram a cada polling bem-sucedido
- Dead Letter Queue: persiste transições se DB cair
- Circuit Breaker: alerta se falhas consecutivas
- Health Check: endpoint que verifica status
"""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

HEARTBEAT_FILE = os.path.expanduser("~/Scripts/data/rastreador_heartbeat.json")
DEAD_LETTER_QUEUE = os.path.expanduser("~/Scripts/data/rastreador_dlq.jsonl")
CIRCUIT_BREAKER_FILE = os.path.expanduser("~/Scripts/data/rastreador_circuit_breaker.json")

HEARTBEAT_TIMEOUT = 35 * 60  # 35 minutos (polling acontece a cada 30)
CIRCUIT_BREAKER_THRESHOLD = 5  # 5 falhas consecutivas = trip


def record_heartbeat(status="ok", error=None):
    """Registra heartbeat do rastreador (chamado após cada polling bem-sucedido)."""
    heartbeat = {
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "error": error,
    }
    with open(HEARTBEAT_FILE, 'w') as f:
        json.dump(heartbeat, f, indent=2)


def check_heartbeat():
    """Verifica se o rastreador está operacional (last heartbeat < 35min)."""
    if not os.path.exists(HEARTBEAT_FILE):
        return False, "Nenhum heartbeat registrado"

    with open(HEARTBEAT_FILE) as f:
        data = json.load(f)

    try:
        last_beat = datetime.fromisoformat(data.get("timestamp", ""))
        age = (datetime.now() - last_beat).total_seconds()

        if age > HEARTBEAT_TIMEOUT:
            return False, f"Heartbeat expirado há {age // 60:.0f} minutos"
        return True, f"Operacional (último ping há {age // 60:.0f}min)"
    except Exception as e:
        return False, f"Erro parsing heartbeat: {e}"


def queue_dead_letter(transition_data):
    """Persiste transição em DLQ se PostgreSQL cair."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "data": transition_data,
    }
    with open(DEAD_LETTER_QUEUE, 'a') as f:
        f.write(json.dumps(entry) + '\n')


def process_dead_letter_queue(db_insert_func):
    """Processa DLQ e sincroniza com DB (chamado quando DB volta online)."""
    if not os.path.exists(DEAD_LETTER_QUEUE):
        return 0

    processed = 0
    failed = []

    with open(DEAD_LETTER_QUEUE, 'r') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                db_insert_func(**entry["data"])
                processed += 1
            except Exception as e:
                failed.append({"line": line, "error": str(e)})

    # Reescrever arquivo com apenas os que falharam
    with open(DEAD_LETTER_QUEUE, 'w') as f:
        for item in failed:
            f.write(item["line"] + '\n')

    return processed


def record_circuit_breaker_failure():
    """Registra falha para circuit breaker."""
    if not os.path.exists(CIRCUIT_BREAKER_FILE):
        cb = {"failures": 0, "last_failure": None, "tripped": False}
    else:
        with open(CIRCUIT_BREAKER_FILE) as f:
            cb = json.load(f)

    cb["failures"] += 1
    cb["last_failure"] = datetime.now().isoformat()
    cb["tripped"] = cb["failures"] >= CIRCUIT_BREAKER_THRESHOLD

    with open(CIRCUIT_BREAKER_FILE, 'w') as f:
        json.dump(cb, f, indent=2)

    return cb


def record_circuit_breaker_success():
    """Reseta circuit breaker após sucesso."""
    with open(CIRCUIT_BREAKER_FILE, 'w') as f:
        json.dump({"failures": 0, "last_failure": None, "tripped": False}, f, indent=2)


def is_circuit_breaker_tripped():
    """Verifica se circuit breaker está ativo."""
    if not os.path.exists(CIRCUIT_BREAKER_FILE):
        return False

    with open(CIRCUIT_BREAKER_FILE) as f:
        cb = json.load(f)

    if not cb.get("tripped"):
        return False

    # Trip dura 5 minutos
    try:
        last_fail = datetime.fromisoformat(cb.get("last_failure", ""))
        age = (datetime.now() - last_fail).total_seconds()
        if age > 5 * 60:
            # Reset after 5 minutes
            record_circuit_breaker_success()
            return False
    except:
        pass

    return True


def health_check_http():
    """
    Simple HTTP endpoint para health check (chamado externamente).
    Retorna JSON com status do rastreador.
    """
    operational, msg = check_heartbeat()
    circuit_tripped = is_circuit_breaker_tripped()

    dlq_count = 0
    if os.path.exists(DEAD_LETTER_QUEUE):
        with open(DEAD_LETTER_QUEUE) as f:
            dlq_count = sum(1 for _ in f if _.strip())

    return {
        "status": "operational" if operational and not circuit_tripped else "degraded",
        "heartbeat": msg,
        "circuit_breaker": "TRIPPED ⚠️" if circuit_tripped else "OK",
        "dlq_pending": dlq_count,
        "timestamp": datetime.now().isoformat(),
    }
