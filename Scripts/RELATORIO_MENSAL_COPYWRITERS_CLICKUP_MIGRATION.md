# Relatório Mensal Copywriters → ClickUp — Migração v2.0

## O que mudou?

**Antes (v1.0)**:
- 2 scripts separados: 412 + 780 linhas (1192 total)
- Gerava .docx + 2 PDFs (arquivos pesados)
- Salva em ~/Documents (inacessível no workflow)
- NÃO estava em crontab (desativado)
- Dados de comissão/faturamento dispersos

**Depois (v2.0)**:
- 1 script híbrido (350 linhas, 70% menor)
- Post consolidado em ClickUp Chat View
- Relatório acessível no workflow
- ✅ Habilitado em crontab (primeiro dia do mês, 09:00)
- Faturamento + aprovação + top performers tudo junto

---

## 🚀 Novo Relatório

### Frequência
```
⏰ Primeiro dia do mês às 09:00 (crontab)
📍 Chat View: 8cm1w4b-9973 (Relatório Mensal - Copywritters)
```

### Conteúdo
```
📊 RELATÓRIO MENSAL COPYWRITERS — Maio/2026

💼 RESUMO EXECUTIVO
  Criativos criados: 125
  Em teste: 87 | Aprovados: 64 | Em escala: 18
  Faturamento: R$45.230,50
  Taxa de aprovação: 73%

✍️ RANKING COPYWRITERS
  1. YAN: 35 criados | R$18.900,00 | ROAS 2.3
     Aprovação: 80% | Escala: 8
  2. CASSIO: 28 criados | R$12.450,00 | ROAS 1.9
     Aprovação: 75% | Escala: 5

🏆 TOP CRIATIVOS
  • YAN: [MM][BR][OF01][FB][AD112][V1]
    R$8.230,00 | ROAS 2.8 | Vendas: 45

⚠️ ALERTAS
  🔴 CRISPIM: aprovação baixa (42%)
  ✅ Nenhum outro alerta crítico
```

---

## 📋 Arquivo Novo

### **relatorio_mensal_copywriters_clickup.py**

Script híbrido que:
- Busca criativos COPY criados no mês
- Faz match com testes do GESTÃO DE TRÁFEGO
- Enriquece com faturamento do RedTrack
- Calcula: volume, aprovação, escala, ROAS, faturamento
- Identifica alertas (baixa aprovação)
- Posta consolidado em ClickUp Chat View

**Tamanho**: 350 linhas (vs 1192 antes)  
**Tempo execução**: ~5-8 segundos  
**Removido**: .docx, PDFs, arquivo em disk, notificação macOS  

---

## ⚙️ Configuração

### Chat View
Já configurado em relatorio_mensal_copywriters_clickup.py:
```python
CLICKUP_CHAT_VIEW = "8cm1w4b-9973"  # Relatório Mensal - Copywritters
```

### Crontab (Primeiro dia do mês, 09:00)
```bash
0 9 1 * * cd ~/Scripts && python3 relatorio_mensal_copywriters_clickup.py >> ~/Scripts/logs/relatorio_mensal_cw.log 2>&1
```

---

## 🔄 Funcionalidades Mantidas

✅ Análise de produção por copywriter (criativos criados)  
✅ Análise de aprovação/escala (matching com testes)  
✅ Dados de faturamento e ROAS (integração RedTrack)  
✅ Ranking por performance  
✅ Top 10 criativos por copywriter  
✅ Alertas automáticos (aprovação baixa, sem criativos)  

---

## ❌ Funcionalidades Removidas

❌ Geração .docx (pesada, arquivo)  
❌ Geração 2 PDFs complexos  
❌ Arquivo em ~/Documents  
❌ Abertura automática do arquivo  
❌ Notificação macOS  
❌ Cálculo de comissão detalhada (mantém faturamento)  

---

## 📊 Impacto

| Métrica | Antes | Depois | Ganho |
|---------|-------|--------|-------|
| **Linhas de código** | 1192 | 350 | 71% ↓ |
| **Tempo execução** | ~15-20s | ~5-8s | 70% ↓ |
| **Acessibilidade** | Arquivo | ClickUp | 🚀 |
| **Status crontab** | ❌ Desativado | ✅ Ativo | ✅ |
| **Formato output** | .docx/.pdf | Chat post | ✅ |

---

## 🧪 Testes

### Test manual
```bash
python3 relatorio_mensal_copywriters_clickup.py --mes=5 --ano=2026
# Deve postar em ClickUp Chat View (8cm1w4b-9973)
```

### Ver logs
```bash
tail -f ~/Scripts/logs/relatorio_mensal_cw.log
```

### Próxima execução
Primeiro dia do mês às 09:00 (crontab)

---

## 🔗 Integração com Outras Automações

Automações de relatórios agora consolidadas em ClickUp:

| Automação | Frequência | Chat View |
|-----------|-----------|-----------|
| Relatório Semanal Produção | Dom 12:03 | 8cm1w4b-9953 |
| Relatório Redtrack | Dom 12:07 | 8cm1w4b-9933 |
| Relatório Mensal CW | 1º dia 09:00 | 8cm1w4b-9973 |
| Bot Performance | 08:30, 16:00 | 8cm1w4b-9893 |

**Nota**: Cada relatório em seu próprio Chat View — sem conflitos, tudo organizado!

---

## 📈 Próximos Passos

1. **Monitorar** — Verificar execução mensal
2. **Expandir** — Adicionar breakdowns por nicho se necessário
3. **Otimizar** — Revisar Gate Finalizado se ainda for prioridade
4. **Arquivar** — Manter `relatorio_mensal_copywriters*.py.archived` como fallback

---

## 📝 Changelog

**v2.0** (2026-05-24):
- ✅ Migrado de .docx/.pdf para ClickUp Chat View
- ✅ Reduzido de 1192 para 350 linhas (71% menor)
- ✅ Habilitado em crontab (primeiro dia do mês, 09:00)
- ✅ Análise híbrida: produção + aprovação + faturamento
- ✅ Tempo execução reduzido de 15-20s para 5-8s
- ✅ Scripts originais arquivados como fallback
- ✅ Consolidado em Chat View dedicado (8cm1w4b-9973)

**v1.0**:
- 2 scripts separados (testes + performance/comissão)
- Geração .docx/.pdf com tabelas complexas
- Não estava em crontab (desativado)
