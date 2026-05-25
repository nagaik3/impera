#!/usr/bin/env python3
"""
ETL Dashboard IMPERA — Popula PostgreSQL com dados RedTrack + ClickUp
Crontab: 2x/dia (09h30, 17h30)

Uso:
    python3 ~/Scripts/dashboard/etl_dashboard.py              # ETL completo
    python3 ~/Scripts/dashboard/etl_dashboard.py --only perf  # Só performance
    python3 ~/Scripts/dashboard/etl_dashboard.py --only prod  # Só produção
    python3 ~/Scripts/dashboard/etl_dashboard.py --days 30    # Últimos 30 dias (default: 7)
"""

import sys
import os
import argparse
from datetime import datetime, timedelta

# Path dos scripts IMPERA
sys.path.insert(0, os.path.expanduser("~/Scripts"))

import psycopg2
from psycopg2.extras import execute_values

from impera_cache import cached_cu_tasks, cached_rt_adgroups
from impera_utils import (
    detect_nicho, detect_mercado, is_ripado, classify_task,
    normalize_person_name, get_cf_value, NICHO_NAMES
)

# ============================================================
# Config
# ============================================================

DATABASE_URL = os.environ.get("DASHBOARD_DATABASE_URL", "")
LIST_COPY = "901324556390"
LIST_TRAFEGO = "901324476398"

# Mapeamento gestores (mesmo do relatorio_redtrack)
GESTOR_MAP = {
    "G.LUCAS": "Lucas", "G.LUDSON": "Ludson", "G.DOUG": "Douglas",
    "G.DOUGLAS": "Douglas", "G.GABRIEL": "Gabriel", "G.GUSTAVO": "Gustavo",
}
GESTOR_FONTE_DEFAULT = {
    "Lucas": "FB", "Ludson": "FB", "Douglas": "FB",
    "Gabriel": "FB", "Gustavo": "KW",
}

# Mapeamento copywriters por prefixo
COPY_PREFIX = {"CE": "Elias", "CY": "Yan", "CC": "Cassio", "C": "Douglas"}


# ============================================================
# Conexão
# ============================================================

def get_conn():
    if not DATABASE_URL:
        raise ValueError("DASHBOARD_DATABASE_URL não configurada. Setar em ~/.zshrc ou env.")
    return psycopg2.connect(DATABASE_URL)


# ============================================================
# Helpers parse (reutiliza lógica dos scripts existentes)
# ============================================================

def parse_campaign_name(name):
    """Extrai fonte, nicho, gestor, oferta do nome da campanha RT."""
    import re
    result = {"fonte": None, "nicho": None, "gestor": None, "oferta": None}

    # Fonte
    m = re.search(r'\[(FB|KW|TT|YT|TB|NTV)\]', name, re.IGNORECASE)
    if m:
        result["fonte"] = m.group(1).upper()

    # Nicho
    nicho_patterns = {
        "EM": r"EMAGRECIMENTO|EMAG",
        "DA": r"DIABETES[^/]|DIABET\b",
        "DB": r"DIABETES\s*B|DB\b",
        "NE": r"NERVO|DOR|NEURO",
        "PT": r"PR[OÓ]STATA",
        "ZB": r"ZUMBIDO",
        "ME": r"MEM[OÓ]RIA|MENTE",
        "MM": r"MASSA|MUSCUL",
        "ED": r"DISF|ER[EÉ]TIL|ED\b",
    }
    for code, pat in nicho_patterns.items():
        if re.search(pat, name, re.IGNORECASE):
            result["nicho"] = code
            break

    # Gestor — normaliza removendo espaços para match
    name_upper_nospace = name.upper().replace(" ", "")
    for prefix, gestor in GESTOR_MAP.items():
        if prefix.replace(" ", "") in name_upper_nospace:
            result["gestor"] = gestor
            break
    # Fallback: busca direta por nome do gestor
    if not result["gestor"]:
        name_upper = name.upper()
        for gestor_name in ["LUCAS", "LUDSON", "DOUGLAS", "GABRIEL", "GUSTAVO"]:
            if gestor_name in name_upper:
                result["gestor"] = gestor_name.capitalize()
                break

    # Oferta (VSL XX ou similar)
    m = re.search(r'VSL\s*(\d+)', name, re.IGNORECASE)
    if m:
        result["oferta"] = f"VSL {m.group(1).zfill(2)}"

    return result


