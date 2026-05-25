# 🚀 Webhook IMPERA - Guia de Configuração

## Status Atual
✅ **Webhook implementado e testado**
- Porta: **5004**
- Batch Size: **5 tarefas**
- Logging: **Resumido**
- Server: **Pronto para ativar**

---

## 📋 COMO ATIVAR O WEBHOOK NO CLICKUP

### 1️⃣ Acesse o ClickUp (Workspace IMPERA)
```
https://app.clickup.com
→ Settings → Workspace
→ Integrations → Webhooks
```

### 2️⃣ Crie novo Webhook
**Nome:** Gate Finalizado Webhook
**URL:** `http://SEU_IP:5004/` ou `http://localhost:5004/` (se local)

### 3️⃣ Configure os Eventos
- ☑️ Task Status Updated
- ✅ Ativa: Sim

### 4️⃣ Configure os Filtros (Opcional)
- Status: `aguardando validação`
- Lista: `COPY (901324556390)`

### 5️⃣ Teste a Conexão
ClickUp enviará um **challenge**. Se a porta estiver aberta, será aceito automaticamente.

---

## 📝 VERIFICAÇÕES PRÉ-WEBHOOK

Antes de ativar no ClickUp, assegure-se:

### ✅ Porta Aberta
```bash
# Verificar se a porta 5004 está disponível
python3 ~/Scripts/gate_finalizado.py --server &
# Deve aparecer: "🚀 Gate Finalizado webhook server na porta 5004"
```

### ✅ Ambiente Configurado
```bash
# Verificar variáveis de ambiente
echo $GATE_WEBHOOK_PORT        # Deve mostrar: 5004
echo $BATCH_SIZE               # Deve mostrar: 5
echo $LOGGING_MODE             # Deve mostrar: resumido
```

### ✅ Logs Funcionando
```bash
# Verificar arquivo de log
tail -f ~/Scripts/logs/gate_webhook.log
```

---

## 🔄 FLUXO DE PROCESSAMENTO

```
Webhook do ClickUp
    ↓
Task movida para "aguardando validação"
    ↓
Servidor recebe evento (porta 5004)
    ↓
Tarefa adicionada ao batch
    ↓
Se 5 tarefas OU 5 segundo timeout
    ↓
Processa BATCH inteiro
    ↓
Valida nomenclatura + Drive
    ↓
Move para "aprovado-trafego" ✅
```

---

## 📊 MONITORAMENTO

### Log Resumido (Padrão)
```
[2026-05-24 13:17:58.393] 📝 Recebido: task_1
[2026-05-24 13:17:59.310] 📦 Acumulado: 2/5 tarefas
[2026-05-24 13:18:03.456] ✅ Batch concluído: 5 OK | 0 erros
```

### Log Detalhado (Troubleshooting)
```bash
export LOGGING_MODE=detalhado
python3 ~/Scripts/gate_finalizado.py --server
```

---

## 🛠️ TROUBLESHOOTING

### Webhook não recebe eventos?
1. Verifique se porta 5004 está aberta: `lsof -i :5004`
2. Confirme URL no ClickUp: `http://SEU_IP:5004/`
3. Verifique logs: `tail ~/Scripts/logs/gate_webhook.log`

### Batch não processa?
1. Aguarde 5 segundos (timeout padrão)
2. Ou envie 5 tarefas para disparar imediatamente

### Tarefas em erro?
Verifique: `tail ~/Scripts/gate_finalizado.log`

---

## 🔄 MODOS DE OPERAÇÃO

### 1. Crontab (Fallback - Já Ativo)
```bash
*/3 * * * 1-6 → Gate Finalizado a cada 3 minutos
```

### 2. Webhook (Novo - Ativar no ClickUp)
```
Real-time quando tarefa movida para "aguardando validação"
```

### Combinado = Máxima Confiabilidade ✅

---

## 📞 SUPORTE

Comando útil para testar:
```bash
python3 ~/Scripts/gate_finalizado.py --server
```

Log em tempo real:
```bash
tail -f ~/Scripts/logs/gate_webhook.log
```

Reiniciar servidor:
```bash
pkill -f "gate_finalizado.*--server"
python3 ~/Scripts/gate_finalizado.py --server &
```

