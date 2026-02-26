# Documentation Cross-Reference & Consolidation Map

**Created:** 2026-02-27  
**Purpose:** Single reference showing how every planning/audit doc relates to MASTER_PLAN.md,
what's unique vs redundant, and what's been addressed.

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅ ADDRESSED | Work described in doc has been implemented in code |
| 🔁 REDUNDANT | Content fully covered by MASTER_PLAN.md (same scope, less detail) |
| 📎 DETAIL SOURCE | Has implementation detail that MASTER_PLAN references or needs |
| 🆕 UNIQUE | Content NOT in MASTER_PLAN — must remain active |
| 🗄️ ARCHIVE | Superseded by a newer doc — historical reference only |
| 📌 REFERENCE | Not an implementation plan — kept for diagnostic/design rationale |

---

## Category A: Move to `docs/finished/` (addressed or redundant)

### 1. `PERSISTENCE_FIX_CHANGELOG.md` → ✅ ADDRESSED
- **What:** S0–S4 persistence fixes (deterministic study_id, evidence UPSERT, indexes)
- **Status:** ALL items checked ✅. 13/13 tests passing.
- **Relation to MASTER_PLAN:** Pre-dates MASTER_PLAN; was a prerequisite.
- **Action:** Move to `docs/finished/`

### 2. `EXTRACTION_AUDIT_v2.md` (227 lines) → ✅ ADDRESSED + 🗄️ ARCHIVE
- **What:** P0–P9 + C1–C8 data quality audit for Cherrier/Campbell
- **Status:** P0–P9 all marked ✅ FIXED. C1–C8 partially addressed.
- **Relation to MASTER_PLAN:** Findings fed into DEEP_AUDIT → MASTER_PLAN Slice 1
- **Superseded by:** DEEP_AUDIT_FINDINGS.md (more thorough, more findings)
- **Action:** Move to `docs/finished/`

### 3. `PIPELINE_AUDIT.md` (981 lines) → 🗄️ ARCHIVE
- **What:** Original root-cause diagnosis (8 issues: BUG-001 to BUG-008)
- **Status:** Superseded by DEEP_AUDIT_FINDINGS.md (9 findings, 5 fatal, more precise diagnosis)
- **Relation to MASTER_PLAN:** MASTER_PLAN was built from DEEP_AUDIT, not this.
- **Superseded by:** DEEP_AUDIT_FINDINGS.md
- **Action:** Move to `docs/finished/`

### 4. `IMPLEMENTATION_SLICES.md` (1,341 lines) → 🗄️ ARCHIVE
- **What:** 9 slices from PIPELINE_AUDIT (edge unification, DB persistence, CSV template, etc.)
- **Status:** Some fixes applied manually; doc itself never tracked completion. 
- **Relation to MASTER_PLAN:** Same problem space as MASTER_PLAN Slices 1–2 but from older audit.
- **Superseded by:** MASTER_PLAN Slices 1–4 + DEEP_AUDIT fix plan
- **Action:** Move to `docs/finished/`

### 5. `REMEDIATION_PLAN.md` (989 lines) → 🔁 REDUNDANT
- **What:** 8 slices directly from DEEP_AUDIT findings (AG05, TB, ConceptEngine, evidence writer, P3, dedup, columns, DB safety)
- **Status:** Slice 2 (TB gate) → implemented as QA gates. Others partially addressed.
- **Relation to MASTER_PLAN:** MASTER_PLAN Slice 1 covers ALL 8 slices with the same + more detail.
- **Why redundant:** MASTER_PLAN Slice 1 was written AFTER this doc and incorporates its content.
- **Action:** Move to `docs/finished/`

### 6. `docs/IMPLEMENTATION_PLAN.md` (677 lines) → 🔁 REDUNDANT
- **What:** Fix evidence extraction data flow (AG05 → TB → P2 → P3)
- **Status:** Same scope as MASTER_PLAN Slice 1.
- **Relation to MASTER_PLAN:** MASTER_PLAN Slice 1 directly supersedes this.
- **Action:** Move to `docs/finished/`

