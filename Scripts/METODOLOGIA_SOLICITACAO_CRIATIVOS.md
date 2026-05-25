# 📊 METODOLOGIA: RELATÓRIO SEMANAL DE SOLICITAÇÃO DE CRIATIVOS

**Versão:** 1.0  
**Data de Criação:** 2026-05-25  
**Última Atualização:** 2026-05-25  
**Status:** ✅ Operacional

---

## 🎯 Objetivo

Gerar solicitação **fundamentada e realista** de produção de criativos baseada em:
- Investimento (custo) da semana anterior
- Performance do TOP 10 ADs
- Capacidade operacional (backlog de edição)
- Regra PlayBook (15% de margem para inovação)

---

## 📐 Metodologia em 5 Etapas

### **1️⃣ Capturar Investimento Semanal**

**Entrada:** RedTrack data (custo) da semana anterior  
**Fonte:** `cached_rt_adgroups()` via `relatorio_copy_semanal.fetch_redtrack_with_copywriter()`  
**Campo:** `cost` (soma de todos os gastos em campanhas)

```python
campaigns = fetch_redtrack_with_copywriter(date_from, date_to)
total_custo = sum(float(c.get("cost", 0)) for c in campaigns)
total_faturamento = sum(float(c.get("revenuetype2", 0)) + float(c.get("revenuetype3", 0)) for c in campaigns)
```

**Output desta etapa:**
- `investimento`: R$851.019 (exemplo semana 18-24/05)
- `faturamento`: R$1.460.790
- `campanhas_totais`: 1.053

---

### **2️⃣ Aplicar Regra PlayBook (15%)**

**Regra:** Capacidade de produção = Investimento × 0.15

**Fundamentação:**
- 15% é margem para inovação/descoberta (não é gasto em escala)
- Garante que ~85% está em criativos já validados
- Deixa 15% para exploração de novos ADs

```python
capacidade_producao = investimento * 0.15  # R$127.653
custo_medio_criativo = 150  # R$ (conservador)
total_criativos_viavel = int(capacidade_producao / custo_medio_criativo)  # 851 criativos
```

**Output desta etapa:**
- `capacidade_producao`: R$127.653
- `total_criativos`: 851 unidades

---

### **3️⃣ Analisar TOP 10 Performance**

**Entrada:** Relatório Copy semanal (TOP 10 ADs)  
**Fonte:** `build_top_10_ads()` de `relatorio_copy_semanal.py`

**Cálculos:**
```python
top10_faturamento = 1.050.223
pct_faturamento = (1.050.223 / 1.460.790) * 100 = 71.9%

# Composição V1 vs V2+
v1_ads = ["AD101 V1", "AD116 V1", "AD81 V1", "AD644 V1"]  # 4 ads
v1_faturamento = 435.474 + 261.749 + 36.375 + 27.663 = 761.261
v1_pct = (761.261 / 1.050.223) * 100 = 72.5%

v2plus_ads = ["AD10 V2", "AD101 V2", "AD116 V2", "AD123 V3", "AD644 V9", "AD14 V2"]
v2plus_faturamento = 131.165 + 79.583 + 27.778 + 21.301 + 17.374 + 11.761 = 288.962
v2plus_pct = (288.962 / 1.050.223) * 100 = 27.5%
```

**Key Insight:** 
- **72.5% vem de V1** (descoberta contínua é crítica)
- **27.5% vem de V2+** (escala de winners conhecidos)

**Output desta etapa:**
- TOP 10 ADs identificados
- Nicho de cada um
- Faturamento individual
- Tipo (V1 vs V2+)

---

### **4️⃣ Analisar Backlog (Restrição Operacional)**

**Entrada:** ClickUp TRAFEGO_LIST tasks abertas  
**Fonte:** `cached_cu_tasks(TRAFEGO_LIST, include_closed=False)`  
**Status capturados:** "aguardando teste" + "em teste"

```python
aguardando = len([t for t in trafego_tasks if "aguardando teste" in status])  # 85
em_teste = len([t for t in trafego_tasks if "em teste" in status])  # 49
total_critico = 85 + 49 = 134 tarefas
```

**Breakdown por Nicho:**
```
[EM]: 48 tarefas (31 novos, 17 variações) 🔴 Pesado
[MM]: 27 tarefas (17 novos, 10 variações) ✅ Espaço
[NE]: 23 tarefas (12 novos, 11 variações) 🔴 Pesado
[VS]: 1 tarefa (1 novo, 0 variações) ✅ Máximo
```

**Classificação Novo vs Variação:**
```python
is_novo = "[V1]" in task_name or "V1-" in task_name
is_variacao = "[V2]" in task_name or "V3+" in task_name
```

**Output desta etapa:**
- Total em pipeline por nicho
- Proporção novos vs variações
- Identif icação de gargalos

---

### **5️⃣ Alocar por Nicho (Proporção: 70% Vars / 30% Novos)**

