#!/usr/bin/env python3
"""
COPY — Relatório Semanal
Setor: Copy (Head: Elias)
Modelo: Consultivo (dados AUTO + campos MANUAIS para validação)

Cron: Domingo 23:00

Uso:
  python3 relatorio_copy_semanal.py          # Gera e posta no Chat View
  python3 relatorio_copy_semanal.py --preview # Apenas preview, sem postar

GPDR — Iago Almeida | Assistido por Claude — Anthropic
"""

import os
import sys
import json
import subprocess
import urllib.request
import re
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.expanduser("~/Scripts"))

from impera_cache import cached_cu_tasks, cached_rt_ads, cached_rt_adgroups
from impera_utils import classify_task, normalize_person_name, get_cf_value, detect_nicho
from cruzamento_clickup_redtrack import (
    fetch_redtrack_campaigns, parse_campaign_name, COPY_LIST, TRAFEGO_LIST,
)
from gpdr_historico import save_week_kpis, get_week_key, load_prev_week
from impera_ad_registry import get_or_build_registry, lookup_ad
from fetch_redtrack_com_copywriter_ultimate import extract_ad_number

API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
REDTRACK_KEY = os.environ.get("REDTRACK_API_KEY", "")
CLICKUP_CHAT_VIEW = "8cm1w4b-9993"

ROAS_VALIDACAO_MIN = 1.8
VENDAS_VALIDACAO_MIN = 3
CPA_MAX = 180


def fetch_redtrack_with_copywriter(date_from, date_to):
    """
    Busca adgroups do RedTrack e cruza com AD registry para atribuir copywriter.

    Usa 3 estratégias em cascata:
    1. Lookup direto no registry de ADs indexados
    2. Range matching (se AD está em um range [AD100-AD110])
    3. Fallback para "Desconhecido"

    Adiciona campos: copywriter_name, confidence, nicho, roas, vendas, cpa
    """
    # Construir/carregar registry
    registry = get_or_build_registry(max_age_hours=4)

    # Buscar adgroups do RedTrack com rt_adgroup
    adgroup_data = cached_rt_adgroups(date_from, date_to)
    adgroups = adgroup_data.get("adgroups", [])

    # Cruzar cada adgroup com registry
    campaigns = []
    for row in adgroups:
        rt_adgroup = row.get("rt_adgroup", "")
        ad_num = extract_ad_number(rt_adgroup)

        if ad_num:
            result = lookup_ad(ad_num, registry, context_campaign=row.get("campaign", ""))
            copywriter_name = result["copywriter"] or "Desconhecido"
            confidence = result["confidence"]
        else:
            copywriter_name = "Desconhecido"
            confidence = 0.0

        # Parse campaign para extrair nicho
        parsed = parse_campaign_name(row.get("campaign", ""))

        # Calcular ROAS, CPA, vendas
        revenue = row.get("revenuetype2", 0) + row.get("revenuetype3", 0)
        cost = row.get("cost", 0)
        vendas = row.get("convtype1", 0)
        roas = revenue / max(cost, 1) if cost > 0 else 0
        cpa = cost / max(vendas, 1) if vendas > 0 else 0

        campaigns.append({
            **row,
            "copywriter_name": copywriter_name,
            "confidence": confidence,
            "nicho": parsed.get("nicho", ""),
            "roas": roas,
            "vendas": vendas,
            "cpa": cpa,
        })

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


def build_copy_data(date_from, date_to):
    """Agrega dados Copy por copywriter."""
    tasks = cached_cu_tasks(COPY_LIST, include_closed=True)

    by_cw = defaultdict(lambda: {
        "volume": 0, "novo": 0, "variacao": 0, "leads": 0, "mlds": 0, "vsls": 0
    })

    for task in tasks:
        try:
            created = task.get("date_created")
            if created:
                task_date = parse_timestamp(created)
                if not task_date or not (datetime.fromisoformat(date_from) <= task_date <= datetime.fromisoformat(date_to)):
                    continue

            cw = normalize_person_name(get_cf_value(task, "copywritter") or "Desconhecido")
            name = task.get("name", "")
            cat, qtd, is_lead, is_mld, is_vsl = classify_task(name)

            by_cw[cw]["volume"] += qtd

            if "V1" in name and "[" in name and "]" in name:
                by_cw[cw]["novo"] += qtd
            else:
                by_cw[cw]["variacao"] += qtd

            if is_lead:
                by_cw[cw]["leads"] += qtd
            if is_mld:
                by_cw[cw]["mlds"] += qtd
            if is_vsl:
                by_cw[cw]["vsls"] += qtd
        except:
            pass

    return dict(by_cw)


