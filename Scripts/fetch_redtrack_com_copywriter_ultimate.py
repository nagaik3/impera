#!/usr/bin/env python3
"""
Fetch RedTrack com Matching Copywriter — ULTIMATE (TODAS AS ESTRATÉGIAS)

3 estratégias de matching em cascata:

ESTRATÉGIA 1: Direct matching
  [AD###], AD###, [AD###-...], etc

ESTRATÉGIA 2: Range matching
  Se AD está dentro de [AD100-AD110], atribui ao copywriter desse range

ESTRATÉGIA 3: Campaign fallback
  Se ainda não encontrou → Extrai NICHO do campaign e procura tarefas desse nicho
"""

import os
import sys
import json
import re
import urllib.request
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.expanduser("~/Scripts"))

from impera_cache import cached_cu_tasks, rt_rate_limit
from impera_utils import normalize_person_name, get_cf_value

REDTRACK_KEY = os.environ.get("REDTRACK_API_KEY", "")
COPY_LIST = "901324556390"
TRAFEGO_LIST = "901324476398"


def extract_ad_number(rt_adgroup):
    """Extrai número do AD."""
    if not rt_adgroup:
        return None
    clean = re.sub(r'(— Cópia\d*|_[\da-z]+)', '', rt_adgroup)
    match = re.search(r'AD[\s\-]?(\d+)', clean, re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r'^(\d+)\s+[Vv]', clean)
    if match:
        return int(match.group(1))
    match = re.search(r'^(\d+)', clean)
    if match:
        return int(match.group(1))
    return None


def parse_campaign_nicho(campaign):
    """Extrai NICHO do campaign."""
    patterns = {
        "MM": r"MEMORIA|MEMÓRIA",
        "EM": r"EMAGRECIMENTO",
        "DB": r"DIABETES",
        "NE": r"NEUROPATIA",
        "PT": r"PRÓSTATA|PROSTATA",
        "DA": r"ARTICULAR",
        "AN": r"ANSIEDADE",
        "ZB": r"ZUMBIDO",
        "VS": r"VSL",
        "CL": r"COLESTEROL",
    }

    for nicho, pattern in patterns.items():
        if re.search(pattern, campaign, re.IGNORECASE):
            return nicho
    return None


# ============================================================================
# ESTRATÉGIA 1: DIRECT MATCHING
# ============================================================================

def strategy1_direct_match(ad_num, all_tasks):
    """Procura por [AD###] ou AD### diretamente."""
    patterns = [
        f"\\[AD{ad_num}\\]",
        f"AD\\s*{ad_num}\\b",
        f"\\[AD{ad_num}-",
        f"AD\\s*{ad_num}-",
        f"-AD{ad_num}\\]",
        f"-AD\\s*{ad_num}\\b"
    ]

    for task in all_tasks:
        task_name = task.get("name", "")

        for pattern in patterns:
            if re.search(pattern, task_name, re.IGNORECASE):
                copywriter = get_cf_value(task, "Copywritter")
                if copywriter:
                    return normalize_person_name(copywriter), "direct"

    return None, None


# ============================================================================
# ESTRATÉGIA 2: RANGE MATCHING
# ============================================================================

def strategy2_range_match(ad_num, all_tasks):
    """Procura por ranges que contenham esse AD: [AD100-AD110]"""

    for task in all_tasks:
        task_name = task.get("name", "")

        # Padrão 1: [AD###-AD###]
        match = re.search(r"\[AD(\d+)-AD(\d+)\]", task_name, re.IGNORECASE)
        if match:
            start = int(match.group(1))
            end = int(match.group(2))

            if start <= ad_num <= end:
                copywriter = get_cf_value(task, "Copywritter")
                if copywriter:
                    return normalize_person_name(copywriter), "range"

        # Padrão 2: AD###-AD###
        match = re.search(r"AD\s*(\d+)-AD\s*(\d+)", task_name, re.IGNORECASE)
        if match:
            start = int(match.group(1))
            end = int(match.group(2))

            if start <= ad_num <= end:
                copywriter = get_cf_value(task, "Copywritter")
                if copywriter:
                    return normalize_person_name(copywriter), "range"

    return None, None


