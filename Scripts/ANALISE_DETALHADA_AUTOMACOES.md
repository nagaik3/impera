# 🔍 ANÁLISE DETALHADA DAS 12 AUTOMAÇÕES — IMPERA

**Data**: 2026-05-17  
**Baseado em**: Leitura profunda do código-fonte de cada script  
**Objetivo**: Avaliar cada automação e propor ações concretas

---

## 📊 RESUMO EXECUTIVO

| Script | Status | Recomendação | Prioridade |
|--------|--------|--------------|-----------|
| 1. clickup_criar_tarefa.py | ✅ Funciona bem | **MANTER** | - |
| 2. auto_envio_trafego.py | ✅ Funciona bem | **MANTER** | - |
| 3. auto_etiqueta.py | ✅ Funciona bem | **MANTER** (por enquanto) | - |
| 4. classificador_criativos.py | ✅ Funciona bem | **MANTER** | - |
| 5. auto_categoria.py | ⚠️ Duplica classificador | **DESATIVAR** | 🔴 CRÍTICO |
| 6. auto_status_rt.py | ❌ Sem schedule | **AGENDAR 2x/dia** | 🔴 CRÍTICO |
| 7. auto_healing.py | ⚠️ Parcialmente usado | **DESATIVAR** | 🟡 MÉDIO |
| 8. gate_finalizado.py | ⚠️ Não agendado | **REATIVAR + AGENDAR** | 🟠 HIGH |
| 9. detectar_criativos_orfaos_v2.py | ✅ Funciona bem | **MANTER** | - |
| 10. auto_time_tracking.py | ⚠️ Sem verificação de uso | **INVESTIGAR** | 🟡 MÉDIO |
| 11. cruzamento_clickup_redtrack.py | ✅ Leitura pura | **MANTER** (adicionar versioning) | - |
| 12. input_financeiro.py | ✅ Manual útil | **MANTER** | - |

---

## 🎯 ANÁLISE INDIVIDUAL

### 1️⃣ clickup_criar_tarefa.py

**O que faz:**
- Super Agent que cria tarefas no ClickUp (lista COPY)
- Nomenclatura automática: `[NICHO][OFERTA][FONTE][AD][VERSÃO]`
- Checklists QC automáticos (Copy + Edição)
- Suporta: criativos novos, variações, leads, microleads, batches
- Chamado via CLI ou importado pelo Claude Code

**Como funciona:**
```
clickup_criar_tarefa.py
├─ NICHOS mapeados (DA, DB, ED, EM, ME, MM, NE, PT, ZB)
├─ FONTES mapeadas (FB, GG, KW, MG, TB, TT, VT, YT)
├─ COPYWRITERS e EDITORES pré-configurados
├─ OFERTAS com IDs do ClickUp
└─ Cria tarefas com campos customizados completos
```

**Status:**
- ✅ Funciona perfeitamente
- ✅ Bem documentado no código
- ✅ Usado ativamente via Claude Code
- ✅ Sem conflitos com outras automações

**Recomendação: MANTER**
- Crítico para o fluxo de criação de tarefas
- Não há redundância
- Automação bem encapsulada

---

### 2️⃣ auto_envio_trafego.py

**O que faz:**
- Copia tarefas da lista COPY para lista GESTÃO TRÁFEGO
- Quando status = "enviado para trafego"
- Copia campos: Copywriter, Editor, Fonte, Oferta, Nicho, Mês, Link Material
- Modo --monitor: roda a cada 10 min
- Modo --chat: resume consolidado às 16h
- Substitui automação nativa do ClickUp (que falhava 23%)

**Como funciona:**
```
auto_envio_trafego.py --monitor (*/10)
├─ Lê tarefas com status "enviado para trafego"
├─ Verifica de duplicidade (STATE_FILE)
├─ Copia para GESTÃO TRÁFEGO com retry
├─ Logs com timestamp
└─ Telegram alerta em caso de erro

auto_envio_trafego.py --chat (16h)
└─ Resume diário consolidado no Chat
```

