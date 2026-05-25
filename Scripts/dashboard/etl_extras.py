#!/usr/bin/env python3
"""
ETL Extras — Popula fato_vturb, fato_lifecycle_v2, fato_esteira, fato_health
Complementa o etl_dashboard.py principal.

Uso:
    python3 ~/Scripts/dashboard/etl_extras.py              # Tudo
    python3 ~/Scripts/dashboard/etl_extras.py --only vturb
    python3 ~/Scripts/dashboard/etl_extras.py --only lifecycle
    python3 ~/Scripts/dashboard/etl_extras.py --only esteira
    python3 ~/Scripts/dashboard/etl_extras.py --only health
"""

import sys
import os
import json
import argparse
from datetime import datetime, timedelta

sys.path.insert(0, os.path.expanduser("~/Scripts"))

import psycopg2
from psycopg2.extras import execute_values

# ============================================================
# Config
# ============================================================

DATABASE_URL = os.environ.get("DASHBOARD_DATABASE_URL", "")
DATA_DIR = os.path.expanduser("~/Scripts/data")

# SLA limits per status (hours)
SLA_MAP = {
    "em fila": 24,
    "copywriting": 48,
    "editando": 48,
    "freelancer - editando": 72,
    "revisao copy": 12,
    "revisao edicao": 12,
    "aguardando teste": 24,
    "correcao": 24,
}


def get_conn():
    if not DATABASE_URL:
        raise ValueError("DASHBOARD_DATABASE_URL not set. Refusing to start without credentials.")
    url = DATABASE_URL
    return psycopg2.connect(url)


# ============================================================
# A. Vturb ETL
# ============================================================

# Nicho detection from player name (same as relatorio_vturb.py)
VSL_NICHO_MAP = {
    'emagrecimento': 'EM', 'gelatina': 'EM', 'slim': 'EM', 'bariatrica': 'EM', 'lipoled': 'EM',
    'diabetes': 'DA', 'glico': 'DA', 'insulvita': 'DA', 'insuvita': 'DA',
    'neuropatia': 'NE', 'neurocare': 'NE',
    'adulto': 'ED', 'eremed': 'ED', 'erepower': 'ED', 'of22': 'ED',
    'memoria': 'ME', 'memotril': 'ME', 'memoforte': 'ME', 'brainvex': 'ME',
    'brain honey': 'MM', 'brainhoney': 'MM',
    'prostata': 'PT', 'prostasafe': 'PT',
    'zumbido': 'ZB', 'neurosilence': 'ZB',
    'articure': 'DA',
    'massa': 'MM',
}

VALID_NICHOS = {'DA', 'DB', 'ED', 'EM', 'ME', 'MM', 'NE', 'PT', 'ZB'}


def detect_vturb_nicho(name):
    lower = name.lower()
    for kw, nicho in VSL_NICHO_MAP.items():
        if kw in lower:
            return nicho if nicho in VALID_NICHOS else None
    return None


