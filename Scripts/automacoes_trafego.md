# 🤖 Mapa de Automações — GESTÃO DE TRÁFEGO

## Transições Automáticas vs Manuais

Análise de todas as transições possíveis entre statuses e quais podem ser automatizadas.

---

## Matriz de Automações

| De Status | Para Status | Critério | Automatizável? | Via | Risco | Prioridade |
|-----------|-------------|----------|---|---|---|---|
| **aguardando teste** | em teste | Gestor abre manualmente na fila | ❌ Manual | — | — | N/A |
| **em teste** | pré-escala | CTR ≥ target + CPC ≤ limite | ✅ Sim | RedTrack polling + threshold | Baixo (gestor revisa) | 🟢 Alta |
| **em teste** | testes concluídos | Duração > 3 dias + sem decisão | ✅ Sim | Timeout | Médio (notifica antes) | 🟡 Média |
| **em teste** | reprovado | CTR < 0.5% ou zero conversões | ✅ Sim | RedTrack polling | Médio (threshold ajustável) | 🟡 Média |
| **testes concluídos** | pré-escala | Gestor revisa dados e aprova | ❌ Manual | — | — | N/A |
| **testes concluídos** | cemitério | Sem movimentação > 7 dias | ✅ Sim | Timeout + notif. | Baixo (gestor autoriza) | 🟢 Alta |
| **pré-escala** | validado | Budget +50% + performance estável | ⚠️ Semi | Manual com threshold helper | Médio | 🟡 Média |
| **validado** | escala | ROI continua positivo | ✅ Sim | RedTrack daily polling | Baixo (é sucesso) | 🟢 Alta |
| **escala** | em risco | ROI cai 20% ou CPC +30% | ✅ Sim | RedTrack daily polling | Médio (alerta enviado) | 🟢 Alta |
| **escala** | pausado | Gestor pausa para revisar | ❌ Manual | — | — | N/A |
| **escala** | vturb | Gestor quer testar outra plataforma | ❌ Manual | — | — | N/A |
| **em risco** | negativo | ROI < 0 por 2 dias consecutivos | ✅ Sim | RedTrack 2-day rule | Alto (decisão final) | 🔴 Crítica |
| **em risco** | pausado | Gestor quer revisar | ❌ Manual | — | — | N/A |
| **negativo** | cemitério | Finalizar criativo | ❌ Manual | — | — | N/A |
| **negativo** | pausado | Revisar depois | ❌ Manual | — | — | N/A |
| **pausado** | validado | Revisão aprovada | ❌ Manual | — | — | N/A |
| **pausado** | cemitério | Revisor descarta após análise | ❌ Manual | — | — | N/A |
| **vturb** | validado | Performance ok em plataforma alt. | ❌ Manual | — | — | N/A |
| **vturb** | cemitério | Não funcionou em alt. plataforma | ❌ Manual | — | — | N/A |
| **reprovado** | cemitério | Teste falhou, descarta | ❌ Manual | — | — | N/A |
| **qualquer** | cemitério | Gestor decide descartar | ❌ Manual | — | — | N/A |

---

## 3 Scripts de Automação Propostos

### 1️⃣ **automacao_timeout_trafego.py** — Timeout Automático

**Objetivo:** Limpar tarefas paradas em estados intermediários

**Transições:**
1. `em teste` → `testes concluídos` (após 5 dias sem decisão)
2. `testes concluídos` → `cemitério` (após 7 dias sem movimentação)
3. `em risco` → `negativo` (confirmação após 2 dias de ROI negativo)

**Executar:** Via crontab 1x/dia (às 09:00)

**Notificações:** Telegram 24h antes de mover, com detalhes da tarefa

**Rollback:** Se gestor mover tarefa manualmente, não mexer

---

### 2️⃣ **automacao_redtrack_trafego.py** — Performance-Based Transitions

**Objetivo:** Transições automáticas baseadas em ROI/CTR do RedTrack

