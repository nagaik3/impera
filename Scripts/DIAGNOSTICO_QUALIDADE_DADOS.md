# 🔍 Diagnóstico de Qualidade de Dados — IMPERA
**Data**: 2026-05-24  
**Score Geral**: 73% ⚠️ ATENÇÃO  
**Status**: Funcional mas com riscos críticos

---

## 📊 Resumo Executivo

| Setor | Score | Status | Impacto |
|-------|-------|--------|---------|
| **Copy** | 99% | ✅ Muito Bom | Dados seguros para uso |
| **Edição** | 100% | ✅ Excelente | Dados válidos |
| **RedTrack** | 91% | ✅ Bom | Parseamento confiável |
| **Cruzamento** | 2% | ❌ CRÍTICO | **COMPROMETE RELATÓRIOS** |

---

## 🎯 Detalhes por Setor

### 1️⃣ Copy (ClickUp) — 99% ✅
```
Total de tarefas: 520

✅ COM COPYWRITER: 487/520 (93.7%)
   └─ Todos os copywriters esperados presentes
   └─ REAPER (=CASSIO) identificado corretamente
   
⚠️ SEM START_DATE: 118/520 (22.7%)
   └─ Afeta cálculo de períodos em relatórios
   └─ Impacto: Relatório semanal pode perder ~23% das tarefas

✅ NOMENCLATURA VÁLIDA: 430/520 (82.7%)
   └─ 90 tarefas com nomenclatura inválida (tasks em progresso)
   └─ Baixo impacto: tarefas auxiliares
```

**Recomendações**:
- ⚠️ Implementar validação automática de `start_date` ao criar tarefas
- ✓ Sistema de nomenclatura está funcionando bem

---

### 2️⃣ Edição (GESTÃO DE TRÁFEGO) — 100% ✅
```
Total de tarefas: 1406

✅ COM EDITOR: 850/1406 (60.5%)
   └─ 11 editores identificados (incluindo subcontratados)
   
❌ SEM PARENT_TASK_ID: 1371/1406 (97.5%)
   └─ CRÍTICO: Quebra o matching com Copy
   └─ Sistema de parent_task não está sendo populado
```

**Recomendações**:
- 🚨 **CRÍTICO**: Implementar população automática de `parent_task_id` quando trafego task é criada
- Ou usar webhook para sincronizar quando tarefa é movida para "aguardando teste"
- Validar entrada de dados na interface (forçar preenchimento)

---

### 3️⃣ RedTrack (Integração API) — 91% ✅
```
Período auditado: 2026-05-17 a 2026-05-24
Total de campanhas: 65

✅ CAMPANHAS PARSEADAS: 59/65 (90.8%)
   └─ Nicho detectado: 9 tipos (DA, DB, ED, EM, MM, NE, PT, VS, ZB)
   
❌ SEM NICHO: 6 campanhas (9.2%)
   └─ Campanhas com nome inválido ou não-padrão
   
⚠️ SEM OFERTA: 5 campanhas (7.7%)
   └─ Parseamento parcial, mas recuperável
   
❌ GESTORES: 0 detectados
   └─ Campo gestor não está siendo parseado das campanhas
   └─ Impacto: Relatório Redtrack perde análise por gestor
```

**Problemas Encontrados**:
1. Padrão de nomenclatura de campanhas inconsistente
2. Campo gestor não está presente ou em formato inválido

**Recomendações**:
- 🔧 Padronizar nomenclatura de campanhas no RedTrack
- 🔧 Adicionar campo/prefixo de gestor nas campanhas
- ✓ Parseamento está 90%+ eficiente (bom!)

---

### 4️⃣ Cruzamento Copy ↔ Tráfego — 2% ❌ **CRÍTICO**
```
Copy tasks: 520
Tráfego tasks: 1406

❌ MATCHING SUCESSO: 35/1406 (2.5%)
   └─ Apenas 35 tarefas têm parent_task_id válido
   
🚨 TAREFAS ÓRFÃS: 1371/1406 (97.5%)
   └─ Sem conexão com tarefa original de Copy
   └─ Sistema relying em fallback (matching por nome)
```

**Impacto nos Relatórios**:
- ❌ **Relatório Mensal Copywriters**: Matching por nome tem ~70% accuracy
- ❌ **Gate Finalizado**: Não consegue atribuir crédito correto
- ⚠️ **Análise de Performance**: Desacoplada de produção original

**O que está acontecendo**:
Quando uma tarefa é criada em "COPY", ela deveria gerar um parent_task_id que é propagado para tarefas em "TRAFEGO". Isso **não está acontecendo**.