def build_assertividade_copy(campaigns):
    """Calcula assertividade copy por copywriter."""
    by_cw = defaultdict(lambda: {"testados": 0, "assertivos": 0})

    for c in campaigns:
        try:
            cw = c.get("copywriter_name", "Desconhecido")
            if not cw:
                continue

            cw = normalize_person_name(cw)
            by_cw[cw]["testados"] += 1

            vendas = int(c.get("convtype1", 0))
            cpa = float(c.get("cost", 0)) / max(vendas, 1) if vendas > 0 else float('inf')
            faturamento = float(c.get("revenuetype2", 0)) + float(c.get("revenuetype3", 0))
            roas = faturamento / float(c.get("cost", 1)) if float(c.get("cost", 0)) > 0 else 0

            if vendas >= VENDAS_VALIDACAO_MIN and cpa <= CPA_MAX and roas >= ROAS_VALIDACAO_MIN:
                by_cw[cw]["assertivos"] += 1
        except:
            pass

    return {cw: (data["assertivos"] / max(data["testados"], 1) * 100) for cw, data in by_cw.items()}


def build_faturamento_por_cw(campaigns):
    """Calcula faturamento por copywriter."""
    by_cw = defaultdict(float)

    for c in campaigns:
        try:
            cw = c.get("copywriter_name", "Desconhecido")
            if not cw:
                continue
            cw = normalize_person_name(cw)
            faturamento = float(c.get("revenuetype2", 0)) + float(c.get("revenuetype3", 0))
            by_cw[cw] += faturamento
        except:
            pass

    return dict(by_cw)


def build_sla_individual(date_from, date_to):
    """Calcula SLA individual por copywriter."""
    tasks = cached_cu_tasks(COPY_LIST, include_closed=True)

    by_cw = defaultdict(lambda: {"total_days": 0, "count": 0})

    for task in tasks:
        try:
            cw = normalize_person_name(get_cf_value(task, "copywritter") or "Desconhecido")

            start_ts = task.get("date_created")
            end_ts = task.get("date_closed")

            start = parse_timestamp(start_ts)
            if not start:
                continue

            end = parse_timestamp(end_ts) if end_ts else datetime.now()

            delta = (end - start).days
            if delta >= 0:
                by_cw[cw]["total_days"] += delta
                by_cw[cw]["count"] += 1
        except:
            pass

    return {cw: data["total_days"] / max(data["count"], 1) for cw, data in by_cw.items()}


