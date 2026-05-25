# 🔄 Automação: "Teve alteração?" — Guia Rápido

## ✅ Status: Sistema Validado e Pronto para Usar

Todos os testes passaram com sucesso. O sistema está pronto para rastrear tarefas que foram movidas para o status **"em alteração"**.

---

## 📋 Resumo Rápido

**O que faz:**
- Quando uma tarefa é movida para "em alteração", o campo `🔄 Teve alteração?` é marcado automaticamente ✅
- Permite visualizar todas as tarefas que sofreram alteração ao longo da semana
- Registra todos os eventos para auditoria

**Componentes:**
1. **Webhook** (`webhook_auto_alteracao.py`) — Recebe mudanças de status e marca o campo
2. **Batch Marker** (`mark_teve_alteracao_batch.py`) — Marca manualmente tarefas retrospectivas
3. **Test Suite** (`test_auto_alteracao.py`) — Valida o sistema (✅ todos passando)

---

## 🚀 Como Usar

### Opção A: Automático com Webhook (Recomendado)

#### 1. Inicie o webhook:
```bash
python3 ~/Scripts/webhook_auto_alteracao.py
```

Deixe rodando em background ou crie um processo permanente.

#### 2. Configure no ClickUp:

1. Acesse: https://app.clickup.com/settings/integrations/webhooks
2. Clique em "Create Webhook"
3. Preencha:
   - **Event**: Task Status Updated
   - **URL**: `http://localhost:5001/webhook/auto-alteracao`
   - **Team/Workspace**: IMPERA PRODUTOS NATURAIS

#### 3. Pronto!

Agora toda vez que uma tarefa for movida para "em alteração", o campo será marcado automaticamente.

### Opção B: Marcar Manualmente (Para histórico passado)

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

## 📊 Exemplos de Uso

### Exemplo 1: Usar o webhook
```bash
# Terminal 1: Inicia o webhook
python3 ~/Scripts/webhook_auto_alteracao.py

# Terminal 2: Monitora logs
curl http://localhost:5001/webhook/logs | jq '.events[-5:]'

# No ClickUp: Mova uma tarefa para "em alteração"
# ✅ Campo é marcado automaticamente
```

### Exemplo 2: Marcar a tarefa que você citou
```bash
python3 ~/Scripts/mark_teve_alteracao_batch.py --task-ids 86ahdcp2a
# Campo "Teve alteração?" fica marcado ✅
```

### Exemplo 3: Gerar relatório semanal
```bash
# Ver todas as tarefas que tiveram alteração
curl http://localhost:5001/webhook/logs | jq '.events[] | {timestamp, task_name, action}'
```

---

## 📁 Arquivos Criados

| Arquivo | Função |
|---------|--------|
| `webhook_auto_alteracao.py` | Webhook que marca campo automaticamente |
| `mark_teve_alteracao_batch.py` | Marca tarefas manualmente em batch |
| `test_auto_alteracao.py` | Suite de testes (✅ todos passando) |
| `SETUP_AUTO_ALTERACAO.md` | Documentação técnica completa |
| `README_TEVE_ALTERACAO.md` | Este arquivo |

---

## 🔍 Monitoramento

### Ver logs do webhook:
```bash
curl http://localhost:5001/webhook/logs | jq '.'
```

### Ver status do webhook:
```bash
curl http://localhost:5001/webhook/status | jq '.'
```

### Ver logs de arquivo:
```bash
cat ~/Scripts/data/auto_alteracao_log.json | jq '.events'
```

---

## 🐛 Troubleshooting

### Webhook não marca campo

**Verificação:**
1. Webhook está rodando?
   ```bash
   curl http://localhost:5001/webhook/status
   ```

2. URL está configurada no ClickUp corretamente?
   - Acesse: https://app.clickup.com/settings/integrations/webhooks
   - Verifique se URL começa com `http://localhost:5001`

3. Veja logs:
   ```bash
   curl http://localhost:5001/webhook/logs | jq '.events[-3:]'
   ```

### Campo não atualiza manualmente

Verifique token:
```bash
echo $CLICKUP_API_TOKEN
# Deve retornar algo como: pk_...xxxxx
```

---

## 📅 Integração com Relatórios

O campo pode ser usado em relatórios semanais:

```bash
# Exemplo: Adicionar seção ao relatorio_semanal_clickup.py
# "Tarefas com Alteração esta Semana"
# Filtrar: status = "Teve alteração?" = TRUE
```

---

## 🔐 Segurança

- Token armazenado em `$CLICKUP_API_TOKEN` (não salvo em código)
- Logs salvos localmente em `~/Scripts/data/`
- Sem exposição de dados sensíveis
- Webhook valida Authorization header

---

## 📞 Suporte Rápido

| Problema | Solução |
|----------|---------|
| Webhook 404 | Não está rodando. Use: `python3 ~/Scripts/webhook_auto_alteracao.py` |
| Campo não marca | Verifique token: `echo $CLICKUP_API_TOKEN` |
| Erro 405 | Endpoint atualizado para POST ✅ (já corrigido) |
| Ver histórico | Use: `curl http://localhost:5001/webhook/logs` |

---

## ✨ Resumo de Capacidades

✅ Marca automaticamente quando tarefa → "em alteração"  
✅ Marca manualmente tarefas retrospectivas  
✅ Registra histórico completo em JSON  
✅ API para consultar logs e status  
✅ Campo visível no ClickUp para análise semanal  
✅ Totalmente testado e validado  

---

**Criado em:** 2026-05-24  
**Status:** ✅ Pronto para Produção  
**Testes:** 6/6 ✅ Passando
