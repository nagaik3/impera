# 📋 ESPECIFICAÇÕES FINAIS - Relatórios Setorizados

**Data**: 2026-05-24  
**Status**: ✅ TODAS AS DÚVIDAS ESCLARECIDAS  
**Tipo**: Relatórios Consultivos (Iago consulta lideranças para validação)

---

## 🎯 ESTRUTURA GERAL: 4 RELATÓRIOS SEPARADOS

Cada relatório é um POST no mesmo Chat View, com dados AUTO + campos MANUAIS para consulta com heads.

```
Chat View: 8cm1w4b-9993 (GPDR Semanal)
├─ Post 1: 📊 GPDR — Visão Executiva (AUTO + MANUAL narrativa)
├─ Post 2: 👨‍💻 COPY — Relatório Semanal (AUTO)
├─ Post 3: 🎬 EDIÇÃO — Relatório Semanal (AUTO)
└─ Post 4: 📈 TRÁFEGO — Relatório Semanal (AUTO)
```

---

## 👨‍💻 1. COPY — RELATÓRIO SEMANAL

**Responsável do Setor**: Elias  
**Período**: 2026-05-18 a 2026-05-24

### KPIs Críticos

| Métrica | Definição | Status |
|---------|-----------|--------|
| **Volume Total** | Criativos criados na semana (data_created 18-24) | ✅ Tenho |
| **Faturamento** | Atribuído ao copywriter via cruzamento RT | ✅ Tenho |
| **Novo vs Variação** | Breakdown por nomenclatura + tags | ✅ Tenho lógica |
| **Assertividade Copy** | % criativos que "acertaram" (saíram de "em teste" → "pré-validado"/"validado"/"escala") | ⚠️ Precisa pesquisar Obsidian |
| **Criativos Enviados a Tráfego** | Completaram ciclo (status "enviado tráfego" + date_created 18-24) | ✅ Tenho |
| **Criativos Produzidos** | Em andamento (backlog, escrevendo, pré-produção, edição, alteração) | ✅ Tenho |

### Seções

**1. KPIs Críticos (Tabela)**
- Volume Total | Novo | Variação | Faturamento | Assertividade Copy | Enviado a Tráfego

**2. Ranking Individual (Tabela)**
- Por VOLUME DE PRODUÇÃO (não faturamento)
- Top copywriters que entregaram mais

**3. SLA Individual (Tabela)**
- Tudo em atividade: backlog copy, escrevendo, em edição, enviado tráfego
- Média em dias

**4. Top 10 ADs (Tabela)** ⭐ EXPANDIR DE TOP 5
- Sugestões para variação
- ⚠️ DEVE SER CRIATIVO INDIVIDUAL (não campanha)
- Se não conseguir extrair criativo individual, Iago passa estruturação

**5. Comparativo Semana Anterior (Tabela)**
- Faturamento Copy (semana anterior vs atual)
- ⚠️ Incluir APENAS criativos de produção Copy:
  - Ripagem direta (ex: Douglas) = NÃO entra
  - Ripagem como variação feita por Copy = ENTRA

**6. Campos Manuais (Para Consulta com Elias)**
- Análise semanal: O que funcionou? Gargalos? Necessidades?

---

## 🎬 2. EDIÇÃO — RELATÓRIO SEMANAL

**Responsável do Setor**: Muryllo  
**Período**: 2026-05-18 a 2026-05-24

### KPIs Críticos

| Métrica | Definição | Status |
|---------|-----------|--------|
| **Criativos Enviados a Tráfego** | Completaram ciclo (status "enviado tráfego" ou "enviado VTURB") | ✅ Tenho |
| **Criativos em Produção** | Em andamento (pré-produção, em edição, em alteração) | ✅ Tenho |
| **Assertividade Geral** | % sem "teve alteração" = (sem_alteracao / total * 100) | ✅ Tenho |
| **No Prazo vs Atrasadas** | Comparar due_date (18-24 maio) vs status de conclusão | ⚠️ Precisa implementar |

