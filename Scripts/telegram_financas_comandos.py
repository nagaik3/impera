#!/usr/bin/env python3
"""
Bot ClaudioFinanças — Comandos Telegram
Processa comandos recebidos e responde com dados financeiros.
Executar via crontab a cada 2 minutos para checar novos comandos.
"""

import json
import urllib.request
import urllib.parse
import os
from datetime import datetime, timedelta

BOT_TOKEN = "8650778497:AAE-fngcbrpWCQc4AtzhbW8bkbH9fvG8yeA"
CHAT_ID = "5883974795"
STATE_FILE = os.path.expanduser("~/Scripts/data/telegram_financas_last_update.txt")
EXTRAS_FILE = os.path.expanduser("~/Scripts/data/financas_extras.json")

# ============================================================
# CATEGORIAS PARA RECEITAS/DESPESAS EXTRAS
# ============================================================

CATEGORIAS_RECEITA = {
    "1": "Trabalho extra",
    "2": "Freelance",
    "3": "Venda",
    "4": "Reembolso",
    "5": "Bônus",
    "6": "Presente recebido",
    "7": "Outro",
}

CATEGORIAS_DESPESA = {
    "1": "Alimentação",
    "2": "Transporte",
    "3": "Saúde/Farmácia",
    "4": "Compras casa",
    "5": "Roupas/Calçados",
    "6": "Lazer/Entretenimento",
    "7": "Presente",
    "8": "Educação",
    "9": "Bebê/Lara",
    "10": "Emergência",
    "11": "Outro",
}

# Estado de conversação por usuário
PENDING_ACTIONS = {}
PENDING_FILE = os.path.expanduser("~/Scripts/data/telegram_financas_pending.json")