### 7. `docs/gapmap.md` (310 lines) → 🗄️ ARCHIVE
- **What:** Early gap identification (4 consolidated gaps + 2 slices)
- **Status:** Very early doc, all gaps now covered by newer docs.
- **Superseded by:** Everything (DEEP_AUDIT, MASTER_PLAN, V2_DEFERRALS)
- **Action:** Move to `docs/finished/`

### 8. `docs/PERSISTENCE_GAP_REMEDIATION.md` (445 lines) → ✅ ADDRESSED
- **What:** DB persistence gap fixes
- **Status:** PERSISTENCE_FIX_CHANGELOG.md confirms all items S0–S4 complete.
- **Relation to MASTER_PLAN:** Pre-dates it; was prerequisite work.
- **Action:** Move to `docs/finished/`

### 9. `docs/PIMP_IMPLEMENTATION_PLAN.md` (v1, 733 lines) → 🗄️ ARCHIVE
- **What:** WP-1 to WP-8 annotation infrastructure
- **Status:** Superseded by v2 (PIMP_IMPLEMENTATION_PLAN_v2.md) which has WP-9, WP-10, WP-11 + refactored WP-3, WP-4, WP-8
- **Action:** Move to `docs/finished/`

---

## Category B: Keep Active (unique content, still needed)

### 10. `MASTER_PLAN.md` (1,864 lines) — 📌 PRIMARY PLAN
- **Status:** Slices 1–4 mostly ✅. Slice 5 unchecked. Slice 6 BLOCKED. R1–R5 unchecked.
- **Covers:** Critical path (data flow → edge deploy → algorithm bridge → vertical integration → SR/MA → F4 risk) + Routing (subtype enum → gates → MA lifecycle → aggregation → LLM guardrails)
- **GAPS in MASTER_PLAN** (detail in §Gaps below):
  - No annotation infrastructure detail (covered by PIMP v2)
  - No Cherrier-specific fix recipes (covered by CHERRIER_AUDIT_REMEDIATION)
  - No presentation layer improvements (covered by PRESENTATION_AUDIT_AND_IDEAS)
  - No deferred feature tracking (covered by V2_DEFERRALS)
  - No risk estimator §8 future components (covered by IMPLEMENTATION_PLAN_RISK_PERCENTAGE)

### 11. `DEEP_AUDIT_FINDINGS.md` (512 lines) — 📌 REFERENCE
- **What:** Root-cause diagnosis with DER criteria, 9 findings, cascading failure chain
- **Status:** Tier 1 fix plan DONE (QA gates). Tiers 2–4 referenced by MASTER_PLAN but detail lives here.
- **Why keep:** MASTER_PLAN Slice 1 says "fix these issues" but this doc explains WHY they're issues. Diagnostic reference.
- **Unique content:** DER criteria definitions, SE inflation decomposition chain, expert feedback integration
- **Cross-ref:** MASTER_PLAN Slice 1 → Findings 1–7 here. QA gates (Tier 1) → implemented in `qa_gate.py`.

### 12. `docs/CHERRIER_AUDIT_REMEDIATION.md` (1,069 lines) — 📎 DETAIL SOURCE
- **What:** 6 critical issues + 6 detailed fix plans for Cherrier 2013 golden path
- **Status:** Fix plans NOT yet implemented (code recipes exist but not applied)
- **Relation to MASTER_PLAN:** MASTER_PLAN Slice 1 references these issues generically. This doc has the EXACT code recipes:
  - Fix 1 (ConceptEngine context-aware mapping) → MASTER_PLAN §1.4
  - Fix 2 (within-study DCR) → MASTER_PLAN §1.3 partially
  - Fix 3 (F-stat df₁ parsing) → MASTER_PLAN §1.1 partially
  - Fix 4 (interaction tagging) → NOT in MASTER_PLAN
  - Fix 5 (study design propagation) → MASTER_PLAN §1.7
  - Fix 6 (n_effect propagation) → MASTER_PLAN §1.1 partially
- **Also unique:** Boundary gate framework (BG-01 to BG-07), golden-path integration test suite, priority order with dependency graph, SE inflation chain appendix