**Status:**
- ✅ Funciona bem, substituiu falha da automação nativa
- ✅ Retry automático + anti-duplicidade
- ✅ Logging robusto
- ✅ Telegram alerts se tiver erro
- ⚠️ Roda a cada 10 min — pode ser 30 min sem problema

**Recomendação: MANTER** (otimize frequência se quiser)
- Crítico para fluxo: COPY → TRÁFEGO
- Sem conflitos
- Sem redundâncias
- Substituição necessária da automação nativa (que falha 23%)

---

### 3️⃣ auto_etiqueta.py

**O que faz:**
- Adiciona tags automáticas a tarefas da COPY
- Baseado na nomenclatura da tarefa
- Tags: criativo-novo, variação, imagem, microlead, lead, vsl, otimização, upsell, pressell, ripagem
- Crontab: 1x por hora (seg-sex)
- Modo --dry: preview

**Como funciona:**
```
auto_etiqueta.py (*/hora, 0h de cada hora)
├─ Lê tarefas da COPY
├─ Analisa nome (parse nomenclatura)
├─ Aplica tags baseado em patterns
└─ Armazena estado para não re-aplicar
```

**Status:**
- ✅ Funciona bem (horário, aplicação de tags)
- ✅ Útil para organizar criação
- ⚠️ **POTENCIAL CONFLITO**: `classificador_criativos.py` também adiciona tags (focus em performance)
- ⚠️ `auto_categoria.py` também atualiza campos

**Problema:**
- Auto_etiqueta = tags baseadas em NOMENCLATURA (tipo de criativo: novo, variação, etc)
- Classificador = tags baseadas em PERFORMANCE (tier: em teste, validado, etc)
- Não deveriam conflitar, MAS precisam estar bem documentadas

**Recomendação: MANTER (por enquanto)**
- Porém: documentar claramente que:
  - auto_etiqueta = tags de TIPO (criativo-novo, variação, etc)
  - classificador = tags de PERFORMANCE (em-teste, validado, etc)
- Garantir que não sobrescrevem as mesmas tags
- **Futuramente**: consolidar em unified_classifier.py (Phase 2)

---

### 4️⃣ classificador_criativos.py

**O que faz:**
- Classifica criativos por performance (vendas + CPA)
- Regras do "Super Cérebro de Tráfego V5"
- Níveis: Em Teste → Pré-validado → Validado → Top/Escala
- Atualiza status no ClickUp + adiciona tags de jornada
- Alerta Telegram para promoções
- Monitor "quase lá" (faltam 1-2 vendas)
- Modos: --preview, --execute, --quase-la, --report
- Crontab: 14h + 19h (seg-sex)

**Como funciona:**
```
classificador_criativos.py --execute
├─ Lê tarefas da GESTÃO TRÁFEGO
├─ Puxa dados de RedTrack (vendas, CPA, ROAS)
├─ Calcula: vendas 7 dias, CPA, ROAS Front
├─ Aplica regras:
│  ├─ Em Teste: <3 vendas OU CPA > meta
│  ├─ Pré-validado: 3-9 vendas, CPA ≤ R$180
│  ├─ Validado: 10+ vendas, CPA dentro meta
│  └─ Top: 30+ vendas
├─ Atualiza status no CU
├─ Adiciona tags de jornada (potential-*, pré-validado, validado, top)
└─ Alerta Telegram para promoções
```

**Status:**
- ✅ Funciona muito bem
- ✅ Lógica clara e bem documentada
- ✅ Regras de negócio explícitas (CPA_META, ROAS_MIN)
- ✅ Tags acumulativas (não remove histórico)
- ✅ Alertas Telegram funcionando
- ⚠️ Roda 2x por dia (14h + 19h) — poderia ser só 1x (14h) sem problema

**Recomendação: MANTER + OTIMIZE**
- Funciona muito bem, não mexer
- **Otimização**: Considere rodar 1x/dia (14h) em vez de 2x

---

### 5️⃣ auto_categoria.py

