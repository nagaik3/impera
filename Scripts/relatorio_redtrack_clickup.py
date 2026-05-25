#!/usr/bin/env python3
"""
Relatório Redtrack → ClickUp Chat View
Migração de .docx para posts consolidados em ClickUp.

Análise semanal de performance: ofertas, nichos, gestores.
Crontab: domingo 12:07

GPDR — Iago Almeida | Assistido por Claude — Anthropic
"""

import json
import os
import re
import subprocess
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta

sys.path.insert(0, os.path.expanduser("~/Scripts"))
try:
    from cruzamento_clickup_redtrack import (
        parse_campaign_name, fetch_redtrack_campaigns, GESTOR_MAP,
    )
except:
    pass

API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
REDTRACK_KEY = os.environ.get("REDTRACK_API_KEY", "")
CLICKUP_CHAT_VIEW = "8cm1w4b-9933"  # Chat View dedicado para Redtrack

LOG_DIR = os.path.expanduser("~/Scripts/logs")

NICHO_NAMES = {
    'EM': 'Emagrecimento',
    'DB': 'Diabetes',
    'NE': 'Neuropatia',
    'MM': 'Memória BR',
    'ME': 'Memória EUA',
    'PT': 'Próstata',
    'DA': 'Dores Articulares',
    'ED': 'Adulto/ED',
    'ZB': 'Zumbido',
    'VS': 'VSL',
}


