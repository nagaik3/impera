# Estratégia Inteligente de Notificações — Rastreador Esteira v2.1

## O Problema Resolvido

Antes: **Webhook detectava TUDO** → 50-100 mensagens/dia no ClickUp (spam)
Depois: **Detecta tudo, mas notifica apenas crítico** → 7-10 mensagens úteis/dia

---

## 🎯 Três Níveis de Notificação

### **Nível 1: 🚨 CRÍTICO (< 1 minuto)**
**Quando**: Webhook detecta instantaneamente
**O que notifica**:
- ❌ Copywriter vazio ao sair de "backlog copy"
- ❌ Task entra em status bloqueado ("parado para revisão", "aguardando aprovação", etc)
- ❌ Task sai de status bloqueado (desbloqueio = melhoria)

**Frequência**: Imediato
**Resultado**: ~3-5 mensagens/dia

**Exemplo**:
```
🚨 CRÍTICO: [MM][BR][OF01][FB][AD01][V1]
→ COPYWRITER_VAZIO
```

---

### **Nível 2: ⚠️ IMPORTANTE (Consolidado 2x/dia)**
**Quando**: 11:00 AM e 4:00 PM
**O que consolida**:
- 🔴 Todas as tarefas atrasadas por setor
- 🟡 Tarefas em risco (70%+ do SLA)
- 🚨 Críticos não resolvidos (se houver)
- 📈 Resumo final (totais)

**Frequência**: 2 mensagens/dia (11h + 16h)
**Resultado**: Relatório completo em 1 mensagem formatada

**Exemplo**:
```
📊 RASTREADOR ESTEIRA — 24/05 11:00

🚨 CRÍTICOS (ação necessária):
  • [MM][BR][OF01][FB][AD01][V1]
    → Copywriter vazio

📂 Produção
  🔴 2 atrasada(s)
  🟡 1 em risco
📂 Alteração
  🟡 3 em risco

📈 RESUMO: 3 atrasadas | 6 em risco
```

---

### **Nível 3: 📊 INFORMATIVO (Semanal)**
**Quando**: Segunda-feira 11:00 AM
**O que mostra**:
- 📈 Métricas da semana (total de atrasos, em risco)
- 🔴 Top 3 gargalos (qual setor está pior)
- 📊 Trends e padrões

**Frequência**: 1 mensagem/semana
**Resultado**: Visão estratégica

*(Ainda não implementado, próxima fase)*

---

## 🔄 Como Funciona

### **Webhook (Real-time)**
```
Task muda de status no ClickUp
    ↓
Webhook recebe em < 1 segundo
    ↓
is_critical_issue() avalia:
  ├─ É copywriter vazio? → CRÍTICO
  ├─ É bloqueado? → CRÍTICO
  ├─ É normal? → não posta
    ↓
Se CRÍTICO:
  ├─ post_clickup_alert() no canal
  └─ log_notification() para auditoria
Se NORMAL:
  └─ Apenas loga em JSON (sem posta)
```

### **Polling (A cada 2 horas)**
```
*/2 horas: poll() roda
    ↓
Detecta status changes (como webhook, mas catch-all)
    ↓
is_critical_issue() avalia:
  ├─ Se crítico → posta imediatamente
  └─ Se normal → apenas loga
```

### **Alert (2x por dia)**
```
11:00 AM / 4:00 PM: cmd_alert() roda
    ↓
poll() valida tudo
    ↓
build_consolidated_alert() coleta:
  ├─ Críticos não resolvidos
  ├─ Tarefas atrasadas por setor
  └─ Tarefas em risco
    ↓
Consolida em UMA ÚNICA mensagem
    ↓
post_clickup_alert() envia no canal
```

---

## 📉 Redução de Mensagens

| Métrica | Antes | Depois | Redução |
|---------|-------|--------|---------|
| Msg/dia (webhook) | 30-50 | 3-5 | 90% ↓ |
| Msg/dia (polls) | 10-20 | 0 | 100% ↓ |
| Msg/dia (alerts) | 2 | 2 | - |
| **Total/dia** | **50-72** | **7-10** | **85% ↓** |

---

## 🛠️ Implementação Técnica

### Arquivo: `rastreador_notificacao_strategy.py`

**Funções principais**:

