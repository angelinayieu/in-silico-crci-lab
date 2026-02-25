# CRCI Build Progress Tracker

## Current Position
- **Phase:** 5 (Algorithm Chains)
- **Prompt:** 5.6 (ALG-F: Analytics)
- **Last completed slice:** E4 (uncertainty_counterfactual.py)
- **Next slice:** F1 (composite_scorer.py)
- **Branch:** `claude/extraction-algorithm-phase-one-iT9pH`
- **Latest commit:** `a8b05c9` — feat: Implement ALG-E4 uncertainty_counterfactual.py

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

### ALG-F (Chain F: Analytics) — IN PROGRESS
| Slice | File | Commit | Status |
|-------|------|--------|--------|
| F1 | `chain_f_analytics/composite_scorer.py` | — | **NEXT** |
| F2 | `chain_f_analytics/variance_decomposer.py` | — | PENDING |
| F3 | `chain_f_analytics/evsi.py` | — | PENDING |

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
```