### Seções

**1. Identificação da Semana**
- Período: 18-24 maio
- Responsável: Muryllo
- Objetivo do mês
- Contexto
- Principal gargalo [MANUAL]

**2. KPIs Críticos (Tabela)**
- Criativos Enviados a Tráfego | Processados | Assertividade % | No Prazo | Atrasadas

**3. Produção por Editor (Tabela)** ⭐ VISUAL MELHORADO
```
| Editor | Total | Novos | Otim. | Leads | MLD | VSL | No Prazo | Atrasadas | % Assert. |
```
- Nicolas, Pablo (⚠️ estavam faltando)
- Breakdown por tipo de criativo

**4. Produtividade Individual**
- Maior volume
- Maior assertividade  
- Maior atraso (se houver)

**5. Detalhamento de Atrasos** ⚠️ NOVO
- Se houver tarefas com due_date 18-24 não concluídas:
  - Lista com descrição
  - Onde estão (qual status)
  - Por quê estão atrasadas

**6. Campos Manuais (Para Consulta com Muryllo)**
- Leitura estratégica: O que funcionou? O que limitou? Atenção imediata?

---

## 📈 3. TRÁFEGO — RELATÓRIO SEMANAL

**Responsável do Setor**: Douglas  
**Período**: 2026-05-18 a 2026-05-24

### KPIs Críticos

| Métrica | Definição | Status |
|---------|-----------|--------|
| **Faturamento Front** | Período 18-24 + Comparativo semana anterior | ✅ Tenho |
| **ROAS Meta** | 1.58 (não usar "ROAS médio") | ✅ Tenho |
| **Volume Vendas** | Total de conversões | ✅ Tenho |
| **Criativos em Teste** | Status "em teste" ou "aguardando teste" | ✅ Tenho |
| **Ofertas em Escala** | Campanhas com investimento alto + ROAS ≥ 1.58 | ⚠️ Precisa definir métrica com Douglas |
| **Status Nichos** | Quais estão ativos (com movimentação 18-24) | ⚠️ Precisa extrair |

### Seções

**1. Identificação da Semana**
- Período: 18-24 maio
- Responsável: Douglas
- Meta ROAS: 1.58

**2. KPIs Críticos (Tabela)**
- Faturamento Front (Atual | Anterior | Delta) | ROAS | Vendas | Criativos em Teste

**3. Performance por Gestor (Tabela)**
- Gestor | Faturamento Front | ROAS | Campanhas | Vendas | TOP 3 Campanhas ⭐ (não TOP 1)

**4. Ofertas em Escala** ⚠️ CONSULTAR COM DOUGLAS
- [ ] Qual é a métrica exata? (investimento mínimo? dias mínimos?)
- Listar ofertas em escala com: faturamento, ROAS, volume

**5. Status de Nichos** ⭐ NOVO — MUITO IMPORTANTE
- Top 5 nichos por faturamento
- Por cada nicho:
  - Campanhas | Faturamento | ROAS Front
- ⚠️ DIFERENÇA BRASIL vs ESTADOS UNIDOS (ex: EDBR pausado, ED USA rodando)
- Usar o que ESTÁ RODANDO (não assumir "congelado" = não roda)

**6. Recomendação de Variação**
- ✅ Não pontuar (já vem do relatório COPY)

**7. Campos Manuais (Para Consulta com Douglas)**
- Análise de ofertas em escala
- Gargalos identificados

---

## 📊 4. GPDR — VISÃO EXECUTIVA

**Responsável**: Iago (GPDR)  
**Período**: 2026-05-18 a 2026-05-24

### Estrutura

**1. Score de Saúde por Departamento (AUTO)**
- Copy: ●●●●● (calculado automaticamente)
- Edição: ●●●●● (calculado automaticamente)
- Tráfego: ●●●●○ (calculado automaticamente)
- ⚠️ Sem margem para erro humano (rígido)