```python
# Detecta se um status change é crítico
is_critical_issue(old_status, new_status, missing_copywriter=False)
  → (is_critical: bool, reason: str)

# Consolida dados para relatório
build_consolidated_alert(tracking, critical_issues=[])
  → "📊 RASTREADOR..." (mensagem formatada)

# Agrupa tarefas por setor
analyze_by_sector(tracking)
  → {"Produção": {...}, "Alteração": {...}, ...}

# Log de auditoria
log_notification(type, task_id, message, posted=bool)
```

### Arquivo: `rastreador_esteira.py` (modificado)

**Mudanças**:
1. Webhook: `if is_critical() → post_alert()`
2. Polling: `if is_critical() → post_alert()`
3. cmd_alert(): `build_consolidated_alert()` em vez de `build_alert_message()`

---

## 🚀 Benefícios

✅ **Menos ruído**: 85% menos mensagens
✅ **Informação importante**: Críticos sempre aparecem
✅ **Consolidado**: Visão clara 2x/dia
✅ **Auditoria**: Tudo logado mesmo se não postado
✅ **Escalável**: Fácil adicionar novos critérios críticos
✅ **Inteligente**: Detecta sem spammar

---

## ⚙️ Customização

### Adicionar novo critério crítico
Edite `rastreador_notificacao_strategy.py`:
```python
def is_critical_issue(old_status, new_status, ...):
    # Crítico novo: entra em status "URGENTE"
    if new_status == "urgente":
        return True, "urgente"
```

### Mudar horário dos alerts
Edite `CRONTAB`:
```bash
0 10 * * 1-6 ... # Alert às 10h em vez de 11h
0 17 * * 1-6 ... # Alert às 17h em vez de 16h
```

### Mudar critério de "em risco"
Edite `rastreador_notificacao_strategy.py`:
```python
# Atual: 70% do SLA
elif days_elapsed >= int(sla_days * 0.7):

# Mudar para 50%
elif days_elapsed >= int(sla_days * 0.5):
```

---

## 📊 Monitoramento

### Ver log de notificações enviadas
```bash
tail ~/Scripts/data/notificacao_log.jsonl
```

### Formato do log
```json
{
  "timestamp": "2026-05-24T13:55:23",
  "type": "critical",
  "task_id": "task_123",
  "message": "copywriter vazio",
  "posted": true
}
```

### Analisar por tipo
```bash
# Críticos postados
grep '"type": "critical"' ~/Scripts/data/notificacao_log.jsonl | grep '"posted": true' | wc -l

# Normais (apenas logados)
grep '"type": "normal"' ~/Scripts/data/notificacao_log.jsonl | wc -l
```

---

## 🧪 Testes

### Teste 1: Webhook com evento crítico
```bash
curl -X POST http://localhost:5002/webhook/esteira \
  -H "Content-Type: application/json" \
  -d '{"event":"taskStatusUpdated","task":{"id":"t1","name":"[MM][BR][OF01][FB][AD01][V1]","status":{"status":"parado para revisão"}}}'
```
**Esperado**: Posta no ClickUp (bloqueado = crítico)

### Teste 2: Webhook com evento normal
```bash
curl -X POST http://localhost:5002/webhook/esteira \
  -H "Content-Type: application/json" \
  -d '{"event":"taskStatusUpdated","task":{"id":"t2","name":"[MM][BR][OF01][FB][AD01][V1]","status":{"status":"pré-produção"}}}'
```
**Esperado**: NÃO posta no ClickUp (apenas loga)

### Teste 3: Alert consolidado
```bash
python3 rastreador_esteira.py alert
```
**Esperado**: 1 mensagem com resumo consolidado

---

## 📈 Próximos Passos

1. **Nível 3** (Semanal): Implementar `build_weekly_report()`
2. **Deduplicação**: Não repostar se já foi postado há < 30 min
3. **Severidade**: Adicionar níveis (HIGH, MEDIUM, LOW)
4. **Escalação**: Se crítico não resolvido em 2h, notificar novamente

---

## 📝 Changelog

**v2.1** (2026-05-24):
- ✅ Implementado 3 níveis de notificação
- ✅ Webhook detecta tudo, notifica apenas crítico
- ✅ Consolidação 2x/dia
- ✅ Log de auditoria completo
- ✅ 85% redução em mensagens/dia
