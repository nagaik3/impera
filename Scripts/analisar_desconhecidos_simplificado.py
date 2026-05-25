#!/usr/bin/env python3
"""
Análise dos criativos DESCONHECIDO — usando relatório já rodado
"""
import os, sys, json, re
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.expanduser('~/Scripts'))
from cruzamento_clickup_redtrack import main as cruzamento_main

# Primeiro, rodar cruzamento em modo 'criativo'
print("=" * 80)
print("ANÁLISE: CRIATIVOS SEM ATRIBUIÇÃO DE COPYWRITER")
print("=" * 80)
print("\nRodando análise completa de cruzamento RT↔CU...\n")

# Chamar cruzamento_clickup_redtrack.py criativo para pegar dados brutos
sys.argv = ['cruzamento_clickup_redtrack.py', 'criativo']

try:
    cruzamento_main()
except SystemExit:
    pass

# Agora ler o cache gerado e analisar desconhecidos
print("\n" + "=" * 80)
print("ANÁLISE DE DESCONHECIDOS")
print("=" * 80)

cache_file = Path(os.path.expanduser('~/Scripts/data/cache/cruzamento_criativo_latest.json'))

if not cache_file.exists():
    print(f"\n⚠️  Arquivo cache não encontrado: {cache_file}")
    sys.exit(1)

with open(cache_file, 'r') as f:
    data = json.load(f)

# Extract desconhecidos
criativos = data.get('criativos', [])
desconhecidos = [c for c in criativos if c.get('copywriter') == 'DESCONHECIDO']

print(f"\nTotal de criativos: {len(criativos)}")
print(f"Desconhecido: {len(desconhecidos)}")
print(f"Faturamento desconhecido: R$ {sum(c['faturamento'] for c in desconhecidos):,.2f}")

if not desconhecidos:
    print("\n✅ Nenhum criativo desconhecido!")
    sys.exit(0)

# Categorize
categories = {
    'template': [],
    'numero_puro': [],
    'no_prefix': [],
    'antigo': [],
    'outro': [],
}

for c in desconhecidos:
    name = c.get('criativo', '')
    
    if '{ad}' in name:
        categories['template'].append(c)
    elif re.match(r'^\d+(\s+V\d+)?$', name):
        categories['numero_puro'].append(c)
    elif not re.search(r'^AD\d+', name, re.IGNORECASE):
        categories['no_prefix'].append(c)
    elif len(name) < 3:
        categories['antigo'].append(c)
    else:
        categories['outro'].append(c)

# Display
for cat_name in ['template', 'numero_puro', 'no_prefix', 'antigo', 'outro']:
    cat_items = categories[cat_name]
    if not cat_items:
        continue
    
    cat_rev = sum(x['faturamento'] for x in cat_items)
    cat_pct = (cat_rev / sum(c['faturamento'] for c in desconhecidos)) * 100
    
    print(f"\n📌 {cat_name.upper()}: {len(cat_items)} criativos | R$ {cat_rev:,.2f} ({cat_pct:.1f}%)")
    print(f"{'-' * 80}")
    
    sorted_items = sorted(cat_items, key=lambda x: x['faturamento'], reverse=True)
    
    for i, c in enumerate(sorted_items[:8], 1):
        name = c['criativo']
        fatuamento = c['faturamento']
        roas = c['roas']
        spend = c['spend']
        nicho = c['nicho']
        
        print(f"\n  #{i}. {name}")
        print(f"     Faturamento: R$ {fatuamento:,.2f} | ROAS: {roas:.2f} | Spend: R$ {spend:,.2f}")
        print(f"     Nicho: {nicho}")
        
        if c.get('campaigns'):
            print(f"     Campaign: {c['campaigns'][0][:60]}")
        
        # Action suggestion
        if cat_name == 'template':
            print(f"     ✅ Ação: Template YouTube — sem ação necessária (ignorar)")
        elif cat_name == 'numero_puro':
            print(f"     ✅ Ação: Buscar em ClickUp por número | Criar task se não existir")
        elif cat_name == 'no_prefix':
            print(f"     ✅ Ação: Verificar naming pattern | Pode ser ad antigo")
        elif cat_name == 'antigo':
            print(f"     ✅ Ação: Ads históricos | Baixa prioridade")
        else:
            print(f"     ✅ Ação: Investigar origem em RedTrack")
    
    if len(sorted_items) > 8:
        print(f"\n  ... e mais {len(sorted_items) - 8} criativos")

# Summary
print(f"\n{'=' * 80}")
print("RESUMO & RECOMENDAÇÕES")
print(f"{'=' * 80}\n")

print("Distribuição por categoria:")
for cat_name in ['template', 'numero_puro', 'no_prefix', 'antigo', 'outro']:
    cat_items = categories[cat_name]
    if cat_items:
        cat_rev = sum(x['faturamento'] for x in cat_items)
        pct = (cat_rev / sum(c['faturamento'] for c in desconhecidos)) * 100
        print(f"  {cat_name:15} | {len(cat_items):3d} criativos | R$ {cat_rev:10,.2f} ({pct:5.1f}%)")

print("\nPróximos passos:")
print("  1. Templates ({ad}): Ignorar — não têm dados de criativo real")
print("  2. Números puros: Buscar em ClickUp + criar tasks se faltarem")
print("  3. Sem prefixo: Validar padrão de nomenclatura em RedTrack")
print("  4. Antigos: Arquivar se data > 30 dias, ou atualizar nomenclatura")
print("  5. Outro: Investigar caso a caso")

print("\n✅ Análise concluída!")
