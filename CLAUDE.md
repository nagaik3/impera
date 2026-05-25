# CLAUDE.md — Grupo IMPERA

## Contexto
Iago Almeida é owner do workspace ClickUp "IMPERA PRODUTOS NATURAIS". Gerencia equipe de copywriters (Yan, Crispim, Cássio, Ana, Elias) e editores de vídeo (Well, Igor Oliveira, Igor Paiva, Nicolas, Muryllo). Áreas: gestão de tráfego, copy, edição de vídeo, estratégia digital para produtos naturais de saúde.

## Super Agente ClickUp
Script em `~/Scripts/clickup_criar_tarefa.py` — para criar tarefas na lista COPY do ClickUp com:
- Nomenclatura automática: `[NICHO][OFERTA][FONTE][AD][VERSÃO]`
- Sequenciamento de AD automático (busca o último e continua)
- Checklists de QC automáticos (Copy + Edição)
- Suporte a: criativos novos, variações, leads, microleads, batches

Para usar: `from clickup_criar_tarefa import *` (após `sys.path.insert(0, '~/Scripts')`)

## Relatório Semanal de Produção
Script em `~/Scripts/relatorio_semanal_impera.py` — crontab todo domingo 12:03.
Gera .docx com produção por copywriter/editor/nicho.
**Gatilho**: "relatório de produção" ou "produção semanal"

## Relatório de Performance RedTrack
Script em `~/Scripts/relatorio_redtrack_impera.py` — crontab todo domingo 12:07.
Gera .docx com performance de campanhas, classificação de ofertas, breakdown por nicho/gestor.
**Gatilho**: "relatório redtrack", "performance das campanhas" ou "relatório de performance"

## Relatório Mensal Arquivo Morto
Script `~/Scripts/relatorio_mensal_arquivo_morto.py` — crontab dia 1 de cada mês 09:07.
Tarefas em "arquivo morto" com date_done no mês anterior, ordenadas por nomenclatura.
**Gatilho**: "relatório mensal arquivo morto" ou "relatório do mês passado"

## Relatório Mensal de Copywriters com Testes
Script `~/Scripts/relatorio_mensal_copywriters_testes.py` — crontab dia 1 de cada mês 09:10.
Cruza criativos criados (lista COPY) com testes (GESTÃO DE TRÁFEGO) por copywriter.
Calcula: criados, em teste, aprovados, em escala, taxas, variações.
**Gatilho**: "relatório mensal de copywriters" ou "produtividade mensal de copywriters"

## Dashboard de Testes — GESTÃO DE TRÁFEGO
Script `~/Scripts/dashboard_trafego_status.py` — exibe criativos por status com copywriter responsável.
1391 tarefas agrupadas nos 12 statuses (aguardando teste, em teste, pré-escala, validado, escala, etc.)
Mostra: nome, copywriter, dias no status. Suporta filtros (--status=) e exportação JSON (--json).
**Gatilho**: "dashboard de tráfego", "status de criativos" ou "dashboard de testes"

## Briefing Diário
Script `~/Scripts/briefing_diario.py` — crontab 10h seg-sáb + schedule Claude Code.
Panorama operacional: performance RedTrack (dia a dia + tendência), breakdown por gestor, top 5 campanhas, top 5 ads, ClickUp, esteira, automações.
- Telegram: formato texto/HTML (automático via cron)
- Claude Code: apresentar em **tabelas markdown** (ler `~/Scripts/data/briefing_diario_latest.txt` ou gerar fresco se >24h)
**Gatilho**: "briefing diário" ou "briefing"

## Relatório GPDR (Completo)
Consolida ClickUp + RedTrack no template `~/Downloads/Relatório GPDR - Resultados Semanal.docx`
Preenche ~70% automaticamente: KPIs, tabelas copy/edição/tráfego, leitura estratégica parcial.
**Gatilho**: "relatório GPDR", "relatório semanal completo" ou "GPDR"
Front Revenuee = revenuetype2 + revenuetype3 | Vendas CC = convtype4

## Expandir Ranges de Tarefas (Webhook)
Script em `~/Scripts/expandir_range_tasks.py` — Webhook receiver que sincroniza expansão de ranges no ClickUp.

