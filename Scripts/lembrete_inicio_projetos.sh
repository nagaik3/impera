#!/bin/bash
# Lembrete especial — início dos projetos SaaS + Cliente Internacional
# Roda uma vez em 01/05/2026, depois se auto-remove do crontab

# Alarme macOS
/Users/iagoalmeida/Scripts/alarme.sh "Dia 1 — Novos Projetos" "Hoje começa BriefForge e Cliente Internacional. Abre o Obsidian PESSOAL e segue o roteiro!"

# Telegram
/bin/bash /Users/iagoalmeida/Scripts/telegram_financas.sh "☀️ <b>BOM DIA IAGO — 01/05/2026</b>

Hoje é feriado e é o Dia 1 dos seus projetos.

<b>🎯 Plano do dia:</b>

<b>1. Cliente Internacional (30-45 min, manhã)</b>
→ Abrir ~/pessoal/cliente-internacional/DIA1_ROTEIRO.md
→ Finalizar LinkedIn + criar Upwork
→ Publicar primeiro post

<b>2. SaaS BriefForge (17:15-19:15)</b>
→ Abrir ~/pessoal/briefforge/docs/DIA1_ROTEIRO.md
→ Testar e refinar prompts de geração de brief
→ 3 cenários reais da IMPERA

<b>📂 Tudo está em:</b>
~/pessoal/briefforge/
~/pessoal/cliente-internacional/
~/Obsidian/PESSOAL/

Abre o Claude no agente pessoal e bora! 💪"

# Auto-remover do crontab após execução
(crontab -l 2>/dev/null | grep -v "lembrete_inicio_projetos.sh") | crontab -
