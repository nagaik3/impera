# 📋 SOLICITAÇÃO SEMANAL DE CRIATIVOS — GUIA OPERACIONAL

**Status:** ✅ Ativo  
**Última Atualização:** 2026-05-25

---

## 🎯 O Que Você Faz Aqui?

Toda semana (segunda-feira, 10:00):
1. Coleta dados da semana anterior
2. Calcula capacidade de produção (Regra 15%)
3. Analisa performance do TOP 10
4. Identifica gargalos em edição
5. **Gera solicitação fundamentada de criativos**

---

## 📊 Relatórios Disponíveis

### **1. Relatório de Solicitação de Criativos** (NOVO)
**Arquivo:** `relatorio_solicitacao_criativos_semanal.py`  
**Frequência:** Semanal (segunda-feira)  
**Saída:** 
- Console: Relatório markdown formatado
- Arquivo: `~/Scripts/data/solicitacao_criativos_YYYY-MM-DD.json`

**Uso:**
```bash
python3 ~/Scripts/relatorio_solicitacao_criativos_semanal.py
```

**Resultado:**
```
📊 RELATÓRIO DE SOLICITAÇÃO DE CRIATIVOS — SEMANA 25/05

1️⃣ ANÁLISE DE INVESTIMENTO E CAPACIDADE
   Investimento: R$851.019
   Capacidade (15%): R$127.653 = 851 criativos

2️⃣ PERFORMANCE DO TOP 10
   Faturamento: R$1.460.790
   TOP 10: R$1.050.223 (71.9%)
   V1: 72.5% | V2+: 27.5%

3️⃣ ANÁLISE DE BACKLOG
   Edição: 134 tarefas em pipeline
   [EM]: 48 (alto) | [MM]: 27 (médio) | [NE]: 23 (alto) | [VS]: 1 (livre)

4️⃣ SOLICITAÇÃO POR NICHO
   [MM]: 360 criativos (170 VAR + 75 NOVO + 25 IMG + 20 RIP)
   [EM]: 80 criativos (80 VAR de winners)
   [NE]: 70 criativos (70 VAR de winners)
   [VS]: 35 criativos (35 VAR de C15)

5️⃣ RESUMO EXECUTIVO
   Total: 545 criativos (70% vars, 30% novos)
```

---

## 🔧 Fluxo de Uso

### **Segunda-feira 10:00 — Gerar Relatório**
```bash
cd ~/Scripts
python3 relatorio_solicitacao_criativos_semanal.py > relatorio_$(date +%Y-%m-%d).txt
```

### **Resultado: Arquivo com solicitação estruturada**
```
Periodo: 2026-05-18 a 2026-05-24
Investimento: R$851.019
Capacidade: 851 criativos
...
[Solicitação por nicho]
```

### **Enviar ao Líder de Copy**
- Copiar solicitação dos nichos
- Mencionar fundamento (TOP 10 + backlog)
- Estimativa de lead time por tipo

### **Enviar ao Líder de Tráfego**
- Compartilhar alocação completa
- Destacar prioridades (MM > EM/NE > VS)
- Explicar restrição de backlog

---

## 📈 Entender a Solicitação

### **Porque [MM] recebe 360 criativos?**
- ✅ Backlog baixo (27 vs 48/23)
- ✅ Domina TOP 10 (60% dos melhores ADs)
- ✅ Permite volume máximo

### **Porque [EM]/[NE] recebem ZERO novos?**
- ✅ Backlog pesado (48 e 23 respectivamente)
- ✅ Há winners no TOP 10 (AD644, AD123, AD81, AD14)
- ✅ Estratégia: variações de winners em vez de descoberta

### **Porque [VS] recebe apenas variações?**
- ✅ Backlog mínimo (1 tarefa)
- ✅ Espaço máximo disponível
- ✅ C15 já está em TOP 10, vale expandir

---

## 📚 Documentação Técnica Completa

Leia: **`METODOLOGIA_SOLICITACAO_CRIATIVOS.md`**

Contém:
- Explicação de cada etapa do cálculo
- Fórmulas exatas
- Tabelas de decisão
- Considerações técnicas

---

## 🔄 Automação (Opcional)

Para agendar automaticamente toda segunda-feira às 10:00:

```bash
# Editar crontab
crontab -e

# Adicionar linha:
0 10 * * 1 cd ~/Scripts && python3 relatorio_solicitacao_criativos_semanal.py >> ~/Scripts/logs/solicitacao_criativos.log 2>&1
```

**Log:** `~/Scripts/logs/solicitacao_criativos.log`

---

## 📞 Dúvidas Frequentes

**P: Como o script escolhe entre novo vs variação?**  
R: Compara TOP 10 performance (72.5% é V1) com backlog atual. Se backlog pesado, prioriza variações de winners.

**P: Posso modificar a proporção 70/30?**  
R: Sim, editando `VAR_PCT` em `relatorio_solicitacao_criativos_semanal.py`. Mas fundamental respeita TOP 10 (que é 72.5/27.5).

**P: E se o investimento cair drasticamente?**  
R: Capacidade cai proporcionalmente (regra 15%). Script recalcula automaticamente.

**P: Quando revisar essa metodologia?**  
R: Mensalmente. Se TOP 10 performance mudar (ex: V1 cair para <65%), ajustar proporção.

---

## 🎓 Detalhes Técnicos Preservados

### **Camada 1: Extração de Dados**
```python
# Investimento real
campaigns = fetch_redtrack_with_copywriter(date_from, date_to)
total_custo = sum(c.get("cost") for c in campaigns)
total_faturamento = sum(c.get("revenuetype2") + c.get("revenuetype3") for c in campaigns)
```

### **Camada 2: Cálculo de Capacidade**
```python
# Regra PlayBook 15%
capacidade = investimento * 0.15
qtd_criativos = int(capacidade / 150)  # R$150 por criativo
```

### **Camada 3: Análise de Performance**
```python
# TOP 10 breakdown
top10_pct = (top10_fat / total_fat) * 100  # 71.9%
v1_pct = sum(v1_ads) / top10_fat * 100  # 72.5%
v2plus_pct = sum(v2plus_ads) / top10_fat * 100  # 27.5%
```

### **Camada 4: Avaliação de Restrições**
```python
# Backlog por nicho
for task in trafego_tasks:
    if "aguardando teste" in status:
        nicho_counts[nicho] += 1
    if "[V1]" in name:
        novo_count += 1
```

### **Camada 5: Alocação Inteligente**
```python
# Decisão por nicho
if nicho_backlog[nicho]["total"] > 40:
    # Backlog pesado → só variações
    alocacao[nicho] = {"vars": X, "novos": 0}
else:
    # Backlog leve → volume máximo
    alocacao[nicho] = {"vars": Y, "novos": Z}
```

---

## ✅ Checklist Semanal

- [ ] Segunda 10:00 — Executar `relatorio_solicitacao_criativos_semanal.py`
- [ ] Revisar solicitação gerada
- [ ] Copiar para documento compartilhado
- [ ] Enviar ao Líder de Copy
- [ ] Enviar ao Líder de Tráfego
- [ ] Documentar feedback (se houver)
- [ ] Arquivo salvo: `~/Scripts/data/solicitacao_criativos_YYYY-MM-DD.json`

---

**Dúvidas? Consulte `METODOLOGIA_SOLICITACAO_CRIATIVOS.md`**

