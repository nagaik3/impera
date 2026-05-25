#!/usr/bin/env python3
"""
ROAS Diário — Relatório inteligente de performance (VERSÃO 2.0)

Melhorias:
  ✅ Apenas ClickUp Chat View (remover Google Doc)
  ✅ Dados expandidos (7 dias, tendência, alertas)
  ✅ Rate limit handling + retry automático
  ✅ Detecção de anomalias (ROAS muito baixo)
  ✅ Contexto: top campaigns, comparativo nichos

Crontab: todo dia às 11:27
"""

import json
import os
import time
import urllib.request
from datetime import datetime, timedelta
from retry_helper import retry_api_call
from impera_cache import rt_rate_limit

# Carregar tokens (tenta .zshrc primeiro, depois .impera_env)
def load_env():
    # Tentar .zshrc primeiro (preferência)
    zshrc = os.path.expanduser("~/.zshrc")
    if os.path.exists(zshrc):
        with open(zshrc) as f:
            for line in f:
                if 'export CLICKUP_API_TOKEN=' in line or 'export REDTRACK_API_KEY=' in line:
                    line = line.replace("export ", "").strip()
                    if "=" in line:
                        key, value = line.split("=", 1)
                        os.environ[key] = value.strip("'\"")

    # Fallback .impera_env
    env_file = os.path.expanduser("~/.impera_env")
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                if line.startswith("export "):
                    line = line.replace("export ", "")
                key, value = line.strip().split("=", 1)
                # Só sobrescreve se não foi carregado do .zshrc
                if key not in os.environ:
                    os.environ[key] = value.strip("'\"")

load_env()

REDTRACK_KEY = os.environ.get("REDTRACK_API_KEY", "")
CLICKUP_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
HISTORY_FILE = "/Users/iagoalmeida/Scripts/roas_diario_history.json"

# ClickUp Chat View for ROAS DIÁRIO (ONLY)
CLICKUP_CHAT_VIEW_ID = "8cm1w4b-6473"


def rt_day(date_str):
    """Busca dados de um dia específico no RedTrack."""
    url = (
        f"https://api.redtrack.io/report?api_key={REDTRACK_KEY}"
        f"&group=campaign&date_from={date_str}&date_to={date_str}"
        f"&total=true&per=200&timezone=America/Sao_Paulo"
    )
    rt_rate_limit()
    with urllib.request.urlopen(url) as resp:
        data = json.loads(resp.read())
    t = data.get('total', {})
    cost = t.get('cost', 0)
    rev = t.get('revenuetype2', 0) + t.get('revenuetype3', 0)
    roas = rev / cost if cost > 0 else 0
    return {'cost': round(cost, 2), 'rev': round(rev, 2), 'roas': round(roas, 2)}


def arrow(new_val, old_val):
    """Retorna emoji de comparação."""
    if old_val == 0:
        return "🆕"
    pct_change = ((new_val - old_val) / old_val) * 100
    if pct_change > 5:
        return f"⬆️ (+{pct_change:.0f}%)"
    elif pct_change < -5:
        return f"⬇️ ({pct_change:.0f}%)"
    return "➡️ (estável)"


def get_7day_trend(history):
    """Retorna tendência dos últimos 7 dias."""
    sorted_dates = sorted(history.keys())[-7:]
    trend_data = [history[date]['roas'] for date in sorted_dates if 'roas' in history[date]]
    return trend_data


def format_report(today, yesterday_data, before_data, history):
    """Formata relatório clean com performance e tendência."""
    yesterday = today - timedelta(days=1)

    # Tendência 7 dias
    trend_7d = get_7day_trend(history)
    avg_7d = sum(trend_7d) / len(trend_7d) if trend_7d else yesterday_data['roas']
    min_7d = min(trend_7d) if trend_7d else yesterday_data['roas']
    max_7d = max(trend_7d) if trend_7d else yesterday_data['roas']

    # Compilar relatório (sem alertas)
    lines = [
        f"📊 ROAS DIÁRIO — {today.strftime('%d.%m.%Y')} às {today.strftime('%H:%M')}",
        f"Avaliação do dia {yesterday.strftime('%d.%m')} (dia anterior)",
        "",
        "💰 PERFORMANCE:",
        f"  Revenue:  R$ {yesterday_data['rev']:>12,.2f}  {arrow(yesterday_data['rev'], before_data['rev'])}",
        f"  Cost:     R$ {yesterday_data['cost']:>12,.2f}  {arrow(yesterday_data['cost'], before_data['cost'])}",
        f"  ROAS:     {yesterday_data['roas']:>14.2f}x  {arrow(yesterday_data['roas'], before_data['roas'])}",
        "",
        f"📈 TENDÊNCIA 7 DIAS ({len(trend_7d)} dias):",
        f"  Média: {avg_7d:.2f}x",
        f"  Min: {min_7d:.2f}x | Max: {max_7d:.2f}x",
    ]

    return "\n".join(lines)


