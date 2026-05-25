#!/usr/bin/env python3
"""
Debug: Lista todos os criativos DESCONHECIDO do relatório
"""
import os, sys, json, re
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.expanduser('~/Scripts'))

# Import direto das funções do relatório
exec(open(os.path.expanduser('~/Scripts/relatorio_copywriters_semanal.py')).read())

# Rodar análise
date_to = datetime.now().date()
date_from = date_to - timedelta(days=7)
date_from_str = date_from.strftime('%Y-%m-%d')
date_to_str = date_to.strftime('%Y-%m-%d')

print("=" * 100)
print("DEBUG: ANÁLISE DE CRIATIVOS DESCONHECIDO")
print(f"Período: {date_from_str} a {date_to_str}")
print("=" * 100)

# Fetch
print("\n[1/4] Buscando RedTrack...")
try:
    raw_ads = fetch_all_ads(date_from_str, date_to_str)
    print(f"  {len(raw_ads)} registros")
except Exception as e:
    print(f"Erro: {e}")
    sys.exit(1)

# Process
print("\n[2/4] Processando...")
creatives = process_ads(raw_ads)
print(f"  {len(creatives)} criativos únicos")

# Attribute
print("\n[3/4] Atribuindo copywriters...")
creatives = attribute_all_copywriters(creatives)

# Filter desconhecidos
desconhecidos = sorted(
    [c for c in creatives if c['copywriter'] == 'DESCONHECIDO'],
    key=lambda x: x['cost'],
    reverse=True
)

print(f"\n{'=' * 100}")
print(f"TOTAL DESCONHECIDO: {len(desconhecidos)} criativos")
print(f"Faturamento total: R$ {sum(c['front_rev'] for c in desconhecidos):,.2f}")
print(f"{'=' * 100}\n")

# Categorize
categories = {'template': [], 'numero': [], 'sem_prefix': [], 'outro': []}

for c in desconhecidos:
    name = c['name']
    if '{ad}' in name:
        categories['template'].append(c)
    elif re.match(r'^\d+(\s+V\d+)?$', name):
        categories['numero'].append(c)
    elif not re.search(r'[AD]', name, re.IGNORECASE):
        categories['sem_prefix'].append(c)
    else:
        categories['outro'].append(c)

# Show cada categoria
for cat, items in categories.items():
    if not items:
        continue
    
    cat_total = sum(x['front_rev'] for x in items)
    cat_pct = (cat_total / sum(c['front_rev'] for c in desconhecidos)) * 100
    
    print(f"\n📌 {cat.upper()}: {len(items)} criativos | R$ {cat_total:,.2f} ({cat_pct:.1f}%)")
    print("-" * 100)
    
    sorted_items = sorted(items, key=lambda x: x['front_rev'], reverse=True)
    
    for i, c in enumerate(sorted_items[:15], 1):
        print(f"{i:2d}. {c['name']:40s} | Faturamento: R$ {c['front_rev']:10,.2f} | ROAS: {c['roas']:5.2f} | Spend: R$ {c['cost']:10,.2f} | Nicho: {c['nicho']:5s}")
    
    if len(sorted_items) > 15:
        rest_total = sum(x['front_rev'] for x in sorted_items[15:])
        print(f"    ... {len(sorted_items) - 15} mais | R$ {rest_total:,.2f}")

print(f"\n{'=' * 100}")
print("RESUMO CATEGORIZADO")
print(f"{'=' * 100}\n")

for cat in ['template', 'numero', 'sem_prefix', 'outro']:
    items = categories[cat]
    if items:
        cat_total = sum(x['front_rev'] for x in items)
        pct = (cat_total / sum(c['front_rev'] for c in desconhecidos)) * 100
        print(f"{cat:15s} | {len(items):3d} criativos | R$ {cat_total:10,.2f} ({pct:5.1f}%)")

print("\nConcluído!")
