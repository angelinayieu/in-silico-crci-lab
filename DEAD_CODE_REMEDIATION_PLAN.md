# Dead Code Remediation Plan

**Created:** 2026-02-26  
**Updated:** 2026-02-26 — **12 of 13 WPs completed** (WP-9 deferred as future milestone)  
**Source:** Front-to-end pipeline trace & import analysis  
**Total dead/unwired LOC:** ~4,311 (Categories 1–2), ~16,000 test-only (Categories 3–5)  
**Status:** 1051 tests passing, 0 failures (1 pre-existing NNT test excluded)

---

## How to Use This Document

Each work package (WP) is independent unless noted. Mark items ✅ as completed.
Before implementing any WP, re-read the referenced files to confirm the issue still exists.

---

## WP-1: Delete Truly Dead Code (3 items, ~664 LOC)

These modules have zero callers in production *and* tests.

### ✅ WP-1A: Delete `scripts/load_seeds.py` (0 LOC)
- **Problem:** Empty file. Superseded by `scripts/seed_database.py` and `scripts/load_seeds_sqlite.py`.
- **Action:** Delete the file.
- **Risk:** None.

### ✅ WP-1B: Delete `crci/retrieval/config.py` (84 LOC)
- **Problem:** Defines `RetrievalBudgetConfig` dataclass, but `acquisition_scheduler.py` reads budget constants directly from `crci/shared/config.py` instead.
- **Action (preferred):** Delete. The constants already live in `shared/config.py`.
- **Action (alternative):** If we want the typed-config pattern, make `acquisition_scheduler.py` instantiate `RetrievalBudgetConfig` and read from it. But this adds indirection for no gain.
- **Risk:** None — no caller exists.

### ✅ WP-1C: Wire `crci/extraction/promotion_monitor.py` (580 LOC)
- **Problem:** Fully implemented `EX-PROM` subsystem (ThresholdChecker, IndependenceValidator, ProposalGenerator). Designed as a daily cron job per spec lines 2014–2100. But no script or entry point ever invokes it.
- **Action:** Create `scripts/run_promotion_monitor.py` that calls `run_daily_promotion_check(session)` from this module. This is spec-required functionality.
- **Depends on:** Database must have `study_annotations_v1` rows with `maturity='reviewed'`.
- **Files to read before implementing:**
  - `crci/extraction/promotion_monitor.py` (full file)
  - `crci/extraction/p1_extraction/accumulation_checker.py` (related — per-paper accumulation vs daily cross-paper promotion)
- **Risk:** Low — self-contained module, just needs a CLI wrapper.

---

## WP-2: Wire Unwired Extraction Modules (4 items, ~2,136 LOC)

These are fully implemented spec modules that their documented callers never import.

### ✅ WP-2A: Wire `ag09_reconciliation.py` into P1 runner (636 LOC)
- **Problem:** P1 runner imports agents AG01–AG08, AG10, AG11 but **skips AG09** (ReconciliationAgent). The P1 runner calls `reconciliation.py` separately, which does its own reconciliation without using AG09's 7 span-level consistency checks.
- **Current flow:** AG01-AG08 → reconciliation.py (cross-agent consensus) → ATB
- **Intended flow:** AG01-AG08 → **AG09 (span-level checks)** → reconciliation.py → ATB
- **Action:** In `crci/extraction/p1_extraction/runner.py`, import and run AG09 after the main agents complete but before reconciliation. AG09 produces a `ReconcReport` that should feed into the reconciliation step or be logged/stored.
- **Files to read:**
  - `crci/extraction/p1_extraction/agents/ag09_reconciliation.py` — understand input/output types
  - `crci/extraction/p1_extraction/runner.py` lines 164–260 — agent execution + reconciliation call
  - `crci/extraction/p1_extraction/reconciliation.py` — see if it can accept AG09's ReconcReport
- **Risk:** Medium — AG09 may flag inconsistencies that cause downstream pipeline changes. Test the reconciliation flow end-to-end.

### ✅ WP-2B: Wire `conversion_executor.py` into P2 (881 LOC)
- **Problem:** `conversion_router.py` routes effect types and does inline conversion. `conversion_executor.py` contains the full conversion math engine (d↔r, OR↔d, etc.) that `conversion_router` should delegate to.
- **Action:** Determine if `conversion_router.py` already duplicates the math in `conversion_executor.py`. If so, refactor `conversion_router` to call `conversion_executor` functions. If the math differs, align to spec.
- **Files to read:**
  - `crci/extraction/p2_harmonization/conversion_executor.py` — all conversion formulas
  - `crci/extraction/p2_harmonization/conversion_router.py` — current inline conversions
  - Spec: `SYS_EXTRACTION_COMPLETE.md` P2 conversion section
- **Risk:** Medium — conversion math is critical for evidence quality. Changes here affect all downstream beta values.

