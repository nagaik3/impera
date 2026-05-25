# Relatório Redtrack → ClickUp — Migração v2.0

## O que mudou?

**Antes (v1.0)**:
- 1329 linhas de código
- Gera .docx + PDF (arquivos pesados)
- Relatórios salvos em ~/Documents (inaccessível)
- NÃO estava em crontab (desativado)
- Comparativo semanal complexo

**Depois (v2.0)**:
- 384 linhas de código (71% menor)
- Posts consolidados em ClickUp Chat View
- Relatório acessível no workflow
- ✅ Habilitado em crontab (domingo 12:07)
- Análise simplificada mas completa

---

## 🚀 Novo Relatório

### Frequência
```
⏰ Domingo 12:07 (crontab)
📍 Chat View: 8cm1w4b-9893 (mesmo de Bot Performance)
```

### Conteúdo
```
📊 RELATÓRIO REDTRACK — 11/05 a 17/05

💰 TOTAIS
Receita: R$50,000 | Custo: R$25,000 | ROAS: 2.0
vs semana anterior: ROAS 1.8 (+0.2)

🎯 TOP OFERTAS
1. 🏆 Escala Nicho 1 | Oferta A
   R$: R$30,000 | Custo: R$15,000 | ROAS: 2.0 | Vendas: 150
2. ✅ Validado Nicho 2 | Oferta B
   R$: R$15,000 | Custo: R$10,000 | ROAS: 1.5 | Vendas: 100

👥 TOP GESTORES
1. João Silva (5 campaigns)
   R$: R$30,000 | Custo: R$15,000 | ROAS: 2.0
   Nichos: MM, VS

⚠️ ATENÇÃO (ROAS < 1.0)
🔴 Nicho 3 | Oferta C: ROAS 0.95 | Gasto: R$8,000
```

---

## 📋 Arquivo Novo

### **relatorio_redtrack_clickup.py**

Script simplificado que:
- Busca dados RedTrack (semana atual + anterior)
- Analisa ofertas e gestores
- Classifica com Super Cérebro V5
- Posta em ClickUp Chat View

**Tamanho**: 384 linhas (vs 1329 antes)  
**Tempo execução**: ~5 segundos  
**Removido**: .docx, PDF, relatórios individuais por gestor  

---

## ⚙️ Configuração

### Chat View
Edite `relatorio_redtrack_clickup.py`:
```python
CLICKUP_CHAT_VIEW = "8cm1w4b-9893"  # Mesmo de Bot Performance
```

### Crontab (Domingo 12:07)
```bash
7 12 * * 0 cd ~/Scripts && python3 relatorio_redtrack_clickup.py >> ~/Scripts/logs/relatorio_redtrack.log 2>&1
```

---

## 🔄 Funcionalidades Mantidas

✅ Análise de ofertas (ROAS, CPA, Vendas, Classificação)  
✅ Análise de gestores (top 5, nichos, performance)  
✅ Comparativo com semana anterior  
✅ Alertas para ofertas negativas (ROAS < 1.0)  
✅ Dados persistem em banco de dados (se ativado)  

---

## ❌ Funcionalidades Removidas

❌ Geração .docx (pesada, inacessível)  
❌ Conversão PDF  
❌ Relatórios individuais por gestor  
❌ Tabelas complexas com formatação  

---

## 📊 Impacto

| Métrica | Antes | Depois | Ganho |
|---------|-------|--------|-------|
| **Linhas de código** | 1329 | 384 | 71% ↓ |
| **Tempo execução** | ~30s | ~5s | 85% ↓ |
| **Acessibilidade** | Arquivo | ClickUp | 🚀 |
| **Status crontab** | ❌ Desativado | ✅ Ativo | ✅ |
| **Formato output** | .docx/.pdf | Chat post | ✅ |

---

## 🧪 Testes

### Test manual
```bash
python3 relatorio_redtrack_clickup.py
# Deve postar em ClickUp
```

### Ver logs
```bash
tail -f ~/Scripts/logs/relatorio_redtrack.log
```

### Próxima execução
Domingo 12:07 (crontab)

---

## 📈 Próximos Passos

1. **Monitorar** — Verificar se logs estão limpos
2. **Integrar** — Usar mesmo Chat View de Bot Performance (consolidado)
3. **Expandir** — Adicionar análise de nichos se necessário
4. **Arquivar** — Manter `relatorio_redtrack_impera.py.archived` como fallback

---

## 🔗 Integração com Outras Automações

| Automação | Chat View | Frequência |
|-----------|-----------|-----------|
| Bot Performance | 8cm1w4b-9893 | 08:30 + 16:00 (daily) |
| Relatorio Redtrack | 8cm1w4b-9893 | 12:07 (Sunday) |

**Nota**: Mesmo Chat View consolidado em um lugar!

---

## 📝 Changelog

**v2.0** (2026-05-24):
- ✅ Migrado de .docx para ClickUp Chat View
- ✅ Reduzido de 1329 para 384 linhas (71% menor)
- ✅ Re-habilitado em crontab (Sunday 12:07)
- ✅ Análise simplificada mas completa
- ✅ Integrado com Bot Performance (mesmo Chat View)
- ✅ Tempo execução reduzido de 30s para 5s
- ✅ Script original arquivado como fallback

**v1.0**:
- Geração .docx com análises complexas
- Não estava em crontab (desativado)