def etl_vturb(conn):
    """Fetch Vturb players and insert into fato_vturb."""
    import urllib.request

    VTURB_KEY = os.environ.get("VTURB_API_KEY", "")
    if not VTURB_KEY:
        print("[VTURB] VTURB_API_KEY not set, skipping")
        return 0
    BASE = "https://analytics.vturb.net"

    print("[VTURB] Buscando players...")

    # Get all players
    req = urllib.request.Request(f"{BASE}/players/list")
    req.add_header("X-Api-Token", VTURB_KEY)
    req.add_header("X-Api-Version", "v1")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            players = json.loads(resp.read())
    except Exception as e:
        print(f"[VTURB] Erro ao buscar players: {e}")
        return 0

    print(f"[VTURB] {len(players)} players encontrados")

    # Get stats for each active player (with pitch_time configured)
    import time
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    rows = []
    active_players = [p for p in players if p.get('pitch_time', 0) > 0]
    print(f"[VTURB] {len(active_players)} players ativos (com pitch)")

    for i, p in enumerate(active_players):
        pid = p['id']
        name = p.get('name', '')
        duration = p.get('duration', 0)
        pitch_time = p.get('pitch_time', 0)
        nicho = detect_vturb_nicho(name)

        # Fetch stats for last 7 days
        try:
            payload = json.dumps({
                "player_id": pid,
                "start_date": f"{week_ago} 00:00:00",
                "end_date": f"{yesterday} 23:59:59",
                "video_duration": duration,
                "pitch_time": pitch_time,
            }).encode()
            req2 = urllib.request.Request(f"{BASE}/sessions/stats", data=payload, method='POST')
            req2.add_header("X-Api-Token", VTURB_KEY)
            req2.add_header("X-Api-Version", "v1")
            req2.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req2, timeout=30) as resp2:
                stats = json.loads(resp2.read())

            vu = stats.get('total_viewed_device_uniq', 0)
            pu = stats.get('total_started_device_uniq', 0)
            play_rate = round(pu / vu * 100, 2) if vu > 0 else 0
            engagement = float(stats.get('engagement_rate', 0))

            rows.append((pid, name, nicho, vu, pu, play_rate, engagement, duration, today))
        except Exception as e:
            print(f"  [WARN] Player {name[:30]}: {e}")
            continue

        if i < len(active_players) - 1:
            time.sleep(1.2)

    if not rows:
        print("[VTURB] Nenhum dado coletado")
        return 0

    # Insert
    cur = conn.cursor()
    for row in rows:
        cur.execute("""
            INSERT INTO fato_vturb (player_id, player_name, nicho_id, views_unicas, plays_unicos,
                                    play_rate, engajamento, duracao_segundos, data_coleta)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (player_id, data_coleta) DO UPDATE SET
                views_unicas = EXCLUDED.views_unicas,
                plays_unicos = EXCLUDED.plays_unicos,
                play_rate = EXCLUDED.play_rate,
                engajamento = EXCLUDED.engajamento,
                updated_at = NOW()
        """, row)
    conn.commit()
    print(f"[VTURB] {len(rows)} players sincronizados")
    return len(rows)


# ============================================================
# B. Creative Lifecycle ETL
# ============================================================

def etl_lifecycle(conn):
    """Read classificador_state.json and insert into fato_lifecycle_v2."""
    state_path = os.path.join(DATA_DIR, "classificador_state.json")
    if not os.path.exists(state_path):
        print("[LIFECYCLE] classificador_state.json nao encontrado")
        return 0

    with open(state_path) as f:
        state = json.load(f)

    print(f"[LIFECYCLE] {len(state)} criativos no classificador")

    cur = conn.cursor()
    # Clear and reload (snapshot approach)
    cur.execute("DELETE FROM fato_lifecycle_v2")

    rows = []
    for task_id, data in state.items():
        nivel = data.get("nivel", "desconhecido")
        vendas = data.get("vendas", 0)
        cpa = data.get("cpa", 0)
        updated = data.get("updated", "")

        # Parse timestamp
        data_class = None
        if updated:
            try:
                data_class = datetime.fromisoformat(updated)
            except:
                data_class = datetime.now()
        else:
            data_class = datetime.now()

        rows.append((task_id, None, None, nivel, vendas, 0, cpa, 0, data_class))

    if rows:
        execute_values(cur, """
            INSERT INTO fato_lifecycle_v2 (clickup_task_id, criativo_nome, nicho_id,
                                           classificacao, vendas_acumuladas, roas_momento,
                                           cpa_momento, custo_acumulado, data_classificacao)
            VALUES %s
        """, rows)
    conn.commit()
    print(f"[LIFECYCLE] {len(rows)} registros inseridos")
    return len(rows)


# ============================================================
# C. Esteira ETL
# ============================================================

