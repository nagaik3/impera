#!/bin/bash
# Script para iniciar o webhook server do Gate Finalizado
# Use: bash ~/Scripts/start_webhook.sh

source ~/.zshrc

# Matar qualquer instância anterior
pkill -f "gate_finalizado.*--server" 2>/dev/null || true
sleep 1

# Criar diretório de logs
mkdir -p ~/Scripts/logs

# Iniciar servidor
nohup python3 ~/Scripts/gate_finalizado.py --server > ~/Scripts/logs/gate_webhook.log 2>&1 &
PID=$!

sleep 2

if ps -p $PID > /dev/null; then
  echo "✅ Webhook server iniciado"
  echo "   PID: $PID"
  echo "   Porta: ${GATE_WEBHOOK_PORT:-5004}"
  echo "   Log: ~/Scripts/logs/gate_webhook.log"
  
  # Salvar PID para referência
  echo $PID > ~/Scripts/.webhook_pid
else
  echo "❌ Falha ao iniciar"
  tail ~/Scripts/logs/gate_webhook.log
  exit 1
fi
