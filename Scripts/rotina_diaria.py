#!/usr/bin/env python3
"""
Rotina Diária — Agenda matinal e relatório noturno
Envia via ClickUp Chat View para Iago
"""

import json
import os
import urllib.request
from datetime import datetime

CLICKUP_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

DIAS_SEMANA = {
    0: "segunda-feira", 1: "terça-feira", 2: "quarta-feira",
    3: "quinta-feira", 4: "sexta-feira", 5: "sábado", 6: "domingo",
}

# Reuniões fixas
REUNIOES_FIXAS = {
    0: [  # Segunda
        {"hora": "09:00", "nome": "Reunião Liderança — Grupo Impera"},
        {"hora": "11:30", "nome": "Daily"},
    ],
    1: [  # Terça
        {"hora": "11:30", "nome": "Daily"},
    ],
    2: [  # Quarta
        {"hora": "11:30", "nome": "Daily"},
    ],
    3: [  # Quinta
        {"hora": "11:30", "nome": "Daily"},
    ],
    4: [  # Sexta
        {"hora": "11:30", "nome": "Daily"},
    ],
}

ROTINA_ESTUDOS = [
    {"hora": "—", "nome": "📚 Estudo: Gestão de Processos (15 min)"},
    {"hora": "—", "nome": "🇯🇵 Estudo: Japonês (15-30 min)"},
]


def post_telegram(text):
    """Envia mensagem via Telegram privado."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": True,
    }).encode()
    req = urllib.request.Request(url, data=payload, method='POST')
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def morning():
    """Mensagem matinal: agenda do dia + perguntas."""
    now = datetime.now()
    dia = DIAS_SEMANA.get(now.weekday(), "dia")
    data = now.strftime('%d/%m/%Y')
    
    reunioes = REUNIOES_FIXAS.get(now.weekday(), [])
    
    lines = [
        f"☀️ Bom dia, Iago!",
        f"{dia.title()}, {data}",
        "",
        "📋 AGENDA DO DIA",
        "─────────────────",
    ]
    
    if reunioes:
        for r in reunioes:
            lines.append(f"  🕐 {r['hora']} — {r['nome']}")
    else:
        lines.append("  Sem reuniões fixas hoje")
    
    lines.append("")
    lines.append("📚 ESTUDOS DO DIA")
    lines.append("─────────────────")
    for e in ROTINA_ESTUDOS:
        lines.append(f"  {e['nome']}")
    
    lines.append("")
    lines.append("❓ PERGUNTAS DO DIA")
    lines.append("─────────────────")
    lines.append("  1. Qual é a sua prioridade #1 de trabalho hoje?")
    lines.append("  2. Tem algum bloqueio ou pendência de ontem para resolver?")
    lines.append("  3. Tem alguma reunião pontual além das fixas?")
    lines.append("  4. Como está se sentindo hoje? (1-10)")
    lines.append("")
    lines.append("Responda quando puder — boa produtividade! 💪")
    
    return "\n".join(lines)


def evening():
    """Mensagem noturna: mini relatório + perguntas de reflexão."""
    now = datetime.now()
    dia = DIAS_SEMANA.get(now.weekday(), "dia")
    data = now.strftime('%d/%m/%Y')
    
    lines = [
        f"🌙 Fechamento do dia — {dia.title()}, {data}",
        "",
        "📊 MINI RELATÓRIO",
        "─────────────────",
        "Me conta como foi o dia respondendo essas perguntas:",
        "",
        "  1. Conseguiu completar sua prioridade #1? (sim/não/parcial)",
        "  2. Quantas tarefas conseguiu finalizar hoje?",
        "  3. Teve algum bloqueio que não conseguiu resolver?",
        "  4. Fez os 15 min de estudo de gestão? (sim/não)",
        "  5. Fez os 15-30 min de japonês? (sim/não)",
        "  6. Qual foi a maior vitória do dia?",
        "  7. O que faria diferente amanhã?",
        "  8. De 1 a 10, como avalia sua produtividade hoje?",
        "",
        "Não precisa responder tudo — qualquer coisa que mandar já ajuda a manter o registro. 📝",
        "",
        "Descanse bem! 🌟",
    ]
    
    return "\n".join(lines)


def main():
    import sys
    
    if not CLICKUP_TOKEN:
        print("ERRO: CLICKUP_API_TOKEN não configurado")
        return
    
    mode = sys.argv[1] if len(sys.argv) > 1 else "morning"
    
    if mode == "morning":
        text = morning()
        print("Enviando agenda matinal...")
    elif mode == "evening":
        text = evening()
        print("Enviando fechamento noturno...")
    else:
        print(f"Uso: python3 rotina_diaria.py [morning|evening]")
        return
    
    print(text)
    post_telegram(text)
    print("\n✅ Enviado ao Telegram!")


if __name__ == "__main__":
    main()