def etl_esteira(conn):
    """Read esteira_tracking.json and insert into fato_esteira with SLA calc."""
    state_path = os.path.join(DATA_DIR, "esteira_tracking.json")
    if not os.path.exists(state_path):
        print("[ESTEIRA] esteira_tracking.json nao encontrado")
        return 0

    with open(state_path) as f:
        state = json.load(f)

    print(f"[ESTEIRA] {len(state)} tarefas rastreadas")

    cur = conn.cursor()
    now = datetime.now()
    count = 0

    for task_id, data in state.items():
        name = data.get("name", "")
        status = data.get("current_status", "")
        responsible = data.get("responsible", "")
        task_type = data.get("task_type", "criativo")
        entered_at_str = data.get("status_entered_at", "")

        # Parse entry timestamp
        entered_at = None
        horas_no_status = 0
        if entered_at_str:
            try:
                entered_at = datetime.fromisoformat(entered_at_str)
                delta = now - entered_at
                horas_no_status = round(delta.total_seconds() / 3600, 1)
            except:
                pass

        # SLA calculation
        sla_limite = SLA_MAP.get(status.lower(), None)
        sla_estourado = False
        if sla_limite and horas_no_status > sla_limite:
            sla_estourado = True

        cur.execute("""
            INSERT INTO fato_esteira (clickup_task_id, nome_tarefa, status_atual, responsavel,
                                      tipo, data_entrada_status, horas_no_status,
                                      sla_limite_horas, sla_estourado)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (clickup_task_id) DO UPDATE SET
                nome_tarefa = EXCLUDED.nome_tarefa,
                status_atual = EXCLUDED.status_atual,
                responsavel = EXCLUDED.responsavel,
                horas_no_status = EXCLUDED.horas_no_status,
                sla_estourado = EXCLUDED.sla_estourado,
                updated_at = NOW()
        """, (task_id, name, status, responsible, task_type, entered_at,
              horas_no_status, sla_limite, sla_estourado))
        count += 1

    conn.commit()
    print(f"[ESTEIRA] {count} tarefas sincronizadas")
    return count


# ============================================================
# D. Health ETL
# ============================================================

SCRIPTS_TO_CHECK = [
    {"name": "etl_dashboard", "state_file": None, "log_pattern": "etl_dashboard"},
    {"name": "classificador_criativos", "state_file": "classificador_state.json"},
    {"name": "esteira_rastreador", "state_file": "esteira_tracking.json"},
    {"name": "briefing_diario", "state_file": "briefing_diario_latest.txt"},
    {"name": "auto_envio_trafego", "state_file": "enviados_trafego.json"},
    {"name": "compliance_drive", "state_file": "compliance_drive_state.json"},
    {"name": "health_check", "state_file": None},
    {"name": "sync_responsavel", "state_file": None},
    {"name": "subtarefas_expansao", "state_file": "subtarefas_expandidas.json"},
]


def etl_health(conn):
    """Check script health by looking at state file modification times."""
    cur = conn.cursor()
    count = 0

    for script in SCRIPTS_TO_CHECK:
        name = script["name"]
        state_file = script.get("state_file")
        status = "unknown"
        last_run = None
        last_error = None

        if state_file:
            path = os.path.join(DATA_DIR, state_file)
            if os.path.exists(path):
                mtime = os.path.getmtime(path)
                last_run = datetime.fromtimestamp(mtime)
                age_hours = (datetime.now() - last_run).total_seconds() / 3600

                # If modified in last 24h, consider OK
                if age_hours < 24:
                    status = "ok"
                elif age_hours < 48:
                    status = "warning"
                else:
                    status = "error"
                    last_error = f"Sem execucao ha {age_hours:.0f}h"
            else:
                status = "error"
                last_error = f"State file nao encontrado: {state_file}"

        # Check stderr logs
        stderr_path = os.path.join(DATA_DIR, f"{name}_stderr.log")
        if os.path.exists(stderr_path):
            size = os.path.getsize(stderr_path)
            if size > 0:
                try:
                    with open(stderr_path, 'r') as f:
                        lines = f.readlines()
                        if lines:
                            last_error = lines[-1].strip()[:500]
                except:
                    pass

        cur.execute("""
            INSERT INTO fato_health (script_name, status, last_run, last_error)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (script_name) DO UPDATE SET
                status = EXCLUDED.status,
                last_run = EXCLUDED.last_run,
                last_error = EXCLUDED.last_error,
                updated_at = NOW()
        """, (name, status, last_run, last_error))
        count += 1

    conn.commit()
    print(f"[HEALTH] {count} scripts verificados")
    return count


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="ETL Extras — Dashboard IMPERA")
    parser.add_argument("--only", choices=["vturb", "lifecycle", "esteira", "health"],
                        help="Rodar apenas um modulo")
    args = parser.parse_args()

    conn = get_conn()
    print(f"[ETL-EXTRAS] Inicio: {datetime.now().strftime('%H:%M:%S')}")

    if not args.only or args.only == "lifecycle":
        etl_lifecycle(conn)

    if not args.only or args.only == "esteira":
        etl_esteira(conn)

    if not args.only or args.only == "health":
        etl_health(conn)

    if not args.only or args.only == "vturb":
        etl_vturb(conn)

    conn.close()
    print(f"[ETL-EXTRAS] Concluido: {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    main()
