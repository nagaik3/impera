#!/usr/bin/env python3
"""
GPDR — Visão Executiva
Consolidação estratégica de todos os setores para decisão executiva
Modelo: Consultivo (dados AUTO + narrativa manual de Iago)

Cron: Domingo 23:00

Uso:
  python3 relatorio_gpdr_executiva.py          # Gera e posta no Chat View
  python3 relatorio_gpdr_executiva.py --preview # Apenas preview, sem postar

GPDR — Iago Almeida | Assistido por Claude — Anthropic
"""

import os
import sys
import json
import subprocess
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.expanduser("~/Scripts"))

from impera_cache import cached_cu_tasks, cached_rt_ads
from impera_utils import classify_task, normalize_person_name, get_cf_value, detect_nicho
from cruzamento_clickup_redtrack import (
    fetch_redtrack_campaigns, parse_campaign_name, COPY_LIST, TRAFEGO_LIST,
)
from relatorio_copy_semanal import fetch_redtrack_with_copywriter

API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
CLICKUP_CHAT_VIEW = "8cm1w4b-9993"

ROAS_META = 1.58
ROAS_VALIDACAO = 1.8
CPA_MAX = 180
VENDAS_VALIDACAO_MIN = 3


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def post_clickup(message):
    if not message or not CLICKUP_CHAT_VIEW or not API_TOKEN:
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
        return result.returncode == 0
    except:
        return False


def get_monday_to_sunday():
    """Retorna período segunda-domingo."""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    days_since_monday = today.weekday()
    monday = today - timedelta(days=days_since_monday)
    sunday = monday + timedelta(days=6)
    return monday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d")


def parse_timestamp(ts):
    """Parse timestamp em múltiplos formatos."""
    if ts is None:
        return None
    try:
        if isinstance(ts, (int, float)) or (isinstance(ts, str) and ts.isdigit()):
            ts_num = int(ts)
            if ts_num > 1000000000:
                return datetime.fromtimestamp(ts_num / 1000)
            else:
                return datetime.fromtimestamp(ts_num)
        else:
            return datetime.fromisoformat(str(ts)[:10])
    except:
        return None


def build_health_score(campaigns, copy_data, edicao_data):
    """Calcula score de saúde por setor (0-5)."""
    scores = {}

    # Copy Health
    if copy_data:
        total_volume = sum(d["volume"] for d in copy_data.values())
        assertividade = sum(d.get("assertivos", 0) for d in copy_data.values()) / max(total_volume, 1) * 100
        copy_score = min(5, max(0, (assertividade / 20)))  # 0% = 0 stars, 100% = 5 stars
        scores["copy"] = copy_score
    else:
        scores["copy"] = 3

    # Edição Health
    if edicao_data:
        total_enviados = sum(d["total"] for d in edicao_data.values())
        sem_alteracao = sum(d.get("sem_alteracao", 0) for d in edicao_data.values())
        edicao_score = min(5, max(0, (sem_alteracao / max(total_enviados, 1) * 100 / 20)))
        scores["edicao"] = edicao_score
    else:
        scores["edicao"] = 3

    # Tráfego Health (ROAS)
    if campaigns:
        total_fat = sum(float(c.get("revenuetype2", 0)) + float(c.get("revenuetype3", 0)) for c in campaigns)
        total_custo = sum(float(c.get("cost", 0)) for c in campaigns)
        roas = total_fat / max(total_custo, 1)

        # Score baseado em ROAS (1.58 = 3 stars, 2.0+ = 5 stars)
        if roas >= 2.0:
            trafego_score = 5
        elif roas >= ROAS_META:
            trafego_score = 3 + (roas - ROAS_META) / (2.0 - ROAS_META) * 2
        else:
            trafego_score = max(0, 1 + (roas / ROAS_META) * 2)

        scores["trafego"] = trafego_score
    else:
        scores["trafego"] = 3

    return scores


def stars(score):
    """Converte score (0-5) para estrelas."""
    full = int(score)
    half = 1 if (score - full) >= 0.5 else 0
    return "●" * full + ("◐" if half else "") + "○" * (5 - full - half)


