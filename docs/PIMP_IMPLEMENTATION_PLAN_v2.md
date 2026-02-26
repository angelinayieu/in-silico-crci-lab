# PIMP Gap Implementation Plan — v2 (Post-Audit Revision)

> **PIMP** = Paper Intelligence Maximization Protocol
> **Purpose:** Step-by-step plan to close every remaining gap in annotation
> infrastructure, verified against actual codebase state and EX-PROM spec.
>
> **v2 Changes from v1:** Incorporates infrastructure re-audit findings:
> - WP-2 (P4 runner wiring) is **partially complete** — `_load_annotations_for_edges()`
>   exists and feeds `annotations_by_edge` to `analyze_all_edges()`, BUT
>   `annotation_ids_map` is NOT passed to `build_compilation_inputs()`.
> - WP-4 restructured as **EX-PROM chain** (per spec L2014-2100), NOT a lifecycle hook.
> - Added WP-9 (annotation provenance traceability), WP-10 (contract integration test),
>   and WP-11 (EX-PROM proposal sink) based on discovered infrastructure gaps.
> - WP-3 refactored to use shared `annotation_features.py` module to avoid
>   import cycles and prevent P3↔P4 circular dependencies.
> - WP-8 refactored to use schema registry pattern instead of if/elif chain.

---

## Infrastructure State (as of this audit)

