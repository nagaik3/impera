# Rastreador Esteira v2.0 — Mudança: Telegram → ClickUp

## O que mudou?

Centralizamos **todas as notificações automáticas** no ClickUp Chat View. Telegram agora é **opcional** e apenas para o bot interativo se precisar.

### Antes (v1.0)
```
Alerts de SLA: Telegram
Aviso Copywriter: Telegram
Comunicação: Telegram
```

### Depois (v2.0)
```
Alerts de SLA: ClickUp Chat View ✅
Aviso Copywriter: ClickUp Chat View ✅
Bot Interativo: Telegram (opcional)
```

---

## Mudanças no Código

### 1. Adicionado: Chat View ID
```python
CHAT_VIEW_ID = "6-901324556390-8"  # Chat View da lista COPY
```

### 2. Nova Função: `post_clickup_alert()`
```python
def post_clickup_alert(message):
    """Posta alerta no ClickUp Chat View em vez de Telegram."""
    url = f"https://api.clickup.com/api/v2/view/{CHAT_VIEW_ID}/comment"
    payload = {"comment_text": message}
    # ... posta no ClickUp ...
```

### 3. Atualizados: Endpoints de Alerta
- `cmd_alert()`: Telegram → ClickUp ✅
- Webhook (copywriter validation): Telegram → ClickUp ✅
- Polling (copywriter validation): Telegram → ClickUp ✅

---

## Como Funciona Agora

### Alertas de SLA (11:00 e 16:00)
```
Crontab executa: python3 rastreador_esteira.py alert
       ↓
cmd_alert() roda poll() + análise
       ↓
Mensagem formatada (setores, atrasos, em risco)
       ↓
post_clickup_alert() → ClickUp Chat View
       ↓
Aparece na aba "Chat" do COPY list
```

### Aviso Copywriter Vazio (real-time)
```
Task sai de "backlog copy" sem copywriter preenchido
       ↓
Webhook detecta (ou polling)
       ↓
post_clickup_alert() → ClickUp Chat View
       ↓
"⚠️ COPYWRITER VAZIO: [MM][BR]..."
```

---

## Próximos Passos (Opcionais)

### Se quiser remover Telegram completamente:
```bash
# Remover variáveis do .zshrc
grep -v "TELEGRAM_BOT_TOKEN\|TELEGRAM_CHAT_ID" ~/.zshrc > ~/.zshrc.tmp
mv ~/.zshrc.tmp ~/.zshrc
```

### Se quiser manter o bot Telegram interativo:
O `cmd_bot()` continua disponível:
```bash
python3 rastreador_esteira.py bot
```
Apenas configure:
```bash
export TELEGRAM_BOT_TOKEN="botXXXXXX..."
export TELEGRAM_CHAT_ID="XXXXXX"
```

---

## Vantagens da Centralização no ClickUp

✅ **Tudo em um lugar**: Copiloto, alertas, tudo no ClickUp
✅ **Menos switching**: Não precisa abrir Telegram
✅ **Contexto preservado**: Links de tarefas, timestamps
✅ **Histórico integrado**: Chat View mantém histórico
✅ **Sem dependência externa**: Um serviço a menos
✅ **Compatível com automações**: Fácil integrar com otros scripts

---

## Testing

Para testar os alertas:

```bash
# Testar alert (SLA report)
python3 rastreador_esteira.py alert

# Testar aviso copywriter vazio (via webhook)
curl -X POST http://localhost:5002/webhook/esteira \
  -H "Content-Type: application/json" \
  -d '{
    "event": "taskStatusUpdated",
    "task": {
      "id": "test",
      "name": "[MM][BR][OF01][FB][AD01][V1]",
      "status": {"status": "Pré-Produção"}
    }
  }'
```

---

## Changelog

**v2.0.1** (2026-05-24):
- Migrado alertas de Telegram → ClickUp Chat View
- Centralização completa de notificações
- Telegram agora opcional (bot interativo apenas)
- Performance: sem mudança, melhor UX
