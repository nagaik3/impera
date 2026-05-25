#!/usr/bin/env python3
"""
Análise detalhada dos criativos 'DESCONHECIDO' — encontra cada um e sugere categoria/ação
"""
import os, sys, json, re
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.expanduser('~/Scripts'))

from impera_cache import cached_rt_ads, cached_cu_tasks

# Importar funções do relatorio_copywriters_semanal
from relatorio_copywriters_semanal import (
    clean_ad_name, extract_creative_id, extract_nicho_from_campaign,
    extract_base_creative, attribute_copywriter, clickup_batch_search
)

def analise_desconhecidos():
    """Fetch data, categorize unknowns, output detailed list"""
    
    # Dates (last 7 days)
    date_to = datetime.now().date()
    date_from = date_to - timedelta(days=7)
    date_from_str = date_from.strftime('%Y-%m-%d')
    date_to_str = date_to.strftime('%Y-%m-%d')
    
    print("=" * 80)
    print("ANÁLISE DETALHADA: CRIATIVOS DESCONHECIDO")
    print(f"Período: {date_from_str} a {date_to_str}")
    print("=" * 80)
    
    # 1. Fetch RedTrack data
    print(f"\n[1/4] Buscando dados RedTrack...")
    try:
        raw_ads = cached_rt_ads(date_from_str, date_to_str)
        print(f"  {len(raw_ads)} registros encontrados")
    except Exception as e:
        print(f"ERRO: {e}")
        sys.exit(1)
    
    # 2. Process and build creative list
    print(f"\n[2/4] Processando criativos...")
    merged = defaultdict(lambda: {
        'cost': 0, 'front_rev': 0, 'sales': 0, 'original_names': [],
        'campaigns': set(),
    })
    
    for item in raw_ads:
        raw_name = item.get('rt_ad', '') or ''
        if not raw_name or raw_name.strip() == '' or raw_name.strip() == '{ad}':
            continue
        
        cost = float(item.get('cost', 0) or 0)
        rev2 = float(item.get('revenuetype2', 0) or 0)
        rev3 = float(item.get('revenuetype3', 0) or 0)
        sales = int(float(item.get('convtype4', 0) or 0))
        front_rev = rev2 + rev3
        
        cleaned = clean_ad_name(raw_name)
        if not cleaned:
            continue
        
        merged[cleaned]['cost'] += cost
        merged[cleaned]['front_rev'] += front_rev
        merged[cleaned]['sales'] += sales
        merged[cleaned]['original_names'].append(raw_name)
        
        campaign = item.get('campaign', '') or ''
        if campaign:
            merged[cleaned]['campaigns'].add(campaign)
    
    # 3. Extract creative IDs and attribute
    print(f"\n[3/4] Extraindo IDs e atribuindo...")
    creatives = []
    for name, data in merged.items():
        if data['cost'] <= 0 and data['front_rev'] <= 0:
            continue
        
        prefix, num, version, full_id = extract_creative_id(name)
        nicho = '??'
        for camp in data['campaigns']:
            nicho = extract_nicho_from_campaign(camp)
            if nicho != '??':
                break
        if nicho == '??':
            nicho = extract_nicho_from_campaign(name)
        
        roas = data['front_rev'] / data['cost'] if data['cost'] > 0 else 0
        
        c = {
            'name': name,
            'prefix': prefix,
            'num': num,
            'version': version,
            'full_id': full_id,
            'base_creative': extract_base_creative(prefix, num),
            'cost': data['cost'],
            'front_rev': data['front_rev'],
            'sales': data['sales'],
            'roas': roas,
            'nicho': nicho,
            'campaigns': list(data['campaigns']),
            'original_names': data['original_names'],
        }
        creatives.append(c)
    
    # 4. Attribute copywriters
    print(f"  Total criativos: {len(creatives)}")
    
    # Prefix-based
    for c in creatives:
        cw = attribute_copywriter(c['prefix'], c['num'], c['version'], c['full_id'])
        c['copywriter'] = cw
    
    # ClickUp batch for unknowns
    unknowns = [c for c in creatives if c['copywriter'] is None]
    print(f"  Pendentes ClickUp: {len(unknowns)}")
    
    if unknowns:
        keys = set()
        for c in unknowns:
            if c['full_id']:
                keys.add(c['full_id'])
                normalized = re.sub(r'(AD\d+)\s+(V\d+)', r'\1\2', c['full_id'], flags=re.IGNORECASE)
                if normalized != c['full_id']:
                    keys.add(normalized)
            if c['base_creative']:
                keys.add(c['base_creative'])
        
        cu_results = clickup_batch_search(list(keys))
        print(f"  ClickUp matches: {len(cu_results)}")
        
        for c in unknowns:
            cw = cu_results.get(c['full_id'])
            if not cw and c['base_creative']:
                cw = cu_results.get(c['base_creative'])
            c['copywriter'] = cw or "DESCONHECIDO"
    
    # 5. Extract DESCONHECIDO creatives
    print(f"\n[4/4] Categorizando DESCONHECIDO...")
    
    desconhecidos = sorted(
        [c for c in creatives if c['copywriter'] == 'DESCONHECIDO'],
        key=lambda x: x['front_rev'],
        reverse=True
    )
    
    print(f"\n{'=' * 80}")
    print(f"TOTAL DESCONHECIDO: {len(desconhecidos)}")
    print(f"{'=' * 80}\n")
    
    # Categorize
    categories = {
        'template': [],
        'antigo': [],
        'numero_puro': [],
        'no_prefix': [],
        'malformed': [],
        'outro': [],
    }
    
    for c in desconhecidos:
        name = c['name']
        
        # Template (YouTube sem UTM)
        if name.strip() == '{ad}' or '{ad}' in name:
            categories['template'].append(c)
        # Número puro
        elif re.match(r'^\d+(\s+V\d+)?$', name):
            categories['numero_puro'].append(c)
        # Sem prefixo AD
        elif not re.search(r'^AD\d+', name, re.IGNORECASE):
            categories['no_prefix'].append(c)
        # Malformed (muito curto, caracteres inválidos)
        elif len(name) < 3 or not re.search(r'\d', name):
            categories['malformed'].append(c)
        # Antigo (nome com padrão incompatível com atual)
        else:
            categories['antigo'].append(c)
    
    # Output por categoria
    for cat_name, cat_items in categories.items():
        if not cat_items:
            continue
        
        print(f"\n📌 {cat_name.upper()} ({len(cat_items)} criativos)")
        print(f"   Faturamento total: R$ {sum(x['front_rev'] for x in cat_items):,.2f}")
        print(f"{'-' * 80}")
        
        for i, c in enumerate(cat_items[:10], 1):  # Top 10 por categoria
            print(f"\n   #{i}. {c['name']}")
            print(f"      Faturamento: R$ {c['front_rev']:,.2f} | ROAS: {c['roas']:.2f} | Spend: R$ {c['cost']:,.2f}")
            print(f"      Nicho: {c['nicho']} | Criativos: {len(c['original_names'])}")
            print(f"      Campaigns: {c['campaigns'][0] if c['campaigns'] else 'N/A'}")
            if len(c['original_names']) > 1:
                print(f"      Variações RT: {', '.join(c['original_names'][:3])}")
        
        if len(cat_items) > 10:
            print(f"\n   ... e mais {len(cat_items) - 10} criativos")
    
    # Summary
    print(f"\n{'=' * 80}")
    print("RESUMO POR CATEGORIA")
    print(f"{'=' * 80}")
    
    summary_data = []
    for cat_name, cat_items in categories.items():
        if cat_items:
            total_rev = sum(x['front_rev'] for x in cat_items)
            pct = (total_rev / sum(c['front_rev'] for c in desconhecidos)) * 100 if desconhecidos else 0
            summary_data.append({
                'categoria': cat_name.upper(),
                'count': len(cat_items),
                'revenue': total_rev,
                'pct': pct,
            })
    
    summary_data.sort(key=lambda x: x['revenue'], reverse=True)
    
    total_unknown_rev = sum(c['front_rev'] for c in desconhecidos)
    
    for row in summary_data:
        print(f"{row['categoria']:15} | {row['count']:3d} criativos | R$ {row['revenue']:10,.2f} ({row['pct']:5.1f}%)")
    
    print(f"\n{'TOTAL':15} | {len(desconhecidos):3d} criativos | R$ {total_unknown_rev:10,.2f} ({100.0:5.1f}%)")
    
    # Export JSON for detail review
    output_file = os.path.expanduser('~/Scripts/data/desconhecidos_detalhado.json')
    export_data = {
        'periodo': {'from': date_from_str, 'to': date_to_str},
        'total': len(desconhecidos),
        'revenue': total_unknown_rev,
        'categorias': {},
    }
    
    for cat_name, cat_items in categories.items():
        if cat_items:
            export_data['categorias'][cat_name] = [
                {
                    'name': c['name'],
                    'faturamento': c['front_rev'],
                    'roas': c['roas'],
                    'spend': c['cost'],
                    'nicho': c['nicho'],
                    'campaigns': c['campaigns'],
                    'original_names': c['original_names'],
                }
                for c in cat_items
            ]
    
    with open(output_file, 'w') as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n📊 Exportado: {output_file}")
    print("\nConcluído!")

if __name__ == '__main__':
    analise_desconhecidos()