### 13. `docs/PIMP_IMPLEMENTATION_PLAN_v2.md` (1,130 lines) — 🆕 UNIQUE
- **What:** WP-1 to WP-11 annotation infrastructure with exact code recipes
- **NOT in MASTER_PLAN:**
  - WP-3: Wire P3 SE inflation from bias annotations
  - WP-4: EX-PROM chain (promotion monitor)
  - WP-5: Wire 13 remaining consumer read paths
  - WP-7: Database index optimization
  - WP-8: `structured_data_json` schema registry (AT-03)
  - WP-9: Annotation provenance traceability (NEW in v2)
  - WP-10: Contract integration test (NEW in v2)
  - WP-11: EX-PROM proposal sink (NEW in v2)
- **Partially in MASTER_PLAN:**
  - WP-1 → MASTER_PLAN R1 (subtype enum expansion covers some)
  - WP-2 → MASTER_PLAN Slice 2 (edge deployment covers annotation wiring partially)
  - WP-6 → MASTER_PLAN R1-R2 (paper-type profiles overlap with subtype enforcement)

### 14. `docs/IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md` (2,522 lines) — 📎 DETAIL SOURCE + 🆕 UNIQUE
- **What:** F4 risk estimator architecture + §8 future components + §9 output contracts
- **Relation to MASTER_PLAN:** Slice 6 says "BLOCKED, see IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md"
- **In MASTER_PLAN:** Only the existence of Slice 6 (F4 risk) — no implementation detail
- **NOT in MASTER_PLAN:**
  - §1–7: Full risk estimator architecture (risk_estimator.py is built from this)
  - §8.1: Subpopulation comparative risk
  - §8.2: Predictive risk under intervention
  - §8.3: Adaptive intensity scheduling
  - §8.4: Research heat map
  - §8.5: Cross-paper pattern detection
  - §8.6: Narrative compiler
  - §8.7: Extraction→Algorithm data bridge (partially overlaps MASTER_PLAN Slice 3)
  - §8.8: Clinical calibration pipeline
  - §8.9: Test-level ICCTF classification
  - §9: Output contract versioning
- **Note:** §8 items are also tracked in V2_DEFERRALS.md — so they have two reference points.

### 15. `docs/PRESENTATION_AUDIT_AND_IDEAS.md` (650 lines) — 🆕 UNIQUE
- **What:** Presentation layer audit — data lost at boundaries, unpopulated fields, improvement ideas
- **Relation to MASTER_PLAN:** Not mentioned or covered at all. MASTER_PLAN focuses on extraction→algorithm path.
- **Unique content:** PAT1–PAT5 + SCI1–SCI5 module audit, `RecommendationReport` bottleneck analysis, ranked improvement ideas

### 16. `docs/V2_DEFERRALS.md` (347 lines) — 🆕 UNIQUE
- **What:** Consolidated deferral tracker — all deferred/placeholder/gap items in one place
- **Relation to MASTER_PLAN:** MASTER_PLAN doesn't track deferred items.
- **Covers:** 33 deferred items across algorithm, extraction, presentation, infrastructure, data
- **Why keep:** Prevents items from falling through cracks across sessions.

### 17. `docs/CRITICAL_REVIEW.md` (263 lines) — 📌 REFERENCE
- **What:** System critique / honest assessment
- **Action:** Keep in `docs/` as reference

---

## Category C: Independent Workstream (not part of core pipeline)

### 18–22. DRAMA docs (5 files, ~3,500 lines total)
- `DRAMA_ADOPTION_ROADMAP.md` (1,286 lines)
- `DRAMA_PATTERNS_for_CRCI.md`
- `DRAMA_vs_CRCI_ANALYSIS.md`
- `DRAMA_ADOPTION_REVISED.md`
- `DRAMA_CRCI_QUICK_REF.md`
- **What:** DRAMA architectural patterns applied to CRCI
- **Relation to MASTER_PLAN:** Independent. DRAMA is a framework being evaluated for adoption.
- **Action:** Move to `docs/drama/` subfolder to declutter root

---

## MASTER_PLAN Coverage Gaps Summary

