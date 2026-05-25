#!/bin/bash
# Auto Etiqueta Webhook Server Startup Script
# Inicia o servidor webhook na porta 5006

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LOG_DIR="$SCRIPT_DIR/logs"
WEBHOOK_LOG="$LOG_DIR/auto_etiqueta_webhook.log"

mkdir -p "$LOG_DIR"

echo "🚀 Iniciando Auto Etiqueta Webhook Server..."
echo "   Porta: 5006"
echo "   Log: $WEBHOOK_LOG"
echo ""

# Carregar env vars
source ~/.zshrc 2>/dev/null || true

cd "$SCRIPT_DIR"
/usr/bin/python3 auto_etiqueta.py --server >> "$WEBHOOK_LOG" 2>&1 &
WEBHOOK_PID=$!

echo "✅ Webhook servidor iniciado (PID: $WEBHOOK_PID)"
echo "   Para parar: kill $WEBHOOK_PID"
echo "   Para logs: tail -f $WEBHOOK_LOG"

# Salvar PID para referência
echo "$WEBHOOK_PID" > "$LOG_DIR/.auto_etiqueta_webhook.pid"

# Manter processo rodando
wait $WEBHOOK_PID