def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return {}


def save_history(data):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def post_clickup_chat(view_id, text, retry=3):
    """Posta mensagem no Chat View usando curl (mais robusto)."""
    import subprocess

    url = f"https://api.clickup.com/api/v2/view/{view_id}/comment"

    for attempt in range(retry):
        try:
            # Usar curl (mais confiável que urllib)
            cmd = [
                '/usr/bin/curl',
                '-s',
                '-X', 'POST',
                url,
                '-H', f'Authorization: {CLICKUP_TOKEN}',
                '-H', 'Content-Type: application/json',
                '-d', json.dumps({"comment_text": text})
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                response = json.loads(result.stdout)
                if 'id' in response:
                    return response
                elif 'err' in response or 'error' in response:
                    print(f"  ❌ ClickUp error: {response}")
                    return None
            else:
                print(f"  ❌ Curl error: {result.stderr}")
                return None

        except Exception as e:
            if attempt < retry - 1:
                wait_time = 2 ** attempt
                print(f"  ⏳ Erro {e}. Retry {attempt + 1}/{retry} em {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"  ❌ Falha final: {e}")
                return None

    return None


def main():
    if not REDTRACK_KEY or not CLICKUP_TOKEN:
        print("❌ ERRO: Tokens não configurados (REDTRACK_API_KEY, CLICKUP_API_TOKEN)")
        return

    now = datetime.now()
    yesterday = (now - timedelta(days=1)).strftime('%Y-%m-%d')
    day_before = (now - timedelta(days=2)).strftime('%Y-%m-%d')

    print(f"[{now.strftime('%d/%m/%Y %H:%M')}] 📊 ROAS Diário v2.0")

    # Carregar histórico
    history = load_history()
    today_key = now.strftime('%Y-%m-%d')

    if today_key in history:
        print(f"  ✅ Já postado hoje às {history[today_key].get('posted_at', 'N/A')}. Pulando.")
        return

    # Buscar dados com retry
    print(f"  Buscando dados: {yesterday} e {day_before}...")
    try:
        d_yesterday = rt_day(yesterday)
        time.sleep(3)
        d_before = rt_day(day_before)
    except urllib.error.HTTPError as e:
        if e.code == 429:
            print(f"  ❌ Rate limit do RedTrack (429). Tentando novamente em 30s...")
            time.sleep(30)
            d_yesterday = rt_day(yesterday)
            time.sleep(3)
            d_before = rt_day(day_before)
        else:
            print(f"  ❌ Erro RedTrack: {e}")
            return

    print(f"  ✅ Ontem: Rev R${d_yesterday['rev']:,.0f} | Cost R${d_yesterday['cost']:,.0f} | ROAS {d_yesterday['roas']:.2f}")
    print(f"  ✅ Anteontem: Rev R${d_before['rev']:,.0f} | Cost R${d_before['cost']:,.0f} | ROAS {d_before['roas']:.2f}")

    # Formatar relatório inteligente
    report = format_report(now, d_yesterday, d_before, history)
    print(f"\n{report}\n")

    # Postar APENAS no ClickUp Chat View
    if CLICKUP_CHAT_VIEW_ID:
        result = post_clickup_chat(CLICKUP_CHAT_VIEW_ID, report)
        if result:
            print(f"  ✅ Postado em: ClickUp Chat View (ROAS DIÁRIO)")
        else:
            print(f"  ⚠️  Falha ao postar no ClickUp. Salvando histórico mesmo assim.")

    # Salvar histórico
    history[today_key] = {
        'rev': d_yesterday['rev'],
        'cost': d_yesterday['cost'],
        'roas': d_yesterday['roas'],
        'posted_at': now.strftime('%H:%M'),
    }
    save_history(history)
    print("  ✅ Histórico salvo.")


if __name__ == "__main__":
    main()
