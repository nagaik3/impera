#!/usr/bin/env python3
"""
Extract detailed list of DESCONHECIDO creatives
"""
import os, sys, re
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.expanduser('~/Scripts'))

from relatorio_copywriters_semanal import (
    clean_ad_name, extract_creative_id, extract_nicho_from_campaign,
    extract_base_creative, attribute_copywriter, clickup_batch_search,
    fetch_all_ads
)

# Fetch data
date_to = datetime.now().date()
date_from = date_to - timedelta(days=7)
date_from_str = date_from.strftime('%Y-%m-%d')
date_to_str = date_to.strftime('%Y-%m-%d')

print("Fetching data...")
raw_ads = fetch_all_ads(date_from_str, date_to_str)

# Process
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

# Extract creatives
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
        'cost': data['cost'],
        'front_rev': data['front_rev'],
        'roas': roas,
        'nicho': nicho,
        'campaigns': list(data['campaigns']),
        'original_names': data['original_names'],
    }
    creatives.append(c)

# Attribute copywriters
for c in creatives:
    cw = attribute_copywriter(c['prefix'], c['num'], c['version'], c['full_id'])
    c['copywriter'] = cw

unknowns = [c for c in creatives if c['copywriter'] is None]

if unknowns:
    keys = set()
    for c in unknowns:
        if c['full_id']:
            keys.add(c['full_id'])
        if c.get('base_creative'):
            keys.add(c['base_creative'])
    
    cu_results = clickup_batch_search(list(keys))
    
    for c in unknowns:
        cw = cu_results.get(c['full_id'])
        if not cw and 'base_creative' in c:
            cw = cu_results.get(c['base_creative'])
        c['copywriter'] = cw or "DESCONHECIDO"

# Get DESCONHECIDO
desconhecidos = sorted(
    [c for c in creatives if c['copywriter'] == 'DESCONHECIDO'],
    key=lambda x: x['front_rev'],
    reverse=True
)

print(f"\nTotal DESCONHECIDO: {len(desconhecidos)}")

# Categorize
cat_template = []
cat_numero = []
cat_sem_prefix = []
cat_outro = []

for c in desconhecidos:
    name = c['name']
    if '{ad}' in name:
        cat_template.append(c)
    elif re.match(r'^\d+(\s+V\d+)?$', name):
        cat_numero.append(c)
    elif not re.search(r'[AD]', name, re.IGNORECASE):
        cat_sem_prefix.append(c)
    else:
        cat_outro.append(c)

# Display
print("\n" + "=" * 110)
print("CATEGORY: TEMPLATE (YouTube {ad} — ignorar)")
print("=" * 110)
print(f"Total: {len(cat_template)} | Revenue: R$ {sum(c['front_rev'] for c in cat_template):,.2f}\n")
for i, c in enumerate(sorted(cat_template, key=lambda x: x['front_rev'], reverse=True)[:20], 1):
    print(f"{i:2d}. {c['name']:50s} | R$ {c['front_rev']:10,.2f} | ROAS {c['roas']:.2f}")

print("\n" + "=" * 110)
print("CATEGORY: NÚMEROS PUROS (buscar em ClickUp)")
print("=" * 110)
print(f"Total: {len(cat_numero)} | Revenue: R$ {sum(c['front_rev'] for c in cat_numero):,.2f}\n")
for i, c in enumerate(sorted(cat_numero, key=lambda x: x['front_rev'], reverse=True)[:20], 1):
    print(f"{i:2d}. {c['name']:50s} | R$ {c['front_rev']:10,.2f} | ROAS {c['roas']:.2f} | Campaign: {c['campaigns'][0][:50] if c['campaigns'] else 'N/A'}")

print("\n" + "=" * 110)
print("CATEGORY: SEM PREFIX (verificar nomenclatura)")
print("=" * 110)
print(f"Total: {len(cat_sem_prefix)} | Revenue: R$ {sum(c['front_rev'] for c in cat_sem_prefix):,.2f}\n")
for i, c in enumerate(sorted(cat_sem_prefix, key=lambda x: x['front_rev'], reverse=True)[:20], 1):
    print(f"{i:2d}. {c['name']:50s} | R$ {c['front_rev']:10,.2f} | ROAS {c['roas']:.2f}")

print("\n" + "=" * 110)
print("CATEGORY: OUTRO (investigar)")
print("=" * 110)
print(f"Total: {len(cat_outro)} | Revenue: R$ {sum(c['front_rev'] for c in cat_outro):,.2f}\n")
for i, c in enumerate(sorted(cat_outro, key=lambda x: x['front_rev'], reverse=True)[:20], 1):
    print(f"{i:2d}. {c['name']:50s} | R$ {c['front_rev']:10,.2f} | ROAS {c['roas']:.2f}")

print("\n" + "=" * 110)
print("SUMMARY")
print("=" * 110)
print(f"{'TEMPLATE':20s} | {len(cat_template):3d} criativos | R$ {sum(c['front_rev'] for c in cat_template):10,.2f}")
print(f"{'NÚMERO PURO':20s} | {len(cat_numero):3d} criativos | R$ {sum(c['front_rev'] for c in cat_numero):10,.2f}")
print(f"{'SEM PREFIX':20s} | {len(cat_sem_prefix):3d} criativos | R$ {sum(c['front_rev'] for c in cat_sem_prefix):10,.2f}")
print(f"{'OUTRO':20s} | {len(cat_outro):3d} criativos | R$ {sum(c['front_rev'] for c in cat_outro):10,.2f}")
print(f"{'':20s} | {'-'*3s} {'':10s} | {'-'*11s}")
print(f"{'TOTAL':20s} | {len(desconhecidos):3d} criativos | R$ {sum(c['front_rev'] for c in desconhecidos):10,.2f}")
