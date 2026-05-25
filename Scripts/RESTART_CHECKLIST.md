# ✅ CHECKLIST: APÓS REINICIALIZAR COMPUTADOR
## IMPERA — Maio 2026

**Tempo Estimado**: 5-10 minutos

---

## 🔍 PASSO 1: Verificar Ambiente (2 min)

```bash
# Abrir terminal e verificar:

# 1a. Variáveis de ambiente carregadas?
echo $CLICKUP_API_TOKEN | head -c 10  # Deve mostrar pk_176...
echo $REDTRACK_API_KEY | head -c 10   # Deve mostrar algo

# 1b. Crontab intacto?
crontab -l | wc -l                    # Deve ser ~15+ linhas

# 1c. Diretórios existem?
ls -d ~/Scripts ~/Obsidian/IMPERA ~/Scripts/logs
```

---

## 🔧 PASSO 2: Iniciar Webhooks (2 min)

```bash
# Terminal 1: Webhook expandir_range
cd ~/Scripts
python3 expandir_range_tasks.py --server &
# Deve mostrar: "Server started on port 5000"

# Terminal 2: Webhook auto_alteracao
cd ~/Scripts
python3 webhook_auto_alteracao.py &
# Deve mostrar: "Server started on port 5001"

# Verificar se estão vivos:
lsof -i :5000 :5001
# Deve listar ambas as portas
```

---

## ✅ PASSO 3: Testar Sincronização (1 min)

```bash
# Testar auto_envio_trafego
python3 ~/Scripts/auto_envio_trafego.py --preview

# Output esperado:
# "Encontradas X tarefas em 'enviado para tráfego'"
# Se encontrado > 0: sincronizar
python3 ~/Scripts/auto_envio_trafego.py --execute
```

---

## 📊 PASSO 4: Verificar Cache (1 min)

```bash
# Cache deve estar reconstruindo-se
ls -lh ~/Scripts/data/*.json | wc -l
# Deve ser > 10 arquivos

# Primeiro relatório será lento (~30-60s)
# Próximos serão normais (~10-15s)
```

---

## 🔔 PASSO 5: Aguardar Próxima Execução Cron

**Próximos eventos:**

| Quando | O Quê | Status |
|--------|-------|--------|
| **10:00** (seg-sáb) | Briefing Diário | ✅ Automático |
| ***/10 min** (seg-sáb) | Auto Envio Tráfego | ✅ Automático |
| **16:00** (seg-sáb) | Chat resumo envio | ✅ Automático |
| **Domingo 12:03** | Relatório Semanal | ✅ Automático |
| **Domingo 23:00** | GPDR Executiva | ✅ Automático |

**Como verificar:**
```bash
tail -20 ~/Scripts/logs/auto_envio_trafego.log
tail -20 ~/Scripts/logs/briefing_diario.log

# Deve mostrar "[YYYY-MM-DD HH:MM] Encontradas X tarefas..."
```

---

## 🚨 SE ALGO FALHAR

### ❌ Variáveis de ambiente vazias

```bash
# Recarregar:
source ~/.zshrc
# ou
source ~/.impera_env

# Verificar novamente:
echo $CLICKUP_API_TOKEN
```

### ❌ Webhook não inicia (porta em uso)

```bash
# Verificar quem está usando:
lsof -i :5000

# Matar processo anterior:
kill -9 <PID>

# Reiniciar:
python3 ~/Scripts/expandir_range_tasks.py --server &
```

### ❌ Cron não rodou

```bash
# Verificar se arquivo de lock existe:
ls -la ~/.auto_envio_trafego_state

# Rodar manualmente:
python3 ~/Scripts/auto_envio_trafego.py --execute

# Verificar logs:
tail -50 ~/Scripts/logs/auto_envio_trafego.log
```

### ❌ Cache vazio (relatórios lentos)

```bash
# Normal! Cache se reconstrói na próxima query
# Aguarde ~60s para primeira consulta
# Próximas serão rápidas

# Ou forçar rebuild:
rm ~/Scripts/data/impera_cache.json
python3 ~/Scripts/briefing_diario.py  # Vai refazer cache
```

---

## 📞 CONTATOS EM CASO DE PROBLEMA

| Problema | Ação |
|----------|------|
| **Webhook morreu** | Terminal 1/2, rodar comando acima, aguarde 30s |
| **Cron não roda** | Verificar `tail -20 ~/Scripts/logs/*.log` |
| **Relatório demora** | Normal pós-restart, cache está sendo reconstruído |
| **ClickUp retorna erro** | Verificar `CLICKUP_API_TOKEN` em `~/.zshrc` |
| **Dashboard falha em enviar webhook** | Verificar se portas 5000/5001 estão vivas |

---

## ✨ CHECKLIST FINAL

- [ ] Terminal 1: Webhook expandir_range rodando (porta 5000)
- [ ] Terminal 2: Webhook auto_alteracao rodando (porta 5001)
- [ ] auto_envio_trafego.py testado (--preview)
- [ ] Cache reconstruído (ls ~/Scripts/data/*.json)
- [ ] Crontab intacto (crontab -l | wc -l > 10)
- [ ] Próxima execução cron aguardada (logs aparecem)

---

**Tempo Total**: ~5 min | **Impacto**: 0 perdido | **Status**: ✅ PRONTO