### What's Already Working
- `_load_annotations_for_edges()` in [runner.py](../crci/extraction/p4_aggregation/runner.py#L257) EXISTS and is called at L148
- `annotations_by_edge` IS passed to `analyze_all_edges()` — σ²_structural + p_inclusion code paths are LIVE
- `EdgeCompilationInput` HAS `annotation_source_ids` field and it flows to `notes` JSON
- Trust boundary reject gates (QA-1 through QA-5) are functional in `qa_gate.py`
- Annotation trust boundary (AT-01 through AT-06) enforced in `annotation_trust_boundary.py`
- `get_sigma_structural_annotations()`, `get_se_inflation_annotations()`, `get_safety_annotations()`, `get_acquisition_annotations()` all exist in `annotation_lifecycle.py`

### What's NOT Working (Gaps Being Closed)
1. `annotation_ids_map` never built or passed to `build_compilation_inputs()` → annotation IDs always `[]` in compiled edges
2. `edge_param_builds_v1` table MISSING dedicated `annotation_source_ids_json` column (spec SYS_EX L2668)
3. P3 `se_eff_assembly.py` L225 always uses `config.SIGMA_SQ_STRUCTURAL_DEFAULT` — never annotation-informed
4. 5 protocol annotation categories not in enum
5. 13 of 16 consumer read paths dead (query functions exist but consuming modules don't call them)
6. No cross-paper accumulation logic (EX-PROM chain not implemented)
7. No paper-type annotation profiles

---

## Status Key

| Symbol | Meaning |
|--------|---------|
| `[ ]`  | Not started |
| `[~]`  | In progress |
| `[x]`  | Done |

---

## WP-1: Add Missing Annotation Categories (5 new enum members)

**Risk:** Low — additive enum change, no existing code breaks.
**Files to modify:** 3 files + 2 prompt templates
**Estimated scope:** ~80 lines changed

> **v2 note:** Added Task 1.8 (ATB schema validation for new categories)
> to prevent agents from emitting poorly structured new-category annotations.
> New categories without exemplars and schema checks dilute precision.

### Task 1.1 — Add 5 enum members to `AnnotationCategory`

**File:** `crci/shared/models/enums.py` lines 1196–1217
**Action:** Insert 5 new members after `CROSS_VALIDATION` (line 1217):

```python
# ── Protocol §3.3 additions (PIMP gap closure) ──
MODEL_DIAGNOSTIC = "model_diagnostic"            # Statistical model fit / assumption violations
MECHANISM_INTERACTION = "mechanism_interaction"   # Interaction between two mechanisms
TEMPORAL_DECAY = "temporal_decay"                 # Observed decay/detraining timing
TEMPORAL_TRAJECTORY = "temporal_trajectory"       # Trajectory class (recovery, plateau, decline)
METHODOLOGICAL_INNOVATION = "methodological_innovation"  # Novel method/instrument/technique
```

**Post-check:** Update the class docstring count from "22 annotation categories" → "27 annotation categories".

### Task 1.2 — Add promotion rules for 5 new categories

**File:** `crci/extraction/p1_extraction/annotation_lifecycle.py` lines 64–251
**Action:** Add 5 new entries to the `PROMOTION_RULES` dict:

| Category | Consumer | `min_confidence` | `min_cross_agent_n` | `auto_promote` |
|----------|----------|-------------------|----------------------|----------------|
| `MODEL_DIAGNOSTIC` | `"quality_assessment"` | `PROM_CONFIDENCE_MEDIUM` | `PROM_CROSS_AGENT_DEFAULT` | `True` |
| `MECHANISM_INTERACTION` | `"synergy_model"` | `PROM_CONFIDENCE_MEDIUM_HIGH` | `PROM_CROSS_AGENT_HIGH_IMPACT` | `False` |
| `TEMPORAL_DECAY` | `"temporal_kernel"` | `PROM_CONFIDENCE_MEDIUM` | `PROM_CROSS_AGENT_DEFAULT` | `True` |
| `TEMPORAL_TRAJECTORY` | `"recovery_model"` | `PROM_CONFIDENCE_MEDIUM` | `PROM_CROSS_AGENT_DEFAULT` | `True` |
| `METHODOLOGICAL_INNOVATION` | `"pipeline_evolution"` | `PROM_CONFIDENCE_LOW` | `PROM_CROSS_AGENT_DEFAULT` | `True` |

### Task 1.3 — Add consumer mappings for 5 new categories

**File:** `crci/extraction/p1_extraction/annotation_trust_boundary.py` lines 397–421
**Action:** Add 5 entries to `category_consumer_map` in `_determine_consumer()`:

```python
AnnotationCategory.MODEL_DIAGNOSTIC: "quality_assessment",
AnnotationCategory.MECHANISM_INTERACTION: "synergy_model",
AnnotationCategory.TEMPORAL_DECAY: "temporal_kernel",
AnnotationCategory.TEMPORAL_TRAJECTORY: "recovery_model",
AnnotationCategory.METHODOLOGICAL_INNOVATION: "pipeline_evolution",
```

### Task 1.4 — Update AG10 prompt template with new categories

**File:** `crci/llm/prompts/ag10_strategic_intel.txt`
**Action:** Add `model_diagnostic`, `mechanism_interaction`, `temporal_decay`,
`temporal_trajectory`, `methodological_innovation` to the "valid category" list
in the prompt. Include 1-2 exemplars per category so the LLM knows what
concrete emissions look like. Without exemplars, yield will be near-zero.

### Task 1.5 — Update AG02 (DesignAgent) to emit `model_diagnostic`

**File:** `crci/extraction/p1_extraction/agents/ag02_design.py`
**Action:** Add `AnnotationCategory.MODEL_DIAGNOSTIC` to the set of categories
this agent emits (alongside existing `limitation_design`). The agent reads Methods
sections and already identifies design issues — model diagnostic annotations
(heteroscedasticity, assumption violations) are a natural extension.

### Task 1.6 — Update AG08 (TemporalAgent) to emit `temporal_decay` + `temporal_trajectory`

**File:** `crci/extraction/p1_extraction/agents/ag08_temporal.py`
**Action:** AG08 already reads Methods/Results for temporal patterns. Add
`TEMPORAL_DECAY` and `TEMPORAL_TRAJECTORY` to its emission set alongside
existing `TEMPORAL_ONSET`.

### Task 1.7 — Update AG07 (MediatorAgent) to emit `mechanism_interaction`

**File:** `crci/extraction/p1_extraction/agents/ag07_mediator.py`
**Action:** AG07 already emits `MECHANISM_HYPOTHESIS`. Add `MECHANISM_INTERACTION`
for when two pathways are observed to interact.

### Task 1.8 — Add AT-03 schema validation for new categories (v2 addition)

**File:** `crci/extraction/p1_extraction/annotation_trust_boundary.py`
**Function:** `_check_at03_category_fields()`
**Action:** Define required `structured_data_json` fields for each new category
BEFORE enabling agent emission. This prevents garbage annotations from
passing the trust boundary:

```python
# MODEL_DIAGNOSTIC: must specify which model assumptions were violated
elif category == AnnotationCategory.MODEL_DIAGNOSTIC:
    diagnostic_type = data.get("diagnostic_type")
    if diagnostic_type not in ("heteroscedasticity", "normality_violation",
                                "multicollinearity", "model_misspecification",
                                "assumption_violation"):
        return ATBRejection(rule="AT-03", ...)

# TEMPORAL_DECAY: must have decay_half_life_weeks
elif category == AnnotationCategory.TEMPORAL_DECAY:
    if data.get("decay_half_life_weeks") is None:
        return ATBRejection(rule="AT-03", ...)

# TEMPORAL_TRAJECTORY: must specify trajectory_class
elif category == AnnotationCategory.TEMPORAL_TRAJECTORY:
    tclass = data.get("trajectory_class")
    if tclass not in ("recovery", "plateau", "decline", "oscillating", "delayed_onset"):
        return ATBRejection(rule="AT-03", ...)

# MECHANISM_INTERACTION: must specify both pathway IDs
elif category == AnnotationCategory.MECHANISM_INTERACTION:
    if not data.get("pathway_id_a") or not data.get("pathway_id_b"):
        return ATBRejection(rule="AT-03", ...)

# METHODOLOGICAL_INNOVATION: must describe the innovation
elif category == AnnotationCategory.METHODOLOGICAL_INNOVATION:
    if not data.get("innovation_description"):
        return ATBRejection(rule="AT-03", ...)
```

**Verification checklist for WP-1:**
- [ ] All 27 enum members parse correctly: `AnnotationCategory("model_diagnostic")` works
- [ ] All 27 categories have a `PROMOTION_RULES` entry
- [ ] All 27 categories have a `_determine_consumer` mapping
- [ ] AG10 prompt lists all 27 categories with exemplars
- [ ] AT-03 rejects malformed new-category annotations
- [ ] `python -c "from crci.shared.models.enums import AnnotationCategory; print(len(AnnotationCategory))"` → 27

---

## WP-2: Complete P4 Runner Annotation Provenance Wiring

**Risk:** Medium — the hardest single gap.
**Files to modify:** 1 file
**Estimated scope:** ~25 lines added

> **v2 finding:** WP-2 is actually **70% done**. The `_load_annotations_for_edges()`
> function exists at `runner.py:257` and is called at L148. `annotations_by_edge`
> IS passed to `analyze_all_edges()`. The σ²_structural and p_inclusion code
> paths in `meta_analyzer.py` are LIVE when annotations exist in the DB.
>
> **Remaining gap:** `annotation_ids_map` is NOT built or passed to
> `build_compilation_inputs()` at L230. So annotation IDs never reach
> `EdgeCompilationInput.annotation_source_ids` → provenance trail is broken.

### Task 2.1 — Build `annotation_ids_map` from `annotations_by_edge` and pass it

**File:** `crci/extraction/p4_aggregation/runner.py` around line 228
**Current code (L228-234):**
```python
    compilation_inputs = build_compilation_inputs(
        pooled_estimates=pooled_estimates,
        prior_specs=prior_specs,
        prior_logs=prior_logs,
        sigma_sq_map=sigma_sq_map,
    ) if prior_specs else []
```

**Action:** Build `annotation_ids_map` from the already-loaded `annotations_by_edge`
and pass it through:

```python
    # Build annotation ID map for provenance traceability
    annotation_ids_map: dict[str, list[str]] = {
        edge_id: [rec.annotation_id for rec in recs]
        for edge_id, recs in annotations_by_edge.items()
        if recs
    }

    compilation_inputs = build_compilation_inputs(
        pooled_estimates=pooled_estimates,
        prior_specs=prior_specs,
        prior_logs=prior_logs,
        sigma_sq_map=sigma_sq_map,
        annotation_ids_map=annotation_ids_map,
    ) if prior_specs else []
```

This is ~8 lines of code. The `build_compilation_inputs()` signature already
accepts `annotation_ids_map` (see `edge_writer.py:480`), and it already passes
it through to `EdgeCompilationInput.annotation_source_ids` (see L575).

**Verification:**
- [ ] After running P4, `edge_param_builds_v1.notes` JSON contains non-empty
      `annotation_source_ids_json` when annotations exist
- [ ] Unit test: mock DB with sigma_structural annotations → verify
      `EdgeCompilationInput.annotation_source_ids` is populated

---

## WP-3: Wire P3 SE Inflation from Bias Annotations

**Risk:** Medium — modifies the seven-layer SE pipeline.
**Files to modify:** 2 files + 1 new shared module
**Estimated scope:** ~60 lines

> **v2 refactor:** Instead of P3 importing directly from P4's `meta_analyzer.py`
> (which creates P3→P4 import dependency while P4 runs AFTER P3), create a shared
> `annotation_features.py` module that both P3 and P4 can import. This module
> holds the query + computation logic for annotation-derived features.

### Task 3.1 — Create shared `annotation_features.py`

**New file:** `crci/extraction/shared_annotation_features.py`

**Purpose:** Single source of truth for annotation-derived features that both
P3 (se_eff_assembly) and P4 (meta_analyzer) need. Prevents import cycles.

```python
"""
Component: Shared annotation feature computation
Purpose: Compute σ²_structural and other annotation-derived features
         from study_annotations_v1, for use by both P3 and P4.
Reads: study_annotations_v1 (via annotation_lifecycle helpers)
Writes: Nothing (pure computation)
"""

from dataclasses import dataclass
from sqlalchemy.orm import Session

from crci.shared import config


@dataclass
class AnnotationFeatures:
    """Annotation-derived features for a single edge."""
    sigma_sq_structural: float
    annotation_ids: list[str]
    n_annotations: int


def get_structural_variance(
    session: Session,
    edge_relation_id: str,
) -> AnnotationFeatures:
    """Compute σ²_structural for an edge from its bias/confounder annotations.

    Formula: σ²_struct = σ²_base + Σ(w_severity × reconciled_confidence)
    where w_severity comes from config.ANNOTATION_SEVERITY_WEIGHTS.

    Returns AnnotationFeatures with sigma_sq_structural and the annotation IDs
    that contributed to the computation (for provenance).

    When no annotations exist, returns sigma_sq_structural = config default.
    """
    from crci.extraction.p1_extraction.annotation_lifecycle import (
        get_sigma_structural_annotations,
    )

    db_rows = get_sigma_structural_annotations(session, edge_relation_id)
    if not db_rows:
        return AnnotationFeatures(
            sigma_sq_structural=config.SIGMA_SQ_STRUCTURAL_DEFAULT,
            annotation_ids=[],
            n_annotations=0,
        )

    # Sum severity-weighted contributions
    import json as _json
    total_adjustment = 0.0
    ann_ids = []
    for row in db_rows:
        ann_ids.append(row.annotation_id)
        severity = None
        sdj = getattr(row, "structured_data_json", None)
        if sdj:
            try:
                parsed = _json.loads(sdj) if isinstance(sdj, str) else sdj
                severity = parsed.get("severity")
            except (TypeError, ValueError):
                pass
        weight = config.ANNOTATION_SEVERITY_WEIGHTS.get(severity or "moderate", 0.05)
        confidence = getattr(row, "reconciled_confidence", None) or 0.0
        total_adjustment += weight * confidence

    return AnnotationFeatures(
        sigma_sq_structural=config.SIGMA_SQ_STRUCTURAL_DEFAULT + total_adjustment,
        annotation_ids=ann_ids,
        n_annotations=len(ann_ids),
    )
```

### Task 3.2 — Wire `get_structural_variance()` into P3 `se_eff_assembly.py`

**File:** `crci/extraction/p3_heterogeneity/se_eff_assembly.py` line 225
**Current code:**
```python
sigma_sq_struct = config.SIGMA_SQ_STRUCTURAL_DEFAULT
```

**Replace with:**
```python
# Formula P3-8: σ²_structural — annotation-informed when available
if session is not None and inp.edge_relation_id:
    from crci.extraction.shared_annotation_features import get_structural_variance
    ann_features = get_structural_variance(session, inp.edge_relation_id)
    sigma_sq_struct = ann_features.sigma_sq_structural
    if ann_features.n_annotations > 0:
        logger.info(
            "P3-8: annotation-informed σ²_struct=%.4f for edge %s "
            "(default=%.4f, %d annotations)",
            sigma_sq_struct, inp.edge_relation_id,
            config.SIGMA_SQ_STRUCTURAL_DEFAULT, ann_features.n_annotations,
        )
else:
    sigma_sq_struct = config.SIGMA_SQ_STRUCTURAL_DEFAULT
```

### Task 3.3 — Thread `session` parameter through P3 call chain

**File:** `crci/extraction/p3_heterogeneity/runner.py`
**File:** `crci/extraction/p3_heterogeneity/se_eff_assembly.py`
**Action:** The P3 runner likely already has a `session` from the pipeline context.
Thread it through to `assemble_se_eff()` as `session: Session | None = None`.
When None (unit tests), fallback to default. Gate P3-G1 (SE_eff ≥ SE_raw) is
guaranteed to hold since annotation inflation only INCREASES σ²_structural.

**Verification:**
- [ ] Gate P3-G1 (SE_eff ≥ SE_raw) still holds with annotation-informed σ²
- [ ] Existing tests pass unchanged (session=None → default path)
- [ ] No import cycles: `se_eff_assembly.py` → `shared_annotation_features.py` → `annotation_lifecycle.py`

---

## WP-4: Implement EX-PROM Chain (Promotion Monitor)

**Risk:** Medium — new chain, but spec is highly detailed (SYS_EX L2014-2100).
**Files to create:** 1 new module
**Estimated scope:** ~250 lines

> **v2 STRUCTURAL CORRECTION:** The v1 plan embedded accumulation checking
> into `annotation_lifecycle.run_lifecycle()`. This is WRONG. SYS_EX L2014-2100
> defines EX-PROM as a **separate scheduled chain** with 3 discrete subsystems:
>
> 1. **EX-PROM-THR** (ThresholdChecker): Count annotations per (category, target), compare to thresholds
> 2. **EX-PROM-IND** (IndependenceValidator): Collapse raw counts to independent evidence units
> 3. **EX-PROM-PRP** (ProposalGenerator): Generate PromotionCandidate[] for human review
>
> This chain runs on a schedule (daily), NOT inline with per-paper extraction.
> Output goes to a human review queue, NOT directly to DB writes.

### Task 4.1 — Define accumulation thresholds in config

**File:** `crci/shared/config.py` after the existing PROM_* constants (~line 340)
**Action:** Add thresholds matching SYS_EX L2078-2086:

```python
# ═══════════════════════════════════════════════════════════════
#  EX-PROM ACCUMULATION THRESHOLDS (SYS_EX L2078-2086)
# ═══════════════════════════════════════════════════════════════
ACCUM_MECHANISM_HYPOTHESIS: int = 3
ACCUM_UNMEASURED_CONFOUNDER: int = 5
ACCUM_INSTRUMENT_OBSERVATION: int = 2
ACCUM_ADHERENCE_DATA: int = 4
ACCUM_ADVERSE_EVENT_SERIOUS: int = 1
ACCUM_ADVERSE_EVENT_MILD: int = 3
ACCUM_TEMPORAL_ONSET_DECAY: int = 3
ACCUM_DOSE_RESPONSE_QUALITATIVE: int = 2
ACCUM_RESEARCH_GAP_CYCLES: int = 2
```

### Task 4.2 — Create EX-PROM chain module

**New file:** `crci/extraction/promotion_monitor.py`

**Purpose:** Implement the 3 subsystems from SYS_EX L2066-2100 as a single
callable module. NOT imported by per-paper extraction — called by a scheduled
runner or CLI command.

```python
"""
Component: EX-PROM (Annotation Promotion Monitor)
Spec: SYS_EXTRACTION_COMPLETE.md lines 2014-2100
Subsystems: EX-PROM-THR, EX-PROM-IND, EX-PROM-PRP
Reads: study_annotations_v1 (WHERE maturity='reviewed'), study_registry_v1
Writes: PromotionCandidate[] (to review_tasks_v1 or JSONL file)
Schedule: Daily (not inline with per-paper extraction)
"""

from dataclasses import dataclass, field
from sqlalchemy.orm import Session
from crci.shared.models.enums import AnnotationCategory
from crci.shared import config


@dataclass
class ThresholdResult:
    """EX-PROM-THR output. One per (category, target_entity_id) cluster."""
    category: AnnotationCategory
    target_entity_type: str
    target_entity_id: str
    raw_count: int
    threshold: int
    threshold_met: bool
    annotation_ids: list[str] = field(default_factory=list)


@dataclass
class IndependenceResult:
    """EX-PROM-IND output."""
    category: AnnotationCategory
    target_entity_id: str
    raw_count: int
    independent_evidence_units: int
    contradiction_ratio: float
    passed: bool


@dataclass
class PromotionCandidate:
    """EX-PROM-PRP output. Human review artifact."""
    category: AnnotationCategory
    target_entity_id: str
    independent_evidence_units: int
    contradiction_ratio: float
    proposed_action: str
    proposed_target_table: str
    annotation_ids: list[str] = field(default_factory=list)


# ── Threshold map: category → config constant ──
THRESHOLD_MAP: dict[AnnotationCategory, int] = {
    AnnotationCategory.MECHANISM_HYPOTHESIS: config.ACCUM_MECHANISM_HYPOTHESIS,
    AnnotationCategory.LIMITATION_UNMEASURED_CONFOUNDER: config.ACCUM_UNMEASURED_CONFOUNDER,
    AnnotationCategory.INSTRUMENT_OBSERVATION: config.ACCUM_INSTRUMENT_OBSERVATION,
    AnnotationCategory.ADHERENCE_DATA: config.ACCUM_ADHERENCE_DATA,
    AnnotationCategory.TEMPORAL_ONSET: config.ACCUM_TEMPORAL_ONSET_DECAY,
    # New from WP-1:
    AnnotationCategory.TEMPORAL_DECAY: config.ACCUM_TEMPORAL_ONSET_DECAY,
    AnnotationCategory.DOSE_RESPONSE_EVIDENCE: config.ACCUM_DOSE_RESPONSE_QUALITATIVE,
    AnnotationCategory.RESEARCH_GAP: config.ACCUM_RESEARCH_GAP_CYCLES,
}


def check_thresholds(session: Session) -> list[ThresholdResult]:
    """EX-PROM-THR: Scan study_annotations_v1 for clusters meeting thresholds.

    Groups by (category, target_entity_type, target_entity_id).
    Counts DISTINCT study_id per group.
    Compares to THRESHOLD_MAP.
    Returns ALL clusters (threshold_met = True or False for reporting).

    SQL:
      SELECT category, target_entity_type, target_entity_id,
             COUNT(DISTINCT study_id) as distinct_studies,
             GROUP_CONCAT(annotation_id) as ann_ids
      FROM study_annotations_v1
      WHERE maturity = 'reviewed'
        AND adjudication_status != 'conflict'
        AND active = 1
      GROUP BY category, target_entity_type, target_entity_id
    """
    ...  # Full implementation in code


def validate_independence(
    session: Session,
    met_clusters: list[ThresholdResult],
) -> list[IndependenceResult]:
    """EX-PROM-IND: Collapse raw distinct-study counts to independent evidence units.

    Per SYS_EX L2088-2094:
    - Papers sharing dataset_id or trial_registry_id → 1 unit
    - Fallback: title/first-author/year Jaccard > 0.85 → 1 unit
    - Contradiction ratio = conflict_annotations / total_cluster
    - Speculative ceiling: require ≥1 annotation with evidence_strength
      'strong' or 'moderate' (not all 'speculative')
    """
    ...  # Full implementation in code


def generate_proposals(
    passed_clusters: list[IndependenceResult],
) -> list[PromotionCandidate]:
    """EX-PROM-PRP: Generate PromotionCandidate[] for human review.

    Per SYS_EX L2096-2100:
    Each category maps to a specific Class A target table:
    - mechanism_hypothesis → edge_relations_definitions_v1 (hypothesized edge)
    - limitation_unmeasured_confounder → edge σ² component
    - instrument_observation → observation_noise_v1 SE multiplier
    - adherence_data → logit(P_adhere) coefficients
    - adverse_event → contraindication_rules_v1
    - temporal_onset/decay → intervention_kernels_v1 params
    - dose_response → flag for Emax-vs-RCS model comparison
    - research_gap → elevated to "critical gap" in sufficiency reporting
    """
    ...  # Full implementation in code


def run_promotion_monitor(session: Session) -> list[PromotionCandidate]:
    """Run the full EX-PROM chain: THR → IND → PRP.

    Called by scheduled runner (scripts/run_promotion_monitor.py) or CLI.
    NOT called inline during per-paper extraction.
    """
    # Step 1: ThresholdChecker
    all_clusters = check_thresholds(session)
    met = [c for c in all_clusters if c.threshold_met]

    # Step 2: IndependenceValidator
    validated = validate_independence(session, met)
    passed = [v for v in validated if v.passed]

    # Step 3: ProposalGenerator
    candidates = generate_proposals(passed)

    return candidates
```

### Task 4.3 — Create CLI runner for EX-PROM

**New file:** `scripts/run_promotion_monitor.py`

**Purpose:** CLI entry point to run the EX-PROM chain on demand or via cron.

```python
"""Run EX-PROM chain: Annotation Promotion Monitor.

Usage:
    python scripts/run_promotion_monitor.py [--dry-run] [--output JSONL_PATH]

Output: PromotionCandidate[] written to JSONL file + logged.
"""
```

### Task 4.4 — DO NOT wire into `annotation_lifecycle.run_lifecycle()`

**Explicit non-action:** The v1 plan (Task 4.3) called `check_accumulation_thresholds()`
at the end of `run_lifecycle()`. This is architecturally wrong per spec.
EX-PROM is a separate scheduled chain, not a per-paper lifecycle hook.
`run_lifecycle()` handles ONLY per-paper promotion evaluation.

**Verification:**
- [ ] `promotion_monitor.py` is NOT imported by any per-paper extraction module
- [ ] `run_promotion_monitor.py` works as standalone CLI command
- [ ] Test with 3 annotations from 3 different studies targeting same mechanism
      → ThresholdResult.threshold_met = True
- [ ] Test with 3 annotations from same study → distinct_studies = 1 → threshold NOT met
- [ ] IndependenceValidator collapses papers sharing trial_registry_id → 1 unit

---

## WP-5: Wire Remaining Consumer Read Paths (as Compilers)

**Risk:** Low per consumer, but many touch points.
**Files to modify:** 6–8 files across pipeline
**Estimated scope:** ~150 lines total

> **v2 STRUCTURAL CORRECTION:** Consumer read paths should compile promoted
> annotations into policy tables at build time, NOT query annotations at runtime.
> The pattern is: "promoted annotation → compiler → policy table row."
> Runtime modules read policy tables, not `study_annotations_v1`.
>
> For consumers where no compilation target exists yet (e.g., `synergy_model`),
> the consumer read path is a reporting/curation tool, not a runtime query.

### Task 5.1 — `safety_rules` → `contraindication_rules_v1` (compiler)

**Consumer:** `"safety_rules"` | **Category:** `ADVERSE_EVENT`
**Query helper:** `get_safety_annotations(session)` — already exists at
`annotation_lifecycle.py:607`
**Target table:** `contraindication_rules_v1`

**Action:** Create a compilation function that reads promoted ADVERSE_EVENT
annotations and generates CANDIDATE rows for `contraindication_rules_v1`.
These are NOT auto-inserted — they go to the review queue (`review_tasks`
table, `ReviewTask` ORM) with `task_type='safety_rule_candidate'`.

### Task 5.2 — `temporal_kernel` → `intervention_kernels_v1` (compiler)

**Consumer:** `"temporal_kernel"` | **Categories:** `TEMPORAL_ONSET`, `TEMPORAL_DECAY`
**Query helper:** Needs new function in `annotation_lifecycle.py`:
```python
def get_temporal_kernel_annotations(
    session: Session, action_id: str | None = None
) -> list[StudyAnnotations]:
```

**Target table:** `intervention_kernels_v1`
**Action:** When ≥ `ACCUM_TEMPORAL_ONSET_DECAY` consistent observations exist,
propose updated kernel parameters as a review candidate.

### Task 5.3 — `dose_bridge` → reporting only (no compilation)

**Consumer:** `"dose_bridge"` | **Category:** `DOSE_RESPONSE_EVIDENCE`
**Action:** Create a curation report function. Dose-response model selection
is a Class A decision requiring human judgment. When ≥ `ACCUM_DOSE_RESPONSE_QUALITATIVE`
papers report non-monotonic patterns for an edge, log it to the sufficiency report.

### Task 5.4 — `scope_matching` → scope weight compiler

**Consumer:** `"scope_matching"` | **Categories:** `POPULATION_SPECIFICITY`,
`GENERALIZABILITY_CONCERN`
**Target:** P3 Layer 5 scope weights. Promoted generalizability concerns
should generate a scope weight override for specific subpopulations.
**Compilation:** Write to `scope_weight_overrides` (new column in edge schema or
separate lookup), consumed by P3 Layer 5.

### Task 5.5 — `modifier_resolution` → calibration data

**Consumer:** `"modifier_resolution"` | **Categories:** `ADHERENCE_DATA`,
`EFFECT_MODIFICATION`
**Action:** Log promoted adherence annotations as calibration data for
adherence model. Direct compilation deferred until adherence model is live.

### Task 5.6 — `dag_expansion` → curation queue

**Consumer:** `"dag_expansion"` | **Categories:** `MECHANISM_HYPOTHESIS`,
`BIOLOGICAL_PLAUSIBILITY`, `THEORY_SUPPORT`, `MECHANISM_INTERACTION`
**Action:** Create `scripts/review_dag_candidates.py` that dumps accumulated
mechanism annotations to a curation review file. This is explicitly offline
curation, not automated.

### Task 5.7 — `confidence_weighting` → P4 p_inclusion

**Consumer:** `"confidence_weighting"` | **Categories:** `REPLICATION_STATUS`,
`CROSS_VALIDATION`
**Action:** Wire into `compute_p_inclusion_adjustment()` in meta_analyzer.
Replication annotations boost P_inclusion. This is the one consumer that
is appropriately a RUNTIME read because p_inclusion is computed per-edge
during meta-analysis, same as the existing sigma_structural path.

### Task 5.8 — `quality_assessment` → quality scoring

**Consumer:** `"quality_assessment"` | **Category:** `MODEL_DIAGNOSTIC` (new from WP-1)
**Action:** Model diagnostic annotations (heteroscedasticity, assumption violations)
can demote `quality_rating` for affected evidence records during P2 harmonization.

**Verification for all of WP-5:**
- [ ] Each consumer has a query function in `annotation_lifecycle.py`
- [ ] Consumers with compilation targets write to review queue (not directly to Class A tables)
- [ ] Runtime consumers (confidence_weighting) read via existing meta_analyzer path
- [ ] `scripts/review_dag_candidates.py` produces a readable curation report

---

## WP-6: Paper-Type Annotation Profiles

**Risk:** Low — additive configuration, no existing behavior changes.
**Files to modify:** 2 files + 1 new file
**Estimated scope:** ~120 lines

### Task 6.1 — Create annotation profile definitions

**New file:** `crci/extraction/p1_extraction/annotation_profiles.py`

**Purpose:** Define expected annotation yield per paper type, used to:
(a) modulate agent prompt emphasis, and (b) post-extraction validation
(warn if a meta-analysis produces 0 research_gap annotations).

```python
@dataclass(frozen=True)
class CategoryProfile:
    """Expected yield for one annotation category from one paper type."""
    category: AnnotationCategory
    expected_yield: str  # "HIGH", "MODERATE", "LOW", "NONE"
    priority: int  # 1-3 stars
    notes: str = ""

@dataclass(frozen=True)
class PaperAnnotationProfile:
    """Complete annotation profile for a paper type."""
    paper_subtype: PaperSubtype
    profiles: list[CategoryProfile]

# §5.1 Meta-Analysis Profile
META_ANALYSIS_PROFILE = PaperAnnotationProfile(
    paper_subtype=PaperSubtype.META_ANALYSIS,
    profiles=[
        CategoryProfile(AnnotationCategory.RESEARCH_GAP, "HIGH", 3,
                        "MAs routinely identify gaps; 2-5 expected"),
        CategoryProfile(AnnotationCategory.LIMITATION_UNMEASURED_CONFOUNDER, "MODERATE", 3),
        CategoryProfile(AnnotationCategory.DOSE_RESPONSE_EVIDENCE, "MODERATE", 3),
        CategoryProfile(AnnotationCategory.NULL_FINDING_CONTEXT, "MODERATE", 2),
        # ... etc per protocol §5.1
    ],
)

# §5.2 RCT Profile, §5.3 Mechanistic Profile, etc.
# ...

ANNOTATION_PROFILES: dict[PaperSubtype, PaperAnnotationProfile] = {
    PaperSubtype.META_ANALYSIS: META_ANALYSIS_PROFILE,
    PaperSubtype.PAIRWISE_MA: META_ANALYSIS_PROFILE,
    PaperSubtype.NMA: META_ANALYSIS_PROFILE,
    ...
}
```

### Task 6.2 — Post-extraction validation using profiles

**File:** `crci/extraction/p1_extraction/runner.py`
**Action:** After all agents run and annotations are collected, validate
against the paper's annotation profile. If a HIGH-priority category yields
0 annotations, log a warning (not a gate failure).

### Task 6.3 — Feed profile into agent prompts (optional enhancement)

**Action:** When constructing agent prompts, include preamble based on paper type:
"This paper is a meta-analysis. Prioritize extracting: research_gap (HIGH),
limitation_unmeasured_confounder (MODERATE)."

**Verification:**
- [ ] Profile exists for MA, RCT, and mechanistic paper types
- [ ] Runner logs warnings for HIGH-category misses
- [ ] No gate failures from profile validation (warnings only)

---

## WP-7: Database Index Optimization

**Risk:** Negligible — additive DDL only.
**Files to modify:** 1 file
**Estimated scope:** ~10 lines

### Task 7.1 — Add composite indexes for annotation queries

**File:** `crci/database/schema/008_v2_migration.sql` after existing indexes (~line 136)

```sql
-- Composite index for get_promoted_for_consumer() queries
CREATE INDEX IF NOT EXISTS idx_sa_consumer_maturity
    ON study_annotations_v1 (consumer, maturity)
    WHERE active = TRUE;

-- Composite index for EX-PROM cross-paper grouping
CREATE INDEX IF NOT EXISTS idx_sa_accumulation
    ON study_annotations_v1 (category, target_entity_type, target_entity_id, study_id)
    WHERE active = TRUE AND maturity IN ('raw', 'reviewed');
```

### Task 7.2 — Apply migration

**Command:** `sqlite3 crci_dev.db < crci/database/schema/008_v2_migration.sql`
(idempotent — uses `CREATE INDEX IF NOT EXISTS`).

**Verification:**
- [ ] `sqlite3 crci_dev.db ".indexes study_annotations_v1"` shows all indexes

---

## WP-8: `structured_data_json` Schema Registry (AT-03 Enhancement)

**Risk:** Low — strengthens existing guardrails.
**Files to modify:** 2 files
**Estimated scope:** ~100 lines

> **v2 refactor:** Instead of an if/elif chain in `_check_at03_category_fields()`,
> use a declarative schema registry pattern. This makes it easy to add new
> categories and keeps validation rules auditable.

### Task 8.1 — Create annotation JSON schema registry

**New addition to:** `crci/extraction/p1_extraction/annotation_trust_boundary.py`
(or separate file `crci/extraction/p1_extraction/annotation_schemas.py`)

```python
"""Schema registry for structured_data_json validation per AnnotationCategory.

Each entry defines required and optional fields, with types and allowed values.
AT-03 uses this registry to validate annotations before DB write.
"""

from dataclasses import dataclass, field
from crci.shared.models.enums import AnnotationCategory


@dataclass(frozen=True)
class FieldSpec:
    """Required or optional field in structured_data_json."""
    name: str
    required: bool = True
    allowed_values: tuple[str, ...] | None = None  # None = any value accepted
    field_type: type = str  # str, float, int, bool


# Registry: category → list of field specs
ANNOTATION_JSON_SCHEMAS: dict[AnnotationCategory, list[FieldSpec]] = {
    AnnotationCategory.ADVERSE_EVENT: [
        FieldSpec("severity", required=True, allowed_values=("mild", "moderate", "serious", "critical")),
        FieldSpec("event_description", required=True),
    ],
    AnnotationCategory.NULL_FINDING_CONTEXT: [
        FieldSpec("powered_adequately", required=True, field_type=bool),
    ],
    AnnotationCategory.LIMITATION_UNMEASURED_CONFOUNDER: [
        FieldSpec("confounder_name", required=True),
    ],
    AnnotationCategory.TEMPORAL_ONSET: [
        FieldSpec("onset_weeks", required=True, field_type=float),
    ],
    AnnotationCategory.TEMPORAL_DECAY: [
        FieldSpec("decay_half_life_weeks", required=True, field_type=float),
    ],
    AnnotationCategory.TEMPORAL_TRAJECTORY: [
        FieldSpec("trajectory_class", required=True,
                  allowed_values=("recovery", "plateau", "decline", "oscillating", "delayed_onset")),
    ],
    AnnotationCategory.ADHERENCE_DATA: [
        FieldSpec("adherence_rate", required=True, field_type=float),
    ],
    AnnotationCategory.MECHANISM_HYPOTHESIS: [
        FieldSpec("mechanism_type", required=False),
        FieldSpec("pathway_id", required=False),
        # AT LEAST ONE of mechanism_type or pathway_id must be present (custom check)
    ],
    AnnotationCategory.MECHANISM_INTERACTION: [
        FieldSpec("pathway_id_a", required=True),
        FieldSpec("pathway_id_b", required=True),
    ],
    AnnotationCategory.MODEL_DIAGNOSTIC: [
        FieldSpec("diagnostic_type", required=True,
                  allowed_values=("heteroscedasticity", "normality_violation",
                                  "multicollinearity", "model_misspecification",
                                  "assumption_violation")),
    ],
    AnnotationCategory.RESEARCH_GAP: [
        FieldSpec("gap_description", required=True),
    ],
    AnnotationCategory.METHODOLOGICAL_INNOVATION: [
        FieldSpec("innovation_description", required=True),
    ],
}
```

### Task 8.2 — Refactor `_check_at03_category_fields()` to use registry

**File:** `crci/extraction/p1_extraction/annotation_trust_boundary.py`
**Function:** `_check_at03_category_fields()` (~line 170)

**Replace** the existing 3-way if/elif chain with a generic validator:

```python
def _check_at03_category_fields(
    category: AnnotationCategory,
    structured_data: dict,
) -> ATBRejection | None:
    """AT-03: Validate structured_data_json against schema registry."""
    schema = ANNOTATION_JSON_SCHEMAS.get(category)
    if schema is None:
        return None  # No schema defined → passes by default

    for field_spec in schema:
        if field_spec.required:
            value = structured_data.get(field_spec.name)
            if value is None:
                return ATBRejection(
                    rule="AT-03",
                    reason=f"Missing required field '{field_spec.name}' for {category.value}",
                )
            if field_spec.allowed_values and value not in field_spec.allowed_values:
                return ATBRejection(
                    rule="AT-03",
                    reason=f"Invalid value '{value}' for '{field_spec.name}' in {category.value}. "
                           f"Allowed: {field_spec.allowed_values}",
                )
    return None
```

**Verification:**
- [ ] Existing annotations for ADVERSE_EVENT, NULL_FINDING_CONTEXT, LIMITATION_UNMEASURED_CONFOUNDER still pass
- [ ] New categories with missing required fields get rejected
- [ ] Adding a new category to the registry requires only one dict entry, not code changes

---

## WP-9: Annotation Provenance Traceability (NEW in v2)

**Risk:** Low — additive schema change + wiring.
**Files to modify:** 3 files
**Estimated scope:** ~30 lines

> **Discovery:** `edge_param_builds_v1` is MISSING the dedicated
> `annotation_source_ids_json` column spec'd at SYS_EX L2668. The annotation
> IDs are currently stuffed into the generic `notes` TEXT column as part of a
> JSON blob. This makes provenance queries impossible without parsing notes.

### Task 9.1 — Add `annotation_source_ids_json` column to ORM

**File:** `crci/shared/models/tables.py` L1035-1057 (EdgeParamBuild class)
**Action:** Add dedicated column:

```python
class EdgeParamBuild(Base):
    """B7. Edge compilation build records."""
    __tablename__ = "edge_param_builds_v1"

    # ... existing columns ...
    annotation_source_ids_json = Column(JSONB)  # NEW: SYS_EX L2668
```

### Task 9.2 — Add column to migration

**File:** `crci/database/schema/008_v2_migration.sql` or new migration file
**Action:**

```sql
ALTER TABLE edge_param_builds_v1
ADD COLUMN annotation_source_ids_json TEXT;  -- JSONB array of annotation IDs
```

### Task 9.3 — Wire edge_writer to write dedicated column

**File:** `crci/extraction/p4_aggregation/edge_writer.py` L338-370
**Action:** In `_write_edge_param_build()`, set the new column directly
instead of (or in addition to) burying it in `notes`:

```python
build_record = EdgeParamBuild(
    # ... existing fields ...
    annotation_source_ids_json=inp.annotation_source_ids,  # Direct column, not notes
    notes=json.dumps({
        "overlap_decision_json": inp.overlap_decision_json,
        # annotation_source_ids no longer needed here — has own column
        "contributing_ler_ids": inp.contributing_ler_ids,
        "prior_provenance": inp.prior_spec.provenance,
    }),
)
```

**Verification:**
- [ ] `edge_param_builds_v1.annotation_source_ids_json` is queryable directly
- [ ] Provenance query works: "Which annotations influenced edge X?" → single column read
- [ ] Backward compatible: existing rows with NULL in new column don't break

---

## WP-10: Contract Integration Test (NEW in v2)

**Risk:** Negligible — test-only.
**Files to create:** 1 test file
**Estimated scope:** ~80 lines

> **Purpose:** Prove end-to-end that annotation → σ²_structural → compiled edge
> works. This is the critical provenance contract:
> 1. Insert a mock annotation into `study_annotations_v1`
> 2. Run P4 pipeline (or the relevant functions)
> 3. Verify `sigma_sq_structural` in `edges_v1` is > default
> 4. Verify `annotation_source_ids_json` in `edge_param_builds_v1` contains the annotation ID

### Task 10.1 — Create integration test

**New file:** `tests/test_annotation_provenance_contract.py`

```python
"""Contract test: annotation → σ²_structural → compiled edge provenance.

Verifies the complete chain:
  study_annotations_v1 (confounder annotation)
    → _load_annotations_for_edges()
    → analyze_all_edges() (sigma_sq_structural inflated)
    → build_compilation_inputs() (annotation_ids_map passed)
    → write_all_edges() (annotation_source_ids_json populated)
    → edge_param_builds_v1.annotation_source_ids_json contains annotation ID
"""

def test_annotation_sigma_sq_flows_to_compiled_edge():
    """Insert confounder annotation → verify σ² inflated in compiled edge."""
    ...

def test_annotation_ids_reach_param_build():
    """Insert annotation → verify its ID appears in edge_param_builds_v1."""
    ...

def test_no_annotations_uses_default_sigma():
    """No annotations → σ² = config.SIGMA_SQ_STRUCTURAL_DEFAULT."""
    ...

def test_null_finding_adjusts_p_inclusion():
    """Insert powered null-finding annotation → p_inclusion decreases."""
    ...
```

**Verification:**
- [ ] All 4 tests pass
- [ ] Tests use in-memory SQLite (no external DB dependency)

---

## WP-11: EX-PROM Proposal Sink (NEW in v2)

**Risk:** Low — simple storage.
**Files to modify:** 1 file
**Estimated scope:** ~30 lines

> **Purpose:** EX-PROM generates `PromotionCandidate[]` but needs somewhere
> to write them. Two options:
> - **Option A (recommended):** Write to `review_tasks` table (`ReviewTask` ORM)
>   with `task_type='promotion_candidate'`
> - **Option B:** Write JSONL to `runs/promotion_candidates/{date}.jsonl`
>
> Option A is preferred because `review_tasks` already exists for
> adjudication workflows and has the right structure (task_type, source_stage,
> context_json, status, priority).

### Task 11.1 — Add promotion candidate writing to EX-PROM

**File:** `crci/extraction/promotion_monitor.py` (created in WP-4)
**Action:** After `generate_proposals()`, write each PromotionCandidate to
`review_tasks` (`ReviewTask` ORM) with:
- `task_type = 'promotion_candidate'`
- `source_stage = 'EX-PROM'`
- `source_entity_id = candidate.target_entity_id`
- `source_table = 'study_annotations_v1'`
- `context_json = {candidate fields as dict}`
- `status = 'pending'`

Also write a summary JSONL to `runs/` for offline review.

**Verification:**
- [ ] After running `run_promotion_monitor.py`, `review_tasks` contains
      new rows with `task_type='promotion_candidate'`
- [ ] JSONL file is human-readable

---

## Implementation Order (v2)

```
WP-1 (Enum + mappings + AT-03)      ← Foundation: everything depends on categories
  ↓
WP-8 (Schema registry)              ← Strengthen data quality before new emissions
  ↓
WP-7 (DB indexes)                   ← Quick win, supports WP-2/WP-4 queries
  ↓
WP-9 (Provenance column)            ← Schema change, do before WP-2 wiring
  ↓
WP-2 (P4 runner annotation_ids_map) ← ~8 lines, completes the provenance chain
  ↓
WP-3 (P3 SE inflation)              ← Uses shared annotation_features.py
  ↓
WP-10 (Contract integration test)   ← Prove WP-2 + WP-3 + WP-9 work end-to-end
  ↓
WP-4 (EX-PROM chain)                ← New module, no dependencies on WP-2/3
  ↓
WP-11 (EX-PROM proposal sink)       ← Storage for WP-4 output
  ↓
WP-5 (Consumer compilers)           ← Incremental, consumer by consumer
  ↓
WP-6 (Annotation profiles)          ← Enhancement, lowest priority
```

**Critical path:** WP-1 → WP-8 → WP-9 → WP-2 → WP-3 → WP-10

---

## Total Estimated Scope (v2)

| WP | Lines | Files | Risk | Status |
|----|-------|-------|------|--------|
| WP-1 | ~80 | 5 + 2 prompts | Low | Not started |
| WP-2 | ~25 | 1 | **Medium** | 70% done (missing annotation_ids_map) |
| WP-3 | ~60 | 2 + 1 new | Medium | Not started |
| WP-4 | ~250 | 1 new + 1 script | Medium | Not started |
| WP-5 | ~150 | 6-8 | Low | Not started |
| WP-6 | ~120 | 2 + 1 new | Low | Not started |
| WP-7 | ~10 | 1 | Negligible | Not started |
| WP-8 | ~100 | 2 | Low | Not started |
| WP-9 | ~30 | 3 | Low | **NEW** |
| WP-10 | ~80 | 1 new (test) | Negligible | **NEW** |
| WP-11 | ~30 | 1 | Low | **NEW** |
| **Total** | **~935** | **~25** | | |

---

## Corrections Log (v1 → v2)

| Item | v1 (Wrong) | v2 (Correct) | Source |
|------|-----------|-------------|--------|
| WP-2 status | "Dead code, fully unwired" | "70% wired, missing annotation_ids_map only" | `runner.py:148,257` |
| WP-3 import | P3 imports from P4 meta_analyzer | Shared `annotation_features.py` prevents circular dep | Architecture review |
| WP-4 structure | Hook in `run_lifecycle()` | Separate EX-PROM chain module | SYS_EX L2014-2100 |
| WP-5 pattern | Runtime DB queries | Compile to policy tables + review queue | Architectural principle |
| WP-8 pattern | if/elif chain | Declarative schema registry | Engineering feedback |
| Missing | No provenance column | WP-9: `annotation_source_ids_json` column | SYS_EX L2668 |
| Missing | No integration test | WP-10: Contract test for annotation→edge chain | Best practice |
| Missing | No proposal storage | WP-11: review_tasks_v1 sink for EX-PROM | EX-PROM output spec |
| WP-1 risk | "Just add enums" | Must add AT-03 schemas + exemplars first | Precision concern |
