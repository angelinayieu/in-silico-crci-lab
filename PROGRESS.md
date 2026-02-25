# CRCI Build Progress Tracker

## Current Position
- **Phase:** 7 (Integration + CLI Scripts) — COMPLETE
- **Prompt:** 7.2 completed (End-to-End Test)
- **Last completed slice:** V-FINAL review round 3
- **Next:** CODE COMPLETE — all spec phases implemented and reviewed
- **Branch:** `claude/extraction-algorithm-phase-one-iT9pH`
- **Total tests:** 720 passing

## Review Summary
- **Round 1:** Fixed SchedulePlan missing `warnings` field, fixed freshness decay test ref year mismatch (3 pre-existing failures fixed)
- **Round 2:** Migrated 7 hardcoded constants to config.py (dose multipliers, safety thresholds, report assembly defaults). Import coherence verified clean.
- **Round 3 (V-FINAL):** Import coherence audit (all valid), hardcode scan (clean), wiring audit (fixed 3 config constant name mismatches in CLI scripts: `SPECTRAL_RADIUS_THRESHOLD`→`MAX_SPECTRAL_RADIUS`, `CONDITION_NUMBER_WARN`→`CONDITION_NUMBER_WARNING`, `spectral_radius`→`spectral_radius_B`). Consolidated duplicate sqlalchemy imports in validate_deployment_readiness.py.

## Completed Slices (this phase)

### ALG-C (Chain C: Patient State Inference) — COMPLETE
| Slice | File | Commit | Status |
|-------|------|--------|--------|
| C1 | `chain_c_posterior/prior_loader.py` | `efad7cf` | DONE |
| C2 | `chain_c_posterior/observation_mapper.py` | `bfc30b5` | DONE |
| C3 | `chain_c_posterior/bayesian_update.py` | `e98967c` | DONE |
| C4 | `chain_c_posterior/modifier_application.py` | `c33b52e` | DONE |
| C5 | `chain_c_posterior/posterior_writer.py` | `988866a` | DONE |

### ALG-D (Chain D: Monte Carlo Simulation) — COMPLETE
| Slice | File | Commit | Status |
|-------|------|--------|--------|
| D0 | `chain_d_simulation/intervention_loader.py` | `e5a09a4` | DONE |
| D1 | `chain_d_simulation/mc_sampler.py` | `f74ee6a` | DONE |
| D2 | `chain_d_simulation/effect_propagation.py` | `0c434ce` | DONE |
| D3 | `chain_d_simulation/safety_checker.py` | `610c101` | DONE |
| D3-syn | `chain_d_simulation/synergy_bundle.py` | `2b3e83f` | DONE |
| D4-D6 | `chain_d_simulation/ranker.py` | `1e262f3` | DONE |

### ALG-E (Chain E: Temporal Prediction) — COMPLETE
| Slice | File | Commit | Status |
|-------|------|--------|--------|
| E1 | `chain_e_temporal/nadir_estimator.py` | `003689c` | DONE |
| E2 | `chain_e_temporal/recovery_trajectory.py` | `c8d6032` | DONE |
| E3 | `chain_e_temporal/intervention_overlay.py` | `689f657` | DONE |
| E4 | `chain_e_temporal/uncertainty_counterfactual.py` | `a8b05c9` | DONE |

### ALG-F (Chain F: Analytics) — COMPLETE
| Slice | File | Commit | Status |
|-------|------|--------|--------|
| F1 | `chain_f_analytics/composite_scorer.py` | `fa03c48` | DONE |
| F2 | `chain_f_analytics/variance_decomposer.py` | `5ef92b4` | DONE |
| F3 | `chain_f_analytics/evsi.py` | `ad9b4c2` | DONE |

### Phase 6: Runtime — COMPLETE
| Slice | File | Commit | Status |
|-------|------|--------|--------|
| RT-G | `runtime/schedule_generator.py` | `07f2ee2` | DONE (30 tests) |
| RT-H | `runtime/adaptive_questions.py` | `1775b20` | DONE (33 tests) |
| RT-I | `runtime/report_assembler.py` | `34b287a` | DONE (18 tests) |
| RT-S | `runtime/session.py` | `61cb7a0` | DONE (6 tests) |

