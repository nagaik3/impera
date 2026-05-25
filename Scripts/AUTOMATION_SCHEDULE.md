# 📅 AUTOMATION_SCHEDULE.md — IMPERA Automation Frequencies

**Date**: 2026-05-17  
**Status**: MASTER SCHEDULE FOR ALL 47 SCRIPTS  
**Timezone**: BRT (GMT-3)

---

## 📋 TABLE OF CONTENTS

1. [📝 Relatórios (10)](#relatórios-10)
2. [🤖 Automações (12)](#automações-12)
3. [💬 Bots (3)](#bots-3)
4. [👀 Monitores (5)](#monitores-5)
5. [🔧 Utilitários (8)](#utilitários-8)
6. [🗂️ Infraestrutura (9)](#infraestrutura-9)

---

## 📝 RELATÓRIOS (10)

### Documentados em CLAUDE.md:

| # | Script | Frequência | Dia/Hora BRT | Saída | Status | Notes |
|---|--------|-----------|-------------|-------|--------|-------|
| 1 | `briefing_diario.py` | Diária (seg-sex) | 10:00 | .txt + Telegram + Obsidian | ✅ | Documentado em CLAUDE.md |
| 2 | `relatorio_semanal_impera.py` | Semanal (domingo) | 12:03 | .docx (produção) | ✅ | Documentado em CLAUDE.md |
| 3 | `relatorio_redtrack_impera.py` | Diária | 06:00 | .docx (performance) | ✅ | Documentado em CLAUDE.md |
| 4 | `relatorio_mensal_arquivo_morto_v2.py` | Mensal (1º dia) | 09:07 | .docx | ✅ | Documentado em CLAUDE.md |
| 5 | `bot_gpdr.py autofix` | A cada 6h | 0/6/12/18h | Obsidian + Slack | ✅ | GPDR consolidado (documentado) |

### Adicionais encontrados em crontab:

| # | Script | Frequência | Dia/Hora BRT | Saída | Status | Notes |
|---|--------|-----------|-------------|-------|--------|-------|
| 6 | `relatorio_copywriters_semanal.py` | Semanal (segunda) | 09:30 | ? | ⚠️ | **REDUNDANTE com #1?** |
| 7 | `relatorio_entregas_trafego.py` | Semanal (domingo) | 13:00 | .docx | ⚠️ | **REDUNDANTE com #3?** |
| 8 | `relatorio_performance_copywriters_pdf.py` | Quinzenal (15º) 12:00 + Mensal (1º) 12:00 | Múltiplas | PDF | ⚠️ | **CONFLITA com #1** |
| 9 | `relatorio_performance_criativos.py` | Semanal (segunda) | 08:30 | ? | ⚠️ | **CONFLITA com #1** |
| 10 | `relatorio_pontuacao_editores.py` | Semanal (segunda) 12:00 + Mensal (1º) 12:00 | Múltiplas | ? | ⚠️ | **CONFLITA com #1** |

### Encontrados mas não em crontab ativo:

| Script | Status | Razão |
|--------|--------|-------|
| `relatorio_assertividade.py` | ❌ OBSOLETO? | Não em crontab ativo |
| `relatorio_vturb.py` | ❌ OBSOLETO? | Não em crontab ativo |

---

## 🤖 AUTOMAÇÕES (12)

| # | Script | Frequência | Condição | Status | Notes |
|---|--------|-----------|----------|--------|-------|
| 1 | `clickup_criar_tarefa.py` | Manual trigger | Via Claude Code | ✅ | Super Agent - será deprecated em Impera.OS v2 |
| 2 | `auto_categoria.py` | COMENTADO | --commented | ❌ | Não está ativo em crontab |
| 3 | `auto_envio_trafego.py` | A cada 10 min (seg-sex) + 16:00 | `--monitor` + `--chat` | ✅ | Ativo: 10min poll + daily chat 16h |
| 4 | `auto_etiqueta.py` | De hora em hora (seg-sex) | 0h de cada hora | ✅ | Ativo: cada hora (0h) nos dias úteis |
| 5 | `auto_healing.py` | COMENTADO | --commented | ❌ | Não está ativo em crontab |
| 6 | `auto_status_rt.py` | **SEM CRONTAB** | ? | ⚠️ | **CRÍTICO - Frequência desconhecida!** |
| 7 | `auto_time_tracking.py` | **SEM CRONTAB** | ? | ⚠️ | **Frequência desconhecida!** |
| 8 | `cruzamento_clickup_redtrack.py` | **SEM CRONTAB** | ? | ⚠️ | **CRÍTICO - Sincronização bidirecional sem schedule!** |
| 9 | `classificador_criativos.py` | Múltiplas vezes (seg-sex) | 14:00 + 19:00 | ✅ | `--execute` às 14h, `--quase-la` às 19h |
| 10 | `gate_finalizado.py` | COMENTADO | --commented | ❌ | Não está ativo em crontab |
| 11 | `detectar_criativos_orfaos_v2.py` | COMENTADO | --commented | ❌ | Não está ativo em crontab |
| 12 | `input_financeiro.py` | Manual | Via Claude Code | ✅ | Manual entry point |

---

## 💬 BOTS (3)

| # | Script | Plataforma | Frequência | Trigger | Status | Notes |
|---|--------|-----------|-----------|---------|--------|-------|
| 1 | `telegram_claude_bot.py` | Telegram | Contínuo | Webhook (inbound) | ✅ | IA Claude - responds to messages |
| 2 | `telegram_financas_comandos.py` | Telegram | A cada 5 min | Poll (*/5) | ✅ | Finance commands - periodic polling |
| 3 | `telegram_gemini_bot.py` | Telegram | ? | ? | ⚠️ | **REDUNDANTE com #1?** Frequência desconhecida |

---

## 👀 MONITORES (5)

| # | Script | O quê monitora | Frequência | Ação | Status | Notes |
|---|--------|-------------|-----------|------|--------|-------|
| 1 | `health_check_impera.py` | Saúde do sistema | COMENTADO | Alerta | ❌ | Não está ativo em crontab |
| 2 | `monitor_aguardando_teste.py` | Tarefas aguardando teste | Diária (13:00) | Log/Report | ✅ | Ativo: diariamente às 13h |
| 3 | `monitor_nichos_ofertas.py` | Performance por nicho/oferta | A cada 6h | Report | ✅ | Ativo: 0/6/12/18h |
| 4 | `monitor_pausados_15d.py` | Campanhas pausadas >15d | Diária (13:00) | Log/Report | ✅ | Ativo: diariamente às 13h |
| 5 | `reminder_em_teste.py` | Reminder para tarefas em teste | Diária (10:00) | Reminder | ✅ | Ativo: diariamente às 10h (seg-dom) |

---

## 🔧 UTILITÁRIOS (8)

| # | Script | Função | Frequência | Trigger | Status |
|---|--------|--------|-----------|---------|--------|
| 1 | `impera_cache.py` | Sistema de cache | On-demand | Importado por outros | ✅ |
| 2 | `impera_utils.py` | Funções utilitárias | On-demand | Importado por outros | ✅ |
| 3 | `obsidian_session.py` | Registra sessão em Obsidian | Manual | Claude Code `/session` | ✅ |
| 4 | `reauth_google.py` | Re-autenticação Google Drive | Manual/On-demand | Trigger manual | ✅ |
| 5 | `sync_responsavel_dropdown.py` | Sincroniza dropdown responsáveis | A cada 10 min | COMENTADO | ❌ |
| 6 | `auditoria_nomenclatura.py` | Audita nomenclatura de criativos | Múltipla (0/6/12/18h) + polls | 3h + 3.5h polls + chats 11h/16h | ✅ |
| 7 | `compliance_drive.py` | Compliance para Google Drive | Múltipla (13h/21h) + polls | Daily + polls 10:30/18:30 | ✅ |
| 8 | `pareto_semanal.py` | Análise Pareto semanal | Semanal (segunda) | 07:03 | ✅ |

---

## 🗂️ INFRAESTRUTURA (9)

| # | Script | Função | Frequência | Output | Status |
|---|--------|--------|-----------|--------|--------|
| 1 | `briefing_diario.py` | Briefing diário (documentado) | Diária (seg-sex) 10:00 | .txt + Telegram + Obsidian | ✅ |
| 2 | `bot_gpdr.py` | Bot GPDR (documentado) | A cada 6h | Obsidian + Slack | ✅ |
| 3 | `bot_performance.py` | Bot performance | 3x dia (08:30/16:00/9-20h check) | Chat reports | ✅ |
| 4 | `rastreador_esteira.py` | Rastreador de pipeline | A cada 30 min (poll) + 11h/16h (alert) | Pipeline tracking | ✅ |
| 5 | `rotina_diaria.py` | Rotina diária | Não encontrado em crontab | ? | ❌ |
| 6 | `dashboard_cobertura_rt_cu.py` | Dashboard RedTrack/ClickUp | Semanal (segunda) 12:00 | Dashboard report | ✅ |
| 7 | `automacao_drive_edicao.py` | Auto edição em Drive | A cada 15 min | Drive automation | ✅ |
| 8 | `roas_diario.py` | ROAS diário | Diária 11:27 | ROAS report | ✅ |
| 9 | `alarme.sh` | Shell script alarme | Múltipla (eventos) | Alarms/Notifications | ✅ |

---

## ⏰ CRONOGRAMA POR HORA BRT

### 06:00
- `relatorio_redtrack_impera.py` (diário)

### 07:03
- `pareto_semanal.py` (segunda)

### 08:30
- `relatorio_performance_criativos.py` (segunda)
- `bot_performance.py morning` (seg-sex)

### 09:00-09:40
- Dashboard ETL extras (09:35)
- Polymarket briefing daily (09:00)

### 10:00
- `briefing_diario.py` (seg-sex)
- `reminder_em_teste.py` (diária)

### 11:00-11:27
- `rastreador_esteira.py alert` (seg-sex)
- `roas_diario.py` (diária)
- Polymarket briefing weekly (11:00 domingo)

### 12:00-12:03
- `relatorio_semanal_impera.py` (domingo 12:03)
- `relatorio_pontuacao_editores.py --semanal` (segunda)
- `relatorio_pontuacao_editores.py --mensal` (1º mês)
- `relatorio_performance_copywriters_pdf.py` (múltiplas datas)
- `dashboard_cobertura_rt_cu.py --chat` (segunda)

### 13:00
- `monitor_aguardando_teste.py` (diária)
- `monitor_pausados_15d.py` (diária)
- `relatorio_entregas_trafego.py` (domingo)

### 14:00
- `classificador_criativos.py --execute` (seg-sex)

### 16:00
- `auto_envio_trafego.py --chat` (seg-sex)
- `bot_performance.py afternoon` (seg-sex)
- `rastreador_esteira.py alert` (seg-sex)

### 19:00
- `classificador_criativos.py --quase-la` (seg-sex)

### 21:00
- `compliance_drive.py` (seg-sex)

---

## ⚠️ PROBLEMAS CRÍTICOS IDENTIFICADOS

### 1. Sincronizações Bidirecional SEM SCHEDULE
```
CRÍTICO:
- cruzamento_clickup_redtrack.py (não está em crontab!)
- auto_status_rt.py (não está em crontab!)

IMPACTO: Impossível validar precisão, testar ou debugar
```

### 2. Automações Comentadas/Inativas
```
INATIVO:
- auto_categoria.py
- auto_healing.py
- gate_finalizado.py
- detectar_criativos_orfaos_v2.py
- sync_responsavel_dropdown.py
- health_check_impera.py
- rotina_diaria.py

IMPACTO: Clareza sobre o que está realmente rodando
```

### 3. Frequências Não Documentadas
```
DESCONHECIDAS:
- auto_time_tracking.py (quando roda?)
- telegram_gemini_bot.py (frequência?)

IMPACTO: Impossível planejar consolidações
```

### 4. Scripts Obsoletos
```
PROVAVELMENTE OBSOLETOS:
- relatorio_assertividade.py (não em crontab ativo)
- relatorio_vturb.py (não em crontab ativo)
- relatorio_semanal_producao.py (conflita com relatórios maiores?)
- relatorio_mensal_copywriters.py (não localizado)

IMPACTO: Confusão sobre qual relatório usar
```

### 5. Redundância de Relatórios
```
POTENCIALMENTE REDUNDANTES:
- relatorio_semanal_impera.py (produção geral)
  + relatorio_copywriters_semanal.py (copywriters apenas)
  + relatorio_performance_copywriters_pdf.py (PDF version)
  → 3 versões do MESMO RELATÓRIO?

- relatorio_redtrack_impera.py (performance RedTrack)
  + relatorio_entregas_trafego.py (entregas ao tráfego)
  + relatorio_performance_criativos.py (performance criativos)
  → 3 versões DO MESMO RELATÓRIO?

IMPACTO: 6 processamentos para 2 relatórios únicos
```

---

## 📊 ESTATÍSTICAS

### Ativo vs Inativo
- **Ativo**: 30 scripts
- **Comentado**: 8 scripts (8 linhas comentadas em crontab)
- **Desconhecido**: 9 scripts (não localizados em crontab)

### Por Categoria
| Categoria | Total | Ativo | Inativo | Desconhecido |
|-----------|-------|-------|---------|-------------|
| Relatórios | 10 | 5 | 0 | 5 |
| Automações | 12 | 3 | 4 | 5 |
| Bots | 3 | 2 | 0 | 1 |
| Monitores | 5 | 4 | 1 | 0 |
| Utilitários | 8 | 3 | 3 | 2 |
| Infraestrutura | 9 | 7 | 0 | 2 |
| **TOTAL** | **47** | **24** | **8** | **15** |

### Frequências
| Tipo | Count | Exemplos |
|------|-------|----------|
| Contínuo/Webhook | 2 | telegram bots |
| A cada 5 min | 1 | telegram_financas |
| A cada 10 min | 2 | auto_envio_trafego, sync_responsavel |
| A cada 15 min | 1 | automacao_drive_edicao |
| A cada 30 min | 2 | rastreador_esteira, auditoria (poll) |
| A cada 6h | 3 | bot_gpdr, monitor_nichos, auditoria (check) |
| Horária | 1 | auto_etiqueta |
| Múltiplas por dia | 8 | bot_performance, compliance_drive, etc |
| Diária | 8 | briefing, monitores, roas, etc |
| Semanal | 7 | vários relatórios |
| Mensal | 3 | arquivo morto, pontuação, copywriters |

---

## ✅ PRÓXIMAS AÇÕES

### SEMANA 1 (Imediato)
1. ☐ Ler código de cada script sem crontab para descobrir frequência
2. ☐ Confirmar quais scripts estão realmente obsoletos
3. ☐ Agendar `cruzamento_clickup_redtrack.py` com versioning
4. ☐ Agendar `auto_status_rt.py` com frequência documentada
5. ☐ Criar AUTOMATION_DEPENDENCIES.md

### SEMANA 2 (Consolidação)
1. ☐ Consolidar 5 relatórios em 2 scripts paramétricos
2. ☐ Remover scripts obsoletos
3. ☐ Criar testes para race conditions

### SEMANA 3-4 (Validação)
1. ☐ Deploy consolidados em staging
2. ☐ Testes com equipe IMPERA
3. ☐ Atualizar crontab com novas frequências

---

## 📝 Sign-off

**Status**: MASTER SCHEDULE CRIADO  
**Data**: 2026-05-17  
**Próximo**: Ler código dos scripts sem frequência documentada

**Problemas Críticos Identificados**: 5  
**Scripts para Ação Imediata**: 5  
**Potencial de Consolidação**: 6 scripts → 2

---

*Este documento é a fonte única de verdade para frequências de automação. Atualizar quando houver mudanças.*