def build_top_10_ads(campaigns):
    """Top 10 ADs separando por VARIAÇÃO (AD101 V1 ≠ AD101 V2)."""
    # Agrupar por AD + Variação + Nicho + Região + Oferta
    by_ad_variant = defaultdict(lambda: {
        "ad_num": None,
        "variacao": None,
        "nicho": None,
        "regiao": None,
        "oferta": None,
        "faturamento": 0.0,
        "custo": 0.0,
        "vendas": 0,
        "cw": None,
        "count": 0,
        "confidence_sum": 0.0,
    })

    for c in campaigns:
        try:
            cost = float(c.get("cost", 0))
            faturamento = float(c.get("revenuetype2", 0)) + float(c.get("revenuetype3", 0))
            vendas = int(c.get("convtype1", 0))

            if cost < 50 or vendas < 3:
                continue

            # Extrair AD number e variação do rt_adgroup
            rt_adgroup = c.get("rt_adgroup", "")
            ad_num = extract_ad_number(rt_adgroup)

            if not ad_num:
                continue

            # Extrair variação (V1, V2, V3...)
            # Formato esperado: "101 V1", "101 V1 — Cópia", "101 V2", etc
            variacao = "V1"  # default
            variant_match = re.search(r'\bV(\d+)\b', rt_adgroup)
            if variant_match:
                variacao = f"V{variant_match.group(1)}"

            # Parse campaign para nicho, região, oferta
            parsed = parse_campaign_name(c.get("campaign", ""))
            nicho = parsed.get("nicho", "desconhecido")
            regiao = parsed.get("regiao", "")
            oferta = parsed.get("oferta", "")

            # Criar chave única: AD + Variação + Nicho + Região + Oferta
            key = f"{ad_num}_{variacao}_{nicho}_{regiao}_{oferta}"

            # Agregar
            by_ad_variant[key]["ad_num"] = ad_num
            by_ad_variant[key]["variacao"] = variacao
            by_ad_variant[key]["nicho"] = nicho
            by_ad_variant[key]["regiao"] = regiao
            by_ad_variant[key]["oferta"] = oferta
            by_ad_variant[key]["faturamento"] += faturamento
            by_ad_variant[key]["custo"] += cost
            by_ad_variant[key]["vendas"] += vendas
            by_ad_variant[key]["cw"] = c.get("copywriter_name", "Desconhecido")
            by_ad_variant[key]["count"] += 1
            by_ad_variant[key]["confidence_sum"] += c.get("confidence", 0)
        except:
            pass

    # Montar resultado final
    top = []
    for key, data in by_ad_variant.items():
        try:
            faturamento = data["faturamento"]
            custo = data["custo"]
            roas = faturamento / max(custo, 1)
            avg_confidence = data["confidence_sum"] / max(data["count"], 1)

            # Nome do AD com variação e contexto
            ad_display = f"AD{data['ad_num']} {data['variacao']}"
            if data["nicho"]:
                ad_display += f" [{data['nicho']}"
                if data["regiao"]:
                    ad_display += f"][{data['regiao']}"
                ad_display += "]"

            top.append({
                "campaign": ad_display,
                "nicho": data["nicho"],
                "faturamento": faturamento,
                "roas": roas,
                "vendas": data["vendas"],
                "cw": data["cw"],
                "count": data["count"],
                "confidence": avg_confidence,
            })
        except:
            pass

    return sorted(top, key=lambda x: x["faturamento"], reverse=True)[:10]


def build_criatividade_enviados_trafego(date_from, date_to):
    """Conta criativos enviados a tráfego por copywriter."""
    tasks = cached_cu_tasks(COPY_LIST, include_closed=True)

    by_cw = defaultdict(int)

    for task in tasks:
        try:
            created = task.get("date_created")
            if created:
                task_date = parse_timestamp(created)
                if not task_date or not (datetime.fromisoformat(date_from) <= task_date <= datetime.fromisoformat(date_to)):
                    continue

            status = task.get("status", {}).get("status", "").lower()
            if "enviado" in status and "trafego" in status:
                cw = normalize_person_name(get_cf_value(task, "copywritter") or "Desconhecido")
                cat, qtd, _, _, _ = classify_task(task.get("name", ""))
                by_cw[cw] += qtd
        except:
            pass

    return dict(by_cw)