def extract_creative_base(ag_name):
    """Extrai base_id e versão do nome do adgroup RT."""
    import re
    name = ag_name.upper().strip()

    # Remove cópias e datas
    name = re.sub(r'\s*[-–—]\s*C[OÓ]PIA.*$', '', name)
    name = re.sub(r'\s+\d{2}/\d{2}$', '', name)
    name = re.sub(r'^\d+[AV]\d+[AV]?\d*\s*', '', name)

    # AD76 V10 - V9 → base=AD76V10, ver=V9
    m = re.match(r'(AD\d+)\s*V(\d+)\s*[-–]\s*V(\d+)', name)
    if m:
        return f"{m.group(1)}V{m.group(2)}", f"V{m.group(3)}"

    # CE08 V1 - V5
    m = re.match(r'(C[EYC]\d+)\s*V(\d+)\s*[-–]\s*V(\d+)', name)
    if m:
        return f"{m.group(1)}V{m.group(2)}", f"V{m.group(3)}"

    # AD644 V3 (simples)
    m = re.match(r'(AD\d+)\s*V(\d+)', name)
    if m:
        return m.group(1), f"V{m.group(2)}"

    # C71 V12
    m = re.match(r'(C\d+)\s*V(\d+)', name)
    if m:
        return m.group(1), f"V{m.group(2)}"

    # CE08, CY05, CC12 sem versão
    m = re.match(r'(C[EYC]\d+)', name)
    if m:
        return m.group(1), None

    # AD644 sem versão (original)
    m = re.match(r'(AD\d+)', name)
    if m:
        return m.group(1), None

    # C71 sem versão
    m = re.match(r'(C\d+)', name)
    if m:
        return m.group(1), None

    return None, None


# ============================================================
# ETL: Dimensões
# ============================================================

def sync_gestores(conn):
    """Sincroniza dim_gestor."""
    cur = conn.cursor()
    for nome, fonte in GESTOR_FONTE_DEFAULT.items():
        cur.execute("""
            INSERT INTO dim_gestor (nome, fonte_principal)
            VALUES (%s, %s)
            ON CONFLICT (nome) DO NOTHING
        """, (nome, fonte))
    conn.commit()
    # Retorna mapa nome→id
    cur.execute("SELECT gestor_id, nome FROM dim_gestor")
    result = {row[1]: row[0] for row in cur.fetchall()}
    conn.commit()
    return result


def sync_pessoas(conn, tasks):
    """Sincroniza dim_pessoa a partir das tasks do ClickUp."""
    cur = conn.cursor()

    # Garantir unique constraint existe
    cur.execute("""
        DO $$ BEGIN
            ALTER TABLE dim_pessoa ADD CONSTRAINT dim_pessoa_nome_role_unique UNIQUE (nome, role);
        EXCEPTION WHEN duplicate_table THEN NULL;
        END $$;
    """)

    pessoas_vistas = set()

    for t in tasks:
        # Copywriter
        copy_name = get_cf_value(t, "✍️ Copywritter")
        if copy_name:
            nome = normalize_person_name(copy_name)
            if nome not in pessoas_vistas:
                pessoas_vistas.add(nome)
                alias = "CASSIO" if nome == "REAPER" else None
                cur.execute("""
                    INSERT INTO dim_pessoa (nome, role, alias)
                    VALUES (%s, 'copy', %s)
                    ON CONFLICT (nome, role) DO NOTHING
                """, (nome, alias))

        # Editor
        editor_name = get_cf_value(t, "🎦 Editor de Video")
        if editor_name:
            nome = normalize_person_name(editor_name)
            if nome not in pessoas_vistas:
                pessoas_vistas.add(nome)
                cur.execute("""
                    INSERT INTO dim_pessoa (nome, role)
                    VALUES (%s, 'editor')
                    ON CONFLICT (nome, role) DO NOTHING
                """, (nome,))

    conn.commit()
    # Retorna mapa nome→id (sem role, pra lookup genérico)
    cur.execute("SELECT pessoa_id, nome FROM dim_pessoa")
    return {row[1]: row[0] for row in cur.fetchall()}


def sync_ofertas(conn):
    """Sincroniza dim_oferta a partir dos dados conhecidos."""
    cur = conn.cursor()
    # Carrega ofertas conhecidas do arquivo de estado se existir
    ofertas_path = os.path.expanduser("~/Scripts/data/nicho_ofertas_conhecidos.json")
    if os.path.exists(ofertas_path):
        import json
        with open(ofertas_path) as f:
            data = json.load(f)
        for nicho, ofertas in data.items():
            for of in ofertas:
                cur.execute("""
                    INSERT INTO dim_oferta (codigo, nicho_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                """, (of, nicho if nicho in ('DA','DB','ED','EM','ME','MM','NE','PT','ZB') else None))
    conn.commit()
    cur.execute("SELECT oferta_id, codigo, nicho_id FROM dim_oferta")
    return {(row[1], row[2]): row[0] for row in cur.fetchall()}