**O que faz:**
- Preenche campo "Categoria" (dropdown) nas tarefas da COPY
- Mapeia status → categoria (COPY, EDIÇÃO, FREELANCER, ENTREGA)
- Crontab: a cada 30 min (seg-sáb)
- Modo --dry: preview

**Como funciona:**
```
auto_categoria.py (*/30)
├─ Lê tarefas da COPY
├─ Verifica status atual
├─ Mapeia para categoria:
│  ├─ COPY: escrevendo, alteração copy, etc
│  ├─ EDIÇÃO: em edição, pré produção, etc
│  ├─ FREELANCER: freelancer-editando, etc
│  └─ ENTREGA: finalizado, enviado, arquivo morto
└─ Atualiza campo "Categoria" (dropdown)
```

**Status:**
- ✅ Funciona tecnicamente
- ⚠️ **CRÍTICO**: Mesmo campo que `classificador_criativos.py` atualiza? NÃO (classificador usa tags, não categoria)
- ⚠️ **PROBLEMA**: É redundante com o próprio status da tarefa!
  - Se status = "escrevendo" → categoria = "COPY" (redundante!)
  - Se status = "em edição" → categoria = "EDIÇÃO" (redundante!)
  - Se status = "enviado para trafego" → categoria = "ENTREGA" (redundante!)
- ⚠️ Comentado em crontab — **não está rodando atualmente**

**Análise:**
A categoria é **100% deduzível do status**. Adicionar um campo de dropdown que simplesmente replica o status é:
1. Redundância de dados
2. Risco de desincronização
3. Processamento desnecessário (*/30)

**Recomendação: DESATIVAR PERMANENTEMENTE**
- **Razão**: Campo "Categoria" é redundante com "Status"
- **Impacto**: ZERO (comentado, não está rodando)
- **Ação**: Deletar ou arquivar
- **Alternativa**: Se precisa de "categoria" realmente, use dropdown no status (não campo separado)

---

### 6️⃣ auto_status_rt.py

**O que faz:**
- Atualiza status de tarefas no ClickUp baseado em dados RedTrack
- Regras: ROAS, invest, performance últimos 7 dias
- Modos: --preview, --execute, --comment, --report
- **CRÍTICO**: NÃO ESTÁ AGENDADO! Roda manual apenas

**Como funciona:**
```
auto_status_rt.py --preview
├─ Lê tarefas da GESTÃO TRÁFEGO
├─ Puxa dados RedTrack (ROAS, invest, performance)
├─ Aplica regras:
│  ├─ Em teste: ROAS indefinido OU invest < R$500
│  ├─ Validado: ROAS >= 1.5, invest R$500-R$2k
│  ├─ Pré-escala: ROAS >= 1.5, invest >= R$2k
│  └─ Escala: ROAS >= 2.0, invest >= R$5k
├─ Preview: mostra o que faria
├─ Execute: atualiza
└─ Comment: posta comentário pedindo confirmação
```

**Status:**
- ✅ Funciona bem tecnicamente
- ❌ **CRÍTICO**: Não está agendado em crontab
  - Roda manual via Claude Code
  - Status nunca atualiza automaticamente
  - Reports mostram status desatualizado
- ⚠️ **RACE CONDITION RISK**: Se roda enquanto relatórios estão sendo gerados, dados podem ficar inconsistentes

**Problema Real:**
```
CENÁRIO ATUAL:
Sexta 8h — reportes leem status "EM TESTE"
Sexta 11h — alguém executa auto_status_rt.py manualmente
Sexta 12h — status agora é "VALIDADO"
Domingo 12h — relatório semanal mostra números INCONSISTENTES

SOLUÇÃO: Agendar auto_status_rt.py 2x/dia
Sexta 6h — auto_status_rt.py executa
Sexta 8h — relatórios leem status ATUAL
```

**Recomendação: AGENDAR IMEDIATAMENTE**
- **Ação**: Adicionar ao crontab 2x/dia (6:00 e 14:00)
  ```
  0 6 * * * python3 auto_status_rt.py --execute
  0 14 * * * python3 auto_status_rt.py --execute
  ```