**Fluxo:**
1. Gestor move subtarefas no dashboard (atribuidor-impera.onrender.com)
2. Dashboard cria 6 subtarefas em ClickUp (ex: AD116V1, AD117V1, ..., AD120V1)
3. Dashboard envia POST `/webhook/expand-range` com parent_task_id + created_tasks
4. Script recebe webhook:
   - Adiciona `parent_task_id` em cada subtarefa (custom field)
   - Marca tarefa PAI com `[EXPANDIDA] - Variações: V##,V##,...` na descrição
   - Move tarefa PAI para status "Testes Concluídos"

**Uso:**
- `python3 ~/Scripts/expandir_range_tasks.py --server` — inicia webhook server (porta 5000)
- `python3 ~/Scripts/expandir_range_tasks.py --test` — envia webhook mock para testar

**Env Vars** (já em ~/.zshrc):
- `CU_FIELD_PARENT_TASK_ID` — ID do campo custom (criado automaticamente)
- `CU_STATUS_TESTES_CONCLUIDOS` — ID do status "testes concluídos"
- `WEBHOOK_PORT` — porta do servidor (default 5000)

**Dashboard Integration:**
O dashboard deve enviar POST para `http://<server>:5000/webhook/expand-range` com payload:
```json
{
  "parent_task_id": "86ah8t9ac",
  "created_tasks": [
    {"id": "task_1", "name": "[MM][BR][OF01][FB][AD116][V1]"},
    {"id": "task_2", "name": "[MM][BR][OF01][FB][AD117][V1]"}
  ],
  "target_status": "aguardando teste"
}
```

## Tokens
- ClickUp: env var `CLICKUP_API_TOKEN` (em ~/.zshrc e crontab)
- RedTrack: env var `REDTRACK_API_KEY` (em ~/.zshrc e crontab)

## Obsidian Vault
Vault em `~/Obsidian/IMPERA/` — base de conhecimento compartilhada com o usuário.
- **Daily Notes**: `Daily Notes/YYYY-MM-DD.md` — criadas automaticamente pelo briefing_diario.py
- **Sessões**: Ao finalizar uma sessão, rodar `python3 ~/Scripts/obsidian_session.py "resumo"`
- **Scripts**: 38+ scripts documentados em `Scripts/`
- **Pessoas**: copywriters e gestores com backlinks
- **MOC**: "IMPERA - Map of Content.md" é o índice principal
- **Fluxo de Testes**: `Fluxo de Testes de Criativos.md` — workflow completo com 12 statuses
- **Entrega Dashboard**: `Entrega - Dashboard e Relatórios de Testes.md` — documentação completa
- Usar `[[Nome]]` para criar links entre notas

## Automação: Rastreamento de Alterações
Sistema automático para marcar tarefas que foram movidas para o status **"em alteração"**.

**Campo**: `🔄 Teve alteração?` (checkbox)

**Scripts**:
- `webhook_auto_alteracao.py` — Webhook que marca automaticamente quando tarefa → "em alteração"
- `mark_teve_alteracao_batch.py` — Marca tarefas manualmente (retrospectivo)
- `test_auto_alteracao.py` — Suite de testes (6/6 ✅ passando)
- `teve_alteracao_menu.py` — Menu interativo

**Como usar**:
1. **Automático**: `python3 ~/Scripts/webhook_auto_alteracao.py` (deixe rodando)
2. **Manual**: `python3 ~/Scripts/mark_teve_alteracao_batch.py --task-ids <id>`
3. **Menu**: `python3 ~/Scripts/teve_alteracao_menu.py`

**Configurar no ClickUp**:
- Settings → Integrations → Webhooks → Create Webhook
- Event: Task Status Updated
- URL: `http://localhost:5001/webhook/auto-alteracao`

**Documentação**:
- Quick guide: `~/Scripts/README_TEVE_ALTERACAO.md`
- Tech docs: `~/Scripts/SETUP_AUTO_ALTERACAO.md`
- Summary: `~/Scripts/AUTOMACAO_TEVE_ALTERACAO_SUMARIO.md`

**Gatilho**: "marcar alteração", "rastrear alterações" ou "webhook de alteração"

## Regras importantes
- Nomenclatura: ver memória `feedback_nomenclatura_criativos.md`
- Copywriter "REAPER" = Cássio
- Fonte padrão quando não especificada: FB (Facebook)
- Contagem de criativos: INCLUSIVA (high - low + 1), e AD × Versão quando ambos existem
- IMG no nome = imagem, senão = vídeo
- [V1] = criativo novo, sem V1 = variação
- Sempre confirmar com o usuário antes de criar tarefas