# ============================================================
# ETL: Fato Performance (RedTrack)
# ============================================================

def _fetch_day(day_str, gestor_map):
    """Busca dados de um único dia no RedTrack e retorna rows formatadas."""
    from impera_cache import rt_fetch_single, REDTRACK_KEY
    import time as _t

    rows = []
    try:
        ags = rt_fetch_single({
            "api_key": REDTRACK_KEY, "group": "campaign,rt_adgroup",
            "date_from": day_str, "date_to": day_str, "per": "10000",
        })
    except Exception as e:
        print(f"  [WARN] Erro dia {day_str}: {e}")
        return rows

    for ag in ags:
        cost = float(ag.get("cost", 0))
        if cost <= 0:
            continue

        campaign_name = ag.get("campaign", "")
        ag_name = ag.get("rt_adgroup", "")
        parsed = parse_campaign_name(campaign_name)

        rev_front = float(ag.get("revenuetype2", 0)) + float(ag.get("revenuetype3", 0))
        rev_total = float(ag.get("revenue", 0))
        vendas_total = int(float(ag.get("convtype1", 0)))
        vendas_cc = int(float(ag.get("convtype4", 0)))
        mc_br = (rev_front * 0.74) - (cost * 1.12)  # SSOT: impera-core/config/constants.py
        roas_front = rev_front / cost if cost > 0 else 0
        roas_total = rev_total / cost if cost > 0 else 0
        cpa = cost / vendas_total if vendas_total > 0 else 0
        clicks = int(float(ag.get("clicks", 0)))
        impressions = int(float(ag.get("impressions", 0)))
        lp_clicks = int(float(ag.get("lp_clicks", 0)))

        gestor_id = gestor_map.get(parsed["gestor"])

        rows.append((
            day_str,
            parsed["nicho"],
            None,  # oferta_id
            gestor_id,
            parsed["fonte"],
            None,  # criativo_id
            cost, rev_front, rev_total,
            vendas_total, vendas_cc, mc_br,
            roas_front, roas_total, cpa,
            clicks, impressions, lp_clicks,
            campaign_name, ag_name,
        ))

    return rows


def etl_performance(conn, date_from, date_to, gestor_map):
    """Extrai RedTrack dia a dia e carrega fato_performance."""
    import time as _t

    cur = conn.cursor()

    # Gerar lista de dias
    d_from = datetime.strptime(date_from, "%Y-%m-%d")
    d_to = datetime.strptime(date_to, "%Y-%m-%d")
    days = []
    d = d_from
    while d <= d_to:
        days.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)

    print(f"[PERF] Extraindo RT dia a dia: {date_from} → {date_to} ({len(days)} dias)...")

    # Limpa período
    cur.execute("DELETE FROM fato_performance WHERE data >= %s AND data <= %s", (date_from, date_to))
    conn.commit()

    total_rows = 0
    for i, day in enumerate(days):
        rows = _fetch_day(day, gestor_map)
        if rows:
            execute_values(cur, """
                INSERT INTO fato_performance (
                    data, nicho_id, oferta_id, gestor_id, fonte_id, criativo_id,
                    cost, revenue_front, revenue_total,
                    vendas_total, vendas_cc, mc_br,
                    roas_front, roas_total, cpa,
                    clicks, impressions, lp_clicks,
                    campaign_name, adgroup_name
                ) VALUES %s
            """, rows)
            conn.commit()
        total_rows += len(rows)
        print(f"  [{i+1}/{len(days)}] {day}: {len(rows)} rows")
        if i < len(days) - 1:
            _t.sleep(1.5)  # Rate limit RedTrack

    print(f"[PERF] {total_rows} rows inseridas ({len(days)} dias)")
    return total_rows


# ============================================================
# ETL: Fato Produção (ClickUp)
# ============================================================

