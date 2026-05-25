#!/usr/bin/env python3
"""
Fetch RedTrack com Matching Copywriter — V3 (REGRESSIVO)
Lógica: rt_adgroup → campaign → parse (NICHO|REGIÃO|FONTE) → ClickUp

Pipeline:
  rt_adgroup = "101 V1"
    ↓
  campaign = "[FB] - BR - MEMORIALMM | ..."
    ↓
  Parse campaign → NICHO=MM, REGIÃO=BR, FONTE=FB
    ↓
  Procura ClickUp: [MM][BR][...][FB][AD101][V1]
    ↓
  ✅ ENCONTRA COM CONTEXTO!
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
TRAFEGO_LIST = "901324476398"  # GESTÃO DE TRÁFEGO
COPY_LIST = "901324556390"     # COPY

# ============================================================================
# ETAPA 1: PARSE CAMPAIGN (REGRESSÃO)
# ============================================================================

def parse_campaign_name(campaign):
    """
    Parse da campaign para extrair contexto.

    Format: "[FONTE] - REGIÃO - DESCRIÇÃO | ... | G. GESTOR"

    Exemplo:
    "[FB] - BR - VSL 03 - MEMORIALMM | 25/04 - P. MANUELA | G. LUDSON"

    Retorna:
    {
        "fonte": "FB",
        "regiao": "BR",
        "nicho": "MM",
        "gestor": "LUDSON",
    }
    """

    result = {
        "fonte": None,
        "regiao": None,
        "nicho": None,
        "gestor": None,
    }

    # 1. FONTE: [FB], [GG], [YT], etc
    match = re.search(r'\[([A-Z]{2})\]', campaign)
    if match:
        result["fonte"] = match.group(1)

    # 2. REGIÃO: BR, EUA, etc (após FONTE)
    match = re.search(r'\[([A-Z]{2})\]\s*-\s*([A-Z]{2,3})', campaign)
    if match:
        result["regiao"] = match.group(2)

    # 3. NICHO: Detectar por sufixo
    nicho_patterns = [
        (r'MEMORIA[LÁ]*\s*([A-Z]{2})', 1),  # MEMORIALMM → MM
        (r'MEMÓRIA[LÁ]*\s*([A-Z]{2})', 1),  # MEMÓRIAMM → MM
        (r'EMAGRECIMENTO', 'EM'),
        (r'DIABETES', 'DB'),
        (r'NEUROPATIA', 'NE'),
        (r'PRÓSTATA|PROSTATA', 'PT'),
        (r'ARTICULAR|ARTICULARES', 'DA'),
        (r'ANSIEDADE', 'AN'),
        (r'ZUMBIDO', 'ZB'),
        (r'VSL', 'VS'),
        (r'COLESTEROL', 'CL'),
        (r'VISÃO|VISAO', 'VC'),
        (r'FÍGADO|FIGADO', 'FG'),
        (r'IMUNIDADE', 'IM'),
    ]

    for pattern, replacement in nicho_patterns:
        match = re.search(pattern, campaign, re.IGNORECASE)
        if match:
            if isinstance(replacement, int):
                result["nicho"] = match.group(replacement).upper()
            else:
                result["nicho"] = replacement
            break

    # 4. GESTOR: G. LUDSON, G.DOUGLAS, etc
    match = re.search(r'G\.?\s*([A-ZÁÉÍÓÚ][A-ZÁÉÍÓÚa-záéíóú]+)', campaign)
    if match:
        result["gestor"] = match.group(1).upper()

    return result


# ============================================================================
# ETAPA 2: EXTRAIR ID DO CRIATIVO
# ============================================================================

def extract_ad_number(rt_adgroup):
    """Extrai número do AD de rt_adgroup."""
    if not rt_adgroup:
        return None

    clean = re.sub(r'(— Cópia\d*|_[\da-z]+)', '', rt_adgroup)

    # Padrão 1: "AD 10" ou "AD10"
    match = re.search(r'AD[\s\-]?(\d+)', clean, re.IGNORECASE)
    if match:
        return int(match.group(1))

    # Padrão 2: Números no início + "V"
    match = re.search(r'^(\d+)\s+[Vv]', clean)
    if match:
        return int(match.group(1))

    # Padrão 3: Apenas números
    match = re.search(r'^(\d+)', clean)
    if match:
        return int(match.group(1))

    return None


# ============================================================================
# ETAPA 3: BUSCAR COPYWRITER (COM CONTEXTO)
# ============================================================================

def find_copywriter_by_context(nicho, regiao, fonte, ad_num):
    """
    Busca copywriter usando contexto da campaign.

    Procura por:  [NICHO][REGIAO][...][FONTE][AD###][...]

    Exemplo: [MM][BR][...][FB][AD101][V1]
    """
    try:
        tasks = cached_cu_tasks(COPY_LIST)

        # Montar padrão de busca
        if nicho and regiao and fonte:
            pattern = f"[{nicho}][{regiao}].*[{fonte}].*[AD{ad_num}]"
        else:
            pattern = f"[AD{ad_num}]"

        for task in tasks:
            task_name = task.get("name", "")

            # Procurar pelo padrão completo
            if re.search(pattern, task_name, re.IGNORECASE):
                copywriter = get_cf_value(task, "Copywritter")  # 2 T's!
                if copywriter:
                    return normalize_person_name(copywriter), "contexto"

            # Fallback: apenas [AD###]
            elif f"[AD{ad_num}]" in task_name:
                copywriter = get_cf_value(task, "Copywritter")
                if copywriter:
                    return normalize_person_name(copywriter), "ad_only"

        return "CRIATIVO ÓRFÃO", "nao_encontrado"

    except Exception as e:
        return "ERRO", "erro"


# ============================================================================
# ETAPA 4: BUSCAR REDTRACK
# ============================================================================

def fetch_redtrack_com_adgroup(date_from, date_to):
    """Busca RedTrack com group=campaign,rt_adgroup."""
    try:
        url = (
            f"https://api.redtrack.io/report?api_key={REDTRACK_KEY}"
            f"&group=campaign,rt_adgroup"
            f"&date_from={date_from}&date_to={date_to}"
            f"&columns=revenuetype2,revenuetype3,convtype1,convtype4,cost,clicks"
        )

        rt_rate_limit()
        data = json.loads(urllib.request.urlopen(url, timeout=15).read())

        return data if isinstance(data, list) else []

    except Exception as e:
        print(f"❌ Erro ao buscar RedTrack: {e}")
        return []


# ============================================================================
# ETAPA 5: PROCESSAR COM REGRESSÃO
# ============================================================================

def process_redtrack_data_regressivo(raw_data):
    """
    Processa dados com lógica REGRESSIVA.

    Para cada row:
    1. Parse campaign → NICHO, REGIÃO, FONTE
    2. Extract ad_num de rt_adgroup
    3. Buscar copywriter com CONTEXTO
    4. Agregar por copywriter
    """

    result = defaultdict(lambda: {
        "cost": 0,
        "revenue": 0,
        "conversions": 0,
        "matching_method": None,
        "ads": defaultdict(lambda: {
            "cost": 0,
            "revenue": 0,
            "conversions": 0,
            "count": 0,
        })
    })

    stats = {
        "total_rows": len(raw_data),
        "encontrados_contexto": 0,
        "encontrados_ad_only": 0,
        "orfaos": 0,
        "erros": 0,
    }

    for row in raw_data:
        campaign = row.get("campaign", "")
        rt_adgroup = row.get("rt_adgroup", "")

        # Parse campaign
        campaign_parsed = parse_campaign_name(campaign)
        nicho = campaign_parsed.get("nicho")
        regiao = campaign_parsed.get("regiao")
        fonte = campaign_parsed.get("fonte")

        # Extract ad_num
        ad_num = extract_ad_number(rt_adgroup)
        if not ad_num:
            continue

        # Buscar copywriter com contexto
        copywriter, method = find_copywriter_by_context(nicho, regiao, fonte, ad_num)

        # Contabilizar
        if method == "contexto":
            stats["encontrados_contexto"] += 1
        elif method == "ad_only":
            stats["encontrados_ad_only"] += 1
        elif method == "nao_encontrado":
            stats["orfaos"] += 1
        else:
            stats["erros"] += 1

        # Processar métricas
        cost = float(row.get("cost", 0))
        rev2 = float(row.get("revenuetype2", 0))
        rev3 = float(row.get("revenuetype3", 0))
        revenue = rev2 + rev3
        conversions = int(row.get("convtype1", 0))

        # Agregar
        result[copywriter]["cost"] += cost
        result[copywriter]["revenue"] += revenue
        result[copywriter]["conversions"] += conversions
        result[copywriter]["matching_method"] = method

        result[copywriter]["ads"][ad_num]["cost"] += cost
        result[copywriter]["ads"][ad_num]["revenue"] += revenue
        result[copywriter]["ads"][ad_num]["conversions"] += conversions
        result[copywriter]["ads"][ad_num]["count"] += 1

    return dict(result), stats


# ============================================================================
# ETAPA 6: GERAR RELATÓRIO
# ============================================================================

def build_report(aggregated_data, stats):
    """Gera relatório completo."""

    lines = [
        "📊 FATURAMENTO POR COPYWRITER (RedTrack + ClickUp - V3 REGRESSIVO)",
        f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "",
        "📈 ESTATÍSTICAS DE MATCHING:",
        f"  Total de rows: {stats['total_rows']:,}",
        f"  ✅ Encontrados (contexto): {stats['encontrados_contexto']} ({stats['encontrados_contexto']/max(stats['total_rows'],1)*100:.1f}%)",
        f"  ✅ Encontrados (AD only): {stats['encontrados_ad_only']} ({stats['encontrados_ad_only']/max(stats['total_rows'],1)*100:.1f}%)",
        f"  ⚠️  Órfãos: {stats['orfaos']} ({stats['orfaos']/max(stats['total_rows'],1)*100:.1f}%)",
        f"  ❌ Erros: {stats['erros']}",
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
        method = data["matching_method"]

        method_emoji = "✅" if method == "contexto" else "⚠️" if method == "ad_only" else "❌"

        lines.append(f"{method_emoji} {cw_name}")
        lines.append(f"   Custo: R${cost:,.0f} | Faturamento: R${revenue:,.0f} | ROAS: {roas:.2f}")
        lines.append(f"   Conversões: {conversions} | ADs: {ad_count}")
        lines.append("")

    return "\n".join(lines)


# ============================================================================
# MAIN
# ============================================================================

def main():
    today = datetime.now()
    date_to = today.strftime("%Y-%m-%d")
    date_from = (today - timedelta(days=6)).strftime("%Y-%m-%d")

    print(f"📊 Buscando dados: {date_from} a {date_to}\n")

    # 1. Buscar dados
    print("1️⃣  Buscando RedTrack (group=campaign,rt_adgroup)...")
    raw_data = fetch_redtrack_com_adgroup(date_from, date_to)
    print(f"   ✅ {len(raw_data):,} registros encontrados\n")

    # 2. Processar (com regressão)
    print("2️⃣  Processando com lógica REGRESSIVA...")
    aggregated, stats = process_redtrack_data_regressivo(raw_data)
    print(f"   ✅ {len(aggregated)} copywriters processados\n")

    # 3. Gerar relatório
    print("3️⃣  Gerando relatório...\n")
    report = build_report(aggregated, stats)

    print(report)

    return aggregated, stats


if __name__ == "__main__":
    main()
