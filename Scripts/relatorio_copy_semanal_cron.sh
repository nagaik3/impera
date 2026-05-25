#!/bin/bash

# Relatório Semanal Copy - Execução via CRON
# Agendado: Segunda-feira às 07:00

export PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
export HOME=/Users/iagoalmeida
export NODE_PATH=/usr/local/lib/node_modules

cd ~/Scripts
node criar_relatorio_copy_profissional.js

# Enviar para usuário
REPORT_FILE="~/relatorio_copy_semanal_final.pdf"
if [ -f "$REPORT_FILE" ]; then
  # Log de sucesso
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Relatório Copy gerado com sucesso" >> ~/Scripts/relatorio_copy_semanal.log
else
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERRO: Falha ao gerar relatório" >> ~/Scripts/relatorio_copy_semanal.log
fi
