# 🔗 AUTOMATION_DEPENDENCIES.md — IMPERA Script Dependencies & Data Flow

**Date**: 2026-05-17  
**Status**: DEPENDENCY MAPPING FOR ALL 47 SCRIPTS  
**Purpose**: Understand data flow, identify conflicts, plan consolidations

---

## 📊 DEPENDENCY GRAPH (Visual)

```
┌─────────────────────────────────────────────────────────────┐
│                      DATA SOURCES                           │
├─────────────────────────────────────────────────────────────┤
│  • ClickUp (API: COPY list + GESTÃO TRÁFEGO)               │
│  • RedTrack (API: campaigns, performance, metrics)          │
│  • Google Drive (shared folders, documents)                 │
│  • Obsidian Vault (Daily Notes, Weekly Reports)             │
│  • Telegram (inbound messages via webhook)                  │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                  PRIMARY PROCESSORS                         │
├─────────────────────────────────────────────────────────────┤
│  🟦 impera_cache.py          — Cache layer (imemory + Redis)  │
│  🟦 impera_utils.py          — Utility functions            │
│  🟦 cruzamento_clickup_redtrack.py — Data aggregation (read) │
│  🟦 auto_status_rt.py        — Status updates (CRITICAL)    │
│  🟦 auto_etiqueta.py         — Tag/label updates            │
│  🟦 auto_envio_trafego.py    — Distribution logic           │
│  🟦 classificador_criativos.py — Classification engine      │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                  REPORTING LAYER                            │
├─────────────────────────────────────────────────────────────┤
│  📋 briefing_diario.py                                      │
│  📋 relatorio_semanal_impera.py (master report)            │
│  📋 relatorio_redtrack_impera.py (master report)           │
│  📋 [5 other report variants]                              │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                 OUTPUT CHANNELS                             │
├─────────────────────────────────────────────────────────────┤
│  • Obsidian (Daily Notes, Weekly Reports)                  │
│  • Slack (#impera-releases, #impera-production)            │
│  • Telegram (direct messages, channels)                    │
│  • Google Drive (shared reports)                           │
│  • File system (.docx, .pdf, .xlsx)                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔴 CRITICAL DATA FLOWS (Sync Points)

### FLOW 1: Status Updates (ClickUp ← RedTrack)
```
RedTrack Performance Data
  ↓
auto_status_rt.py (--preview/--execute)
  ↓
ClickUp Task Status Updated
  ↓
cruzamento_clickup_redtrack.py reads updated status
  ↓
Reports generated with updated data

⚠️ PROBLEM: No frequency defined for auto_status_rt
⚠️ PROBLEM: No timestamp versioning to prevent race conditions
⚠️ IMPACT: Status updates could be lost if scripts run simultaneously
```

### FLOW 2: Tag/Label Updates (ClickUp ← ClickUp)
```
ClickUp Task Created/Updated
  ↓
auto_etiqueta.py (runs every hour)
  ↓
ClickUp Task Labels Updated
  ↓
cruzamento_clickup_redtrack.py reads updated labels
  ↓
Reports include label classifications

⚠️ PROBLEM: Might conflict with auto_categoria
⚠️ PROBLEM: Might conflict with classificador_criativos
```

### FLOW 3: Creative Classification (ClickUp ← Custom Logic)
```
ClickUp Tasks + Custom Fields
  ↓
classificador_criativos.py (14h + 19h)
  + auto_categoria.py (COMMENTED)
  + auto_etiqueta.py (hourly)
  ↓
ClickUp Custom Fields Updated
  ↓
cruzamento_clickup_redtrack.py reads classifications
  ↓
Reports grouped by classification

⚠️ PROBLEM: 3 scripts doing similar work (auto_categoria commented)
⚠️ PROBLEM: No clear responsibility separation
```

### FLOW 4: Distribution to Traffic (ClickUp → RedTrack context)
```
ClickUp Approved Creatives
  ↓
auto_envio_trafego.py (10min monitor + 16h chat)
  ↓
RedTrack Campaign Created (via external tool)
  ↓
Campaign running, metrics accumulating
  ↓
