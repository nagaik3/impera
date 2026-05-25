#!/usr/bin/env python3
"""
Fetch RedTrack com Matching Copywriter — FINAL (AMBAS LISTAS)

Pipeline:
  rt_adgroup = "101 V1"
    ↓
  Procura [AD101] em COPY_LIST
    ↓
  Se não encontrar → Procura em GESTÃO DE TRÁFEGO
    ↓
  ✅ ENCONTRA COM ALTA PRECISÃO!
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


def find_copywriter_by_ad_v2(ad_num):
    """
    Busca copywriter em AMBAS as listas.
    
    1. Procura em COPY_LIST (onde foi criado)
    2. Se não encontrar → Procura em GESTÃO DE TRÁFEGO (onde está em teste)
    """
    
    # 1. Procurar em COPY
    try:
        copy_tasks = cached_cu_tasks(COPY_LIST)
        for task in copy_tasks:
            if f"[AD{ad_num}]" in task.get("name", ""):
                copywriter = get_cf_value(task, "Copywritter")
                if copywriter:
                    return normalize_person_name(copywriter), "copy_list"
    except:
        pass
    
    # 2. Procurar em GESTÃO DE TRÁFEGO
    try:
        trafego_tasks = cached_cu_tasks(TRAFEGO_LIST)
        for task in trafego_tasks:
            if f"[AD{ad_num}]" in task.get("name", ""):
                copywriter = get_cf_value(task, "Copywritter")
                if copywriter:
                    return normalize_person_name(copywriter), "trafego_list"
    except:
        pass
    
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


def process_redtrack_data_final(raw_data):
    """Processa com matching em ambas as listas."""
    
    result = defaultdict(lambda: {
        "cost": 0,
        "revenue": 0,
        "conversions": 0,
        "ads": defaultdict(int),
        "method": None,
    })
    
    stats = {
        "total": len(raw_data),
        "copy_list": 0,
        "trafego_list": 0,
        "orfaos": 0,
    }
    
    for row in raw_data:
        rt_adgroup = row.get("rt_adgroup", "")
        ad_num = extract_ad_number(rt_adgroup)
        
        if not ad_num:
            continue
        
        # Buscar copywriter
        copywriter, method = find_copywriter_by_ad_v2(ad_num)
        
        # Contabilizar
        if method == "copy_list":
            stats["copy_list"] += 1
        elif method == "trafego_list":
            stats["trafego_list"] += 1
        else:
            stats["orfaos"] += 1
        
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


def build_report_final(aggregated_data, stats):
    """Gera relatório final."""
    
    lines = [
        "📊 FATURAMENTO POR COPYWRITER (RedTrack + ClickUp)",
        f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "",
        "📈 ESTATÍSTICAS DE MATCHING:",
        f"  Total de rows: {stats['total']:,}",
        f"  ✅ Encontrados em COPY: {stats['copy_list']} ({stats['copy_list']/max(stats['total'],1)*100:.1f}%)",
        f"  ✅ Encontrados em TRÁFEGO: {stats['trafego_list']} ({stats['trafego_list']/max(stats['total'],1)*100:.1f}%)",
        f"  ❌ Órfãos: {stats['orfaos']} ({stats['orfaos']/max(stats['total'],1)*100:.1f}%)",
        f"  Taxa de sucesso: {(stats['copy_list'] + stats['trafego_list'])/max(stats['total'],1)*100:.1f}%",
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
        
        method_emoji = "✅" if data["method"] in ["copy_list", "trafego_list"] else "❌"
        
        lines.append(f"{method_emoji} {cw_name}")
        lines.append(f"   Custo: R${cost:,.0f} | Faturamento: R${revenue:,.0f} | ROAS: {roas:.2f}")
        lines.append(f"   Conversões: {conversions} | ADs: {ad_count}")
        lines.append("")
    
    return "\n".join(lines)


def main():
    today = datetime.now()
    date_to = today.strftime("%Y-%m-%d")
    date_from = (today - timedelta(days=6)).strftime("%Y-%m-%d")
    
    print(f"📊 Buscando dados: {date_from} a {date_to}\n")
    
    # 1. Buscar dados
    print("1️⃣  Buscando RedTrack...")
    raw_data = fetch_redtrack_com_adgroup(date_from, date_to)
    print(f"   ✅ {len(raw_data):,} registros encontrados\n")
    
    # 2. Processar
    print("2️⃣  Processando (buscando em COPY_LIST + TRAFEGO_LIST)...")
    aggregated, stats = process_redtrack_data_final(raw_data)
    print(f"   ✅ {len(aggregated)} copywriters processados\n")
    
    # 3. Gerar relatório
    print("3️⃣  Gerando relatório...\n")
    report = build_report_final(aggregated, stats)
    
    print(report)


if __name__ == "__main__":
    main()