def build_report(date_from, date_to):
    """Gera relatório completo de Copy."""
    log(f"Gerando relatório Copy para {date_from} a {date_to}")

    copy_data = build_copy_data(date_from, date_to)
    campaigns = fetch_redtrack_with_copywriter(date_from, date_to)
    assertividade = build_assertividade_copy(campaigns)
    faturamento = build_faturamento_por_cw(campaigns)
    sla = build_sla_individual(date_from, date_to)
    top_10 = build_top_10_ads(campaigns)
    enviados = build_criatividade_enviados_trafego(date_from, date_to)

    report = []
    report.append("📊 COPY — RELATÓRIO SEMANAL\n")
    report.append(f"**Período**: {date_from} a {date_to}")
    report.append(f"**Responsável**: Elias")
    report.append(f"**Status**: Consultivo (validar dados com head)\n")

    # KPIs Críticos
    report.append("## 1️⃣ KPIs Críticos\n")
    report.append("| Métrica | Valor |")
    report.append("|---------|-------|")

    total_volume = sum(d["volume"] for d in copy_data.values())
    total_novo = sum(d["novo"] for d in copy_data.values())
    total_variacao = sum(d["variacao"] for d in copy_data.values())
    total_faturamento = sum(faturamento.values())
    avg_assertividade = sum(assertividade.values()) / len(assertividade) if assertividade else 0
    total_enviados = sum(enviados.values())

    report.append(f"| **Volume Total** | {total_volume} criativos |")
    report.append(f"| **Novo vs Variação** | {total_novo} novo / {total_variacao} variação |")
    report.append(f"| **Faturamento** | R${total_faturamento:,.0f} |")
    report.append(f"| **Assertividade Copy** | {avg_assertividade:.1f}% |")
    report.append(f"| **Enviado a Tráfego** | {total_enviados} criativos |\n")

    # Ranking Individual
    report.append("## 2️⃣ Ranking Individual (Volume)\n")
    report.append("| Copywriter | Volume | Novo | Variação | Faturamento | Assertividade |")
    report.append("|------------|--------|------|----------|-------------|----------------|")

    for cw in sorted(copy_data.keys(), key=lambda x: copy_data[x]["volume"], reverse=True):
        vol = copy_data[cw]["volume"]
        novo = copy_data[cw]["novo"]
        var = copy_data[cw]["variacao"]
        fat = faturamento.get(cw, 0)
        asser = assertividade.get(cw, 0)
        report.append(f"| {cw} | {vol} | {novo} | {var} | R${fat:,.0f} | {asser:.1f}% |")

    report.append("")

    # SLA Individual
    report.append("## 3️⃣ SLA Individual (Dias)\n")
    report.append("| Copywriter | Dias Médios |")
    report.append("|------------|-------------|")

    for cw in sorted(sla.keys(), key=lambda x: sla[x]):
        report.append(f"| {cw} | {sla[cw]:.1f} dias |")

    report.append("")

    # Top 10 ADs
    report.append("## 4️⃣ Top 10 ADs para Variação\n")
    report.append("| Rank | AD (Variação) | Nicho | Faturamento | ROAS | Vendas | Copywriter | Confiança |")
    report.append("|------|---------------|-------|-------------|------|--------|------------|-----------|")

    for i, ad in enumerate(top_10, 1):
        conf_pct = ad.get("confidence", 0) * 100
        report.append(f"| {i} | {ad['campaign']} | {ad['nicho']} | R${ad['faturamento']:,.0f} | {ad['roas']:.2f}x | {ad['vendas']} | {ad['cw']} | {conf_pct:.0f}% |")

    report.append("")

    # Campos Manuais
    report.append("## 5️⃣ Análise Semanal (Preencher com Elias)\n")
    report.append("**O que funcionou bem?**\n")
    report.append("_[Elias, descreva qual foi o ponto forte da semana]_\n")
    report.append("**Gargalos identificados?**\n")
    report.append("_[Elias, quais foram os desafios/atrasos?]_\n")
    report.append("**Necessidades?**\n")
    report.append("_[Elias, o que é preciso para melhorar?]_\n")

    # Glossário
    report.append("---\n")
    report.append("## 📋 GLOSSÁRIO — Definições de Métricas\n")
    report.append("**Volume Total**: Quantidade de criativos criados no período (data_created)")
    report.append("\n**Novo vs Variação**: Criativos com [V1] = novo | sem [V1] = variação")
    report.append("\n**Faturamento**: Receita de front (revenuetype2 + revenuetype3) atribuída por copywriter via RedTrack")
    report.append("\n**Assertividade Copy**: % de criativos que atingiram **Pré-validado+** (≥3 vendas + CPA ≤ R$180 + ROAS Front ≥ 1.8)")
    report.append("\n**Enviado a Tráfego**: Criativos que completaram ciclo (status 'enviado trafego')")
    report.append("\n**SLA**: Tempo médio em dias desde criação até conclusão")
    report.append("\n**ROAS Front**: (revenuetype2 + revenuetype3) / cost")
    report.append("\n**CPA**: cost / conversões")

    return "\n".join(report)


def main():
    date_from, date_to = get_monday_to_sunday()
    report = build_report(date_from, date_to)

    if "--preview" in sys.argv:
        print(report)
        log("Preview mode — relatório não foi postado")
    else:
        if post_clickup(report):
            log("✅ Relatório Copy postado com sucesso")
        else:
            log("❌ Erro ao postar relatório Copy")
            print(report)


if __name__ == "__main__":
    main()
