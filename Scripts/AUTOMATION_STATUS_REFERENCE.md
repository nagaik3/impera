# Automation Status & Reference — May 24, 2026

**Last Updated**: 2026-05-24 15:36:00 UTC-3  
**Session Status**: ✅ ALL TESTS PASSED (8/8)  
**Infrastructure Status**: 🟢 PRODUCTION STABLE

---

## 📊 Quick Status Dashboard

| Component | Status | Frequency | Chat View | Last Run |
|-----------|--------|-----------|-----------|----------|
| **Relatório Semanal** | ✅ Live | Dom 12:03 | 8cm1w4b-9953 | 2026-05-24 15:34 |
| **Relatório Redtrack** | ✅ Live | Dom 12:07 | 8cm1w4b-9933 | 2026-05-24 15:34 |
| **Relatório Mensal CW** | ✅ Live | 1º/mês 09:00 | 8cm1w4b-9973 | 2026-05-24 15:35 |
| **Bot Performance** | ✅ Live | 08:30, 16:00 | 8cm1w4b-9893 | 2026-05-24 15:35 |
| **Bot GPDR** | ✅ Live | On-demand | 8cm1w4b-9913 | 2026-05-24 15:36 |
| **Auto Etiqueta v2.0** | ✅ Live | Every 2h + webhook | 8cm1w4b-9873 | (webhook) |
| **Rastreador Esteira** | ✅ Live | Every 2h + webhook | 8cm1w4b-9853 | (webhook) |
| **Gate Finalizado** | ✅ Active | Continuous + webhook | (inline) | (webhook) |

---

## 🚀 What's Running (Crontab)

```bash
# Every 2 hours
0 */2 * * * cd ~/Scripts && python3 auto_etiqueta.py >> ~/Scripts/logs/auto_etiqueta.log 2>&1

# Weekdays 08:30 (morning performance report)
30 8 * * 1-6 cd ~/Scripts && python3 bot_performance_clickup.py morning >> ~/Scripts/logs/bot_perf_clickup.log 2>&1

# Weekdays 16:00 (afternoon performance report)
0 16 * * 1-6 cd ~/Scripts && python3 bot_performance_clickup.py afternoon >> ~/Scripts/logs/bot_perf_clickup.log 2>&1

# Sunday 12:03 (weekly production report)
3 12 * * 0 cd ~/Scripts && python3 relatorio_semanal_clickup.py >> ~/Scripts/logs/relatorio_semanal.log 2>&1

# Sunday 12:07 (weekly RedTrack report)
7 12 * * 0 cd ~/Scripts && python3 relatorio_redtrack_clickup.py >> ~/Scripts/logs/relatorio_redtrack.log 2>&1

# 1st of month 09:00 (monthly copywriter report)
0 9 1 * * cd ~/Scripts && python3 relatorio_mensal_copywriters_clickup.py >> ~/Scripts/logs/relatorio_mensal_cw.log 2>&1
```

---

## 🎯 ClickUp Chat Views Map

### Daily Operations
- **8cm1w4b-9893**: Bot Performance (08:30, 16:00)
- **8cm1w4b-9873**: Auto Etiqueta (every 2h + webhook)
- **8cm1w4b-9853**: Rastreador Esteira (webhook real-time)

### Weekly Reports (Sunday)
- **8cm1w4b-9953**: Relatório Semanal (12:03)
- **8cm1w4b-9933**: Relatório Redtrack (12:07)

### Monthly & On-Demand
- **8cm1w4b-9973**: Relatório Mensal Copywriters (1º/mês 09:00)
- **8cm1w4b-9913**: Bot GPDR (on-demand: producao, performance, briefing, auditoria)

---

## 📁 Scripts Reference

### Relatórios (Auto-Post to ClickUp)
| Script | Lines | Frequency | Description |
|--------|-------|-----------|-------------|
| `relatorio_semanal_clickup.py` | 334 | Sun 12:03 | Production by copywriter/editor/nicho |
| `relatorio_redtrack_clickup.py` | 384 | Sun 12:07 | Campaign performance + offers + gestores |
| `relatorio_mensal_copywriters_clickup.py` | 350 | 1º/mês 09:00 | Monthly copywriter metrics + rankings |