def build_alertas_criticos(campaigns, trafego_data):
    """Identifica alertas críticos."""
    alertas = []

    # ROAS abaixo da meta
    total_fat = sum(float(c.get("revenuetype2", 0)) + float(c.get("revenuetype3", 0)) for c in campaigns)
    total_custo = sum(float(c.get("cost", 0)) for c in campaigns)
    roas_geral = total_fat / max(total_custo, 1)

    if roas_geral < ROAS_META:
        alertas.append(f"🔴 ROAS Front ({roas_geral:.2f}x) abaixo da meta {ROAS_META}x — empresa em prejuízo")

    # Gestores com ROAS crítico
    for gestor, data in trafego_data.items():
        roas_gestor = data["faturamento"] / max(data["custo"], 1)
        if roas_gestor < 1.0:
            alertas.append(f"🔴 {gestor}: ROAS {roas_gestor:.2f}x — crítico (negativo)")
        elif roas_gestor < ROAS_META:
            alertas.append(f"⚠️ {gestor}: ROAS {roas_gestor:.2f}x — abaixo da meta")

    return alertas


def build_report(date_from, date_to):
    """Gera relatório GPDR Executiva."""
    log(f"Gerando relatório GPDR Executiva para {date_from} a {date_to}")

    campaigns = fetch_redtrack_campaigns(date_from, date_to)
    tasks = cached_cu_tasks(COPY_LIST, include_closed=True)

    # Agregar dados por setor
    copy_data = defaultdict(lambda: {"volume": 0, "assertivos": 0})
    edicao_data = defaultdict(lambda: {"total": 0, "sem_alteracao": 0})
    trafego_data = defaultdict(lambda: {"faturamento": 0.0, "custo": 0.0})

    date_from_obj = datetime.fromisoformat(date_from)
    date_to_obj = datetime.fromisoformat(date_to)

    # Copy
    for t in tasks:
        try:
            created = parse_timestamp(t.get("date_created"))
            if created and date_from_obj <= created <= date_to_obj:
                cw = normalize_person_name(get_cf_value(t, "copywritter") or "Desconhecido")
                cat, qtd, _, _, _ = classify_task(t.get("name", ""))
                copy_data[cw]["volume"] += qtd
        except:
            pass

    # Tráfego
    for c in campaigns:
        try:
            gestor = c.get("gestor", "Sem gestor")
            faturamento = float(c.get("revenuetype2", 0)) + float(c.get("revenuetype3", 0))
            custo = float(c.get("cost", 0))
            trafego_data[gestor]["faturamento"] += faturamento
            trafego_data[gestor]["custo"] += custo
        except:
            pass

    # Health scores
    health_scores = build_health_score(campaigns, dict(copy_data), dict(edicao_data))
    alertas = build_alertas_criticos(campaigns, dict(trafego_data))

    report = []
    report.append("📊 GPDR — VISÃO EXECUTIVA\n")
    report.append(f"**Período**: {date_from} a {date_to}")
    report.append(f"**Responsável**: Iago Almeida")
    report.append(f"**Status**: Consultivo (narrativa manual de Iago)\n")

    # Score de Saúde
    report.append("## 1️⃣ Score de Saúde por Departamento\n")
    report.append("| Departamento | Saúde |")
    report.append("|--------------|-------|")
    report.append(f"| **Copy** | {stars(health_scores['copy'])} ({health_scores['copy']:.1f}/5) |")
    report.append(f"| **Edição** | {stars(health_scores['edicao'])} ({health_scores['edicao']:.1f}/5) |")
    report.append(f"| **Tráfego** | {stars(health_scores['trafego'])} ({health_scores['trafego']:.1f}/5) |\n")

    # Alertas Críticos
    if alertas:
        report.append("## 2️⃣ Alertas Críticos\n")
        for alerta in alertas:
            report.append(f"- {alerta}")
        report.append("")
    else:
        report.append("## 2️⃣ Alertas Críticos\n")
        report.append("✅ Nenhum alerta crítico detectado\n")

    # KPIs Consolidados
    report.append("## 3️⃣ KPIs Consolidados\n")
    report.append("| Setor | Métrica | Valor |")
    report.append("|-------|---------|-------|")

    total_copy_volume = sum(d["volume"] for d in copy_data.values())
    total_fat = sum(d["faturamento"] for d in trafego_data.values())
    total_custo = sum(d["custo"] for d in trafego_data.values())
    total_roas = total_fat / max(total_custo, 1)
    total_vendas = sum(int(c.get("convtype1", 0)) for c in campaigns)

    report.append(f"| **Copy** | Volume Total | {total_copy_volume} criativos |")
    report.append(f"| **Tráfego** | Faturamento Front | R${total_fat:,.0f} |")
    report.append(f"| **Tráfego** | ROAS Front | {total_roas:.2f}x |")
    report.append(f"| **Tráfego** | Vendas | {total_vendas:,} |\n")

    # Faturamento por Copywriter (using new registry-based attribution)
    report.append("## 3️⃣A Faturamento por Copywriter\n")
    campaigns_with_cw = fetch_redtrack_with_copywriter(date_from, date_to)
    fat_por_cw = defaultdict(lambda: {"faturamento": 0.0, "confidence": 0.0, "count": 0})

    for c in campaigns_with_cw:
        try:
            cw = c.get("copywriter_name", "Desconhecido")
            faturamento = float(c.get("revenuetype2", 0)) + float(c.get("revenuetype3", 0))
            confidence = float(c.get("confidence", 0.0))
            fat_por_cw[cw]["faturamento"] += faturamento
            fat_por_cw[cw]["confidence"] = max(fat_por_cw[cw]["confidence"], confidence)
            fat_por_cw[cw]["count"] += 1
        except:
            pass

    if fat_por_cw:
        report.append("| Copywriter | Faturamento | % | Confiança |")
        report.append("|-------------|-------------|---|-----------|")
        total_fat_cw = sum(d["faturamento"] for d in fat_por_cw.values())
        for cw in sorted(fat_por_cw.keys(), key=lambda x: fat_por_cw[x]["faturamento"], reverse=True):
            fat = fat_por_cw[cw]["faturamento"]
            pct = 100 * fat / max(total_fat_cw, 1)
            conf = fat_por_cw[cw]["confidence"]
            report.append(f"| **{cw}** | R${fat:,.0f} | {pct:.1f}% | {conf:.0%} |")
        report.append("")

    # Comparativo Anterior
    report.append("## 4️⃣ Comparativo Semana Anterior\n")
    report.append("| Métrica | Semana Anterior | Atual | Delta |")
    report.append("|---------|-----------------|-------|-------|")
    report.append("| Faturamento Front | _dados não disponíveis_ | R${:,.0f} | — |".format(total_fat))
    report.append("| Volume Copy | _dados não disponíveis_ | {} | — |\n".format(total_copy_volume))

    # Campos Manuais
    report.append("## 5️⃣ Análise Estratégica (Preencher Iago)\n")
    report.append("**O que funcionou bem?**\n")
    report.append("_[Iago, quais foram os destaques da semana?]_\n")
    report.append("**Principais gargalos?**\n")
    report.append("_[Iago, o que limitou o resultado?]_\n")
    report.append("**Ações para curto-médio prazo?**\n")
    report.append("_[Iago, qual é o plano de ação?]_\n")

    # Necessidades CEO
    report.append("## 6️⃣ Necessidades CEO (Preencher Iago)\n")
    report.append("**O que está faltando?**\n")
    report.append("_[Iago, existem recursos/decisões bloqueando a operação?]_\n")
    report.append("**Decisões necessárias?**\n")
    report.append("_[Iago, quais decisões executivas são urgentes?]_\n")

    # Próximas Prioridades
    report.append("## 7️⃣ Próximas Prioridades (Preencher Iago)\n")
    report.append("_[Iago, qual é o foco da próxima semana?]_\n")

    # Glossário
    report.append("---\n")
    report.append("## 📋 GLOSSÁRIO — Definições de Métricas\n")
    report.append("**Score de Saúde**: Avaliação 0-5 estrelas por departamento baseada em KPIs críticos")
    report.append("\n  - Copy: baseado em assertividade (% que atingiram Pré-validado+)")
    report.append("\n  - Edição: baseado em assertividade (% sem alterações)")
    report.append("\n  - Tráfego: baseado em ROAS Front")
    report.append("\n**ROAS Front**: (revenuetype2 + revenuetype3) / cost — retorno sobre investimento")
    report.append("\n**ROAS Meta (Saúde Executiva)**: 1.58 — abaixo disso, empresa em prejuízo")
    report.append("\n**Assertividade Copy**: % de criativos que atingiram Pré-validado+ (≥3 vendas, CPA ≤ R$180, ROAS ≥ 1.8)")
    report.append("\n**Assertividade Edição**: % de criativos sem revisão (campo 'Teve alteração?' não marcado)")
    report.append("\n**Volume Copy**: Total de criativos criados no período")
    report.append("\n**Faturamento Front**: Receita de frente (revenuetype2 + revenuetype3)")
    report.append("\n**Vendas**: convtype1 (conversões do tipo 1)")

    return "\n".join(report)


def main():
    date_from, date_to = get_monday_to_sunday()
    report = build_report(date_from, date_to)

    if "--preview" in sys.argv:
        print(report)
        log("Preview mode — relatório não foi postado")
    else:
        if post_clickup(report):
            log("✅ Relatório GPDR Executiva postado com sucesso")
        else:
            log("❌ Erro ao postar relatório GPDR Executiva")
            print(report)


if __name__ == "__main__":
    main()