### Phase 6: Presentation — COMPLETE
| Slice | File | Commit | Status |
|-------|------|--------|--------|
| PR-1 | `presentation/crci_dashboard.py` | `1d9fc39` | DONE (13 tests) |
| PR-2 | `presentation/intervention_cards.py` | `1d9fc39` | DONE (7 tests) |
| PR-3 | `presentation/trajectory_plot.py` | `1d9fc39` | DONE (12 tests) |
| PR-4 | `presentation/variance_pie.py` | `1d9fc39` | DONE (9 tests) |
| PR-5 | `presentation/dag_viz.py` | `1d9fc39` | DONE (5 tests) |
| PR-6 | `presentation/evidence_browser.py` | `1d9fc39` | DONE (8 tests) |
| PR-7 | `presentation/provenance_viewer.py` | `1d9fc39` | DONE (7 tests) |

### Phase 7: CLI Scripts + End-to-End — COMPLETE
| Slice | File | Commit | Status |
|-------|------|--------|--------|
| 7.1-a | `scripts/run_build.py` | `ca6545a` | DONE |
| 7.1-b | `scripts/run_session.py` | `ca6545a` | DONE |
| 7.1-c | `scripts/seed_database.py` | `ca6545a` | DONE |
| 7.1-d | `scripts/validate_model.py` | `ca6545a` | DONE |
| 7.1-e | `scripts/validate_deployment_readiness.py` | `ca6545a` | DONE |
| 7.2 | `tests/test_end_to_end/test_full_pipeline.py` | `ca6545a` | DONE (20 tests) |

### Review Fixes
| Fix | Commit | Status |
|-----|--------|--------|
| SchedulePlan.warnings + freshness decay test fix | `847a0b1` | DONE |
| Hardcode migration to config.py (7 constants) | `7e976be` | DONE |

## Known Limitations (Not Yet Populated)
These RecommendationReport fields are defined but not yet populated by report_assembler.py, because their upstream data sources don't exist yet:
- `trajectories` — needs ALG-E temporal trajectory builder integration
- `evidence_gaps` — needs extraction pipeline evidence gap compilation
- `pathway_profile` — needs ALG pathway activation computation

All presentation modules handle these gracefully with empty-state views.

## Slice Implementation Protocol

For each slice, execute this cycle:

### 1. CONTEXT GATHERING
- Read `PROGRESS.md` → identify next slice
- Read `FILE_CONTEXT_MANIFEST.md` → find spec lines, formulas, gates, dependencies
- Read the EXACT spec lines referenced
- Read ALL upstream files that produce this slice's input types
- Read `config.py` for existing constants
- Read the downstream consumers (what will read YOUR output)

### 2. PLAN
State explicitly:
- What this file receives (types + which file produces them)
- What this file outputs (types + which file consumes them)
- Which formulas (by ID)
- Which gates (by ID)
- Which config constants needed (existing + new)

### 3. IMPLEMENT
- Add any new config constants to `config.py`
- Create the implementation file
- Follow all 12 enforcement rules from CODE_QUALITY_ENFORCEMENT.md

### 4. TEST
- Create `tests/test_algorithm/test_*.py`
- Hand-computable expected values for each formula
- Edge cases and gate violation tests
- Verify constants come from config (not hardcoded)

### 5. VERIFY
- Hardcode scan (grep for float literals)
- Formula accuracy (character-by-character vs spec)
- Backward coherence (input types match upstream output)
- Forward coherence (output types match what downstream needs)
- Gate enforcement (raises on failure)

### 6. COMMIT & UPDATE
- `git add` + `git commit` with descriptive message
- `git push -u origin <branch>`
- Update THIS FILE (PROGRESS.md): mark slice DONE, advance "Next slice"

### 7. AUTO-CONTINUE
- Immediately begin the next slice (step 1) without waiting for user input
- Continue until all slices in current chain are done
- At chain boundary, report summary and continue to next chain

## Key Architectural Patterns
- Each chain subsystem defines its own output dataclass locally
- All formulas use `config.py` constants, never hardcoded numbers
- Gates raise `GateViolation`, never just log
- `scipy.linalg.cholesky` for numerical stability
- Verification stamp headers on every file
- Mock session pattern for testing DB-writing code
- Common random numbers for MC reproducibility

## Key Type Dependencies (upstream → downstream)
```
FrozenModelState (chain_b) → MCDraws (D1) → EffectResult (D2) → SafetyResult (D3) → RankingResult (D4-D6)
PatientState (chain_c) ──────↗         ↗
InterventionSet (D0) ──────────────────↗

RankingResult (D4-D6) ──→ RankedSchedules (RT-G) ──→ RecommendationReport (RT-I) ──→ SYS_PRESENTATION
CompositeState (F1) ───────────────────────────────↗
StabilityState (F2) ───────────────────────────────↗
VarianceState (F3) ────────────────────────────────↗
```