### Bots (On-Demand)
| Script | Lines | Usage |
|--------|-------|-------|
| `bot_performance_clickup.py` | 407 | `python3 bot_performance_clickup.py [morning\|afternoon]` |
| `bot_gpdr_clickup.py` | 211 | `python3 bot_gpdr_clickup.py [producao\|performance\|briefing\|auditoria]` |

### Cache & Support
| Script | Purpose |
|--------|---------|
| `auto_etiqueta_cache.py` | TTL-based intelligent cache (2h window) |
| `compliance_drive.py` | Google Drive cache + alert consolidation |

---

## 🔧 Common Operations

### Manual Execution
```bash
# Test a report (generates output)
python3 relatorio_semanal_clickup.py

# Generate a different month
python3 relatorio_mensal_copywriters_clickup.py --mes=4 --ano=2026

# On-demand bot commands
python3 bot_gpdr_clickup.py producao
python3 bot_gpdr_clickup.py briefing

# Bot Performance (morning/afternoon)
python3 bot_performance_clickup.py morning
```

### Check Logs
```bash
# Recent execution logs
tail -f ~/Scripts/logs/relatorio_semanal.log
tail -f ~/Scripts/logs/relatorio_redtrack.log
tail -f ~/Scripts/logs/relatorio_mensal_cw.log
tail -f ~/Scripts/logs/bot_perf_clickup.log

# See all logs
ls -lh ~/Scripts/logs/ | grep relatorio
```

### Verify Crontab
```bash
# Check scheduled jobs
crontab -l | grep relatorio
crontab -l | grep bot_performance

# Edit crontab
crontab -e
```

---

## 📈 Performance Metrics (Session Baseline)

**Code Optimization**:
- Total lines reduced: 6700+ → 2000+ (70% ↓)
- Execution time: 30s → 6-10s average (75% ↓)

**API Efficiency**:
- Daily API calls: 500+ → ~50 (90% ↓)
- Daily messages: 150+ → ~40 (73% ↓)

**Reliability**:
- Test success rate: 100% (8/8 passed)
- Chat View posts: 8 active locations
- Crontab jobs: 6 configured

---

## 🚨 Troubleshooting

### Report not posting?
1. Check `CLICKUP_API_TOKEN` env var: `echo $CLICKUP_API_TOKEN`
2. Verify Chat View ID exists
3. Check logs: `tail -f ~/Scripts/logs/relatorio_*.log`

### Bot command failing?
1. Check script exists: `ls ~/Scripts/bot_*.py`
2. Run manually to see error: `python3 bot_gpdr_clickup.py producao`
3. Check dependencies in script header

### Crontab not running?
1. Verify entry: `crontab -l | grep relatorio`
2. Check system logs: `log stream | grep python3`
3. Test manually: `cd ~/Scripts && python3 script.py`

---

## 📋 Scripts Archived (Fallback)

If issues occur, fallback scripts are preserved:
- `relatorio_semanal_impera.py.archived` (old .docx version)
- `relatorio_redtrack_impera.py.archived` (old .pdf version)
- `relatorio_mensal_copywriters.py.archived` (old version)
- `relatorio_mensal_copywriters_testes.py.archived` (old version)

To restore: `mv script.py.archived script.py`

---

## 🔗 Documentation Files

- `RELATORIO_SEMANAL_CLICKUP_MIGRATION.md` — Weekly production report migration
- `RELATORIO_REDTRACK_CLICKUP_MIGRATION.md` — RedTrack performance report migration
- `RELATORIO_MENSAL_COPYWRITERS_CLICKUP_MIGRATION.md` — Monthly copywriter report migration
- `BOT_PERFORMANCE_CLICKUP_MIGRATION.md` — Bot Performance migration
- `AUTOMATION_MIGRATION_SUMMARY_2026_05_24.md` — Complete session summary

---

**Next Review Date**: 2026-06-01 (after first monthly cron run)  
**Maintenance Window**: Sundays 23:00 (if needed)