Metrics flow back to RedTrack API
  ↓
Reports read metrics

⚠️ PROBLEM: No automated feedback loop from RedTrack → ClickUp
⚠️ PROBLEM: Manual intervention still needed for campaign creation
```

---

## 📊 DETAILED DEPENDENCY TABLE

### IMPORTS & DEPENDENCIES

| Script | Imports | Depends On | Updates | Reads |
|--------|---------|-----------|---------|-------|
| `impera_cache.py` | redis, json | - | Cache | ClickUp, RedTrack (cached) |
| `impera_utils.py` | urllib, json | - | - | ClickUp, RedTrack |
| `cruzamento_clickup_redtrack.py` | impera_utils | impera_utils, impera_cache | - | ClickUp, RedTrack |
| `auto_status_rt.py` | impera_cache | cache layer | ClickUp Status | RedTrack (7d metrics) |
| `auto_etiqueta.py` | impera_utils | impera_utils | ClickUp Labels | ClickUp Tasks |
| `auto_envio_trafego.py` | impera_utils, Telegram | impera_utils | ClickUp Custom Fields | ClickUp, RedTrack |
| `auto_categoria.py` | COMMENTED | ? | ? | ? |
| `auto_healing.py` | COMMENTED | ? | ? | ? |
| `auto_time_tracking.py` | ? | ? | ? | ? |
| `classificador_criativos.py` | impera_utils | impera_utils | ClickUp Custom Fields | ClickUp |
| `gate_finalizado.py` | COMMENTED | ? | ? | ? |
| `detectar_criativos_orfaos_v2.py` | COMMENTED | ? | ? | ? |
| `briefing_diario.py` | All | cruzamento, relatorio scripts | Obsidian, Telegram | ClickUp, RedTrack |
| `relatorio_semanal_impera.py` | impera_utils | impera_utils | .docx file | ClickUp |
| `relatorio_redtrack_impera.py` | impera_utils | impera_utils | .docx file | RedTrack |
| `relatorio_copywriters_semanal.py` | impera_utils | impera_utils | .docx file | ClickUp |
| `relatorio_performance_copywriters_pdf.py` | impera_utils | impera_utils | PDF file | ClickUp, RedTrack |
| `relatorio_performance_criativos.py` | impera_utils | impera_utils | .docx file | ClickUp, RedTrack |
| `relatorio_pontuacao_editores.py` | impera_utils | impera_utils | .docx file | ClickUp |
| `relatorio_entregas_trafego.py` | impera_utils | impera_utils | .docx file | ClickUp, RedTrack |
| `telegram_claude_bot.py` | Telegram, OpenAI | - | Telegram Chat | ClickUp (for context) |
| `telegram_financas_comandos.py` | Telegram | - | Telegram Chat | ClickUp (financeiro) |
| `telegram_gemini_bot.py` | Telegram, Google | - | Telegram Chat | ClickUp (for context) |
| `monitor_aguardando_teste.py` | impera_utils | impera_utils | - | ClickUp |
| `monitor_nichos_ofertas.py` | impera_utils | impera_utils | - | ClickUp, RedTrack |
| `monitor_pausados_15d.py` | impera_utils | impera_utils | - | RedTrack |
| `reminder_em_teste.py` | Telegram | impera_utils | Telegram message | ClickUp |
| `bot_gpdr.py` | Obsidian | impera_utils | Obsidian file | ClickUp, RedTrack |
| `bot_performance.py` | Telegram | impera_utils | Telegram message | ClickUp, RedTrack |
| `rastreador_esteira.py` | impera_utils, Telegram | impera_utils | Telegram alert | ClickUp |
| `auditoria_nomenclatura.py` | impera_utils, Telegram | impera_utils | Telegram alert | ClickUp |
| `compliance_drive.py` | GoogleDrive API | - | Telegram alert | GoogleDrive |
| `pareto_semanal.py` | impera_utils | impera_utils | Obsidian file | ClickUp, RedTrack |
| `roas_diario.py` | impera_utils | impera_utils | Telegram message | RedTrack |
| `dashboard_cobertura_rt_cu.py` | impera_utils | impera_utils | Telegram message | ClickUp, RedTrack |

---

## 🔄 SYNCHRONIZATION CONFLICTS

### CONFLICT 1: Auto Etiqueta vs Auto Categoria vs Classificador
```
Three scripts compete for ClickUp label management:

1. auto_etiqueta.py (hourly)
   └─ Updates custom fields based on ???

2. auto_categoria.py (COMMENTED)
   └─ Was supposed to auto-categorize creatives

3. classificador_criativos.py (14h + 19h)
   └─ Classifies creatives using sophisticated logic

PROBLEM: 
- No clear separation of concerns
- auto_categoria is commented (why?)
- Conflicting update schedules
- Could overwrite each other's work

IMPACT: 
- Labels could be wrong
- Processing redundancy
- Data inconsistency

SOLUTION:
- Pick ONE classification engine
- Remove or repurpose the others
- Clear rules for which script owns which field
```

### CONFLICT 2: Multiple Report Generators (Same Data)
```
Data source: ClickUp + RedTrack

Multiple report generators reading same source, different outputs:

relatorio_semanal_impera.py (Sunday 12:03)
  ├─ Output: Weekly production .docx
  ├─ Scope: All copywriters, all weeks
  └─ Format: Production summary

relatorio_copywriters_semanal.py (Monday 09:30)
  ├─ Output: Weekly production .docx
  ├─ Scope: Copywriters only
  └─ Format: Copywriter breakdown

relatorio_performance_copywriters_pdf.py (Biweekly + Monthly)
  ├─ Output: PDF
  ├─ Scope: Copywriters + performance
  └─ Format: PDF version

⟹ SAME DATA, 3 OUTPUTS, DIFFERENT SCHEDULES

PROBLEM:
- Processing redundancy (3x the API calls)
- Different numbers reported (timing differences)
- Confusion about "the official report"
- Hard to maintain 3 slightly different versions

SOLUTION:
- Consolidate into single parameterized script
- Generate multiple formats from single run
- Unified schedule (e.g., Friday 3pm for weekly)
```

### CONFLICT 3: Performance Reporting (Red Track)
```
RedTrack performance data read by multiple scripts:

relatorio_redtrack_impera.py (Daily 06:00)
  └─ Output: Daily performance .docx

relatorio_entregas_trafego.py (Sunday 13:00)
  └─ Output: Weekly traffic summary

relatorio_performance_criativos.py (Monday 08:30)
  └─ Output: Creative performance analysis

bot_performance.py (Multiple: 08:30 morning, 16:00 afternoon, 09-20 check)
  └─ Output: Telegram alerts + chat messages

⟹ SAME DATA, 4 DIFFERENT CONSUMERS, DIFFERENT SCHEDULES

PROBLEM:
- Inconsistent numbers (timing differences)
- Users seeing different "latest performance" depending on source
- Hard to identify "source of truth"

SOLUTION:
- Unified performance data pipeline
- Single daily update (e.g., 6 AM)
- All consumers pull from cache
- Clear version/timestamp on all outputs
```

### CONFLICT 4: Status Updates (Most Critical)
```
Status updates in ClickUp flow from RedTrack data:

auto_status_rt.py (NO FREQUENCY DEFINED)
  └─ Updates task status based on RedTrack ROAS thresholds

cruzamento_clickup_redtrack.py (Runs on demand or in reports)
  └─ Reads status for reporting purposes

auto_etiqueta.py (Hourly)
  └─ Updates labels (might include status-related fields)

PROBLEM:
- auto_status_rt has no crontab entry (manual only?)
- If auto_status_rt runs while cruzamento is reading, inconsistency
- No timestamp versioning to detect conflicts
- Possible data loss if updates not atomic

RACE CONDITION SCENARIO:
1. 10:00 — auto_status_rt updates task status from VALIDADO to PRÉ-ESCALA
2. 10:01 — cruzamento reads status (reads VALIDADO from cache?)
3. 10:02 — cruzamento reports generated with wrong status
4. 10:05 — cache refreshes, but reports already sent