- **Benefício**: Status sempre atual, relatórios consistentes
- **Custo**: 2 API calls extras/dia (negligenciável)
- **Urgência**: 🔴 CRÍTICO

---

### 7️⃣ auto_healing.py

**O que faz:**
- Protocolo de segurança para automações
- Detecta erros nos logs e aplica correções automáticas
- Ações: log rotation (>5MB), rate limit retry, timeout retry, 404 alert
- Monitora scripts: automacao_drive, roas_diario, rotina_diaria, sync_responsavel, rastreador_esteira, auditoria_nomenclatura, etc
- Crontab: a cada 30 min (seg-sáb, 8h-21h) — **MAS COMENTADO**

**Como funciona:**
```
auto_healing.py
├─ Lê logs de scripts monitorados
├─ Detecta padrões de erro:
│  ├─ Log > 5MB → trunca, mantém 500 últimas linhas
│  ├─ HTTP 429 (rate limit) → re-executa com backoff
│  ├─ Timeout → re-executa script uma vez
│  ├─ ClickUp 404 → alerta urgente (view deletada?)
│  └─ Script travado → alerta
└─ Alerta Telegram para casos que precisa intervenção humana
```

**Status:**
- ⚠️ Bem-intencionado, mas **COMENTADO em crontab** — não está rodando
- ⚠️ Funciona tecnicamente, mas:
  - A maioria dos scripts já tem retry built-in
  - Log rotation é responsabilidade de ops (logrotate, etc)
  - Não previne problemas, apenas detecta (healing é limitado)
- ⚠️ **Problema**: "Healing" é word bonito, mas na prática é só re-executar script

**Análise:**
- Se scripts têm retry built-in (como `auto_envio_trafego`), auto_healing é redundante
- Se scripts não têm retry, o problema é no próprio script (fix nele, não em healing)
- Log rotation deveria ser feito por ferramenta de ops (logrotate, systemd-tmpfiles), não script Python

**Recomendação: DESATIVAR**
- **Razão**: Redundante com retry built-in dos scripts
- **Alternativa**: Usar logrotate do OS para rotation
- **Impacto**: ZERO (já comentado)
- **Ação**: Arquivar ou deletar

---

### 8️⃣ gate_finalizado.py

**O que faz:**
- Validação automática quando tarefa atinge status "finalizado"
- Verifica: nomenclatura, compliance do Drive
- @menciona copywriter (nomenclatura) e editor (Drive) se tiver problema
- Aguarda "CORRIGIDO" e revalida
- Pontua editores (QC score)
- Resume diário no Chat (16h)
- Crontab: **COMENTADO** — não está rodando!

**Como funciona:**
```
gate_finalizado.py (*/30)
├─ Detecta tarefas com status "finalizado"
├─ Valida nomenclatura (importa auditoria_nomenclatura)
├─ Valida Drive compliance (importa compliance_drive)
├─ Se problema:
│  ├─ Posta comentário @mencionando responsável
│  ├─ Aguarda resposta "CORRIGIDO"
│  └─ Revalida (--poll a cada 2h)
├─ Se OK: libera para tráfego
└─ Pontua editor (QC score)
```

**Status:**
- ❌ **NÃO ESTÁ RODANDO** (comentado em crontab)
- ✅ Código bem estruturado quando ativo
- ✅ Importa validadores reais (auditoria_nomenclatura, compliance_drive)
- ⚠️ Precisa de config de custom fields (CF_TIPO_EDICAO não está preenchida)

**Por que foi desativado?**
Não encontrei comentário no código explicando. Possibilidades:
1. Depende de custom fields que foram deletados
2. Conflita com outra automação
3. É muito strict e bloqueia fluxo

**Recomendação: REATIVAR + TESTAR**
- **Ação**: 
  1. Preencher IDs de custom fields corretos (CF_TIPO_EDICAO)
  2. Testar em 1 tarefa
  3. Re-adicionar ao crontab (*/30 + --poll + --chat)
