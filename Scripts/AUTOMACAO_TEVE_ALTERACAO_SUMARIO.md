# 📦 Automação "Teve alteração?" — Sumário de Implementação

## ✅ Implementação Concluída

Sistema completo criado para rastrear automaticamente tarefas movidas para o status **"em alteração"** marcando o campo `🔄 Teve alteração?`.

---

## 📊 O que foi criado

### 1. **Webhook Automático** ⚙️
**Arquivo**: `webhook_auto_alteracao.py`

- Recebe notificações quando tarefa muda de status
- Marca campo automaticamente quando status = "em alteração"
- Registra todos os eventos em JSON para auditoria
- Endpoints REST para consultar logs e status
- Pronto para integração com ClickUp webhooks

**Como usar**:
```bash
python3 ~/Scripts/webhook_auto_alteracao.py
# Deixe rodando (ctrl+c para parar)
```

### 2. **Marcador em Batch** 📋
**Arquivo**: `mark_teve_alteracao_batch.py`

- Marca tarefas retrospectivas (histórico passado)
- Marca tarefas específicas ou todas da lista
- Pode desmarcar também
- Perfeito para atualizar tarefas antigas

**Como usar**:
```bash
# Tarefas específicas
python3 ~/Scripts/mark_teve_alteracao_batch.py --task-ids 86ahdcp2a 86ahe25wy

# Todas da lista
python3 ~/Scripts/mark_teve_alteracao_batch.py --all

# Desmarcar
python3 ~/Scripts/mark_teve_alteracao_batch.py --task-ids 86ahdcp2a --unmark
```

### 3. **Suite de Testes** 🧪
**Arquivo**: `test_auto_alteracao.py`

- Valida token do ClickUp
- Testa conexão com API
- Verifica se campo existe
- Verifica se status existe
- Testa atualização do campo
- Testa webhook endpoint

**Status**: ✅ **6/6 testes passando**

**Como usar**:
```bash
python3 ~/Scripts/test_auto_alteracao.py
```

### 4. **Menu Interativo** 🎯
**Arquivo**: `teve_alteracao_menu.py`

- Interface amigável para gerenciar tudo
- Iniciar webhook
- Marcar tarefas
- Ver logs
- Executar testes
- Visualizar docs

**Como usar**:
```bash
python3 ~/Scripts/teve_alteracao_menu.py
```

### 5. **Documentação Técnica** 📖
**Arquivo**: `SETUP_AUTO_ALTERACAO.md`

- Setup completo
- Instalação de dependências
- Configuração no ClickUp
- Troubleshooting
- Exemplos avançados

### 6. **Guia Rápido** 📚
**Arquivo**: `README_TEVE_ALTERACAO.md`

- Resumo rápido do sistema
- Como usar (opção A e B)
- Exemplos práticos
- Monitoramento
- Troubleshooting básico

---

## 🎯 Casos de Uso

### Cenário 1: Automático (Recomendado)
```
Tarefa movida para "em alteração" 
    ↓
Webhook recebe notificação 
    ↓
Campo marcado automaticamente ✅
    ↓
Visível no ClickUp
```

### Cenário 2: Manual (Histórico)
```
Você identifica tarefa com alteração 
    ↓
Executa: python3 mark_teve_alteracao_batch.py --task-ids <id>
    ↓
Campo marcado ✅
    ↓
Visível no ClickUp
```

### Cenário 3: Relatório Semanal
```
Busca logs: curl http://localhost:5001/webhook/logs
    ↓
Filtra tarefas com campo "Teve alteração?" = verdadeiro
    ↓
Inclui em relatório semanal
```

---

## 🚀 Getting Started (3 passos)

### Passo 1: Testar o sistema
```bash
python3 ~/Scripts/test_auto_alteracao.py
```
✅ Deve exibir: "Todos os testes passaram!"

### Passo 2: Escolher abordagem
- **Automática**: Webhook rodando permanentemente
- **Manual**: Marcar conforme necessário
- **Híbrida**: Webhook + marcação manual para histórico

