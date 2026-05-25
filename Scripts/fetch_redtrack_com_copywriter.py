#!/usr/bin/env python3
"""
Fetch RedTrack com Matching Copywriter — V2 COMPLETA
Usa group=campaign,rt_adgroup para extrair dados estruturados.

Pipeline:
  RedTrack (group=campaign,rt_adgroup)
    ↓
  Extract ad_num de rt_adgroup
    ↓
  Buscar [AD###] no ClickUp GESTÃO DE TRÁFEGO
    ↓
  Ler campo ✍️ Copywritter
    ↓
  Agregar por copywriter
"""

import os
import sys
import json
import re
import urllib.request
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, os.path.expanduser("~/Scripts"))

from impera_cache import cached_cu_tasks, rt_rate_limit
from impera_utils import normalize_person_name, get_cf_value

REDTRACK_KEY = os.environ.get("REDTRACK_API_KEY", "")
TRAFEGO_LIST = "901324476398"  # GESTÃO DE TRÁFEGO

# ============================================================================
# ETAPA 1: EXTRAIR ID DO CRIATIVO
# ============================================================================

def extract_ad_number(rt_adgroup):
    """
    Extrai número do AD de padrões desorganizados.
    
    Padrões suportados:
      • "101 V1"              → 101
      • "AD 101"              → 101
      • "AD101"               → 101
      • "101 V1 — Cópia"      → 101
      • "AD 10 V2 — Cópia1"   → 10
      • "CE15V28"             → 15
    """
    if not rt_adgroup:
        return None
    
    # Remove variações comuns primeiro
    clean = re.sub(r'(— Cópia\d*|_[\da-z]+)', '', rt_adgroup)
    
    # Padrão 1: "AD 10" ou "AD10" ou "AD-10"
    match = re.search(r'AD[\s\-]?(\d+)', clean, re.IGNORECASE)
    if match:
        return int(match.group(1))
    
    # Padrão 2: Números no início seguidos de espaço e "V"
    # Ex: "101 V1" → 101
    match = re.search(r'^(\d+)\s+[Vv]', clean)
    if match:
        return int(match.group(1))
    
    # Padrão 3: Apenas números no início (fallback)
    match = re.search(r'^(\d+)', clean)
    if match:
        return int(match.group(1))
    
    return None


# ============================================================================
# ETAPA 2: BUSCAR COPYWRITER NO CLICKUP
# ============================================================================

def find_copywriter_by_ad(ad_num):
    """
    Busca o copywriter que criou um AD específico.
    
    1. Busca todas as tarefas em "GESTÃO DE TRÁFEGO"
    2. Procura por nome contendo [AD{ad_num}]
    3. Lê campo ✍️ Copywritter (NOTE: 2 T's!)
    4. Retorna copywriter ou "CRIATIVO ÓRFÃO"
    """
    try:
        tasks = cached_cu_tasks(TRAFEGO_LIST)
        
        for task in tasks:
            task_name = task.get("name", "")
            
            # Procura por [AD###]
            if f"[AD{ad_num}]" in task_name:
                copywriter = get_cf_value(task, "Copywritter")  # 2 T's!
                
                if copywriter:
                    return normalize_person_name(copywriter)
        
        return "CRIATIVO ÓRFÃO"
    
    except Exception as e:
        print(f"  ⚠️ Erro ao buscar copywriter: {e}")
        return "ERRO"


# ============================================================================
# ETAPA 3: BUSCAR REDTRACK COM group=campaign,rt_adgroup
# ============================================================================

def fetch_redtrack_com_adgroup(date_from, date_to):
    """
    Busca RedTrack com group=campaign,rt_adgroup.
    
    Retorna lista de dicts com:
      - campaign: nome da campanha
      - rt_adgroup: nome do grupo de ads (criativo)
      - cost, revenue, conversions, etc.
    """
    try:
        url = (
            f"https://api.redtrack.io/report?api_key={REDTRACK_KEY}"
            f"&group=campaign,rt_adgroup"
            f"&date_from={date_from}&date_to={date_to}"
            f"&columns=revenuetype2,revenuetype3,convtype1,convtype4,cost,clicks"
        )
        
        rt_rate_limit()
        data = json.loads(urllib.request.urlopen(url, timeout=15).read())
        
        if isinstance(data, list):
            return data
        else:
            return []
    
    except Exception as e:
        print(f"❌ Erro ao buscar RedTrack: {e}")
        return []


