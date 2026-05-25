#!/usr/bin/env python3
"""
Dashboard IMPERA — Performance de Campanhas
Flask app local em localhost:5000
"""

import json
import os
import re
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

REDTRACK_API_KEY = os.environ.get("REDTRACK_API_KEY", "")
CLICKUP_API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")

NICHO_NAMES = {
    'EM': 'Emagrecimento', 'DB': 'Diabetes', 'NE': 'Neuropatia',
    'MM': 'Memória BR', 'ME': 'Memória EUA', 'PT': 'Próstata',
    'DA': 'Dores Articulares', 'ED': 'Adulto / ED', 'ZB': 'Zumbido',
    'RJ': 'Rejuvenescimento',
}
GESTOR_MAP = {
    'LUCAS': 'Lucas Cavalcanti', 'LUDSON': 'Ludson Chaves',
    'DOUG': 'Douglas Oliveira', 'FRAZA': 'Gabriel Fraza',
    'GABRIEL': 'Gabriel Fraza',
}
NICHO_KW = {
    'EMAGRECIMENTO': 'EM', 'DIABETES': 'DB', 'NEUROPATIA': 'NE',
    'MEMORIA': 'MM', 'PROSTATA': 'PT', 'REJUVENESCIMENTO': 'RJ',
    'GELATINAFIT': 'EM', 'GELATINA': 'EM', 'EREMED': 'ED',
}
NICHO_COLORS = {
    'EM': '#10b981', 'DB': '#3b82f6', 'NE': '#8b5cf6',
    'MM': '#f59e0b', 'ME': '#f97316', 'PT': '#06b6d4',
    'ED': '#ef4444', 'ZB': '#6366f1', 'RJ': '#ec4899',
    'DA': '#14b8a6',
}


def rt_report(date_from, date_to):
    url = (
        f"https://api.redtrack.io/report?api_key={REDTRACK_API_KEY}"
        f"&group=campaign&date_from={date_from}&date_to={date_to}"
        f"&total=true&per=200"
    )
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read())


def parse_campaign(name):
    info = {'name': name}
    m = re.match(r'\[(\w+)\]', name)
    info['fonte'] = m.group(1) if m else '?'

    m = re.search(r'VSL\s*(\d+)', name)
    info['oferta'] = f"VSL {m.group(1)}" if m else '-'

    info['nicho'] = '?'
    upper = name.upper()
    if 'MEMORIA EUA' in upper:
        info['nicho'] = 'ME'
    elif 'EMAGRECIMENTOLUDSON' in upper:
        info['nicho'] = 'EM'
    else:
        for kw, sig in NICHO_KW.items():
            if kw in upper:
                info['nicho'] = sig
                break

    g = re.search(r'G\.\s*(\w+)', name, re.IGNORECASE)
    info['gestor'] = GESTOR_MAP.get(g.group(1).upper(), g.group(1)) if g else (
        'Gabriel Fraza' if 'Gabriel Fraza' in name else '?')

    return info


def classify(roas, cost):
    if roas >= 2.0 and cost >= 10000:
        return 'Principal'
    elif roas >= 1.5 and cost >= 1000:
        return 'Positiva'
    elif roas < 1.0:
        return 'Negativa'
    elif roas < 1.5:
        return 'Em Risco'
    else:
        return 'Positiva'


def get_data(date_from, date_to):
    data = rt_report(date_from, date_to)
    items = data.get('items', [])
    total = data.get('total', {})

    campaigns = []
    for item in items:
        cost = item.get('cost', 0)
        if cost <= 0:
            continue
        info = parse_campaign(item.get('campaign', ''))
        front_rev = item.get('revenuetype2', 0) + item.get('revenuetype3', 0)
        roas = front_rev / cost if cost > 0 else 0
        info.update({
            'cost': cost,
            'front_rev': front_rev,
            'roas': round(roas, 2),
            'profit': round(front_rev - cost, 2),
            'clicks': item.get('clicks', 0),
            'classificacao': classify(roas, cost),
        })
        campaigns.append(info)

    campaigns.sort(key=lambda x: -x['cost'])

    # Aggregations
    nicho_stats = defaultdict(lambda: {'cost': 0, 'front_rev': 0, 'campaigns': 0})
    gestor_stats = defaultdict(lambda: {'cost': 0, 'front_rev': 0, 'testes': 0, 'validadas': 0})

    for c in campaigns:
        n = nicho_stats[c['nicho']]
        n['cost'] += c['cost']
        n['front_rev'] += c['front_rev']
        n['campaigns'] += 1

        g = gestor_stats[c['gestor']]
        g['cost'] += c['cost']
        g['front_rev'] += c['front_rev']
        g['testes'] += 1
        if c['roas'] >= 1.5:
            g['validadas'] += 1

    t_cost = total.get('cost', 0)
    t_rev = total.get('revenuetype2', 0) + total.get('revenuetype3', 0)
    t_roas = round(t_rev / t_cost, 2) if t_cost > 0 else 0

    cls_count = defaultdict(int)
    for c in campaigns:
        cls_count[c['classificacao']] += 1

    return {
        'campaigns': campaigns,
        'nicho_stats': dict(nicho_stats),
        'gestor_stats': dict(gestor_stats),
        'totals': {'cost': t_cost, 'front_rev': t_rev, 'roas': t_roas},
        'classificacao_count': dict(cls_count),
        'nicho_names': NICHO_NAMES,
        'nicho_colors': NICHO_COLORS,
        'date_from': date_from,
        'date_to': date_to,
    }


@app.route('/')
def dashboard():
    today = datetime.now()
    df = request.args.get('date_from', (today - timedelta(days=7)).strftime('%Y-%m-%d'))
    dt = request.args.get('date_to', (today - timedelta(days=1)).strftime('%Y-%m-%d'))
    data = get_data(df, dt)
    return render_template('dashboard.html', data=data)


@app.route('/api/data')
def api_data():
    today = datetime.now()
    df = request.args.get('date_from', (today - timedelta(days=7)).strftime('%Y-%m-%d'))
    dt = request.args.get('date_to', (today - timedelta(days=1)).strftime('%Y-%m-%d'))
    data = get_data(df, dt)
    return jsonify(data)


if __name__ == '__main__':
    app.run(debug=True, port=5000)