**Dados de entrada:** RedTrack API (campanhas diárias)

**Lógica:**

```
Para cada tarefa em "em teste":
  Busca campanha correspondente em RedTrack (por AD# ou nome)
  Se CTR >= 1.2% E CPC <= R$10:
    Aprova para pré-escala
    Notifica gestor no Telegram
  
Para cada tarefa em "escala":
  Se ROI < 0 por 2 dias consecutivos:
    Move para "em risco"
    Alerta gestor imediatamente
  Se ROI >= 150%:
    Confirma em "validado"

Para cada tarefa em "em risco":
  Se ROI permanecer < 0 por mais 2 dias:
    Move para "negativo" (FINAL)
    Notifica com relatório de falha
```

**Parâmetros ajustáveis:**
- `CTR_MIN_PASSE` = 1.2%
- `CPC_MAX_PASSE` = R$ 10
- `ROI_NEGATIVO_DIAS` = 2
- `ROI_MIN_VALIDADO` = 150%

**Executar:** Via crontab 2x/dia (09:00 e 17:00)

---

### 3️⃣ **automacao_limpeza_manual.py** — Helper Manual

**Objetivo:** Ferramentas para gestor acelerar transições manuais

**Funções:**
- `move_batch(status_from, status_to, task_ids)` — mover múltiplas tarefas de uma vez
- `approve_by_metric(metric, operator, value)` — ex: `approve_by_metric("CTR", ">=", 1.0)` aprova todos
- `generate_report(status)` — relatório para gestor revisar antes de aprovar

**Uso:** CLI interativa

---

## Fluxo de Execução Recomendado

### Semana 1-2: MVP
- ✅ Deploy `automacao_timeout_trafego.py`
- ✅ Teste manual de transições
- ✅ Feedback com gestor

### Semana 3-4: Integração RedTrack
- ✅ Deploy `automacao_redtrack_trafego.py`
- ✅ Tuning de thresholds com dados reais
- ✅ Validação com gestor

### Semana 5+: Otimização
- ✅ Integrar `automacao_limpeza_manual.py`
- ✅ Dashboard de automações em tempo real
- ✅ Histórico de transições automáticas vs manuais

---

## Segurança e Rollback

### Regras Gerais

1. **Nunca mover para CEMITÉRIO automaticamente** — sempre com aprovação manual ou notificação 24h
2. **Sempre notificar gestor antes de mover** — em Telegram com detalhes
3. **Todas as transições registram log** — arquivo `~/.claude/logs/automacoes_trafego.log`
4. **Dry-run mode** — scripts podem rodar em modo `-–dry-run` sem fazer mudanças
5. **Whitelist de gestor** — se tarefa foi movida manualmente nos últimos 2 dias, não mexer

### Rollback

Se algo der errado:
1. Parar script via `crontab -e` (comentar linha)
2. Buscar tarefas afetadas em arquivo de log
3. Restaurar status manualmente via ClickUp ou via script `restore_status.py`

---

## Dependências

Scripts precisam de:
- `impera_utils.py` — parsing de nomenclatura
- RedTrack API token (`REDTRACK_API_KEY`)
- ClickUp API token (`CLICKUP_API_TOKEN`)
- Telegram bot token (opcional, para notificações)

---

## Métricas de Sucesso

**Após 30 dias de deploy:**

| Métrica | Target |
|---------|--------|
| % de tarefas que avançam automaticamente | 40% |
| Tempo médio em "em teste" | -2 dias (vs. 5 dias) |
| Taxa de false positives | < 2% |
| Gestor satisfação | ≥ 8/10 |

---

## Próximos Passos

1. Validar thresholds RedTrack com gestor (CTR, CPC, ROI)
2. Criar testes unitários para cada regra de transição
3. Implementar dashboard de "próximas automações agendadas"
4. Documentar em Obsidian as mudanças de status automáticas
