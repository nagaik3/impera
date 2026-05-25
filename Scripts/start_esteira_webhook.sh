#!/bin/bash
# Startup script for Rastreador Esteira Webhook Server
# Called via crontab @reboot

cd ~/Scripts

export CLICKUP_API_TOKEN=$(grep 'export CLICKUP_API_TOKEN=' ~/.zshrc | sed "s/.*='\(.*\)'/\1/" | tr -d "'" | tr -d '"')
export ESTEIRA_WEBHOOK_PORT=5002

# Kill any previous instance
pkill -f "python3 rastreador_esteira.py --server" 2>/dev/null || true
sleep 1

# Start webhook server
nohup python3 rastreador_esteira.py --server >> ~/Scripts/logs/esteira_webhook.log 2>&1 &

echo "✅ Rastreador Esteira webhook server started (PID: $!)" >> ~/Scripts/logs/esteira_webhook.log