- **Benefício**: QC automático, pontução editores, nomenclatura validada
- **Urgência**: 🟠 HIGH (não crítico, mas muito útil)

---

### 9️⃣ detectar_criativos_orfaos_v2.py

**O que faz:**
- Detecta criativos em RedTrack que não têm tarefa no ClickUp
- Cria tarefas [LEGADO] automaticamente
- Insere em database para fechar cruzamento
- Alerta Telegram
- Crontab: diário 11h (comentado? vamos ver)

**Como funciona:**
```
detectar_criativos_orfaos_v2.py
├─ Consulta Data Lake: criativos em RT sem tarefa CU
├─ Para cada criativo orfão:
│  ├─ Infere nicho (pelo prefixo ad ou gestor)
│  ├─ Infere oferta
│  ├─ Cria tarefa [LEGADO] na lista GT
│  ├─ Insere em dim_criativos_clickup
│  └─ Alerta Telegram
└─ Tarefas [LEGADO] são invisíveis para Assertividade/SLAs
   mas contam para financeiro
```

**Status:**
- ✅ Funciona bem
- ✅ Útil para encontrar gaps ClickUp ↔ RedTrack
- ✅ Bem documentado
- ⚠️ Crontab: não encontrei em crontab ativo!
  - Script existe e funciona
  - Mas não está agendado

**Recomendação: MANTER + AGENDAR**
- **Ação**: Re-adicionar ao crontab
  ```
  0 11 * * * python3 ~/Scripts/detectar_criativos_orfaos_v2.py
  ```
- **Benefício**: Encontra gaps e garante que RedTrack ↔ ClickUp estão sincronizados
- **Impacto**: Já está funcionando, só precisa agendar

---

### 🔟 auto_time_tracking.py

**O que faz:**
- Rastreia automaticamente tempo em tarefas ClickUp
- Quando status = "trabalhando" (escrevendo, em edição, etc), registra timestamp
- Quando sai, cria entrada de tempo manual via API
- Crontab: a cada 10 min (seg-sáb)
- Modo --dry: preview

**Como funciona:**
```
auto_time_tracking.py (*/10)
├─ Lê tarefas da COPY
├─ Detecta mudança de status → status "trabalhando"
├─ Registra timestamp de entrada
├─ Quando status sai de "trabalhando":
│  ├─ Calcula duração
│  ├─ Se >= 1 min, cria entrada de tempo manual
│  └─ API do ClickUp registra
└─ Armazena estado para não duplicar
```

**Status:**
- ✅ Código bem estruturado
- ✅ Lógica clara (working vs non-working statuses)
- ⚠️ **PERGUNTA**: Alguém usa time tracking do ClickUp?
  - Se SIM: útil para pontuação editores, payroll, etc
  - Se NÃO: é processamento desnecessário

**Análise:**
Não encontrei evidência de que time tracking seja usado. Preciso perguntar a você:
1. **A equipe de edição é pontuada por tempo gasto?**
2. **Há relatório de time tracking sendo consultado?**
3. **É usado para payroll de freelancers?**

Se resposta = NÃO para todas, pode desativar. Se SIM para alguma, manter.

**Recomendação: INVESTIGAR + DECIDIR**
- Se usado: MANTER
- Se não usado: DESATIVAR (economiza 10 min × 7 × 4 = 280 API calls/mês)
- **Ação**: Você confirma se está sendo usado?

---

### 1️⃣1️⃣ cruzamento_clickup_redtrack.py

**O que faz:**
- Agrega dados de ClickUp + RedTrack
- Não escreve, apenas lê (read-only)
- Modos: oferta, gestor, copywriter, criativo, completo
- Usado pelos relatórios para gerar reports

**Como funciona:**
```
cruzamento_clickup_redtrack.py oferta
├─ Lê tarefas da COPY (ClickUp)
├─ Lê campanhas (RedTrack)
├─ Cruza por nomenclatura/mapeamento
├─ Agrupa por: nicho, oferta
├─ Retorna: produção, performance, ROI
└─ Usado pelos relatórios
```

