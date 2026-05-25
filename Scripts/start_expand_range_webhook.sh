#!/bin/bash

# Iniciar webhook server para expandir_range_tasks.py
# Uso: ./start_expand_range_webhook.sh
# Para parar: Ctrl+C ou kill do processo

LOG_FILE="$HOME/Scripts/logs/expand_range_webhook.log"
mkdir -p "$(dirname "$LOG_FILE")"

echo "🚀 Iniciando Webhook Server para Expandir Ranges..."
echo "Configuração:"
echo "  Port: 5000"
echo "  Log: $LOG_FILE"
echo "  Env: CU_FIELD_PARENT_TASK_ID, CU_STATUS_TESTES_CONCLUIDOS"
echo ""
echo "Para parar: Ctrl+C ou kill do processo"
echo "---"

source ~/.zshrc

cd ~/Scripts && python3 expandir_range_tasks.py --server 2>&1 | tee -a "$LOG_FILE"