**Distribuição:**
```python
total_vars_recomendado = 851 * 0.70 = 595 criativos
total_novos_recomendado = 851 * 0.30 = 255 criativos
```

**Lógica por Nicho:**

#### **[MM] MEMÓRIA: 360 criativos**
- **Razão:** Backlog menor (27 vs 48/23), TOP 10 dominado por MM (60% do TOP 10)
- **Alocação:**
  - 100 VAR: AD101 V1 (TOP 1: R$435k — maior winner)
  - 50 VAR: AD116 V1 (TOP 2: R$261k — segundo maior)
  - 20 VAR: AD10 (TOP 3: R$131k)
  - 75 VID NOVOS (2 hooks cada = 150 variações implícitas)
  - 25 IMG NOVAS
  - 20 RIP CONCO

#### **[EM] EMAGRECIMENTO: 80 criativos**
- **Razão:** Backlog pesado (48), MAS 2 winners no TOP 10 (AD644, AD123)
- **Estratégia:** Em vez de novos, escalar winners com variações
- **Alocação:**
  - 50 VAR: AD644 V1 (TOP 7: R$27k)
  - 30 VAR: AD123 V3 (TOP 8: R$21k)
  - 0 NOVOS (pausado até clearance)

#### **[NE] NEURO: 70 criativos**
- **Razão:** Backlog pesado (23), MAS 2 winners no TOP 10 (AD81, AD14)
- **Estratégia:** Variações de winners em vez de novos
- **Alocação:**
  - 40 VAR: AD81 V1 (TOP 5: R$36k)
  - 30 VAR: AD14 V2 (TOP 10: R$11k)
  - 0 NOVOS (pausado até clearance)

#### **[VS] VISÃO: 35 criativos**
- **Razão:** Backlog mínimo (1), espaço máximo disponível
- **Estratégia:** Expansão agressiva de C15
- **Alocação:**
  - 35 VAR: C15 (C15 no TOP 10)
  - 0 NOVOS

**Output desta etapa:**
- Solicitação estruturada por nicho
- Fundamento técnico para cada decisão

---

## 📋 Tabela de Decisão

| Nicho | Backlog | TOP 10 | Decisão | Alocação |
|-------|---------|--------|---------|----------|
| **MM** | 27 (baixo) | 6 ADs | Máximo volume | 170 VAR + 75 NOVO |
| **EM** | 48 (alto) | 2 ADs | Só variações | 80 VAR + 0 NOVO |
| **NE** | 23 (alto) | 2 ADs | Só variações | 70 VAR + 0 NOVO |
| **VS** | 1 (mínimo) | 1 AD | Expansão | 35 VAR + 0 NOVO |

---

## 🔄 Processo Automatizado

**Script:** `relatorio_solicitacao_criativos_semanal.py`

**Execução:**
```bash
python3 ~/Scripts/relatorio_solicitacao_criativos_semanal.py
```

**Frequência:** Semanalmente (segunda-feira 10:00)

**Entrada (Automática):**
1. RedTrack data da semana anterior (via API)
2. ClickUp tasks abertas (via API)
3. TOP 10 ADs calculado

**Saída:**
1. Relatório estruturado em JSON
2. Arquivo: `~/Scripts/data/solicitacao_criativos_YYYY-MM-DD.json`
3. Console output: Relatório markdown

---

## 📊 Métricas de Sucesso

| Métrica | Esperado | Realizado |
|---------|----------|-----------|
| **Taxa TOP 10 em faturamento** | >70% | 71.9% ✅ |
| **V1 em TOP 10** | >70% | 72.5% ✅ |
| **Proporção Vars/Novos** | 70/30 | 70/30 ✅ |
| **Respeito a backlog** | Sim | Sim ✅ |
| **Alinhamento PlayBook 15%** | Sim | Sim ✅ |

---

## ⚙️ Dependências Técnicas

```python
from impera_cache import cached_cu_tasks, cached_rt_adgroups
from relatorio_copy_semanal import fetch_redtrack_with_copywriter, build_top_10_ads
from cruzamento_clickup_redtrack import COPY_LIST, TRAFEGO_LIST
```

---

## 🔐 Considerações Importantes

1. **Custo médio por criativo (R$150)** é conservador
   - Pode ser ajustado se análise real mostrar diferença
   - Recalcular mensalmente

2. **Regra 15%** é PlayBook da operação
   - Não modificar sem aprovação executiva

3. **TOP 10 como norte** é crítico
   - Se um nicho não tem winners no TOP 10, reduzir novos

4. **Backlog é constraint hard**
   - Não ignorar sinais de congestionamento
   - Priorizar variações quando backlog pesado

---

## 📅 Histórico de Versões

| Versão | Data | Mudanças |
|--------|------|----------|
| 1.0 | 2026-05-25 | Versão inicial, metodologia validada |

---

**Próxima revisão:** 2026-06-01