# ============================================================================
# ESTRATÉGIA 3: CAMPAIGN FALLBACK
# ============================================================================

def strategy3_campaign_fallback(ad_num, campaign, all_tasks):
    """Fallback: Extrai NICHO do campaign e procura tarefas desse nicho."""

    nicho = parse_campaign_nicho(campaign)
    if not nicho:
        return None, None

    # Procurar tarefas que contenham [NICHO] e o AD
    for task in all_tasks:
        task_name = task.get("name", "")

        # Procurar por [NICHO]...[AD###]
        if f"[{nicho}]" in task_name:
            # Tentar direct match
            if f"[AD{ad_num}]" in task_name or re.search(f"AD\\s*{ad_num}\\b", task_name, re.IGNORECASE):
                copywriter = get_cf_value(task, "Copywritter")
                if copywriter:
                    return normalize_person_name(copywriter), "campaign_fallback"

            # Tentar range match
            match = re.search(r"\[AD(\d+)-AD(\d+)\]", task_name, re.IGNORECASE)
            if match:
                start = int(match.group(1))
                end = int(match.group(2))

                if start <= ad_num <= end:
                    copywriter = get_cf_value(task, "Copywritter")
                    if copywriter:
                        return normalize_person_name(copywriter), "campaign_fallback_range"

    return None, None


# ============================================================================
# ORQUESTRAÇÃO: CASCATA DE ESTRATÉGIAS
# ============================================================================

def find_copywriter_ultimate(ad_num, campaign, all_tasks):
    """Tenta 3 estratégias em cascata."""

    # Estratégia 1
    cw, method = strategy1_direct_match(ad_num, all_tasks)
    if cw:
        return cw, method

    # Estratégia 2
    cw, method = strategy2_range_match(ad_num, all_tasks)
    if cw:
        return cw, method

    # Estratégia 3
    cw, method = strategy3_campaign_fallback(ad_num, campaign, all_tasks)
    if cw:
        return cw, method

    # Nenhuma estratégia funcionou
    return "CRIATIVO ÓRFÃO", "nao_encontrado"


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def fetch_redtrack_com_adgroup(date_from, date_to):
    """Busca RedTrack."""
    try:
        url = (
            f"https://api.redtrack.io/report?api_key={REDTRACK_KEY}"
            f"&group=campaign,rt_adgroup"
            f"&date_from={date_from}&date_to={date_to}"
            f"&columns=revenuetype2,revenuetype3,convtype1,cost,clicks"
        )
        rt_rate_limit()
        data = json.loads(urllib.request.urlopen(url, timeout=15).read())
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"❌ Erro ao buscar RedTrack: {e}")
        return []


def process_redtrack_ultimate(raw_data, all_tasks):
    """Processa com cascata de estratégias."""

    result = defaultdict(lambda: {
        "cost": 0,
        "revenue": 0,
        "conversions": 0,
        "ads": defaultdict(int),
        "method": None,
    })

    stats = {
        "total": len(raw_data),
        "direct": 0,
        "range": 0,
        "campaign_fallback": 0,
        "campaign_fallback_range": 0,
        "orfaos": 0,
    }

    for row in raw_data:
        rt_adgroup = row.get("rt_adgroup", "")
        campaign = row.get("campaign", "")
        ad_num = extract_ad_number(rt_adgroup)

        if not ad_num:
            continue

        # Cascata de estratégias
        copywriter, method = find_copywriter_ultimate(ad_num, campaign, all_tasks)

        # Contabilizar
        stats[method if method != "nao_encontrado" else "orfaos"] += 1

        # Processar métricas
        cost = float(row.get("cost", 0))
        rev2 = float(row.get("revenuetype2", 0))
        rev3 = float(row.get("revenuetype3", 0))
        revenue = rev2 + rev3
        conversions = int(row.get("convtype1", 0))

        result[copywriter]["cost"] += cost
        result[copywriter]["revenue"] += revenue
        result[copywriter]["conversions"] += conversions
        result[copywriter]["ads"][ad_num] += 1
        result[copywriter]["method"] = method

    return dict(result), stats