def log(msg):
    """Log com timestamp."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def post_clickup(message):
    """Posta mensagem no ClickUp Chat View."""
    if not message or not CLICKUP_CHAT_VIEW:
        return False

    try:
        cmd = [
            "curl", "-s", "-X", "POST",
            f"https://api.clickup.com/api/v2/view/{CLICKUP_CHAT_VIEW}/comment",
            "-H", f"Authorization: {API_TOKEN}",
            "-H", "Content-Type: application/json",
            "-d", json.dumps({"comment_text": message})
        ]
        result = subprocess.run(cmd, timeout=10, capture_output=True, text=True)
        if result.returncode == 0:
            log("✓ Relatório postado em ClickUp")
            return True
        else:
            log(f"✗ Erro ao postar: {result.stderr}")
            return False
    except Exception as e:
        log(f"✗ Erro: {e}")
        return False


def get_week_dates():
    """Retorna data_from e data_to para última semana completa (seg-dom)."""
    today = datetime.now()
    # Segunda da semana anterior
    days_since_monday = today.weekday()
    last_monday = today - timedelta(days=days_since_monday + 7)
    last_sunday = last_monday + timedelta(days=6)

    return last_monday.strftime("%Y-%m-%d"), last_sunday.strftime("%Y-%m-%d")


def fetch_redtrack_data(date_from, date_to):
    """Fetch RedTrack data using cruzamento_clickup_redtrack."""
    try:
        campaigns = fetch_redtrack_campaigns(date_from, date_to)
        return campaigns or []
    except Exception as e:
        log(f"Erro ao buscar RedTrack: {e}")
        return []


def classify_offer(roas, vendas, cpa):
    """Classificação Super Cérebro V5."""
    if vendas >= 30 and roas >= 1.8:
        return "🏆 Escala"
    elif vendas >= 10 and cpa <= 180 and roas >= 1.8:
        return "✅ Validado"
    elif vendas >= 3 and cpa <= 180 and roas >= 1.8:
        return "🟡 Pré-validado"
    elif roas < 1.0:
        return "🔴 Negativa"
    else:
        return "🔵 Em Teste"


def analyze_offers(campaigns):
    """Agrupa e analisa ofertas."""
    ofertas = defaultdict(lambda: {
        "cost": 0,
        "revenue": 0,
        "vendas": 0,
        "campanhas": 0,
        "nichos": set(),
    })

    for c in campaigns:
        parsed = parse_campaign_name(c.get("campaign", ""))
        nicho = parsed.get("nicho", "?")
        oferta = parsed.get("oferta", "?")

        if not nicho or nicho == "?":
            continue

        key = f"{nicho} | {oferta}"
        cost = float(c.get("cost", 0))
        rev = float(c.get("revenuetype2", 0)) + float(c.get("revenuetype3", 0))
        vendas = int(c.get("convtype1", 0))

        ofertas[key]["cost"] += cost
        ofertas[key]["revenue"] += rev
        ofertas[key]["vendas"] += vendas
        ofertas[key]["campanhas"] += 1
        ofertas[key]["nichos"].add(nicho)

    return ofertas


def analyze_gestores(campaigns):
    """Agrupa e analisa gestores."""
    gestores = defaultdict(lambda: {
        "cost": 0,
        "revenue": 0,
        "vendas": 0,
        "campanhas": 0,
        "nichos": set(),
    })

    for c in campaigns:
        parsed = parse_campaign_name(c.get("campaign", ""))
        gestor = parsed.get("gestor", "?")

        if not gestor or gestor == "?":
            continue

        cost = float(c.get("cost", 0))
        rev = float(c.get("revenuetype2", 0)) + float(c.get("revenuetype3", 0))
        vendas = int(c.get("convtype1", 0))

        gestores[gestor]["cost"] += cost
        gestores[gestor]["revenue"] += rev
        gestores[gestor]["vendas"] += vendas
        gestores[gestor]["campanhas"] += 1
        if parsed.get("nicho"):
            gestores[gestor]["nichos"].add(parsed["nicho"])

    return gestores


def build_report(date_from, date_to, curr_campaigns, prev_campaigns):
    """Constrói relatório consolidado para ClickUp."""

    # Análise atual
    curr_ofertas = analyze_offers(curr_campaigns)
    curr_gestores = analyze_gestores(curr_campaigns)

    # Análise anterior (para comparativo)
    prev_ofertas = analyze_offers(prev_campaigns) if prev_campaigns else {}
    prev_gestores = analyze_gestores(prev_campaigns) if prev_campaigns else {}

    # Totais
    curr_cost = sum(o["cost"] for o in curr_ofertas.values())
    curr_rev = sum(o["revenue"] for o in curr_ofertas.values())
    curr_roas = curr_rev / curr_cost if curr_cost > 0 else 0

    prev_cost = sum(o["cost"] for o in prev_ofertas.values())
    prev_rev = sum(o["revenue"] for o in prev_ofertas.values())
    prev_roas = prev_rev / prev_cost if prev_cost > 0 else 0

    date_from_fmt = datetime.strptime(date_from, "%Y-%m-%d").strftime("%d/%m")
    date_to_fmt = datetime.strptime(date_to, "%Y-%m-%d").strftime("%d/%m")

    lines = [
        f"📊 RELATÓRIO REDTRACK — {date_from_fmt} a {date_to_fmt}",
        f"",
        f"💰 TOTAIS",
        f"Receita: R${curr_rev:,.0f} | Custo: R${curr_cost:,.0f} | ROAS: {curr_roas:.2f}",
        f"vs semana anterior: ROAS {prev_roas:.2f} ({curr_roas-prev_roas:+.2f})",
        f"",
    ]

    # Top ofertas
    lines.append("🎯 TOP OFERTAS")
    sorted_ofertas = sorted(
        curr_ofertas.items(),
        key=lambda x: x[1]["revenue"],
        reverse=True
    )
    for i, (key, data) in enumerate(sorted_ofertas[:8], 1):
        if data["cost"] < 50:
            continue
        roas = data["revenue"] / data["cost"] if data["cost"] > 0 else 0
        cpa = data["cost"] / data["vendas"] if data["vendas"] > 0 else 0
        status = classify_offer(roas, data["vendas"], cpa)
        lines.append(f"{i}. {status} {key}")
        lines.append(f"   R$: {data['revenue']:,.0f} | Custo: {data['cost']:,.0f} | ROAS: {roas:.2f} | Vendas: {data['vendas']}")
    lines.append("")

    # Top gestores
    lines.append("👥 TOP GESTORES")
    sorted_gestores = sorted(
        curr_gestores.items(),
        key=lambda x: x[1]["revenue"],
        reverse=True
    )
    for i, (gestor, data) in enumerate(sorted_gestores[:5], 1):
        if data["cost"] < 50:
            continue
        roas = data["revenue"] / data["cost"] if data["cost"] > 0 else 0
        nichos = ", ".join(sorted(data["nichos"]))[:40]
        lines.append(f"{i}. {gestor} ({data['campanhas']} camps)")
        lines.append(f"   R$: {data['revenue']:,.0f} | Custo: {data['cost']:,.0f} | ROAS: {roas:.2f}")
        lines.append(f"   Nichos: {nichos}")
    lines.append("")

    # Ofertas negativas
    lines.append("⚠️ ATENÇÃO (ROAS < 1.0)")
    negatives = [
        (k, v) for k, v in curr_ofertas.items()
        if v["cost"] >= 50 and (v["revenue"] / v["cost"] if v["cost"] > 0 else 0) < 1.0
    ]
    if negatives:
        for key, data in negatives[:5]:
            roas = data["revenue"] / data["cost"] if data["cost"] > 0 else 0
            lines.append(f"🔴 {key}: ROAS {roas:.2f} | Gasto: R${data['cost']:,.0f}")
    else:
        lines.append("✅ Nenhuma oferta com ROAS negativa")

    return "\n".join(lines)


def main():
    """Executa relatório semanal."""
    log("Iniciando relatório Redtrack...")

    # Datas
    date_from, date_to = get_week_dates()
    log(f"Período: {date_from} a {date_to}")

    # Dados atuais
    campaigns = fetch_redtrack_data(date_from, date_to)
    if not campaigns:
        log("⚠️ Nenhum dado RedTrack retornado")
        return False

    # Dados da semana anterior (para comparativo)
    prev_sunday = datetime.strptime(date_from, "%Y-%m-%d") - timedelta(days=7)
    prev_monday = prev_sunday - timedelta(days=6)
    prev_date_from = prev_monday.strftime("%Y-%m-%d")
    prev_date_to = prev_sunday.strftime("%Y-%m-%d")
    prev_campaigns = fetch_redtrack_data(prev_date_from, prev_date_to)

    # Build report
    report = build_report(date_from, date_to, campaigns, prev_campaigns)

    # Post
    success = post_clickup(report)

    if success:
        log(f"✓ Relatório gerado com sucesso")
        return True
    else:
        log(f"✗ Erro ao postar relatório")
        return False


if __name__ == "__main__":
    os.makedirs(LOG_DIR, exist_ok=True)

    if not API_TOKEN or not REDTRACK_KEY:
        log("ERRO: CLICKUP_API_TOKEN ou REDTRACK_API_KEY não definido.")
        sys.exit(1)

    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        log(f"ERRO FATAL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
