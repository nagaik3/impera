#!/usr/bin/env python3
"""
TRÁFEGO — Relatório Semanal
Setor: Gestão de Tráfego (Head: Douglas)
Modelo: Consultivo (dados AUTO + campos MANUAIS para validação)

Cron: Domingo 23:00

Uso:
  python3 relatorio_trafego_semanal.py          # Gera e posta no Chat View
  python3 relatorio_trafego_semanal.py --preview # Apenas preview, sem postar

GPDR — Iago Almeida | Assistido por Claude — Anthropic
"""

import os
import sys
import json
import subprocess
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.expanduser("~/Scripts"))

from cruzamento_clickup_redtrack import fetch_redtrack_campaigns, parse_campaign_name
from impera_utils import normalize_person_name
from impera_cache import cached_cu_tasks
from cruzamento_clickup_redtrack import COPY_LIST
from relatorio_copy_semanal import fetch_redtrack_with_copywriter

API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
REDTRACK_KEY = os.environ.get("REDTRACK_API_KEY", "")
CLICKUP_CHAT_VIEW = "8cm1w4b-9993"

ROAS_META = 1.58
ROAS_VALIDACAO = 1.8
INVESTIMENTO_ESCALA_MIN = 5000


def fetch_redtrack_with_gestor(date_from, date_to):
    """Busca campanhas do RedTrack com copywriter e extrai gestor.

    Agora usa fetch_redtrack_with_copywriter que cruza com AD Registry,
    garantindo que copywriter_name está preenchido com dados reais.
    """
    campaigns = fetch_redtrack_with_copywriter(date_from, date_to)

    # Extrai gestor do nome da campanha
    for c in campaigns:
        campaign_name = c.get("campaign", "")
        # Parse gestor do nome da campanha
        parsed = parse_campaign_name(campaign_name)
        c["gestor"] = parsed.get("gestor", "Sem gestor")

    return campaigns


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


def build_trafego_data(campaigns):
    """Agrega dados de tráfego por gestor."""
    by_gestor = defaultdict(lambda: {
        "faturamento": 0.0, "custo": 0.0, "vendas": 0, "campanhas": 0,
        "em_teste": 0, "pré_escala": 0, "validado": 0, "escala": 0, "em_risco": 0, "negativo": 0
    })

    for c in campaigns:
        try:
            gestor = c.get("gestor", "Sem gestor")
            faturamento = float(c.get("revenuetype2", 0)) + float(c.get("revenuetype3", 0))
            custo = float(c.get("cost", 0))
            vendas = int(c.get("convtype1", 0))
            roas = faturamento / custo if custo > 0 else 0

            by_gestor[gestor]["faturamento"] += faturamento
            by_gestor[gestor]["custo"] += custo
            by_gestor[gestor]["vendas"] += vendas
            by_gestor[gestor]["campanhas"] += 1

            # Status
            if custo < 500 or roas < 1.5:
                by_gestor[gestor]["em_teste"] += 1
            elif vendas >= 3 and custo >= 2000 and roas >= 1.5:
                by_gestor[gestor]["pré_escala"] += 1
            elif vendas >= 10 and roas >= 1.8:
                by_gestor[gestor]["validado"] += 1
            elif custo >= INVESTIMENTO_ESCALA_MIN and roas >= ROAS_VALIDACAO:
                by_gestor[gestor]["escala"] += 1
            elif custo >= 200 and roas < 1.0:
                by_gestor[gestor]["em_risco"] += 1
            elif custo >= 500 and vendas == 0:
                by_gestor[gestor]["negativo"] += 1
        except:
            pass

    return dict(by_gestor)


def build_faturamento_por_copywriter(campaigns):
    """Agrega faturamento por copywriter."""
    by_cw = defaultdict(lambda: {
        "faturamento": 0.0, "custo": 0.0, "vendas": 0, "campanhas": 0,
        "confidence": 0.0, "confidence_count": 0
    })

    for c in campaigns:
        try:
            cw = c.get("copywriter_name", "Desconhecido")
            faturamento = float(c.get("revenuetype2", 0)) + float(c.get("revenuetype3", 0))
            custo = float(c.get("cost", 0))
            vendas = int(c.get("convtype1", 0))
            confidence = float(c.get("confidence", 0.0))

            by_cw[cw]["faturamento"] += faturamento
            by_cw[cw]["custo"] += custo
            by_cw[cw]["vendas"] += vendas
            by_cw[cw]["campanhas"] += 1
            by_cw[cw]["confidence_sum"] = by_cw[cw].get("confidence_sum", 0) + confidence
            by_cw[cw]["confidence_count"] += 1
        except:
            pass

    # Calcular confiança média
    for cw in by_cw:
        if by_cw[cw]["confidence_count"] > 0:
            by_cw[cw]["confidence"] = by_cw[cw]["confidence_sum"] / by_cw[cw]["confidence_count"]

    return dict(by_cw)