def build_report_ultimate(aggregated_data, stats):
    """Gera relatório final."""

    total_encontrados = stats["direct"] + stats["range"] + stats["campaign_fallback"] + stats["campaign_fallback_range"]
    pct = total_encontrados / max(stats["total"], 1) * 100

    lines = [
        "📊 FATURAMENTO POR COPYWRITER (RedTrack + ClickUp - ULTIMATE)",
        f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "",
        "📈 ESTATÍSTICAS DE MATCHING (3 ESTRATÉGIAS EM CASCATA):",
        f"  Total de rows: {stats['total']:,}",
        f"  ✅ ENCONTRADOS: {total_encontrados:,} ({pct:.1f}%)",
        f"     └─ Estratégia 1 (Direct): {stats['direct']:,}",
        f"     └─ Estratégia 2 (Range): {stats['range']:,}",
        f"     └─ Estratégia 3 (Campaign): {stats['campaign_fallback'] + stats['campaign_fallback_range']:,}",
        f"  ❌ Órfãos: {stats['orfaos']:,} ({stats['orfaos']/max(stats['total'],1)*100:.1f}%)",
        "",
        "💰 FATURAMENTO POR COPYWRITER:",
        "=" * 80,
        ""
    ]

    # Ordenar por revenue
    sorted_cws = sorted(
        aggregated_data.items(),
        key=lambda x: x[1]["revenue"],
        reverse=True
    )

    for cw_name, data in sorted_cws:
        cost = data["cost"]
        revenue = data["revenue"]
        conversions = data["conversions"]
        roas = revenue / cost if cost > 0 else 0
        ad_count = len(data["ads"])

        method = data["method"]
        if method == "nao_encontrado":
            emoji = "❌"
        elif method == "direct":
            emoji = "✅"
        elif method == "range":
            emoji = "✅"
        else:
            emoji = "⚠️"

        lines.append(f"{emoji} {cw_name}")
        lines.append(f"   Custo: R${cost:,.0f} | Faturamento: R${revenue:,.0f} | ROAS: {roas:.2f}")
        lines.append(f"   Conversões: {conversions:,} | ADs: {ad_count}")
        lines.append("")

    return "\n".join(lines)


def main():
    today = datetime.now()
    date_to = today.strftime("%Y-%m-%d")
    date_from = (today - timedelta(days=6)).strftime("%Y-%m-%d")

    print(f"🚀 ULTIMATE VERSION - 3 Estratégias em Cascata\n")
    print(f"📊 Período: {date_from} a {date_to}\n")

    # 1. Load tasks
    print("0️⃣  Carregando ClickUp...")
    copy_tasks = cached_cu_tasks(COPY_LIST)
    trafego_tasks = cached_cu_tasks(TRAFEGO_LIST)
    all_tasks = copy_tasks + trafego_tasks
    print(f"   ✅ {len(all_tasks)} tarefas carregadas\n")

    # 2. Fetch RedTrack
    print("1️⃣  Buscando RedTrack...")
    raw_data = fetch_redtrack_com_adgroup(date_from, date_to)
    print(f"   ✅ {len(raw_data):,} registros\n")

    # 3. Process
    print("2️⃣  Processando (3 estratégias)...")
    aggregated, stats = process_redtrack_ultimate(raw_data, all_tasks)
    print(f"   ✅ {len(aggregated)} copywriters\n")

    # 4. Report
    print("3️⃣  Gerando relatório...\n")
    report = build_report_ultimate(aggregated, stats)

    print(report)


if __name__ == "__main__":
    main()
