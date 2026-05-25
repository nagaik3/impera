# Bot Performance → ClickUp Chat View — Migração Completa

## O que mudou?

**Antes:**
- Interface: Telegram (polling + interativo)
- Relatórios: 2/dia (08:30 + 16:00) + alerts horários
- Alertas: No Telegram
- Dados: RedTrack + ClickUp fetched on-demand

**Depois:**
- Interface: ClickUp Chat View (centralizado)
- Relatórios: 2/dia (08:30 + 16:00) - Performance + Gestores + Alertas
- Alertas: Consolidados no relatório
- Dados: Fetch otimizado, cache-friendly
- Telegram bot: **Desativado**

---

## 🚀 Novas Automações

### 1️⃣ Relatório da Manhã (08:30)

```
⏰ Horário: 08:30 seg-sáb
📍 Chat View: 8cm1w4b-9893
🔗 Crontab: 30 8 * * 1-6 cd ~/Scripts && python3 bot_performance_clickup.py morning
```

**Conteúdo:**
- 📊 Performance geral (últimas 24h)
- 👥 Ranking de gestores
- ⚠️ Alertas (se houver ROAS baixo, gasto sem venda, etc)

### 2️⃣ Relatório da Tarde (16:00)

```
⏰ Horário: 16:00 seg-sáb
📍 Chat View: 8cm1w4b-9893
🔗 Crontab: 0 16 * * 1-6 cd ~/Scripts && python3 bot_performance_clickup.py afternoon
```

**Conteúdo:** Igual ao da manhã (atualizado com dados do dia)

---

## 📋 Arquivo Novo

### **bot_performance_clickup.py**

Script que substitui a funcionalidade do bot Telegram.

**Modos:**
```bash
python3 bot_performance_clickup.py morning    # Relatório 08:30
python3 bot_performance_clickup.py afternoon  # Relatório 16:00
python3 bot_performance_clickup.py check      # Alertas horários (opcional)
```

**Funções principais:**
- `build_performance_report()` — Relatório por oferta
- `build_gestores_report()` — Ranking de gestores
- `build_alerts_report()` — Alertas de problemas
- `post_clickup()` — Posts para ClickUp Chat View

---

## 📊 Conteúdo dos Relatórios

### Performance
```
📊 PERFORMANCE — 24/05 08:30

💰 Receita: R$50,000 | Custo: R$25,000 | ROAS: 2.0

✅ Nicho 1 | Oferta A
  • R$: R$30,000 | Custo: R$15,000 | ROAS: 2.0
  • Vendas: 150 | CPA: R$100 | Camps: 3

⚠️ Nicho 2 | Oferta B
  • R$: R$15,000 | Custo: R$10,000 | ROAS: 1.5
  • Vendas: 100 | CPA: R$100 | Camps: 2

❌ Nicho 3 | Oferta C
  • R$: R$5,000 | Custo: R$5,000 | ROAS: 1.0
  • Vendas: 20 | CPA: R$250 | Camps: 1
```

### Gestores
```
👥 GESTORES DE TRÁFEGO — 24/05 08:30

1. ✅ João Silva (5 campaigns)
   R$: R$30,000 | Custo: R$15,000 | ROAS: 2.0
   Vendas: 100 | CPA: R$150 | Nichos: MM, VS

2. ⚠️ Maria Santos (3 campaigns)
   R$: R$15,000 | Custo: R$10,000 | ROAS: 1.5
   Vendas: 80 | CPA: R$125 | Nichos: DA, ED
```

### Alertas
```
⚠️ ALERTAS — 24/05 08:30

❌ Nicho 2 | Oferta B: ROAS 0.95 (crítico!) | Gasto: R$10,000
⚠️ Nicho 3 | Oferta C: ROAS 1.3 (atenção) | Gasto: R$5,000
🚨 Campaign Name Here: Gastou R$8,000 sem venda!
```

---

## ⚙️ Configuração

### Chat View ID
Edite `bot_performance_clickup.py`:
```python
CLICKUP_CHAT_VIEW = "8cm1w4b-9893"  # Chat View correto
```

### Thresholds de Alertas
Edite `CONFIG` em `bot_performance_clickup.py`:
```python
CONFIG = {
    "MIN_COST_CRITICAL": 500,        # Gasto mínimo para alertar
    "ROAS_WARNING": 1.5,             # ROAS amarelo
    "ROAS_CRITICAL": 1.0,            # ROAS vermelho
    "CPA_META": 180,                 # CPA máximo
}
```

### Crontab (horários)
```bash
# Manhã (08:30)
30 8 * * 1-6 cd ~/Scripts && python3 bot_performance_clickup.py morning >> ~/Scripts/logs/bot_perf_clickup.log 2>&1

# Tarde (16:00)
0 16 * * 1-6 cd ~/Scripts && python3 bot_performance_clickup.py afternoon >> ~/Scripts/logs/bot_perf_clickup.log 2>&1
```

---

## 📊 Monitoramento

### Ver logs
```bash
tail -f ~/Scripts/logs/bot_perf_clickup.log
```

### Forçar execução manual
```bash
python3 bot_performance_clickup.py morning   # Executa agora
python3 bot_performance_clickup.py afternoon # Executa agora
```

### Ver estado/últimos relatórios
```bash
cat ~/Scripts/data/bot_perf_state.json | jq .reports
```

---

## 🧪 Testes Realizados

✅ Morning report — Executado com sucesso  
✅ Dados de performance — Fetched corretamente  
✅ ClickUp post — Mensagem chegou no Chat View  
✅ Crontab — Agendado para 08:30 e 16:00  

---

## 🚨 Telegram Bot Status

**Status:** ✅ Desativado

O `bot_performance.py` original continua no diretório, mas:
- ❌ Não está em crontab
- ❌ Não é executado automaticamente
- ✅ Pode ser mantido como fallback se necessário

Para reativar Telegram (não recomendado):
```bash
# Adicionar ao crontab
0 * * * * cd ~/Scripts && python3 bot_performance.py bot >> ~/Scripts/logs/bot_perf_telegram.log 2>&1
```

---

## 📈 Próximos Passos (Opcional)

1. **Adicionar hourly check** — Alertas a cada hora
   ```bash
   0 * * * 1-6 cd ~/Scripts && python3 bot_performance_clickup.py check >> ~/Scripts/logs/bot_perf_clickup.log 2>&1
   ```

2. **Integrar com outras automações** — Consolidar com Rastreador, Compliance, etc

3. **Expandir relatórios** — Adicionar copywriters, criativos top, etc

---

## 🔄 Changelog

**v1.0** (2026-05-24):
- ✅ Migrado de Telegram para ClickUp Chat View
- ✅ Reports consolidados (Performance + Gestores + Alertas)
- ✅ Crontab configurado (08:30 + 16:00)
- ✅ Telegram bot desativado
- ✅ Chat View: 8cm1w4b-9893
