# 📋 PHASE 1: ACTION PLAN — IMPERA Automation Consolidation

**Date**: 2026-05-17  
**Phase**: 1 (Consolidation & Quick Fixes)  
**Duration**: WEEK 1-2  
**Goal**: Fix critical issues, document frequencies, prepare for consolidation

---

## 📌 EXECUTIVE SUMMARY

**5 Critical Issues to Fix**:
1. ❌ `auto_status_rt.py` not scheduled (MANUAL mode)
2. ❌ `cruzamento_clickup_redtrack.py` no versioning (RACE CONDITIONS)
3. ❌ 5 report generators doing similar work (REDUNDANCY)
4. ❌ 3 classifiers competing (CONFLICTS)
5. ❌ Broken crontab entry (relatorio_semanal_producao.py doesn't exist)

**Quick Wins (< 1 hour total)**:
- Fix broken crontab entries
- Document missing frequencies
- Remove obsolete scripts
- Activate/clarify commented scripts

**Short-term Consolidations (4-8 hours total)**:
- Create unified report generator
- Create unified classifier
- Create unified status engine
- Add versioning to sync scripts

---

## 🎯 TIER 1: QUICK FIXES (15-30 min each)

### FIX 1: Remove Broken Crontab Entry
```
STATUS: BROKEN
  File: relatorio_semanal_producao.py
  Entry: "30 8 * * 4" (Thursday 08:30)
  Problem: File doesn't exist

ACTION:
  1. Remove crontab entry for relatorio_semanal_producao.py
  2. Verify: relatorio_semanal_producao.py should NOT exist
  3. Keep: relatorio_semanal_impera.py (Sunday 12:03) — this is the main one

VERIFICATION:
  $ crontab -e
  # Remove: 30 8 * * 4 /path/to/relatorio_semanal_producao.py
  $ crontab -l | grep relatorio_semanal
  # Should only show: relatorio_semanal_impera.py (Sunday 12:03)

EFFORT: 10 minutes
```

### FIX 2: Clarify Commented Scripts
```
STATUS: 8 scripts commented out in crontab

SCRIPTS:
  1. auto_categoria.py (*/30 commented)
  2. auto_healing.py (*/30 commented)
  3. gate_finalizado.py (multiple entries commented)
  4. detectar_criativos_orfaos_v2.py (commented)
  5. sync_responsavel_dropdown.py (commented)
  6. health_check_impera.py (commented)

ACTION for each:
  A. Read the script (5 min)
  B. Determine: Is it obsolete OR still needed but inactive?
  C. If obsolete: Mark with "# OBSOLETE: reason"
  D. If needed: Uncomment and document frequency

EXAMPLE:
  Before:
    # */30 * * * 1-6 auto_categoria.py
  
  After (if obsolete):
    # OBSOLETE: 2026-05-17 — Replaced by classificador_criativos.py
    # */30 * * * 1-6 auto_categoria.py
  
  After (if still needed):
    */30 * * * 1-6 auto_categoria.py >> logs/auto_categoria.log 2>&1

EFFORT: 45 minutes (5 min per script + decision)
DECISION NEEDED: Ask Iago which scripts are still needed
```

### FIX 3: Document Missing Frequencies
```
STATUS: 3 scripts without documented crontab frequency

SCRIPTS:
  1. auto_time_tracking.py (appears in script list, no crontab)
  2. telegram_gemini_bot.py (appears in script list, no crontab)
  3. rotina_diaria.py (appears in script list, no crontab)

ACTION:
  1. Read each script (5 min per)
  2. Check for internal timing/frequency logic
  3. Document: Is it:
     a) Manual trigger only?
     b) Continuous daemon?
     c) Should be scheduled but isn't?

EFFORT: 20 minutes

RESULT: Update AUTOMATION_SCHEDULE.md with findings
```

### FIX 4: Remove Obsolete Scripts
```
STATUS: 2-3 scripts identified as probably obsolete

SCRIPTS:
  1. relatorio_assertividade.py (not in crontab)
  2. relatorio_vturb.py (not in crontab)
  3. relatorio_mensal_copywriters.py (found but not in documented list)

ACTION:
  1. Search git history: when was each last modified?
  2. Check: Are any of them referenced in other scripts?
  3. Decision:
     a) If obsolete: Move to /archive/ folder with date
     b) If needed: Document frequency in AUTOMATION_SCHEDULE.md

COMMAND:
  $ git log --oneline -- ~/Scripts/relatorio_assertividade.py | head -5
  $ grep -r "relatorio_assertividade" ~/Scripts/*.py
  $ git log --oneline -- ~/Scripts/relatorio_vturb.py | head -5
  $ grep -r "relatorio_vturb" ~/Scripts/*.py

EFFORT: 15 minutes
```

---

## 🎯 TIER 2: SHORT-TERM CONSOLIDATIONS (Week 1)

### CONSOLIDATION 1: Schedule auto_status_rt.py
```
STATUS: CRITICAL — Currently MANUAL only

PROBLEM:
  - auto_status_rt.py not in crontab
  - Runs MANUAL --preview/--execute modes
  - No automatic status updates from RedTrack
  - Status updates happen after reports (timing issue)

SOLUTION:
  Schedule for automatic daily execution

PROPOSED SCHEDULE:
  Option A: 3x daily (morning/midday/evening)
    0 06 * * * auto_status_rt.py --preview --report >> logs/auto_status_rt.log 2>&1
    0 12 * * * auto_status_rt.py --preview --report >> logs/auto_status_rt.log 2>&1
    0 18 * * * auto_status_rt.py --execute >> logs/auto_status_rt.log 2>&1
    (Preview at 6am/12pm, Execute at 6pm)
  
  Option B: Twice daily
    0 06 * * * auto_status_rt.py --execute >> logs/auto_status_rt.log 2>&1
    0 14 * * * auto_status_rt.py --execute >> logs/auto_status_rt.log 2>&1
    (Execute at 6am and 2pm)
  
  Option C: Once daily (conservative)
    0 06 * * * auto_status_rt.py --preview >> logs/auto_status_rt.log 2>&1
    0 07 * * * auto_status_rt.py --execute >> logs/auto_status_rt.log 2>&1
    (Preview at 6am, Execute at 7am — manual review in between)

RECOMMENDATION: Option B (2x daily, 6am and 2pm)
  - Frequent enough to catch ROAS changes
  - Not too frequent (unnecessary API calls)
  - Runs before daily reports (6am) and afternoon reports (2pm)

IMPLEMENTATION:
  1. Test: python3 auto_status_rt.py --preview
  2. If safe: Add to crontab
  3. Monitor: Check logs for first week
  4. Adjust: If issues, switch to different frequency

EFFORT: 30 minutes (testing + crontab edit)
PRIORITY: CRITICAL
```

### CONSOLIDATION 2: Version Tracking for cruzamento_clickup_redtrack.py
```
STATUS: CRITICAL — Possible race conditions

PROBLEM:
  - Bidirecitonal sync (ClickUp ↔ RedTrack)
  - No versioning/timestamps
  - Multiple scripts updating ClickUp simultaneously
  - Could lose data if updates collide

RACE CONDITION EXAMPLE:
  1. 10:00 — auto_status_rt updates task status
  2. 10:01 — cruzamento starts reading for report
  3. 10:02 — auto_etiqueta updates task labels
  4. 10:03 — cruzamento finishes report with stale data

SOLUTION: Add timestamp-based versioning

IMPLEMENTATION:
  1. Add to each ClickUp task (new Custom Field):
     - "last_updated_at": ISO8601 timestamp
     - "last_updated_by": script name
     - "data_version": integer (increments on each update)
  
  2. In update scripts (auto_status_rt, auto_etiqueta, etc):
     Before updating:
       - Read current timestamp
       - Compare with expected timestamp
       - If different: Log warning, skip update (or merge)
     After updating:
       - Write new timestamp
       - Increment version
  
  3. In read scripts (cruzamento, reports):
     - Log data version when reading
     - Include version in reports
     - Alert if version too old

DETAILED CHANGES:
  File: auto_status_rt.py
    Line ~150: Add timestamp write after status update
    Before: task.update({"status": new_status})
    After:
      task.update({
        "status": new_status,
        "last_updated_at": datetime.utcnow().isoformat(),
        "last_updated_by": "auto_status_rt",
        "data_version": current_version + 1
      })
  
  File: auto_etiqueta.py
    Similar changes for label updates
  
  File: cruzamento_clickup_redtrack.py
    Add version logging when reading:
      data_version = task.get("data_version")
      last_update_time = task.get("last_updated_at")
      logger.info(f"Data version: {data_version}, Last update: {last_update_time}")

TESTING:
  1. Simulate: Run auto_status_rt + auto_etiqueta simultaneously
  2. Check: Verify timestamps updated correctly
  3. Validate: No data loss or overwrites

EFFORT: 2-3 hours
PRIORITY: CRITICAL

DELIVERABLE:
  - Updated auto_status_rt.py with versioning
  - Updated auto_etiqueta.py with versioning
  - Updated cruzamento with version logging
  - Test script to verify no race conditions
```

### CONSOLIDATION 3: Unified Report Generator (MVP)
```
STATUS: HIGH — 5 reports from 2-3 data sources

PROBLEM:
  - relatorio_semanal_impera.py (production data)
  - relatorio_copywriters_semanal.py (copywriter breakdown)
  - relatorio_performance_copywriters_pdf.py (PDF version)
  - relatorio_entregas_trafego.py (traffic summary)
  - relatorio_performance_criativos.py (creative performance)

All read from ClickUp + RedTrack, generate similar data, different formats.

SOLUTION: Single parameterized script

FILE: unified_report_generator.py (NEW)

INTERFACE:
  python3 unified_report_generator.py \
    --report-type production \
    --format docx \
    --date-range weekly \
    --week 20

MODES:
  --report-type production   → Weekly production by copywriter
  --report-type performance  → Weekly performance by creative
  --report-type traffic      → Weekly traffic summary
  --report-type comprehensive → All the above

  --format docx              → Microsoft Word
  --format pdf               → PDF
  --format xlsx              → Excel
  --format all               → Generate all formats

  --date-range weekly        → Last 7 days
  --date-range monthly       → Last 30 days
  --date-range custom        → --start 2026-05-01 --end 2026-05-15

CRONTAB:
  # Unified report generator (replaces 5 scripts)
  # Weekly production (Sunday 12:00)
  0 12 * * 0 unified_report_generator.py --report-type production --format docx >> logs/reports.log 2>&1
  
  # Daily performance (Monday 08:30)
  0 8 * * 1 unified_report_generator.py --report-type performance --format docx >> logs/reports.log 2>&1
  
  # Weekly traffic (Sunday 13:00)
  0 13 * * 0 unified_report_generator.py --report-type traffic --format docx >> logs/reports.log 2>&1

IMPLEMENTATION STEPS:
  1. Create /reports_new/ directory for new consolidated script
  2. Read all 5 existing report generators (analyze data extraction logic)
  3. Identify common patterns:
     - Data query logic (same ClickUp + RedTrack API calls)
     - Grouping logic (by copywriter, by nicho, etc)
     - Formatting logic (table generation, styling)
  4. Create unified_report_generator.py:
     - Single data extraction function
     - Pluggable report types (production, performance, traffic)
     - Pluggable output formats (docx, pdf, xlsx)
  5. Test each mode against old reports:
     - Run with --format docx
     - Compare output with old relatorio_semanal_impera.py
     - Verify numbers match
  6. Parallel run (1 week):
     - Keep old 5 scripts running in parallel
     - Run new unified script
     - Compare outputs daily
     - Fix any discrepancies
  7. Cutover:
     - Remove 5 old scripts from crontab
     - Keep files for 1 month (archive)
     - Switch to new unified script

BENEFITS:
  - 5 scripts → 1 script
  - Single query to ClickUp/RedTrack
  - Consistent numbers across all reports
  - Easier to add new formats (e.g., HTML dashboard)
  - Clear versioning/audit trail

EFFORT: 4-5 hours (including testing)
PRIORITY: HIGH
```

### CONSOLIDATION 4: Unified Classifier (MVP)
```
STATUS: MEDIUM — 3 scripts doing similar work

PROBLEM:
  - auto_categoria.py (COMMENTED — auto-categorize)
  - auto_etiqueta.py (ACTIVE — auto-label)
  - classificador_criativos.py (ACTIVE — classify with logic)

Unclear separation of concerns. Possible conflicts.

SOLUTION: Single classifier script with pluggable rules

FILE: unified_classifier.py (NEW)

MODES:
  --check                   → Show what would be classified (no updates)
  --apply                   → Update ClickUp custom fields
  --audit                   → Check consistency, flag conflicts
  --force-recalculate       → Recalculate all creatives

CLASSIFICATION RULES:
  1. Nicho detection:
     - Parse campaign name from ClickUp custom field
     - Map to nicho (EM, DB, NE, etc.)
  
  2. Oferta classification:
     - Use nicho to determine likely oferta
     - Check if custom field "oferta" already set
     - Suggest or override
  
  3. Performance tier:
     - If linked to RedTrack campaign:
       - Calculate ROAS
       - Assign tier: EM_TESTE, VALIDADO, PRÉ-ESCALA, ESCALA
     - Else: Mark as AGUARDANDO_TRAFEGO
  
  4. QC score:
     - Count completed checkboxes in QC field
     - Assign: QC_FAIL (0-25%), QC_PARTIAL (25-75%), QC_PASS (75%+)

CRONTAB:
  # Unified classifier
  # Run every 3 hours (audit mode)
  0 */3 * * * unified_classifier.py --audit >> logs/classifier.log 2>&1
  
  # Apply classifications every 6 hours
  30 */6 * * * unified_classifier.py --apply --batch >> logs/classifier.log 2>&1

IMPLEMENTATION:
  1. Create unified_classifier.py (new file)
  2. Read all 3 existing classifier scripts
  3. Extract classification logic:
     - Nicho detection (from auto_categoria)
     - Labeling rules (from auto_etiqueta)
     - Performance tier assignment (from classificador_criativos)
  4. Consolidate into single rule engine:
     - Clear if-then rules
     - Pluggable custom logic
     - Logging of all decisions
  5. Test:
     - Run --audit mode, check for conflicts
     - Run --check mode, compare to old scripts
     - Run --apply on staging, verify ClickUp updates
  6. Deploy:
     - Uncomment auto_categoria (verify not in use)
     - Keep auto_etiqueta (will deprecate later)
     - Add unified_classifier to crontab

EFFORT: 3-4 hours
PRIORITY: MEDIUM (can defer to Phase 2)
```

---

## 📋 WEEK 1 CHECKLIST

### MONDAY (Day 1)

- [ ] Read AUTOMATION_SCHEDULE.md and AUTOMATION_DEPENDENCIES.md
- [ ] Identify obsolete scripts (relatorio_assertividade, relatorio_vturb)
- [ ] Document decision on commented scripts (auto_categoria, auto_healing, etc)
- [ ] Create git commit: "docs: update automation schedules and dependencies"

**Time Budget**: 2 hours

### TUESDAY (Day 2)

- [ ] Fix broken crontab entry (relatorio_semanal_producao.py)
- [ ] Document missing frequencies (auto_time_tracking, telegram_gemini)
- [ ] Remove obsolete scripts (move to /archive/)
- [ ] Update AUTOMATION_SCHEDULE.md with new findings
- [ ] Create git commit: "fix: remove obsolete scripts and fix crontab"

**Time Budget**: 1.5 hours

### WEDNESDAY (Day 3)

- [ ] Test auto_status_rt.py --preview (verify it works)
- [ ] Add auto_status_rt to crontab (2x daily: 6am and 2pm)
- [ ] Monitor logs for first day of automatic execution
- [ ] Create git commit: "automation: schedule auto_status_rt.py 2x daily"

**Time Budget**: 1 hour

### THURSDAY (Day 4)

- [ ] Begin versioning work on cruzamento_clickup_redtrack.py
- [ ] Add timestamp fields to ClickUp (new Custom Field)
- [ ] Update auto_status_rt.py to write timestamps
- [ ] Create test script to verify no race conditions
- [ ] Create git commit: "feature: add version tracking to status updates"

**Time Budget**: 2.5 hours

### FRIDAY (Day 5)

- [ ] Test versioning changes
- [ ] Fix any issues with timestamp logic
- [ ] Update AUTOMATION_DEPENDENCIES.md with completed work
- [ ] Plan unified_report_generator.py architecture
- [ ] Create git commit: "test: verify version tracking prevents race conditions"

**Time Budget**: 2 hours

---

## 📊 SUCCESS METRICS

### By End of Week 1:
- ✅ All 5 crontab entries fixed
- ✅ All frequencies documented (no "?" in AUTOMATION_SCHEDULE.md)
- ✅ auto_status_rt.py running automatically 2x daily
- ✅ Versioning system in place (timestamps + versions)
- ✅ Zero obsolete scripts in /Scripts/ directory
- ✅ Commented scripts clearly documented (will/won't be reactivated)

### By End of Week 2:
- ✅ Unified report generator tested (parallel run with old scripts)
- ✅ All 5 old report generators validated for deprecation
- ✅ Numbers match between old and new
- ✅ Crontab ready to switch to unified script
- ✅ All documentation updated

---

## 🚨 RISKS & MITIGATIONS

| Risk | Severity | Mitigation |
|------|----------|-----------|
| auto_status_rt conflicts with reports | HIGH | Versioning + timestamps prevents this |
| Unified generator produces wrong numbers | HIGH | Parallel run + compare for 1 week |
| Breaking crontab entry breaks something | MEDIUM | Verify file doesn't exist first |
| Commented scripts are still needed | MEDIUM | Ask Iago before removing |
| Race conditions in simultaneous updates | CRITICAL | Add mutex/versioning |

---

## 📝 Sign-off

**Phase**: 1 (Consolidation & Quick Fixes)  
**Duration**: Week 1-2  
**Effort**: ~15 hours  
**Expected Outcome**: Stable, documented, versioned automation system

**Next**: Phase 2 (Report & Classifier Consolidation) — Week 3

---

*This action plan is the foundation for IMPERA automation modernization.*
