#!/usr/bin/env python3
"""
Pareto Semanal — Top criativos que geram 80% do faturamento
Atualiza toda segunda-feira às 07h no canal privado do ClickUp
"""

import json
import os
import re
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta

REDTRACK_KEY = os.environ.get("REDTRACK_API_KEY", "")
CLICKUP_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
CHAT_VIEW_ID = "8cm1w4b-9913"  # Main Chat View para briefings


def rt_campaigns(df, dt):
    url = (f"https://api.redtrack.io/report?api_key={REDTRACK_KEY}"
           f"&group=campaign&date_from={df}&date_to={dt}&total=true&per=200&timezone=America/Sao_Paulo")
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read())


def rt_adgroups_campaign(df, dt, cid):
    url = (f"https://api.redtrack.io/report?api_key={REDTRACK_KEY}"
           f"&group=rt_adgroup&date_from={df}&date_to={dt}&campaign_id={cid}"
           f"&total=true&per=500&timezone=America/Sao_Paulo")
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read())


def extract_base(adgroup):
    name = adgroup.strip()
    if not name:
        return None
    name = re.sub(r'\s*[—-]\s*[Cc][oó]pia.*$', '', name)
    name = re.sub(r'\s*-\s*Copy.*$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*[-—]\s*\d{2}/\d{2}.*$', '', name)
    name = re.sub(r'\s*[-—]\s*\d{4}.*$', '', name)
    name = re.sub(r'^\d+[a-z]\d+v\d+\s+', '', name, flags=re.IGNORECASE)
    name = re.sub(r'^0\d\s+', '', name)
    name = re.sub(r'\s*-\s*\d+$', '', name)
    name = re.sub(r'^[-—]\s*', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    if not name or name in ['01', '02', '03']:
        return None
    return name


def post_chat(text):
    url = f"https://api.clickup.com/api/v2/view/{CHAT_VIEW_ID}/chat"
    payload = json.dumps({"content": text}).encode()
    req = urllib.request.Request(url, data=payload, method='POST')
    req.add_header("Authorization", CLICKUP_TOKEN)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"Erro ao postar no ClickUp: {e}")
        return None


def main():
    if not REDTRACK_KEY or not CLICKUP_TOKEN:
        print("ERRO: tokens não configurados")
        return

    now = datetime.now()
    # Last 7 days (last Monday to Sunday)
    yesterday = now - timedelta(days=1)
    week_start = yesterday - timedelta(days=6)
    df = week_start.strftime('%Y-%m-%d')
    dt = yesterday.strftime('%Y-%m-%d')

    df_display = week_start.strftime('%d.%m')
    dt_display = yesterday.strftime('%d.%m')

    print(f"[{now.strftime('%d/%m/%Y %H:%M')}] Pareto Semanal [{df_display} a {dt_display}]")

    # Fetch all campaigns
    campaigns = rt_campaigns(df, dt)
    active = [c for c in campaigns.get('items', []) if c.get('cost', 0) > 0]
    print(f"  {len(active)} campanhas ativas")

    # Consolidate adgroups across all campaigns
    consolidated = defaultdict(lambda: {'cost': 0, 'rev': 0, 'vendas': 0})

    for i, camp in enumerate(active):
        cid = camp.get('campaign_id', '')
        if not cid:
            continue
        try:
            data = rt_adgroups_campaign(df, dt, cid)
            for it in data.get('items', []):
                cost = it.get('cost', 0)
                if cost <= 0:
                    continue
                base = extract_base(it.get('rt_adgroup', ''))
                if not base:
                    continue
                rev = it.get('revenuetype2', 0) + it.get('revenuetype3', 0)
                consolidated[base]['cost'] += cost
                consolidated[base]['rev'] += rev
                consolidated[base]['vendas'] += it.get('convtype2', 0)
        except Exception as e:
            print(f"    Erro campanha {i+1}: {e}")
        time.sleep(1.5)

    # Build Pareto
    with_sales = []
    for name, d in consolidated.items():
        if d['vendas'] > 0:
            roas = d['rev'] / d['cost'] if d['cost'] > 0 else 0
            with_sales.append({
                'name': name, 'vendas': d['vendas'],
                'cost': d['cost'], 'rev': d['rev'], 'roas': round(roas, 2),
            })

    with_sales.sort(key=lambda x: -x['rev'])
    total_rev = sum(c['rev'] for c in with_sales)
    total_vendas = sum(c['vendas'] for c in with_sales)
    total_cost = sum(c['cost'] for c in with_sales)

    if total_rev == 0:
        print("  Sem dados de receita. Abortando.")
        return

    cumulative = 0
    pareto = []
    for c in with_sales:
        cumulative += c['rev']
        pct = cumulative / total_rev * 100
        pareto.append({**c, 'pct': pct})
        if cumulative >= total_rev * 0.80:
            break

    n_pareto = len(pareto)
    n_total = len(with_sales)
    pct_criativos = n_pareto / n_total * 100
    pareto_rev = sum(c['rev'] for c in pareto)
    pareto_vendas = sum(c['vendas'] for c in pareto)
    pareto_cost = sum(c['cost'] for c in pareto)
    pareto_roas = pareto_rev / pareto_cost if pareto_cost > 0 else 0
    geral_roas = total_rev / total_cost if total_cost > 0 else 0

    # Format message
    lines = [
        f"📊 ANÁLISE DE PARETO — SEMANA [{df_display} a {dt_display}]",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "RESUMO",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"• {n_pareto} criativos ({pct_criativos:.0f}% do total) geram 80% do faturamento",
        f"• Faturamento top {n_pareto}: R${pareto_rev:,.0f} de R${total_rev:,.0f}",
        f"• Vendas top {n_pareto}: {pareto_vendas} de {total_vendas}",
        f"• ROAS Pareto: {pareto_roas:.2f} (vs geral {geral_roas:.2f})",
        f"• Os outros {n_total - n_pareto} criativos geram apenas {100 - pareto_rev / total_rev * 100:.0f}%",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"TOP {n_pareto} CRIATIVOS (80% do faturamento)",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    for i, c in enumerate(pareto):
        arrow = "🟢" if c['roas'] >= 2.0 else ("🟡" if c['roas'] >= 1.5 else "🔴")
        lines.append(
            f"  {i + 1}. {arrow} {c['name']:<20} "
            f"{c['vendas']:>4} vendas | R${c['rev']:>10,.0f} | "
            f"ROAS {c['roas']:.2f} | {c['pct']:.1f}% acum."
        )

    lines.extend([
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "RECOMENDAÇÃO",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "• Concentrar variações nos criativos do Top 80%",
        "• Revisar criativos fora do Pareto com custo alto",
        "• Testar com mais budget os de amostra pequena + ROAS alto",
        "",
        f"— GPDR | {now.strftime('%d/%m/%Y %H:%M')}",
    ])

    text = "\n".join(lines)
    print(f"\n{text}\n")

    post_chat(text)
    print("✅ Pareto postado no canal ClickUp!")


if __name__ == "__main__":
    main()