def etl_producao(conn, pessoa_map):
    """Extrai ClickUp e carrega fato_producao."""
    print("[PROD] Extraindo ClickUp...")

    tasks = cached_cu_tasks(LIST_COPY, include_closed=True, ttl=1800, force=True)
    print(f"[PROD] {len(tasks)} tasks encontradas")

    cur = conn.cursor()
    rows = []

    for t in tasks:
        task_id = t.get("id", "")
        name = t.get("name", "")
        status = t.get("status", {}).get("status", "")

        # Classificar
        cat, qtd, nicho, mercado, is_rp = classify_task(name)
        if nicho == "??" or nicho not in ('DA','DB','ED','EM','ME','MM','NE','PT','ZB'):
            nicho = None

        # Copywriter
        copy_name = get_cf_value(t, "✍️ Copywritter")
        copy_norm = normalize_person_name(copy_name) if copy_name else None
        copy_id = pessoa_map.get(copy_norm)

        # Editor
        editor_name = get_cf_value(t, "🎦 Editor de Video")
        editor_norm = normalize_person_name(editor_name) if editor_name else None
        editor_id = pessoa_map.get(editor_norm)

        # Datas
        date_created = None
        if t.get("date_created"):
            ts = int(t["date_created"]) / 1000
            date_created = datetime.fromtimestamp(ts)

        date_done = None
        if t.get("date_done"):
            ts = int(t["date_done"]) / 1000
            date_done = datetime.fromtimestamp(ts)

        # SLA
        sla_dias = None
        sla_cumprido = None
        if date_created and date_done:
            sla_dias = (date_done - date_created).days
            # SLA padrão: 3 dias para copy, 2 para edição
            sla_limite = 3
            sla_cumprido = sla_dias <= sla_limite

        rows.append((
            task_id, name, nicho, None,  # oferta_id
            copy_id, editor_id, cat, qtd,
            is_rp, status, date_created, date_done,
            sla_dias, sla_cumprido,
        ))

    # Upsert
    for row in rows:
        cur.execute("""
            INSERT INTO fato_producao (
                clickup_task_id, nome_tarefa, nicho_id, oferta_id,
                copywriter_id, editor_id, tipo, qtd_criativos,
                eh_ripagem, status_atual, data_criacao, data_done,
                sla_dias, sla_cumprido
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (clickup_task_id) DO UPDATE SET
                status_atual = EXCLUDED.status_atual,
                data_done = EXCLUDED.data_done,
                sla_dias = EXCLUDED.sla_dias,
                sla_cumprido = EXCLUDED.sla_cumprido,
                copywriter_id = EXCLUDED.copywriter_id,
                editor_id = EXCLUDED.editor_id,
                updated_at = NOW()
        """, row)

    conn.commit()
    print(f"[PROD] {len(rows)} tasks sincronizadas")
    return len(rows)


# ============================================================
# ETL: Refresh Views
# ============================================================

def refresh_views(conn):
    """Atualiza materialized views."""
    cur = conn.cursor()
    cur.execute("REFRESH MATERIALIZED VIEW mv_performance_diaria")
    cur.execute("REFRESH MATERIALIZED VIEW mv_producao_semanal")
    conn.commit()
    print("[VIEWS] Materialized views atualizadas")


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="ETL Dashboard IMPERA")
    parser.add_argument("--only", choices=["perf", "prod"], help="Rodar apenas um módulo")
    parser.add_argument("--days", type=int, default=7, help="Dias retroativos (default: 7)")
    parser.add_argument("--init-schema", action="store_true", help="Criar tabelas (primeira execução)")
    args = parser.parse_args()

    conn = get_conn()
    print(f"[ETL] Conectado ao banco. Início: {datetime.now().strftime('%H:%M:%S')}")

    # Init schema se pedido
    if args.init_schema:
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        with open(schema_path) as f:
            conn.cursor().execute(f.read())
        conn.commit()
        print("[SCHEMA] Tabelas criadas com sucesso")

    # Datas
    date_to = datetime.now().strftime("%Y-%m-%d")
    date_from = (datetime.now() - timedelta(days=args.days)).strftime("%Y-%m-%d")

    # Sync dimensões
    gestor_map = sync_gestores(conn)

    if args.only != "perf":
        tasks = cached_cu_tasks(LIST_COPY, include_closed=True, ttl=1800, force=True)
        pessoa_map = sync_pessoas(conn, tasks)

    # ETL módulos
    if args.only != "prod":
        etl_performance(conn, date_from, date_to, gestor_map)

    if args.only != "perf":
        etl_producao(conn, pessoa_map)

    # Refresh views
    try:
        refresh_views(conn)
    except Exception as e:
        print(f"[VIEWS] Erro ao atualizar views (pode ser primeira execução): {e}")
        conn.rollback()

    conn.close()
    print(f"[ETL] Concluído: {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    main()