### ✅ WP-2C: Wire `sd_standardization.py` into P2 (283 LOC)
- **Problem:** SD standardization module exists but P2 runner handles SD inline.
- **Action:** Check if P2 runner's inline SD handling duplicates this module. If so, refactor P2 runner to call `standardize_sd()` from this module.
- **Files to read:**
  - `crci/extraction/p2_harmonization/sd_standardization.py`
  - `crci/extraction/p2_harmonization/runner.py` — search for SD standardization logic
- **Risk:** Low — isolated computation.

### ✅ WP-2D: Wire `se_derivation_cascade.py` into P2 (336 LOC)
- **Problem:** SE derivation cascade module built but unused. P3's `se_eff_assembly.py` does SE derivation in the seven-layer model.
- **Action:** Check if `se_eff_assembly.py` Layer 1 (raw SE derivation) duplicates this module's cascade logic. If so, refactor Layer 1 to call this module. If not, determine if it should be called from P2 runner before P3.
- **Files to read:**
  - `crci/extraction/p2_harmonization/se_derivation_cascade.py`
  - `crci/extraction/p3_heterogeneity/se_eff_assembly.py` — especially Layer 1
- **Risk:** Low — SE derivation is well-specified.

---

## WP-3: Wire Unwired Algorithm Modules (2 items, ~1,007 LOC)

### ✅ WP-3A: Wire `observation_mapper.py` into chain C (569 LOC)
- **Problem:** Implements C2b–C2d formulas (observation noise, cancer SE multiplier, temporal decay). Docstring says "consumed by bayesian_update.py" but `bayesian_update.py` only imports `prior_loader` — never `observation_mapper`.
- **Action:** In `bayesian_update.py`, add a step that calls `observation_mapper.prepare_observations()` to transform raw observations into `PreparedObservation[]` before the Bayesian update loop.
- **Files to read:**
  - `crci/algorithm/chain_c_posterior/observation_mapper.py` — `PreparedObservation` type, `prepare_observations()` function
  - `crci/algorithm/chain_c_posterior/bayesian_update.py` — find where observations enter the update loop
  - Spec: `SYS_ALGORITHM_COMPLETE.md` lines 1862–1878
- **Risk:** Medium — changes the Bayesian update's input pipeline. Must verify observation noise formulas.

### ✅ WP-3B: Wire `posterior_writer.py` into chain C (438 LOC)
- **Problem:** Designed to write posterior distributions to DB after Bayesian update completes. Never called.
- **Action:** After `bayesian_update.py` produces posteriors, call `posterior_writer.write_posteriors()` to persist them. This enables the runtime to read posteriors from DB instead of recomputing.
- **Files to read:**
  - `crci/algorithm/chain_c_posterior/posterior_writer.py` — `write_posteriors()` function signature
  - `crci/algorithm/chain_c_posterior/bayesian_update.py` — where posteriors are produced
- **Risk:** Low — additive (persistence), doesn't change computation.

---

## ✅ WP-4: Wire `cost_tracker.py` into LLM Client (173 LOC)

- **Problem:** `crci/llm/cost_tracker.py` implements CSV-based LLM cost logging. Its docstring says "used by client.py and pipeline.py" but neither imports it.
- **Action:** In `crci/llm/client.py`, after each LLM call, log the usage via `CostTracker.log_call()`. This gives visibility into extraction costs.
- **Files to read:**
  - `crci/llm/cost_tracker.py` — `CostTracker` class, `log_call()` method
  - `crci/llm/client.py` — find the main `call()` / `complete()` method
- **Risk:** Very low — additive logging only.

---

## ✅ WP-5: Wire `pathway_evidence_auditor.py` (330 LOC)

- **Problem:** Fully implemented pathway evidence auditor with no callers.
- **Action:** Determine intended call site. Likely should be called from `scripts/run_acquisition.py` or as part of the retrieval cycle to audit pathway evidence gaps.
- **Files to read:**
  - `crci/retrieval/pathway_evidence_auditor.py` — understand inputs/outputs
  - `crci/retrieval/acquisition_scheduler.py` — find where gap analysis fits
- **Risk:** Low — read-only auditing module.

---

## ✅ WP-6: Create Full Model Orchestration Script (~new, ~450 LOC)

**This is the single biggest gap.** No production script chains A→B→C→D→E→F→session together.

- **Problem:** `run_build.py` stops after chain B (producing `FrozenModelState`). `run_session.py` expects pre-computed `RankingResult`, `CompositeState`, etc. as inputs. The ~15,000 LOC in chains C–F is tested but has **no production orchestration**.
- **Action:** Create `scripts/run_full_model.py` that:
  1. Runs chain A → `GraphObject`
  2. Runs chain B → `FrozenModelState`
  3. Runs chain C (prior_loader → observation_mapper → bayesian_update → posterior_writer) → posteriors
  4. Runs chain D (intervention_loader → effect_propagation → mc_sampler → safety_checker → ranker → synergy_bundle) → `RankingResult`
  5. Runs chain E (nadir_estimator → recovery_trajectory → intervention_overlay → uncertainty_counterfactual) → temporal results
  6. Runs chain F (composite_scorer → variance_decomposer → evsi → risk_estimator → temporal_risk) → analytics
  7. Calls `run_session()` with all computed inputs → `RecommendationReport`
