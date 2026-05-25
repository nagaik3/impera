#!/usr/bin/env python3
"""
Fetch RedTrack com Matching Copywriter — V4 FINAL (COM REGEX MELHORADO)

Fix: Procurar por AD### com OU SEM colchetes
     [AD101] ou AD101 ou [AD101-AD105]
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


def find_copywriter_by_ad_v4(ad_num, copy_tasks, trafego_tasks):
    """
    Busca copywriter com regex MELHORADO.
    
    Procura por:
      [AD101]       ← Com colchetes
      AD101         ← Sem colchetes
      [AD101-AD105] ← Range com colchetes
      AD101-AD105   ← Range sem colchetes
    """
    
    all_tasks = copy_tasks + trafego_tasks
    
    # Padrão 1: [AD###] com colchetes
    pattern1 = f"\\[AD{ad_num}\\]"
    
    # Padrão 2: AD### sem colchetes (mas não dentro de outro token)
    pattern2 = f"AD\\s*{ad_num}\\b"
    
    # Padrão 3: [AD###-...] range com colchetes
    pattern3 = f"\\[AD{ad_num}-"
    
    # Padrão 4: AD###-... range sem colchetes
    pattern4 = f"AD\\s*{ad_num}-"
    
    # Padrão 5: ...-AD###] range final com colchetes
    pattern5 = f"-AD{ad_num}\\]"
    
    # Padrão 6: ...-AD### range final sem colchetes
    pattern6 = f"-AD\\s*{ad_num}\\b"
    
    patterns = [pattern1, pattern2, pattern3, pattern4, pattern5, pattern6]
    
    for task in all_tasks:
        task_name = task.get("name", "")
        
        for pattern in patterns:
            if re.search(pattern, task_name, re.IGNORECASE):
                copywriter = get_cf_value(task, "Copywritter")
                if copywriter:
                    return normalize_person_name(copywriter), "encontrado"
    
    return "CRIATIVO ÓRFÃO", "nao_encontrado"


def fetch_redtrack_com_adgroup(date_from, date_to):
    """Busca RedTrack com group=campaign,rt_adgroup."""
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


def process_redtrack_data_v4(raw_data, copy_tasks, trafego_tasks):
    """Processa com regex melhorado."""
    
    result = defaultdict(lambda: {
        "cost": 0,
        "revenue": 0,
        "conversions": 0,
        "ads": defaultdict(int),
    })
    
    stats = {
        "total": len(raw_data),
        "encontrados": 0,
        "orfaos": 0,
        "ads_unicos": set(),
        "ads_orfaos": set(),
    }
    
    for row in raw_data:
        rt_adgroup = row.get("rt_adgroup", "")
        ad_num = extract_ad_number(rt_adgroup)
        
        if not ad_num:
            continue
        
        stats["ads_unicos"].add(ad_num)
        
        # Buscar copywriter (com regex melhorado)
        copywriter, method = find_copywriter_by_ad_v4(ad_num, copy_tasks, trafego_tasks)
        
        # Contabilizar
        if method == "encontrado":
            stats["encontrados"] += 1
        else:
            stats["orfaos"] += 1
            stats["ads_orfaos"].add(ad_num)
        
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
    
    return dict(result), stats


def build_report_v4(aggregated_data, stats):
    """Gera relatório."""
    
    lines = [
        "📊 FATURAMENTO POR COPYWRITER (RedTrack + ClickUp - V4 FINAL)",
        f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "",
        "📈 ESTATÍSTICAS DE MATCHING:",
        f"  Total de rows: {stats['total']:,}",
        f"  ✅ Encontrados: {stats['encontrados']:,} ({stats['encontrados']/max(stats['total'],1)*100:.1f}%)",
        f"  ❌ Órfãos: {stats['orfaos']:,} ({stats['orfaos']/max(stats['total'],1)*100:.1f}%)",
        f"  ADs únicos: {len(stats['ads_unicos'])}",
        f"  ADs órfãos: {len(stats['ads_orfaos'])}",
        f"  Taxa de sucesso (ADs): {(len(stats['ads_unicos']) - len(stats['ads_orfaos']))/len(stats['ads_unicos'])*100:.1f}%",
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
        
        method_emoji = "✅" if cw_name != "CRIATIVO ÓRFÃO" else "❌"
        
        lines.append(f"{method_emoji} {cw_name}")
        lines.append(f"   Custo: R${cost:,.0f} | Faturamento: R${revenue:,.0f} | ROAS: {roas:.2f}")
        lines.append(f"   Conversões: {conversions:,} | ADs: {ad_count}")
        lines.append("")
    
    return "\n".join(lines)


def main():
    today = datetime.now()
    date_to = today.strftime("%Y-%m-%d")
    date_from = (today - timedelta(days=6)).strftime("%Y-%m-%d")
    
    print(f"📊 Buscando dados: {date_from} a {date_to}\n")
    
    # 1. Cache de tarefas
    print("0️⃣  Carregando tarefas do ClickUp...")
    copy_tasks = cached_cu_tasks(COPY_LIST)
    trafego_tasks = cached_cu_tasks(TRAFEGO_LIST)
    print(f"   ✅ {len(copy_tasks)} tarefas em COPY + {len(trafego_tasks)} em TRÁFEGO\n")
    
    # 2. Buscar dados
    print("1️⃣  Buscando RedTrack...")
    raw_data = fetch_redtrack_com_adgroup(date_from, date_to)
    print(f"   ✅ {len(raw_data):,} registros encontrados\n")
    
    # 3. Processar
    print("2️⃣  Processando com regex melhorado...")
    aggregated, stats = process_redtrack_data_v4(raw_data, copy_tasks, trafego_tasks)
    print(f"   ✅ {len(aggregated)} copywriters processados\n")
    
    # 4. Gerar relatório
    print("3️⃣  Gerando relatório...\n")
    report = build_report_v4(aggregated, stats)
    
    print(report)
    
    # Debug: Listar órfãos
    if stats['ads_orfaos']:
        print("\n\n⚠️ CRIATIVOS AINDA ÓRFÃOS:")
        print("="*80)
        print(f"\nADs: {sorted(stats['ads_orfaos'])}")


if __name__ == "__main__":
    main()