MASTER_PLAN is comprehensive for the **critical path** (Slices 1–6) and **routing** (R1–R5).
These areas are NOT covered and require separate active docs:

| Gap Area | Detail Source | Lines of Detail |
|----------|-------------|-----------------|
| Annotation infrastructure (WP-3 to WP-11) | `docs/PIMP_IMPLEMENTATION_PLAN_v2.md` | ~800 lines |
| F4 risk estimator architecture | `docs/IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md` §1–7 | ~1,500 lines |
| F4 future components (§8.1–8.9) | `docs/IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md` §8–9 | ~600 lines |
| Presentation layer improvements | `docs/PRESENTATION_AUDIT_AND_IDEAS.md` | 650 lines |
| Deferred features tracker | `docs/V2_DEFERRALS.md` | 347 lines |
| Cherrier fix recipes (code-level) | `docs/CHERRIER_AUDIT_REMEDIATION.md` §5 | ~450 lines |
| Interaction effect tagging (Fix 4) | `docs/CHERRIER_AUDIT_REMEDIATION.md` §5 Fix 4 | ~80 lines |
| Boundary gate framework (BG-01 to BG-07) | `docs/CHERRIER_AUDIT_REMEDIATION.md` §7 | ~120 lines |
| DRAMA patterns adoption | `DRAMA_ADOPTION_ROADMAP.md` + 4 related files | ~3,500 lines |

---

## Recommended Active Doc Set (post-consolidation)

After moving finished/archived/redundant docs, you should reference only these:

| Doc | Role | When to Read |
|-----|------|-------------|
| **MASTER_PLAN.md** | Primary implementation plan | Before any implementation work |
| **DEEP_AUDIT_FINDINGS.md** | Diagnostic reference | When debugging pipeline issues |
| **docs/PIMP_IMPLEMENTATION_PLAN_v2.md** | Annotation work packages | When implementing annotation features |
| **docs/IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md** | F4 risk architecture | When Slice 6 becomes unblocked |
| **docs/CHERRIER_AUDIT_REMEDIATION.md** | Cherrier fix recipes | When implementing MASTER_PLAN Slice 1 fixes |
| **docs/PRESENTATION_AUDIT_AND_IDEAS.md** | Presentation improvements | When working on presentation layer |
| **docs/V2_DEFERRALS.md** | Deferred features | Before starting new features (check if already tracked) |
| **docs/CRITICAL_REVIEW.md** | System critique | For context on design decisions |
| **EXTRACTION_PLAYBOOK.md** | Paper extraction procedure | When extracting a new paper |
| **EXTRACTION_LOG.md** | Extraction history | When extracting (avoid duplication) |

---

## File Moves Summary

### → `docs/finished/` (9 files)
```
PERSISTENCE_FIX_CHANGELOG.md
EXTRACTION_AUDIT_v2.md
PIPELINE_AUDIT.md
IMPLEMENTATION_SLICES.md
REMEDIATION_PLAN.md
docs/IMPLEMENTATION_PLAN.md
docs/gapmap.md
docs/PERSISTENCE_GAP_REMEDIATION.md
docs/PIMP_IMPLEMENTATION_PLAN.md  (v1, superseded by v2)
```

### → `docs/drama/` (5 files)
```
DRAMA_ADOPTION_ROADMAP.md
DRAMA_PATTERNS_for_CRCI.md
DRAMA_vs_CRCI_ANALYSIS.md
DRAMA_ADOPTION_REVISED.md
DRAMA_CRCI_QUICK_REF.md
```

### → Stay in place (active, 10+ files)
```
MASTER_PLAN.md
DEEP_AUDIT_FINDINGS.md
EXTRACTION_PLAYBOOK.md
EXTRACTION_LOG.md
PROGRESS.md
CLAUDE.md
README.md
docs/PIMP_IMPLEMENTATION_PLAN_v2.md
docs/IMPLEMENTATION_PLAN_RISK_PERCENTAGE.md
docs/PRESENTATION_AUDIT_AND_IDEAS.md
docs/V2_DEFERRALS.md
docs/CRITICAL_REVIEW.md
docs/CHERRIER_AUDIT_REMEDIATION.md
```