- **Files to read before implementing:**
  - `scripts/run_build.py` — existing A→B orchestration pattern
  - `scripts/run_session.py` — existing session invocation pattern
  - `crci/algorithm/chain_c_posterior/bayesian_update.py` — chain C entry point
  - `crci/algorithm/chain_d_simulation/ranker.py` — chain D entry point
  - `crci/algorithm/chain_e_temporal/recovery_trajectory.py` — chain E entry point
  - `crci/algorithm/chain_f_analytics/composite_scorer.py` — chain F entry point
  - `crci/runtime/session.py` — `run_session()` full signature
- **Risk:** High — this is the integration layer. Each chain boundary must be verified for type compatibility.
- **Testing:** Run with the 8 existing evidence rows (Cherrier 2013 + Campbell 2017).

---

## ✅ WP-7: Wire `risk_dashboard.py` into Presentation Layer (262 LOC)

- **Problem:** `crci/presentation/risk_dashboard.py` is an F4-specific risk view. Unlike the other 10 presentation modules (which are at least imported by tests), `risk_dashboard.py` is imported by **nothing** — not even tests.
- **Action:** Create `crci/tests/test_presentation/test_risk_dashboard.py` with basic tests, matching the pattern of other presentation test files. Optionally, ensure it's reachable from a future web integration point.
- **Files to read:**
  - `crci/presentation/risk_dashboard.py`
  - `crci/tests/test_presentation/test_crci_dashboard.py` — test pattern to follow
- **Risk:** Very low.

---

## ✅ WP-8: Wire Runtime Evidence Gap & Pathway Profiler (functionally inert)

- **Problem:** `evidence_gap_compiler.py` and `pathway_profiler.py` define builder functions, and their output types flow through `session.py` → `report_assembler.py` — but the builder functions are never called. `run_session.py` always passes `None` for `evidence_gap_report` and `pathway_profile`.
- **Action:** In `scripts/run_session.py` (or `run_full_model.py` from WP-6), construct `EvidenceGapReport` from the `FrozenModelState` edge coverage, and `PathwayProfile` from chain A's pathway data. Pass these into `run_session()`.
- **Files to read:**
  - `crci/runtime/evidence_gap_compiler.py` — `compile_evidence_gaps()` signature
  - `crci/runtime/pathway_profiler.py` — `build_pathway_profile()` signature
  - `crci/runtime/session.py` — parameter names for these inputs
- **Risk:** Low — additive, populates already-wired report sections.
- **Depends on:** WP-6 (or modify `run_session.py` standalone).

---

## WP-9: Wire Presentation Layer to Production (11 modules, ~3,200 LOC)

- **Problem:** All 11 presentation modules are imported only by tests. No production script or web framework calls them.
- **Action:** This is a **future milestone**, not a bug. The presentation modules produce data structures (views/summaries) that need a renderer (web framework, CLI formatter, or Jupyter integration). Options:
  1. Create `scripts/generate_report.py` — CLI tool that runs presentation modules and outputs JSON/HTML
  2. Create a minimal FastAPI/Streamlit app that serves the views
  3. Create Jupyter notebook integration
- **Priority:** Lower than WP-1 through WP-8. These modules work correctly in tests.
- **Risk:** Low — modules are render-only, no computation or DB writes.

---

## Implementation Priority Order

| Priority | WP | Effort | Impact |
|----------|-----|--------|--------|
| 1 | **WP-6** | High (~200 LOC new) | **Critical** — unlocks 15K LOC of algorithm code |
| 2 | **WP-3A** | Medium (~30 LOC edits) | Fixes chain C observation pipeline |
| 3 | **WP-3B** | Low (~15 LOC edits) | Enables posterior persistence |
| 4 | **WP-8** | Medium (~40 LOC edits) | Populates report evidence gaps + pathway profile |
| 5 | **WP-2A** | Medium (~30 LOC edits) | Enables AG09 span-level consistency checks |
| 6 | **WP-2B** | Medium (~50 LOC edits) | Consolidates conversion math (may be refactor only) |
| 7 | **WP-2C** | Low (~20 LOC edits) | Consolidates SD standardization |
| 8 | **WP-2D** | Low (~20 LOC edits) | Consolidates SE derivation |
| 9 | **WP-4** | Low (~10 LOC edits) | Adds cost tracking visibility |
| 10 | **WP-5** | Low (~20 LOC edits) | Adds pathway evidence auditing |
| 11 | **WP-1** | Trivial (delete) | Removes dead weight |
| 12 | **WP-7** | Low (~50 LOC new) | Test coverage for risk dashboard |
| 13 | **WP-9** | High (new app) | Future milestone — presentation rendering |

---

## Verification After Each WP

After completing each WP:
1. Run `python -m pytest crci/tests/ -x -q` — all 1002+ tests must pass
2. For WP-6: run the full model end-to-end with existing evidence
3. For WP-2/3: verify upstream/downstream type compatibility
4. Update this document: mark the WP as ✅ and note any issues found