def build_top_campanhas_por_gestor(campaigns):
    """Top 3-5 campanhas por gestor."""
    by_gestor = defaultdict(list)

    for c in campaigns:
        try:
            gestor = c.get("gestor", "Sem gestor")
            faturamento = float(c.get("revenuetype2", 0)) + float(c.get("revenuetype3", 0))
            custo = float(c.get("cost", 0))
            roas = faturamento / custo if custo > 0 else 0

            by_gestor[gestor].append({
                "campaign": c.get("campaign", "").split("|")[0].strip(),
                "faturamento": faturamento,
                "roas": roas,
                "custo": custo,
                "vendas": int(c.get("convtype1", 0))
            })
        except:
            pass

    result = {}
    for gestor, camps in by_gestor.items():
        sorted_camps = sorted(camps, key=lambda x: x["faturamento"], reverse=True)[:5]
        result[gestor] = sorted_camps

    return result


def build_status_nichos(campaigns):
    """Status dos nichos por faturamento."""
    by_nicho = defaultdict(lambda: {
        "faturamento": 0.0, "custo": 0.0, "roas": 0.0, "campanhas": 0,
        "brasil": False, "usa": False
    })

    for c in campaigns:
        try:
            faturamento = float(c.get("revenuetype2", 0)) + float(c.get("revenuetype3", 0))
            custo = float(c.get("cost", 0))
            roas = faturamento / custo if custo > 0 else 0

            parsed = parse_campaign_name(c.get("campaign", ""))
            nicho = parsed.get("nicho", "desconhecido")
            mercado = parsed.get("mercado", "BR").upper()

            by_nicho[nicho]["faturamento"] += faturamento
            by_nicho[nicho]["custo"] += custo
            by_nicho[nicho]["campanhas"] += 1

            if mercado == "BR" or "BR" in str(mercado):
                by_nicho[nicho]["brasil"] = True
            if "USA" in str(mercado) or "EUA" in str(mercado):
                by_nicho[nicho]["usa"] = True
        except:
            pass

    # Recalcular ROAS por nicho
    for nicho in by_nicho:
        if by_nicho[nicho]["custo"] > 0:
            by_nicho[nicho]["roas"] = by_nicho[nicho]["faturamento"] / by_nicho[nicho]["custo"]

    return dict(sorted(by_nicho.items(), key=lambda x: x[1]["faturamento"], reverse=True)[:5])


def build_ofertas_em_escala(campaigns):
    """Ofertas com investimento >= R$5.000 e performance ok."""
    escala = []

    for c in campaigns:
        try:
            custo = float(c.get("cost", 0))
            faturamento = float(c.get("revenuetype2", 0)) + float(c.get("revenuetype3", 0))

            if custo >= INVESTIMENTO_ESCALA_MIN:
                roas = faturamento / custo if custo > 0 else 0
                escala.append({
                    "campaign": c.get("campaign", "").split("|")[0].strip(),
                    "faturamento": faturamento,
                    "custo": custo,
                    "roas": roas,
                    "vendas": int(c.get("convtype1", 0))
                })
        except:
            pass

    return sorted(escala, key=lambda x: x["faturamento"], reverse=True)