def load_pending():
    try:
        with open(PENDING_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_pending(data):
    os.makedirs(os.path.dirname(PENDING_FILE), exist_ok=True)
    with open(PENDING_FILE, "w") as f:
        json.dump(data, f)

def load_extras():
    try:
        with open(EXTRAS_FILE, "r") as f:
            return json.load(f)
    except:
        return {"receitas": [], "despesas": []}

def save_extras(data):
    os.makedirs(os.path.dirname(EXTRAS_FILE), exist_ok=True)
    with open(EXTRAS_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def send_message(text, parse_mode="HTML"):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = json.dumps({
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": parse_mode
    }).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req)
    except:
        pass

def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    if offset:
        url += f"?offset={offset}"
    try:
        resp = urllib.request.urlopen(url)
        return json.loads(resp.read())
    except:
        return {"result": []}

def get_last_update_id():
    try:
        with open(STATE_FILE, "r") as f:
            return int(f.read().strip())
    except:
        return 0

def save_last_update_id(update_id):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        f.write(str(update_id))

# ============================================================
# DADOS FINANCEIROS (atualizar mensalmente)
# ============================================================

RECEITAS = {
    "IMPERA fixo": 6500,
    "IMPERA MC BR (2,5%)": 6250,  # base R$250K
    "Metabofit": 2000,
    "Cut Creative": 1600,
    "Lucas Assis": 2000,
    "Reembolso padrasto": 1200,
    "Well notebook": 290,
}

DESPESAS_FIXAS = {
    "Empréstimo PicPay": 2204,
    "Moradia": 2577,
    "Parcelas cartão": 2500,
    "Editores (3)": 2000,
    "Alimentação/farmácia": 1500,
    "Plano saúde (Unimed)": 800,
    "Transporte (99)": 400,
    "Assinaturas": 380,
    "C6 Carbon anuidade": 98,
    "Clube Livelo": 50,
    "Contador": 350,
    "Light": 300,
    "Vivo": 210,
}

IMPOSTOS = {
    "DAS Simples (Anexo III)": 1363,
    "INSS pro-labore": 500,
}

CARTOES = {
    "Mercado Pago": {"limite": 18000, "vencimento": 5, "alarme": 3},
    "Banco Inter": {"limite": 20390, "vencimento": 10, "alarme": 8},
    "PicPay": {"limite": 6090, "vencimento": 15, "alarme": 13},
    "Iti/Itaú": {"limite": 5930, "vencimento": 20, "alarme": 18},
    "Nubank": {"limite": 6100, "vencimento": 24, "alarme": 22},
}

PICPAY_EMPRESTIMO = {
    "parcelas_pagas": 5,
    "parcelas_total": 18,
    "valor_parcela": 2204,
    "valor_quitar_hoje": 19584,
    "desconto_quitacao": 9071,
    "previsao_quitacao": "Ago/26",
}

MILHAS = {
    "cartao": "C6 Carbon (PF)",
    "pts_por_dolar": 2.5,
    "gasto_mensal_carbon": 5500,
    "contas_pelo_c6": 1300,  # Light, Vivo, Unimed, etc
    "pts_por_mes_carbon": 2500,
    "pts_por_mes_contas": 591,
    "clube_livelo_ano": 15000,
    "anuidade_mes": 98,
    "meta_europa": 100000,
    "meta_canada": 127000,
    "meta_japao": 250000,
}

EMIGRACAO = {
    "Paraguai": {"custo": 48000, "data": "Fev/27"},
    "Canadá": {"custo": 80000, "data": "Jun/27"},
    "Japão": {"custo": 150000, "data": "2028+"},
}

# ============================================================
# COMANDOS
# ============================================================

def cmd_resumo():
    receita_bruta = sum(RECEITAS.values())
    impostos = sum(IMPOSTOS.values())
    receita_liq = receita_bruta - impostos
    despesas = sum(DESPESAS_FIXAS.values())

    # Extras do mês
    extras = load_extras()
    mes_atual = datetime.now().strftime("%Y-%m")
    extras_rec = sum(r["valor"] for r in extras["receitas"] if r["data"].startswith(mes_atual))
    extras_desp = sum(d["valor"] for d in extras["despesas"] if d["data"].startswith(mes_atual))

    receita_total = receita_liq + extras_rec
    despesa_total = despesas + extras_desp
    margem = receita_total - despesa_total

    extras_line = ""
    if extras_rec > 0 or extras_desp > 0:
        extras_line = f"\n📝 <b>Extras mês:</b> +R$ {extras_rec:,.0f} receita / -R$ {extras_desp:,.0f} despesa"

    return f"""📊 <b>RESUMO FINANCEIRO — {datetime.now().strftime('%B/%Y')}</b>

💰 <b>Receita bruta:</b> R$ {receita_bruta:,.0f}
🏛 <b>Impostos:</b> R$ {impostos:,.0f}
💵 <b>Receita líquida:</b> R$ {receita_liq:,.0f}
📉 <b>Despesas fixas:</b> R$ {despesas:,.0f}{extras_line}

{'🟢' if margem > 3000 else '🟡' if margem > 0 else '🔴'} <b>Margem:</b> R$ {margem:,.0f}
📈 <b>Taxa poupança:</b> {margem/receita_total*100:.1f}%"""


def cmd_receitas():
    total = sum(RECEITAS.values())
    linhas = "\n".join([f"  • {k}: R$ {v:,.0f}" for k, v in RECEITAS.items()])
    return f"""💰 <b>RECEITAS</b>

{linhas}

<b>Total bruto:</b> R$ {total:,.0f}"""


def cmd_despesas():
    total = sum(DESPESAS_FIXAS.values())
    linhas = "\n".join([f"  • {k}: R$ {v:,.0f}" for k, v in DESPESAS_FIXAS.items()])
    return f"""📉 <b>DESPESAS</b>

{linhas}

<b>Total:</b> R$ {total:,.0f}"""


def cmd_cartoes():
    hoje = datetime.now().day
    linhas = []
    for nome, info in CARTOES.items():
        dias_ate = info["vencimento"] - hoje
        if dias_ate < 0:
            dias_ate += 30
        status = "⚠️" if dias_ate <= 3 else "✅"
        linhas.append(f"  {status} <b>{nome}</b> — vence dia {info['vencimento']} ({dias_ate} dias)")

    return f"""💳 <b>CARTÕES DE CRÉDITO</b>

{chr(10).join(linhas)}

Limite total: R$ {sum(c['limite'] for c in CARTOES.values()):,.0f}"""


def cmd_picpay():
    p = PICPAY_EMPRESTIMO
    restantes = p["parcelas_total"] - p["parcelas_pagas"]
    total_normal = restantes * p["valor_parcela"]

    return f"""🏦 <b>EMPRÉSTIMO PICPAY</b>

📋 Parcelas: {p['parcelas_pagas']}/{p['parcelas_total']} pagas ({restantes} restantes)
💵 Parcela mensal: R$ {p['valor_parcela']:,.0f}
📊 Total restante (normal): R$ {total_normal:,.0f}
🏷 Valor para quitar hoje: R$ {p['valor_quitar_hoje']:,.0f}
💰 Desconto quitação: R$ {p['desconto_quitacao']:,.0f}
🎯 Previsão quitação (amortizando): <b>{p['previsao_quitacao']}</b>

💡 Dica: antecipar as ÚLTIMAS parcelas primeiro (desconto de até 55%)"""


def cmd_milhas():
    m = MILHAS
    pts_mes_total = m["pts_por_mes_carbon"] + m["pts_por_mes_contas"]
    pts_ano = pts_mes_total * 12 + m["clube_livelo_ano"]
    pts_ano_bonus80 = int(pts_ano * 1.8)
    pts_ano_bonus100 = int(pts_ano * 2.0)

    meses_europa = round(m["meta_europa"] / (pts_ano_bonus80 / 12))
    meses_canada = round(m["meta_canada"] / (pts_ano_bonus80 / 12))
    meses_japao = round(m["meta_japao"] / (pts_ano_bonus80 / 12))

    return f"""✈️ <b>ESTRATÉGIA DE MILHAS</b>

🃏 <b>Cartão:</b> {m['cartao']}
⚡ <b>Pontuação:</b> {m['pts_por_dolar']} pts/USD

📊 <b>Acúmulo mensal:</b>
  • Gastos pessoais (R$ {m['gasto_mensal_carbon']:,.0f}): ~{m['pts_por_mes_carbon']:,} pts
  • Contas pelo C6 (R$ {m['contas_pelo_c6']:,.0f}): ~{m['pts_por_mes_contas']:,} pts
  • Clube Livelo: ~1.250 pts/mês
  • <b>Total: ~{pts_mes_total + 1250:,} pts/mês</b>

📅 <b>Acúmulo anual:</b>
  • Base: {pts_ano:,} pontos
  • Com bônus 80%: <b>{pts_ano_bonus80:,} milhas</b>
  • Com bônus 100%: <b>{pts_ano_bonus100:,} milhas</b>

🎯 <b>Timeline (com bônus 80%):</b>
  🇪🇺 Europa: ~{meses_europa} meses
  🇨🇦 Canadá: ~{meses_canada} meses
  🇯🇵 Japão: ~{meses_japao} meses

💰 Anuidade Carbon: R$ {m['anuidade_mes']}/mês
💡 Concentrar TODOS gastos pessoais no C6 Carbon!
💡 Aguardar promoções de transferência bonificada!"""


def cmd_emigracao():
    linhas = []
    for pais, info in EMIGRACAO.items():
        linhas.append(f"  🌍 <b>{pais}</b>: R$ {info['custo']:,.0f} — {info['data']}")

    return f"""🛫 <b>PLANO DE EMIGRAÇÃO</b>

{chr(10).join(linhas)}

📋 Próximos passos:
1. Quitar PicPay (Ago/26)
2. Poupar R$ 7.800+/mês (Set/26+)
3. Acumular milhas C6 Carbon
4. Contratar plano de saúde
5. Migrar MEI → ME"""


def cmd_faturas():
    hoje = datetime.now()
    linhas = []
    for nome, info in sorted(CARTOES.items(), key=lambda x: x[1]["vencimento"]):
        venc = info["vencimento"]
        dias = venc - hoje.day
        if dias < 0:
            dias += 30
            mes = "próximo mês"
        else:
            mes = "este mês"

        if dias <= 2:
            emoji = "🔴"
        elif dias <= 5:
            emoji = "🟡"
        else:
            emoji = "🟢"

        linhas.append(f"  {emoji} {nome}: dia {venc} ({dias} dias) — {mes}")

    return f"""📅 <b>PRÓXIMAS FATURAS</b>

{chr(10).join(linhas)}

💡 Pagar sempre o valor TOTAL para evitar juros!"""


def cmd_adicionar_receita():
    cats = "\n".join([f"  {k}. {v}" for k, v in CATEGORIAS_RECEITA.items()])
    return f"""💰 <b>ADICIONAR RECEITA EXTRA</b>

Escolha a categoria:
{cats}

📝 Responda no formato:
<code>categoria | valor | descrição</code>

Exemplo:
<code>1 | 500 | Edição extra pro João</code>
<code>5 | 2500 | Bônus IMPERA março</code>"""


def cmd_adicionar_despesa():
    cats = "\n".join([f"  {k}. {v}" for k, v in CATEGORIAS_DESPESA.items()])
    return f"""📉 <b>ADICIONAR DESPESA EXTRA</b>

Escolha a categoria:
{cats}

📝 Responda no formato:
<code>categoria | valor | descrição</code>

Exemplo:
<code>7 | 150 | Presente dia das mães esposa</code>
<code>9 | 89 | Fralda Pampers Lara</code>"""


def cmd_extrato():
    extras = load_extras()
    hoje = datetime.now()
    mes_atual = hoje.strftime("%Y-%m")

    receitas_mes = [r for r in extras["receitas"] if r["data"].startswith(mes_atual)]
    despesas_mes = [d for d in extras["despesas"] if d["data"].startswith(mes_atual)]

    total_rec = sum(r["valor"] for r in receitas_mes)
    total_desp = sum(d["valor"] for d in despesas_mes)

    linhas = []

    if receitas_mes:
        linhas.append("\n💰 <b>Receitas extras:</b>")
        for r in receitas_mes:
            linhas.append(f"  ✅ R$ {r['valor']:,.0f} — {r['categoria']}: {r['descricao']} ({r['data'][8:10]}/{r['data'][5:7]})")

    if despesas_mes:
        linhas.append("\n📉 <b>Despesas extras:</b>")
        for d in despesas_mes:
            linhas.append(f"  🔸 R$ {d['valor']:,.0f} — {d['categoria']}: {d['descricao']} ({d['data'][8:10]}/{d['data'][5:7]})")

    if not receitas_mes and not despesas_mes:
        linhas.append("\nNenhum lançamento extra este mês.")

    saldo = total_rec - total_desp
    emoji_saldo = "🟢" if saldo >= 0 else "🔴"

    return f"""📋 <b>EXTRATO EXTRAS — {hoje.strftime('%B/%Y')}</b>
{chr(10).join(linhas)}

💰 Total receitas extras: R$ {total_rec:,.0f}
📉 Total despesas extras: R$ {total_desp:,.0f}
{emoji_saldo} Saldo extras: R$ {saldo:,.0f}"""


def cmd_apagar():
    extras = load_extras()
    hoje = datetime.now()
    mes_atual = hoje.strftime("%Y-%m")

    todos = []
    for r in extras["receitas"]:
        if r["data"].startswith(mes_atual):
            todos.append(("receita", r))
    for d in extras["despesas"]:
        if d["data"].startswith(mes_atual):
            todos.append(("despesa", d))

    if not todos:
        return "📋 Nenhum lançamento extra este mês para apagar."

    linhas = []
    for i, (tipo, item) in enumerate(todos, 1):
        emoji = "💰" if tipo == "receita" else "📉"
        linhas.append(f"  {i}. {emoji} R$ {item['valor']:,.0f} — {item['descricao']}")

    return f"""🗑 <b>APAGAR LANÇAMENTO</b>

Qual lançamento deseja apagar?
{chr(10).join(linhas)}

📝 Responda com o número. Ex: <code>apagar 2</code>"""


def process_add_receita(text):
    try:
        parts = text.split("|")
        if len(parts) < 3:
            return "❌ Formato incorreto. Use: <code>categoria | valor | descrição</code>"

        cat_num = parts[0].strip()
        valor = float(parts[1].strip().replace(",", ".").replace("R$", "").strip())
        descricao = parts[2].strip()

        if cat_num not in CATEGORIAS_RECEITA:
            return f"❌ Categoria {cat_num} não existe. Use /receita para ver as opções."

        categoria = CATEGORIAS_RECEITA[cat_num]

        extras = load_extras()
        entry = {
            "data": datetime.now().strftime("%Y-%m-%d"),
            "hora": datetime.now().strftime("%H:%M"),
            "categoria": categoria,
            "valor": valor,
            "descricao": descricao,
        }
        extras["receitas"].append(entry)
        save_extras(extras)

        return f"""✅ <b>Receita adicionada!</b>

💰 R$ {valor:,.2f}
📂 {categoria}
📝 {descricao}
📅 {entry['data']}"""

    except ValueError:
        return "❌ Valor inválido. Use números. Ex: <code>1 | 500 | Trabalho extra</code>"


def process_add_despesa(text):
    try:
        parts = text.split("|")
        if len(parts) < 3:
            return "❌ Formato incorreto. Use: <code>categoria | valor | descrição</code>"

        cat_num = parts[0].strip()
        valor = float(parts[1].strip().replace(",", ".").replace("R$", "").strip())
        descricao = parts[2].strip()

        if cat_num not in CATEGORIAS_DESPESA:
            return f"❌ Categoria {cat_num} não existe. Use /despesa para ver as opções."

        categoria = CATEGORIAS_DESPESA[cat_num]

        extras = load_extras()
        entry = {
            "data": datetime.now().strftime("%Y-%m-%d"),
            "hora": datetime.now().strftime("%H:%M"),
            "categoria": categoria,
            "valor": valor,
            "descricao": descricao,
        }
        extras["despesas"].append(entry)
        save_extras(extras)

        return f"""✅ <b>Despesa adicionada!</b>

📉 R$ {valor:,.2f}
📂 {categoria}
📝 {descricao}
📅 {entry['data']}"""

    except ValueError:
        return "❌ Valor inválido. Use números. Ex: <code>7 | 150 | Presente esposa</code>"


def process_apagar(text):
    try:
        num = int(text.strip())
        extras = load_extras()
        hoje = datetime.now()
        mes_atual = hoje.strftime("%Y-%m")

        todos = []
        for r in extras["receitas"]:
            if r["data"].startswith(mes_atual):
                todos.append(("receita", r))
        for d in extras["despesas"]:
            if d["data"].startswith(mes_atual):
                todos.append(("despesa", d))

        if num < 1 or num > len(todos):
            return f"❌ Número inválido. Escolha entre 1 e {len(todos)}."

        tipo, item = todos[num - 1]
        if tipo == "receita":
            extras["receitas"].remove(item)
        else:
            extras["despesas"].remove(item)

        save_extras(extras)
        return f"""🗑 <b>Lançamento apagado!</b>

{'💰' if tipo == 'receita' else '📉'} R$ {item['valor']:,.2f} — {item['descricao']}"""

    except (ValueError, IndexError):
        return "❌ Número inválido. Use /apagar para ver a lista."


def cmd_help():
    return """🤖 <b>ClaudioFinanças — Comandos</b>

📊 <b>Consultas:</b>
/resumo — Visão geral (receita, despesa, margem)
/receitas — Detalhamento das receitas fixas
/despesas — Detalhamento das despesas fixas
/cartoes — Status dos cartões de crédito
/faturas — Próximas faturas e prazos
/picpay — Status do empréstimo PicPay
/milhas — Estratégia de acúmulo de milhas
/emigracao — Plano e timeline de emigração

📝 <b>Lançamentos extras:</b>
/receita — Adicionar receita extra
/despesa — Adicionar despesa extra
/extrato — Ver lançamentos extras do mês
/apagar — Apagar um lançamento extra

/help — Esta mensagem

📊 Dados atualizados em: Abr/2026
💡 Diga /resumo para começar!"""


COMANDOS = {
    "/resumo": cmd_resumo,
    "/receitas": cmd_receitas,
    "/despesas": cmd_despesas,
    "/cartoes": cmd_cartoes,
    "/faturas": cmd_faturas,
    "/picpay": cmd_picpay,
    "/milhas": cmd_milhas,
    "/emigracao": cmd_emigracao,
    "/receita": cmd_adicionar_receita,
    "/despesa": cmd_adicionar_despesa,
    "/extrato": cmd_extrato,
    "/apagar": cmd_apagar,
    "/help": cmd_help,
    "/start": cmd_help,
}

# ============================================================
# MAIN
# ============================================================

def main():
    last_id = get_last_update_id()
    updates = get_updates(offset=last_id + 1 if last_id else None)
    pending = load_pending()

    for update in updates.get("result", []):
        update_id = update["update_id"]
        message = update.get("message", {})
        text = message.get("text", "").strip()
        text_lower = text.lower()
        chat_id = str(message.get("chat", {}).get("id", ""))

        # Só responde pro Iago
        if chat_id != CHAT_ID:
            save_last_update_id(update_id)
            continue

        # Verifica se tem ação pendente (aguardando dados de receita/despesa)
        user_pending = pending.get(chat_id)

        if user_pending:
            if text_lower in ["/cancelar", "cancelar"]:
                del pending[chat_id]
                save_pending(pending)
                send_message("❌ Operação cancelada.")
                save_last_update_id(update_id)
                continue

            if user_pending == "receita":
                response = process_add_receita(text)
                del pending[chat_id]
                save_pending(pending)
                send_message(response)
                save_last_update_id(update_id)
                continue

            elif user_pending == "despesa":
                response = process_add_despesa(text)
                del pending[chat_id]
                save_pending(pending)
                send_message(response)
                save_last_update_id(update_id)
                continue

            elif user_pending == "apagar":
                response = process_apagar(text)
                del pending[chat_id]
                save_pending(pending)
                send_message(response)
                save_last_update_id(update_id)
                continue

        # Processa comando
        cmd = text_lower.split()[0] if text_lower else ""

        if cmd in COMANDOS:
            response = COMANDOS[cmd]()
            send_message(response)

            # Se foi comando de adicionar, marca como pendente
            if cmd == "/receita":
                pending[chat_id] = "receita"
                save_pending(pending)
            elif cmd == "/despesa":
                pending[chat_id] = "despesa"
                save_pending(pending)
            elif cmd == "/apagar":
                pending[chat_id] = "apagar"
                save_pending(pending)

        elif text and not text_lower.startswith("/"):
            # Mensagem livre — não responde (pode ser dados enviados pro Claude)
            pass
        elif text_lower.startswith("/"):
            send_message(f"❓ Comando não reconhecido: {cmd}\n\nDigite /help para ver os comandos disponíveis.")

        save_last_update_id(update_id)

if __name__ == "__main__":
    main()