# ============================================================================
# ETAPA 4: PROCESSAR E AGREGAR
# ============================================================================

def process_redtrack_data(raw_data):
    """
    Processa dados do RedTrack:
      1. Extrai ad_num de rt_adgroup
      2. Busca copywriter no ClickUp
      3. Unifica variações (remove "— Cópia")
      4. Agrega por copywriter
    """
    
    result = defaultdict(lambda: {
        "cost": 0,
        "revenue": 0,
        "conversions": 0,
        "ads": defaultdict(lambda: {
            "cost": 0,
            "revenue": 0,
            "conversions": 0,
            "count": 0,
            "variants": []
        })
    })
    
    for row in raw_data:
        rt_adgroup = row.get("rt_adgroup", "")
        
        # ETAPA 1: Extrair ad_num
        ad_num = extract_ad_number(rt_adgroup)
        if not ad_num:
            continue
        
        # ETAPA 2: Buscar copywriter
        copywriter = find_copywriter_by_ad(ad_num)
        
        # ETAPA 3: Processar métricas
        cost = float(row.get("cost", 0))
        rev2 = float(row.get("revenuetype2", 0))
        rev3 = float(row.get("revenuetype3", 0))
        revenue = rev2 + rev3
        conversions = int(row.get("convtype1", 0))
        
        # Agregar por copywriter
        result[copywriter]["cost"] += cost
        result[copywriter]["revenue"] += revenue
        result[copywriter]["conversions"] += conversions
        
        # Agregar por AD (unificado)
        result[copywriter]["ads"][ad_num]["cost"] += cost
        result[copywriter]["ads"][ad_num]["revenue"] += revenue
        result[copywriter]["ads"][ad_num]["conversions"] += conversions
        result[copywriter]["ads"][ad_num]["count"] += 1
        result[copywriter]["ads"][ad_num]["variants"].append(rt_adgroup)
    
    return result


# ============================================================================
# ETAPA 5: GERAR RELATÓRIO
# ============================================================================

def build_report(aggregated_data):
    """Gera relatório de faturamento por copywriter."""
    
    lines = [
        "📊 FATURAMENTO POR COPYWRITER (RedTrack + ClickUp)",
        f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}",
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
        
        lines.append(f"👤 {cw_name}")
        lines.append(f"   Custo: R${cost:,.0f} | Faturamento: R${revenue:,.0f} | ROAS: {roas:.2f}")
        lines.append(f"   Conversões: {conversions} | ADs: {ad_count}")
        lines.append("")
    
    return "\n".join(lines)


# ============================================================================
# MAIN
# ============================================================================

def main():
    from datetime import timedelta
    
    today = datetime.now()
    date_to = today.strftime("%Y-%m-%d")
    date_from = (today - timedelta(days=6)).strftime("%Y-%m-%d")
    
    print(f"📊 Buscando dados: {date_from} a {date_to}\n")
    
    # 1. Buscar dados
    print("1️⃣  Buscando RedTrack (group=campaign,rt_adgroup)...")
    raw_data = fetch_redtrack_com_adgroup(date_from, date_to)
    print(f"   ✅ {len(raw_data)} registros encontrados\n")
    
    # 2. Processar
    print("2️⃣  Processando dados...")
    aggregated = process_redtrack_data(raw_data)
    print(f"   ✅ {len(aggregated)} copywriters processados\n")
    
    # 3. Gerar relatório
    print("3️⃣  Gerando relatório...\n")
    report = build_report(aggregated)
    
    print(report)
    
    return aggregated


if __name__ == "__main__":
    main()