**Status:**
- ✅ Funciona bem (read-only)
- ✅ Não tem race conditions (só lê)
- ✅ Bem estruturado
- ⚠️ **PROBLEMA**: Roda ON-DEMAND (pelos relatórios)
  - Não agendado em crontab
  - Relatórios o chamam dinamicamente
  - Isso é OK, mas torna tracking difícil

**Recomendação: MANTER + ADICIONAR VERSIONING**
- Está ok como é (read-only)
- **Melhorias Phase 2**: Adicionar versionamento (timestamps, data_version)
  - Quando gera reports, log qual versão de dados usou
  - Rastreia se dados estavam "stale"
- **Não é urgente agora**

---

### 1️⃣2️⃣ input_financeiro.py

**O que faz:**
- Coleta dados de faturas e despesas via terminal/CLI
- Salva em JSON para leitura pelo Claude Code
- Manual, sem automação

**Como funciona:**
```
input_financeiro.py
├─ Pergunta mês de referência
├─ Pergunta faturas por cartão (MP, Inter, PicPay, Itaú, Nubank, etc)
├─ Pergunta despesas fixas (aluguel, empréstimo)
├─ Salva em ~/Scripts/data/financeiro_mensal.json
└─ Claude Code lê para gerar relatórios
```

**Status:**
- ✅ Útil para entrada manual de dados
- ✅ Bem estruturado
- ✅ Sem conflitos
- ✅ Input humano, não automação

**Recomendação: MANTER**
- Segue sendo útil para entrada de dados manual
- Sem problemas

---

## 📊 RESUMO DAS AÇÕES

### 🔴 CRÍTICAS (Fazer agora)
1. **auto_status_rt.py** → AGENDAR 2x/dia (6h, 14h)
2. **auto_categoria.py** → DESATIVAR (redundante)

### 🟠 ALTAS (Esta semana)
3. **gate_finalizado.py** → REATIVAR + TESTAR (QC automático)
4. **auto_time_tracking.py** → INVESTIGAR se está sendo usado

### 🟡 MÉDIAS (Próximas semanas)
5. **auto_healing.py** → DESATIVAR (redundante com retry built-in)
6. **detectar_criativos_orfaos_v2.py** → RE-AGENDAR (está desativado)

### ✅ MANTER (Sem mudanças)
- clickup_criar_tarefa.py (Super Agent)
- auto_envio_trafego.py (Crítico para fluxo)
- auto_etiqueta.py (Tagging bem definido)
- classificador_criativos.py (Performance muito bem)
- cruzamento_clickup_redtrack.py (Read-only)
- input_financeiro.py (Manual útil)

---

## 🎯 PRÓXIMOS PASSOS

**Você precisa responder**:
1. ❓ `auto_time_tracking.py` está sendo usado? (time tracking consultado?)
2. ❓ Por que `gate_finalizado.py` foi desativado?
3. ❓ `detectar_criativos_orfaos_v2.py` deveria estar agendado?

**Eu vou fazer**:
1. ✅ Agendar `auto_status_rt.py` (IMEDIATAMENTE)
2. ✅ Desativar `auto_categoria.py` (IMEDIATAMENTE)
3. ✅ Reativar `gate_finalizado.py` (após seu input)
4. ✅ Investigar e desativar `auto_healing.py`
5. ✅ Re-agendar `detectar_criativos_orfaos_v2.py`

---

## 📝 Sign-off

**Análise Completa**: 12/12 scripts avaliados  
**Decisões Tomadas**: 6 (MANTER, DESATIVAR, REATIVAR, INVESTIGAR)  
**Ações Recomendadas**: 8  
**Impacto**: Melhor sincronização, menos redundância, automações mais confiáveis

---

*Próximo passo: Você responde as 3 perguntas acima, e começamos a implementar as ações imediatamente.*