### Passo 3: Usar
```bash
# Opção A: Menu interativo
python3 ~/Scripts/teve_alteracao_menu.py

# Opção B: Iniciar webhook direto
python3 ~/Scripts/webhook_auto_alteracao.py

# Opção C: Marcar tarefas
python3 ~/Scripts/mark_teve_alteracao_batch.py --task-ids <id>
```

---

## 🔧 Configuração ClickUp (Se usar webhook)

1. Acesse: https://app.clickup.com/settings/integrations/webhooks
2. "Create Webhook"
3. Preencha:
   ```
   Event: Task Status Updated
   URL: http://localhost:5001/webhook/auto-alteracao
   Team: IMPERA PRODUTOS NATURAIS
   ```
4. Salve

**Nota**: Se usar máquina local, configure ngrok para expor (veja docs técnica).

---

## 📊 Arquivos Criados

```
~/Scripts/
├── webhook_auto_alteracao.py          [Webhook automático]
├── mark_teve_alteracao_batch.py       [Marcador em batch]
├── test_auto_alteracao.py             [Suite de testes]
├── teve_alteracao_menu.py             [Menu interativo]
├── SETUP_AUTO_ALTERACAO.md            [Docs técnica]
├── README_TEVE_ALTERACAO.md           [Guia rápido]
└── data/
    └── auto_alteracao_log.json        [Logs de eventos]
```

---

## 📈 Capacidades

✅ Marca automaticamente em "em alteração"  
✅ Marca manualmente histórico passado  
✅ Registra eventos em JSON  
✅ API REST para logs e status  
✅ Menu interativo  
✅ Suite de testes completa  
✅ Documentação técnica  
✅ Pronto para produção  

---

## 🔍 Monitoramento & Logs

### Ver logs do webhook:
```bash
curl http://localhost:5001/webhook/logs | jq '.events'
```

### Ver status:
```bash
curl http://localhost:5001/webhook/status | jq '.'
```

### Ver arquivo de logs:
```bash
cat ~/Scripts/data/auto_alteracao_log.json | jq '.'
```

---

## 🐛 Troubleshooting Rápido

| Problema | Solução |
|----------|---------|
| Testes falhando | Verifique: `echo $CLICKUP_API_TOKEN` |
| Webhook 404 | Inicie: `python3 ~/Scripts/webhook_auto_alteracao.py` |
| Campo não marca | Verifique token e execute: `test_auto_alteracao.py` |
| Conexão recusada | Webhook não está rodando |

---

## 💡 Próximas Integrações Sugeridas

1. **Relatório Semanal**: Adicionar seção "Tarefas com Alteração"
2. **Dashboard**: Mostrar tarefas alteradas em gráfico
3. **Alertas**: Notificar quando tarefa entra em "em alteração"
4. **Filtro ClickUp**: Criar view que mostra tarefas com alteração

---

## 📅 Timeline da Implementação

| Etapa | Status |
|-------|--------|
| Design da solução | ✅ Concluído |
| Implementação do webhook | ✅ Concluído |
| Script de marcação batch | ✅ Concluído |
| Suite de testes | ✅ 6/6 passando |
| Documentação | ✅ Completa |
| Menu interativo | ✅ Concluído |
| Validação em produção | ✅ Pronto |

---

## 🎓 Aprendizados

- ClickUp API v2 não expõe histórico completo (solução: webhook + marcação manual)
- Endpoint correto é POST (não PUT) para atualizar campos
- Campo `3617b249-06e2-4d2e-9ba0-c48da305e42a` está ativo e funcional
- Webhook é a forma mais confiável de rastrear mudanças em tempo real

---

## 📞 Suporte

Para dúvidas:
1. Execute testes: `python3 ~/Scripts/test_auto_alteracao.py`
2. Veja docs: `cat ~/Scripts/README_TEVE_ALTERACAO.md`
3. Use menu: `python3 ~/Scripts/teve_alteracao_menu.py`

---

**Data de Conclusão**: 2026-05-24  
**Status**: ✅ Pronto para Produção  
**Testes**: 6/6 ✅  
**Documentação**: Completa ✅  

🎉 **Sistema implementado com sucesso!**