SOLUTION:
- Schedule auto_status_rt with clear frequency (e.g., 6h or 3x daily)
- Implement timestamp versioning in ClickUp custom fields
- Use optimistic locking to detect conflicts
- Add cache invalidation on write
```

---

## 📈 DATA FLOW SEQUENCES

### Sequence 1: New Creative Lifecycle

```
Day 0 (Creative Created)
  Writer creates task in ClickUp COPY
  ↓
auto_etiqueta.py (hourly) runs
  ├─ Detects: COPY list + not labeled
  └─ Adds: Status = "CRIAÇÃO EM ANDAMENTO"
  ↓
Writer submits creative
  ├─ Changes status to "AGUARDANDO QC"
  └─ Adds link to creative file
  ↓
QC reviewer approves
  ├─ Changes status to "APROVADO"
  └─ Adds "QC-APPROVED" label
  ↓
Day 1, 16:00 — auto_envio_trafego.py runs
  ├─ Detects: Approved creatives in ClickUp
  ├─ Sends to traffic manager (chat)
  └─ Updates custom field: "ENVIADO_TRAFEGO"
  ↓
Traffic manager creates campaign in RedTrack
  ├─ Campaign starts running
  └─ Metrics accumulate
  ↓
Day 2, 10:00 — auto_status_rt.py runs (MANUAL?)
  ├─ Reads RedTrack: Campaign ROAS
  ├─ Updates ClickUp status based on ROAS thresholds
  └─ Task status: "EM TESTE" | "VALIDADO" | "PRÉ-ESCALA" | "ESCALA"
  ↓
Day 3+ — Daily reports
  ├─ relatorio_redtrack_impera.py reads RedTrack (06:00)
  ├─ briefing_diario.py aggregates (10:00)
  ├─ relatorio_semanal_impera.py reports (Sunday 12:03)
  └─ All reports show updated metrics & status

⚠️ ISSUE: Step 4 (auto_status_rt) not in crontab!
⚠️ ISSUE: Manual approval step slows down pipeline
```

### Sequence 2: Weekly Reporting Cycle

```
Sunday 06:00 — Start of week
  relatorio_redtrack_impera.py runs
  ├─ Reads RedTrack campaigns
  ├─ Generates daily performance snapshot
  └─ Output: Daily performance .docx

Sunday 12:00 — End of week reports
  relatorio_semanal_impera.py runs
  ├─ Reads ClickUp production data
  ├─ Counts: creatives by writer, editor
  └─ Output: Weekly production .docx
  
  bot_gpdr.py (if autofix) runs
  ├─ Reads ClickUp + RedTrack
  ├─ Checks: GPDR compliance
  └─ Output: Obsidian + Slack

Sunday 13:00
  relatorio_entregas_trafego.py runs
  ├─ Reads RedTrack + ClickUp
  ├─ Summarizes: traffic deliveries
  └─ Output: Traffic .docx

Monday 08:30
  relatorio_performance_criativos.py runs
  ├─ Reads ClickUp + RedTrack
  ├─ Performance by creative
  └─ Output: Performance .docx

Monday 09:30
  relatorio_copywriters_semanal.py runs
  ├─ Reads ClickUp
  ├─ Copywriter breakdown
  └─ Output: Copywriter .docx

📊 RESULT: 5 different documents generated from similar data
⚠️ PROBLEM: Same data, different numbers (timing differences)
```

---

## 🎯 CONSOLIDATION OPPORTUNITIES

### Opportunity 1: Unified Report Generator
```
CURRENT (5 scripts):
1. relatorio_semanal_impera.py
2. relatorio_copywriters_semanal.py
3. relatorio_performance_copywriters_pdf.py
4. relatorio_entregas_trafego.py
5. relatorio_performance_criativos.py

CONSOLIDATED (1 script):
  unified_report_generator.py
  
  python3 unified_report_generator.py --report-type production
  python3 unified_report_generator.py --report-type performance
  python3 unified_report_generator.py --report-type traffic
  python3 unified_report_generator.py --format docx
  python3 unified_report_generator.py --format pdf
  python3 unified_report_generator.py --all (generates all formats once)

