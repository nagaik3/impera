#!/bin/bash
# Startup script for Nomenclatura Webhook Server
# Called via crontab @reboot

cd ~/Scripts

export CLICKUP_API_TOKEN=$(grep 'export CLICKUP_API_TOKEN=' ~/.zshrc | sed "s/.*='\(.*\)'/\1/" | tr -d "'" | tr -d '"')
export NOMENCLATURA_WEBHOOK_PORT=5003

# Kill any previous instance
pkill -f "python3 auditoria_nomenclatura.py --server" 2>/dev/null || true
sleep 1

# Start webhook server
nohup python3 auditoria_nomenclatura.py --server >> ~/Scripts/logs/nomenclatura_webhook.log 2>&1 &

echo "✅ Nomenclatura webhook server started (PID: $!)" >> ~/Scripts/logs/nomenclatura_webhook.log