**Solução**:
1. Implementar webhook que popula parent_task_id quando trafego task é criada
2. Ou usar expansão de ranges automática (já existe em `expandir_range_tasks.py`)
3. Validar se `CU_FIELD_PARENT_TASK_ID` está configurado corretamente

---

## 🚨 Problemas Críticos Identificados

### #1: Parent Task ID não populado (97.5% afetadas)
**Severidade**: 🔴 CRÍTICO  
**Afeta**: Relatório Mensal, Gate Finalizado, Análise completa  
**Causa**: Sistema de webhook/range expansion não está ativo

**Ação Imediata**:
```bash
# Verificar se campo existe
echo $CU_FIELD_PARENT_TASK_ID

# Testar webhook
python3 ~/Scripts/expandir_range_tasks.py --test

# Verificar estado
grep -i parent_task_id ~/.zshrc
```

---

### #2: Start Date faltando (22.7% das Copy tasks)
**Severidade**: 🟠 MÉDIO  
**Afeta**: Relatório Semanal (perde ~23% das tarefas)  
**Causa**: Criação manual de tarefas sem preencher data

**Ação**: Implementar validação/obrigatoriedade no ClickUp

---

### #3: Editores não 100% preenchidos (39.5%)
**Severidade**: 🟠 MÉDIO  
**Afeta**: Relatório de Edição, Pontuação  
**Causa**: Tarefas com editor "Freelancer", "Candidato", etc

**Ação**: Standardizar lista de editores no ClickUp

---

### #4: Gestores não parseados do RedTrack (0)
**Severidade**: 🟠 MÉDIO  
**Afeta**: Breakdown por gestor nos relatórios  
**Causa**: Nomenclatura de campanha inconsistente

**Ação**: Adicionar prefixo de gestor às campanhas no RedTrack

---

## 📈 Confiabilidade dos Relatórios (Com dados atuais)

| Relatório | Confiabilidade | Motivo |
|-----------|----------------|--------|
| **Semanal** | 77% | 23% das tarefas sem start_date |
| **Redtrack** | 91% | 9% campanhas sem nicho, 0% gestores |
| **Mensal CW** | 70% | Matching por nome tem ~70% accuracy |
| **Performance** | 91% | RedTrack parseamento bom |

**Conclusão**: Relatórios funcionais mas com **gaps de dados que podem mascarar realidade**

---

## ✅ Ações Recomendadas (Prioridade)

### 🔴 P1 - IMEDIATO (hoje)
1. Validar se `expandir_range_tasks.py` webhook está ativo
   ```bash
   ps aux | grep expandir_range_tasks
   ```
2. Se não ativo, iniciar:
   ```bash
   python3 ~/Scripts/expandir_range_tasks.py --server &
   ```
3. Testar criação de range para validar parent_task_id population

### 🟠 P2 - CURTO PRAZO (até fim de semana)
1. Implementar obrigatoriedade de `start_date` no ClickUp
2. Standardizar lista de editores (remover "Freelancer", etc)
3. Validar e corrigir 6 campanhas sem nicho no RedTrack

### 🟡 P3 - MÉDIO PRAZO (próxima semana)
1. Adicionar prefixo de gestor nas campanhas RedTrack
2. Implementar validação automática de nomenclatura
3. Dashboard de qualidade de dados (weekly)

---

## 🎯 Métricas Atuais vs Metas

| Métrica | Atual | Meta | Gap |
|---------|-------|------|-----|
| Parent Task Population | 2.5% | 95% | -92.5% 🔴 |
| Start Date Coverage | 77.3% | 100% | -22.7% 🟠 |
| Editor Assignment | 60.5% | 100% | -39.5% 🟠 |
| RedTrack Parseamento | 90.8% | 95% | -4.2% 🟡 |
| **Score Geral** | **73%** | **90%** | **-17%** 🟠 |

---

## 📋 Próximos Passos

**Antes de confiar nos relatórios para decisões críticas**:
1. ✓ Fixar parent_task_id population (webhook/range)
2. ✓ Validar que start_date está sendo preenchido
3. ✓ Standardizar editores no ClickUp
4. ✓ Re-rodar auditoria para validar melhoria

**Comando para re-auditar**:
```bash
python3 ~/Scripts/auditoria_dados_completa.py
```

---

**Relatório Gerado**: 2026-05-24 16:02:32  
**Próxima Auditoria Recomendada**: 2026-05-31 (após fixes)
