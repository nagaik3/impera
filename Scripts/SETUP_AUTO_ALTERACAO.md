# ⚙️ Automação: "Teve alteração?" — Setup Completo

## 📋 Visão Geral

Sistema automático para rastrear tarefas que foram movidas para o status **"em alteração"** marcando o campo `🔄 Teve alteração?`

### Como funciona:
1. **Webhook**: Recebe notificação quando tarefa é movida para "em alteração"
2. **Automação**: Marca o campo automaticamente ✅
3. **Logging**: Registra todos os eventos para auditoria
4. **Visualização**: Campo fica visível no ClickUp para análise semanal

---

## 🚀 Instalação

### 1. Dependências
```bash
pip3 install flask requests
```

### 2. Diretório de dados
```bash
mkdir -p ~/Scripts/data
```

### 3. Teste rápido
```bash
# Testar se o campo está acessível
curl -H "Authorization: $CLICKUP_API_TOKEN" \
  "https://api.clickup.com/api/v2/list/901324556390/field" | \
  jq '.fields[] | select(.name | contains("alteração"))'
```

---

## 🔗 Configuração no ClickUp

### Criar Webhook

1. **Acesse**: https://app.clickup.com/settings/integrations/webhooks
2. **Clique**: "Create Webhook"
3. **Configure**:
   - **Event**: Task Status Updated
   - **URL**: `http://localhost:5001/webhook/auto-alteracao`
   - **Team**: IMPERA PRODUTOS NATURAIS
4. **Salve**

### ⚠️ Nota: Localhost
Se você estiver usando uma máquina local, você terá que:
- Usar **ngrok** para expor o webhook localmente, ou
- Configurar em um servidor remoto com IP fixo/domínio

**Usando ngrok**:
```bash
# Terminal 1: Iniciar webhook
python3 ~/Scripts/webhook_auto_alteracao.py

# Terminal 2: Expor com ngrok
ngrok http 5001
# Copie a URL gerada (ex: https://abc123.ngrok.io)
# Use em "URL do Webhook": https://abc123.ngrok.io/webhook/auto-alteracao
```

---

## 🎯 Como Usar

### Opção 1: Iniciar o Webhook (Automático)
```bash
python3 ~/Scripts/webhook_auto_alteracao.py

# Verifica status
curl http://localhost:5001/webhook/status | jq .

# Vê logs
curl http://localhost:5001/webhook/logs | jq .
```

### Opção 2: Marcar Manualmente (Retrospectivo)

#### Marcar tarefas específicas:
```bash
python3 ~/Scripts/mark_teve_alteracao_batch.py \
  --task-ids 86ahdcp2a 86ahe25wy 86ahe25x6
```

#### Marcar TODAS as tarefas da lista:
```bash
python3 ~/Scripts/mark_teve_alteracao_batch.py --all
```

#### Desmarcar tarefas:
```bash
python3 ~/Scripts/mark_teve_alteracao_batch.py \
  --task-ids 86ahdcp2a --unmark
```

---

## 📊 Exemplos

### Exemplo 1: Workflow padrão
```bash
# 1. Inicia webhook (deixa rodando)
python3 ~/Scripts/webhook_auto_alteracao.py

# 2. Usuário move tarefa para "em alteração" no ClickUp
# 3. Webhook recebe notificação automaticamente
# 4. Campo é marcado ✅
```

### Exemplo 2: Histórico passado
```bash
# 1. Você identifica que a tarefa 86ahdcp2a foi alterada
# 2. Marca manualmente
python3 ~/Scripts/mark_teve_alteracao_batch.py --task-ids 86ahdcp2a

# 3. Agora fica visível no ClickUp com checkbox ✅
```

### Exemplo 3: Ver logs do webhook
```bash
curl http://localhost:5001/webhook/logs | jq '.events[] | {timestamp, task_name, action}'
```

---

## 🔍 Verificação

### Verificar se webhook recebeu evento
```bash
curl http://localhost:5001/webhook/logs | jq '.'
```

### Verificar se campo foi atualizado
```bash
# No ClickUp:
# 1. Abra uma tarefa
# 2. Procure por "Teve alteração?" (deve ter checkbox ✅)
```

---

## 📝 Campos do Sistema

| Campo | ID | Tipo | Função |
|-------|-----|------|--------|
| 🔄 Teve alteração? | `3617b249-06e2-4d2e-9ba0-c48da305e42a` | Checkbox | Marca se tarefa foi alterada |

---

## 🐛 Troubleshooting

### Webhook não recebe eventos
- [ ] Verifique se URL está correta no ClickUp (Settings → Webhooks)
- [ ] Se localhost, use ngrok para expor
- [ ] Teste com `curl http://localhost:5001/webhook/status`

### Campo não é marcado
- [ ] Verifique token `$CLICKUP_API_TOKEN`
- [ ] Verifique se tarefa existe e está na lista COPY
- [ ] Veja logs: `curl http://localhost:5001/webhook/logs | jq .`

### "Authorization failed"
```bash
# Verifique token
echo $CLICKUP_API_TOKEN
# Deve retornar um valor longo (pk_...)
```

---

## 📅 Relatório Semanal

Para gerar relatório de tarefas que tiveram alteração:

```bash
# Integrar com relatorio_semanal_clickup.py para incluir seção:
# "📝 Tarefas com Alteração esta Semana"
# Filtrar por: status = "Teve alteração?" = verdadeiro
```

---

## 🔐 Segurança

- Token armazenado em `$CLICKUP_API_TOKEN` (não commit para git)
- Logs salvos em `~/Scripts/data/auto_alteracao_log.json` (local)
- Webhook valida `Authorization` header
- Sem exposição de senhas ou dados sensíveis

---

## 📞 Suporte

Para dúvidas:
1. Verifique os logs: `curl http://localhost:5001/webhook/logs | jq .`
2. Teste o endpoint: `curl http://localhost:5001/webhook/status`
3. Consulte este documento

---

**Última atualização**: 2026-05-24  
**Status**: ✅ Pronto para uso