**2. Alertas Críticos (AUTO)**
- ROAS < 1.58
- Assertividade < X%
- SLA > X dias
- Atrasadas > X%

**3. KPIs Consolidados (AUTO + Tabela)**
| Setor | Métrica | Valor | Status |

**4. Comparativo Semana Anterior (AUTO)**
- Faturamento Front
- Volume Copy
- Assertividade Edição

**5. Análise Semanal (MANUAL - Iago)**
- O que funcionou bem?
- Principais gargalos?
- Ações para curto-médio prazo?

**6. Necessidades do CEO/Heads (MANUAL - Iago)**
- O que está faltando?
- Decisões necessárias?

**7. Próximas Prioridades (MANUAL - Iago)**
- Foco da próxima semana

---

## 🔄 MODELO CONSULTIVO

**Processo:**
1. Script gera relatório AUTO com todos os dados
2. Iago CONSULTA cada head:
   - "Você concorda com esses dados?"
   - "Tem pontuações manuais a fazer?"
3. Heads trazem:
   - Validação dos dados
   - Narrativa (O que funcionou/limitou/atenção)
   - Necessidades
4. Iago consolida:
   - Visão de gestor de processos
   - Visão de liderança de setor
   - Resultado final

---

## ✅ O QUE TENHO PRONTO

- ✅ Volume Copy (data_created)
- ✅ ROAS por copywriter
- ✅ Criativos enviados a tráfego (Copy)
- ✅ SLA individual
- ✅ Top ADs ranking
- ✅ Novo vs Variação (lógica por nomenclatura)
- ✅ Produção por editor
- ✅ Assertividade edição (teve alteracao)
- ✅ SLA individual Edição
- ✅ Performance por gestor (tráfego)
- ✅ Top campanhas por gestor
- ✅ Faturamento Front
- ✅ ROAS Front
- ✅ Histórico semana anterior

---

## ⚠️ O QUE PRECISA IMPLEMENTAR

**Crítico (Bloqueia implementação):**
- [ ] **Assertividade Copy**: Pesquisar Obsidian para fórmula de testes → pré-validado/validado/escala
- [ ] **No Prazo vs Atrasadas (Edição)**: Lógica para verificar due_date vs status "enviado tráfego"/"enviado VTURB"
- [ ] **Ofertas em Escala**: Conversar com Douglas para definir métrica exata
- [ ] **Top 10 ADs Criativo Individual**: Se não conseguir extrair criativo individual, pedir estruturação

**Importante (Para melhorar relatório):**
- [ ] **Status de Nichos**: Breakdown por nicho (top 5) com campanhas/faturamento/ROAS
- [ ] **Diferença Brasil vs USA**: Detectar quando nicho está em Brasil mas não em USA
- [ ] **Score de Saúde**: Fórmula automática baseada na média dos KPIs

---

## 🚀 PRÓXIMOS PASSOS

1. **Pesquisar no Obsidian**: Assertividade Copy (testes → validação)
2. **Perguntar a Iago**:
   - Ofertas em escala: qual métrica exata?
   - Top 10 ADs: consegue extrair criativo individual ou precisa estruturação?
3. **Implementar**:
   - Lógica de "no prazo vs atrasadas" com due_date
   - Status de nichos com breakdown
   - Score de saúde auto
4. **Testar**: Gerar todos os 4 relatórios e validar

---

## 📌 NOTAS IMPORTANTES

- **Relatório Consultivo**: Iago não faz automático 100%, ele CONSULTA
- **KPIs Rígidos**: Sem margem para erro humano (score auto)
- **Narrativa Manual**: O que funcionou, limitou, necessidades = head escreve
- **Responsáveis Conhecidos**:
  - Copy: Elias
  - Edição: Muryllo
  - Tráfego: Douglas
  - GPDR: Iago