def build_report(date_from, date_to):
    """Gera relatório completo de Tráfego."""
    log(f"Gerando relatório Tráfego para {date_from} a {date_to}")

    campaigns = fetch_redtrack_with_gestor(date_from, date_to)
    trafego_data = build_trafego_data(campaigns)
    top_campanhas = build_top_campanhas_por_gestor(campaigns)
    status_nichos = build_status_nichos(campaigns)
    ofertas_escala = build_ofertas_em_escala(campaigns)
    fat_por_cw = build_faturamento_por_copywriter(campaigns)

    report = []
    report.append("📈 TRÁFEGO — RELATÓRIO SEMANAL\n")
    report.append(f"**Período**: {date_from} a {date_to}")
    report.append(f"**Responsável**: Douglas")
    report.append(f"**Meta ROAS**: 1.58")
    report.append(f"**Status**: Consultivo (validar dados com head)\n")

    # KPIs Críticos
    report.append("## 1️⃣ KPIs Críticos\n")
    report.append("| Métrica | Valor |")
    report.append("|---------|-------|")

    total_fat = sum(d["faturamento"] for d in trafego_data.values())
    total_custo = sum(d["custo"] for d in trafego_data.values())
    total_roas = total_fat / max(total_custo, 1)
    total_vendas = sum(d["vendas"] for d in trafego_data.values())

    health_status = "✅" if total_roas >= ROAS_META else "⚠️"

    report.append(f"| **Faturamento Front** | R${total_fat:,.0f} |")
    report.append(f"| **ROAS Front** | {total_roas:.2f}x {health_status} |")
    report.append(f"| **Volume de Vendas** | {total_vendas:,} |")
    report.append(f"| **Total de Campanhas** | {len(campaigns)} |\n")

    # Performance por Gestor
    report.append("## 2️⃣ Performance por Gestor\n")
    report.append("| Gestor | Faturamento | ROAS | Campanhas | Vendas | Top 3 Campanhas |")
    report.append("|--------|-------------|------|-----------|--------|-----------------|")

    for gestor in sorted(trafego_data.keys(), key=lambda x: trafego_data[x]["faturamento"], reverse=True):
        data = trafego_data[gestor]
        roas_gestor = data["faturamento"] / max(data["custo"], 1)
        top3 = ", ".join([c["campaign"][:20] for c in top_campanhas.get(gestor, [])[:3]])

        report.append(
            f"| {gestor} | R${data['faturamento']:,.0f} | {roas_gestor:.2f}x | {data['campanhas']} | {data['vendas']:,} | {top3} |"
        )

    report.append("")

    # Faturamento por Copywriter
    report.append("## 2️⃣A Faturamento Rastreável por Copywriter\n")
    if fat_por_cw:
        report.append("| Copywriter | Faturamento | % | ROAS | Confiança |")
        report.append("|------------|-------------|---|------|-----------|")
        total_fat_cw = sum(d["faturamento"] for d in fat_por_cw.values())
        for cw in sorted(fat_por_cw.keys(), key=lambda x: fat_por_cw[x]["faturamento"], reverse=True):
            data = fat_por_cw[cw]
            fat = data["faturamento"]
            pct = 100 * fat / max(total_fat_cw, 1)
            roas = fat / max(data["custo"], 1) if data["custo"] > 0 else 0
            conf = data["confidence"]
            report.append(f"| **{cw}** | R${fat:,.0f} | {pct:.1f}% | {roas:.2f}x | {conf:.0%} |")
    else:
        report.append("_Sem dados de copywriter rastreáveis_")

    report.append("")

    # Ofertas em Escala
    report.append("## 3️⃣ Ofertas em Escala (≥ R$5.000)\n")
    if ofertas_escala:
        report.append("| Oferta | Faturamento | ROAS | Custo | Vendas |")
        report.append("|--------|-------------|------|-------|--------|")
        for of in ofertas_escala[:10]:
            report.append(f"| {of['campaign'][:30]} | R${of['faturamento']:,.0f} | {of['roas']:.2f}x | R${of['custo']:,.0f} | {of['vendas']:,} |")
    else:
        report.append("_Sem ofertas em escala (≥ R$5.000) neste período_")

    report.append("")

    # Status de Nichos
    report.append("## 4️⃣ Top 5 Nichos por Faturamento\n")
    report.append("| Nicho | Faturamento | ROAS | Campanhas | Brasil | EUA |")
    report.append("|-------|-------------|------|-----------|--------|-----|")

    for nicho, data in status_nichos.items():
        br = "✅" if data["brasil"] else "❌"
        usa = "✅" if data["usa"] else "❌"
        report.append(f"| {nicho} | R${data['faturamento']:,.0f} | {data['roas']:.2f}x | {data['campanhas']} | {br} | {usa} |")

    report.append("")

    # Campos Manuais
    report.append("## 5️⃣ Análise Estratégica (Preencher com Douglas)\n")
    report.append("**Ofertas em Escala - Análise:**\n")
    report.append("_[Douglas, qual é a situação das ofertas em escala? Estão saudáveis?]_\n")
    report.append("**Gargalos Identificados:**\n")
    report.append("_[Douglas, existem nichos/ofertas travadas? Limitações operacionais?]_\n")
    report.append("**Recomendações:**\n")
    report.append("_[Douglas, qual é o foco para a próxima semana?]_\n")

    # Glossário
    report.append("---\n")
    report.append("## 📋 GLOSSÁRIO — Definições de Métricas\n")
    report.append("**Faturamento Front**: revenuetype2 + revenuetype3 (receita de frente)")
    report.append("\n**ROAS Front**: Faturamento Front / Custo (retorno de investimento)")
    report.append("\n**ROAS Meta (Saúde Executiva)**: 1.58 — abaixo disso a empresa está em prejuízo")
    report.append("\n**ROAS Validação (Criativos)**: 1.8 — threshold para criativo alcançar 'validado' ou 'escala'")
    report.append("\n**Ofertas em Escala**: Campanhas com investimento ≥ R$5.000 (comprovam volume sustentável)")
    report.append("\n**Em Teste**: Custo < R$500 ou ROAS < 1.5")
    report.append("\n**Pré-Escala**: 3+ vendas, Custo ≥ R$2.000, ROAS ≥ 1.5")
    report.append("\n**Validado**: 10+ vendas, ROAS ≥ 1.8")
    report.append("\n**Escala**: Custo ≥ R$5.000, ROAS ≥ 1.8")
    report.append("\n**Em Risco**: Custo ≥ R$200, ROAS < 1.0")
    report.append("\n**Negativo**: Custo ≥ R$500, 0 vendas OU ROAS < 1.0")

    return "\n".join(report)


def main():
    date_from, date_to = get_monday_to_sunday()
    report = build_report(date_from, date_to)

    if "--preview" in sys.argv:
        print(report)
        log("Preview mode — relatório não foi postado")
    else:
        if post_clickup(report):
            log("✅ Relatório Tráfego postado com sucesso")
        else:
            log("❌ Erro ao postar relatório Tráfego")
            print(report)


if __name__ == "__main__":
    main()