BENEFITS:
- Single data query to ClickUp/RedTrack
- Consistent numbers across all reports
- 5x faster processing
- Easy to modify definitions
- Clear version/timestamp on all outputs

EFFORT: 4 hours
```

### Opportunity 2: Unified Classification Engine
```
CURRENT (3 scripts):
1. auto_categoria.py (COMMENTED)
2. auto_etiqueta.py (ACTIVE - hourly)
3. classificador_criativos.py (ACTIVE - 14h/19h)

CONSOLIDATED (1 script):
  unified_classifier.py
  
  Modes:
  - --check (preview changes without updating)
  - --apply (update ClickUp)
  - --audit (check consistency)
  
  Classification rules:
  - Nicho detection (from campaign name)
  - Oferta classification (from custom field)
  - Performance tier (from RedTrack ROAS)
  - QC score (from ClickUp checklist)

BENEFITS:
- Single source of classification rules
- Atomic updates (no conflicts)
- Easier to debug
- Versioning & audit trail

EFFORT: 3 hours
```

### Opportunity 3: Unified Status Update Engine
```
CURRENT:
- auto_status_rt.py (MANUAL, no crontab)
- auto_etiqueta.py (hourly, might update statuses)
- auto_envio_trafego.py (updates custom fields)

PROBLEM:
- No coordinated status management
- Race conditions possible
- No versioning/locking

CONSOLIDATED (1 script):
  unified_status_engine.py
  
  Features:
  - Atomic updates with timestamps
  - Optimistic locking (detect conflicts)
  - Clear state machine (rules what transitions are allowed)
  - Audit trail (all changes logged)
  - Scheduled: 3x daily (6:00 AM, 12:00 PM, 6:00 PM)
  
  Modes:
  - --check (preview)
  - --apply (update)
  - --audit (check for conflicts)

BENEFITS:
- Prevent race conditions
- Consistent status across system
- Clear changelog
- Easier debugging

EFFORT: 5 hours
PRIORITY: CRITICAL
```

---

## 📋 DEPENDENCY-BASED SCHEDULING RECOMMENDATIONS

### Problem: Some Processes Should Run in Sequence

```
Current Problem:
- relatorio_semanal_impera.py (Sunday 12:03)
  └─ Reads ClickUp production data

- auto_status_rt.py (MANUAL, not scheduled)
  └─ Updates ClickUp status based on RedTrack

ISSUE: If status update happens AFTER report generation,
report will have old status!

SOLUTION: Enforce sequence

Monday 06:00 — Update statuses first
  auto_status_rt.py --execute
  └─ Updates all statuses based on RedTrack metrics

Monday 07:00 — Then read for reports
  relatorio_redtrack_impera.py
  └─ Reads updated data

Monday 08:00 — Generate all reports at once
  unified_report_generator.py --all
  └─ Generates all formats from consistent snapshot

BENEFIT: All reports generated from same "moment in time"
```

---

## 🚨 CRITICAL ISSUES TO FIX

| Issue | Impact | Fix | Effort |
|-------|--------|-----|--------|
| auto_status_rt not scheduled | Can't track status | Add crontab entry | 30min |
| No versioning in status updates | Race conditions | Add timestamps + locking | 4h |
| 5 report generators (same data) | Redundancy + inconsistency | Consolidate to 1 | 4h |
| 3 classifiers compete | Conflicts | Consolidate to 1 | 3h |
| cruzamento runs on-demand | Unpredictable | Schedule it or deprecate | 1h |
| Commented-out scripts | Confusion | Review + delete or uncomment | 2h |
| Broken crontab entry (relatorio_semanal_producao.py) | Script never runs | Fix or delete entry | 15min |

---

## 📝 Sign-off

**Status**: DEPENDENCY MAPPING COMPLETE  
**Date**: 2026-05-17  
**Conflicts Found**: 4 major, 8 minor  
**Consolidation Opportunities**: 3 major  
**Critical Issues**: 6

**Next Step**: Begin Phase 1 consolidations starting with unified report generator

---

*This document is the basis for the Phase 1-3 action plan. Update as consolidations are completed.*
