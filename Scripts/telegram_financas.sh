#!/bin/bash
# Bot ClaudioFinanças — Enviar mensagens financeiras via Telegram
# Uso: telegram_financas.sh "Mensagem aqui"

BOT_TOKEN="8650778497:AAE-fngcbrpWCQc4AtzhbW8bkbH9fvG8yeA"
CHAT_ID="5883974795"
MENSAGEM="${1:-Sem mensagem}"

curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
  -H "Content-Type: application/json" \
  -d "{
    \"chat_id\": \"${CHAT_ID}\",
    \"text\": \"${MENSAGEM}\",
    \"parse_mode\": \"HTML\"
  }" > /dev/null 2>&1
