# PIMP Gap Implementation Plan

> **PIMP** = Paper Intelligence Maximization Protocol  
> **Purpose:** Step-by-step technical plan to close every gap identified in the
> PIMP-vs-codebase audit. Each task specifies exact files, line numbers,
> functions, and the code changes needed. Follow sequentially within each
> work-package; work-packages are independent and can be parallelized.

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
**Estimated scope:** ~60 lines changed

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
in the prompt. For AG10's 7 primary categories, these new ones should go into
the "15 Secondary categories" section of the prompt.

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

**Verification checklist for WP-1:**
- [ ] All 27 enum members parse correctly: `AnnotationCategory("model_diagnostic")` works
- [ ] All 27 categories have a `PROMOTION_RULES` entry
- [ ] All 27 categories have a `_determine_consumer` mapping
- [ ] AG10 prompt lists all 27 categories
- [ ] `python -c "from crci.shared.models.enums import AnnotationCategory; print(len(AnnotationCategory))"` → 27

---

## WP-2: Wire P4 Runner to Actually Read Annotations from DB

**Risk:** Medium — this is the single most impactful gap. Without this, the
`sigma_sq_structural` and `p_inclusion_adjustment` code paths in `meta_analyzer.py`
are dead code (always receive empty lists).  
**Files to modify:** 1 file  
**Estimated scope:** ~40 lines added

### Task 2.1 — Add annotation query function to P4 runner

**File:** `crci/extraction/p4_aggregation/runner.py` around line 146  
**Current code (line 146):**
```python
ma_results = analyze_all_edges(resolved_groups)
```

**Problem:** `annotations_by_edge` parameter is not passed → defaults to `{}`.

**Action:** Add a helper function that queries `study_annotations_v1` via the lifecycle
convenience functions, builds the `dict[str, list[AnnotationRecord]]` keyed by
`edge_relation_id`, and passes it to `analyze_all_edges()`.

**Implementation:**

```python
def _load_annotations_for_edges(
    session: Session,
    edge_relation_ids: list[str],
) -> dict[str, list[AnnotationRecord]]:
    """Query study_annotations_v1 for sigma_structural + null_finding annotations.

    Reads only promoted annotations (maturity='promoted') or reviewed ones
    (maturity='reviewed') that target the given edges.
    Uses get_sigma_structural_annotations() and equivalent queries.
    """
    from crci.extraction.p1_extraction.annotation_lifecycle import (
        get_sigma_structural_annotations,
    )
    from crci.extraction.p4_aggregation.meta_analyzer import AnnotationRecord

    annotations_by_edge: dict[str, list[AnnotationRecord]] = {}

    for edge_id in edge_relation_ids:
        db_rows = get_sigma_structural_annotations(session, edge_id)
        records = []
        for row in db_rows:
            records.append(AnnotationRecord(
                annotation_id=row.annotation_id,
                category=row.category,
                target_edge_relation_id=edge_id,
                reconciled_confidence=row.reconciled_confidence or 0.0,
                severity=_extract_severity(row.structured_data_json),
                powered_adequately=_extract_powered(row.structured_data_json),
                content=row.content or "",
            ))
        if records:
            annotations_by_edge[edge_id] = records

    return annotations_by_edge
```

**Then change line 146 from:**
```python
ma_results = analyze_all_edges(resolved_groups)
```
**To:**
```python
edge_ids = [rg.edge_relation_id for rg in resolved_groups]
annotations_by_edge = _load_annotations_for_edges(session, edge_ids)
ma_results = analyze_all_edges(resolved_groups, annotations_by_edge=annotations_by_edge)
```

**Verification:**
- [ ] Unit test: with a mocked `study_annotations_v1` containing a confounder annotation,
      `sigma_sq_structural` should be > `config.SIGMA_SQ_STRUCTURAL_DEFAULT`
- [ ] Unit test: with a null_finding annotation (powered=True), `p_inclusion_final < p_inclusion_raw`

---

## WP-3: Wire P3 SE Inflation from Bias Annotations

**Risk:** Medium — modifies the seven-layer SE pipeline.  
**Files to modify:** 2 files  
**Estimated scope:** ~50 lines

### Task 3.1 — Add annotation-aware σ²_structural to `se_eff_assembly.py`

**File:** `crci/extraction/p3_heterogeneity/se_eff_assembly.py` line 225  
**Current code:**
```python
sigma_sq_struct = config.SIGMA_SQ_STRUCTURAL_DEFAULT
```

**Problem:** This is always the generic default (0.04). When confounder/bias
annotations exist for the edge, it should be inflated.

**Action:** Add an optional `annotation_sigma_sq_override: float | None` parameter
to the `assemble_se_eff()` function (or whatever calls line 225). When provided
and > 0, use it instead of the default. This value comes from
`meta_analyzer.compute_sigma_sq_structural()`.

**Design decision:** P3 runs BEFORE P4 in the pipeline. The annotation-informed
σ²_structural is computed in `meta_analyzer.py` (P4). Two options:

- **Option A (recommended):** Compute σ²_structural from annotations in P3 as well
  (duplicate the simple query + sum logic), so P3 has annotation-aware SE_eff.
  This is ~15 lines.
- **Option B:** Leave P3 with the default and let P4 apply the annotation delta
  to the pooled estimate afterwards. Simpler but means per-record SE_eff in P3
  doesn't reflect annotation intelligence.

**Recommended approach (Option A):**

```python
# In se_eff_assembly.py, add at top:
from crci.extraction.p1_extraction.annotation_lifecycle import (
    get_sigma_structural_annotations,
)

# At line 225, replace:
#   sigma_sq_struct = config.SIGMA_SQ_STRUCTURAL_DEFAULT
# With:
if session is not None and inp.edge_relation_id:
    ann_rows = get_sigma_structural_annotations(session, inp.edge_relation_id)
    if ann_rows:
        from crci.extraction.p4_aggregation.meta_analyzer import compute_sigma_sq_structural, AnnotationRecord
        ann_records = [AnnotationRecord(
            annotation_id=r.annotation_id,
            category=r.category,
            target_edge_relation_id=inp.edge_relation_id,
            reconciled_confidence=r.reconciled_confidence or 0.0,
            severity=_parse_severity(r.structured_data_json),
            content=r.content or "",
        ) for r in ann_rows]
        sigma_sq_struct = compute_sigma_sq_structural(ann_records, inp.edge_relation_id)
        logger.info(
            "P3-8: annotation-informed σ²_struct=%.4f for edge %s "
            "(default would be %.4f, %d annotations)",
            sigma_sq_struct, inp.edge_relation_id,
            config.SIGMA_SQ_STRUCTURAL_DEFAULT, len(ann_records),
        )
    else:
        sigma_sq_struct = config.SIGMA_SQ_STRUCTURAL_DEFAULT
else:
    sigma_sq_struct = config.SIGMA_SQ_STRUCTURAL_DEFAULT
```

### Task 3.2 — Thread `session` parameter through P3 call chain

**File:** `crci/extraction/p3_heterogeneity/runner.py`  
**File:** `crci/extraction/p3_heterogeneity/se_eff_assembly.py`  
**Action:** The P3 runner likely already has a `session` from the pipeline context.
Thread it through to `assemble_se_eff()` so the annotation query is possible.
If `session` is None (e.g., unit tests), fallback to default.

**Verification:**
- [ ] Gate P3-G1 (SE_eff ≥ SE_raw) still holds — annotation inflation always
      increases σ²_structural, so this is guaranteed
- [ ] Existing tests pass unchanged (session=None → default path)

---

## WP-4: Cross-Paper Accumulation Promotion Logic

**Risk:** Medium — implements the "self-improvement loop" (§3.6 of protocol).  
**Files to modify:** 1 file + 1 new file  
**Estimated scope:** ~200 lines new code

### Task 4.1 — Define accumulation thresholds in config

**File:** `crci/shared/config.py` after the existing PROM_* constants (~line 340)  
**Action:** Add protocol §3.6 thresholds:

```python
# ═══════════════════════════════════════════════════════════════
#  CROSS-PAPER ACCUMULATION THRESHOLDS (PIMP §3.6)
# ═══════════════════════════════════════════════════════════════
# Number of independent studies proposing same annotation target before
# promotion becomes eligible. "Independent" = distinct study_id.
ACCUM_MECHANISM_HYPOTHESIS: int = 3        # ≥3 papers propose same edge
ACCUM_UNMEASURED_CONFOUNDER: int = 5       # ≥5 papers name same confounder for edge family
ACCUM_INSTRUMENT_OBSERVATION: int = 2      # ≥2 papers report same DIF/reliability issue
ACCUM_ADHERENCE_DATA: int = 4              # ≥4 data points for same intervention type
ACCUM_ADVERSE_EVENT_SERIOUS: int = 1       # Any serious AE → immediate promotion candidate
ACCUM_ADVERSE_EVENT_MILD: int = 3          # ≥3 reports of same mild/moderate event
ACCUM_TEMPORAL_ONSET_DECAY: int = 3        # ≥3 consistent observations for same intervention
ACCUM_DOSE_RESPONSE_QUALITATIVE: int = 2   # ≥2 papers report same nonlinear pattern
ACCUM_RESEARCH_GAP_CYCLES: int = 2         # Gap persists after ≥2 acquisition cycles → critical
```

### Task 4.2 — Create accumulation checker module

**New file:** `crci/extraction/p1_extraction/accumulation_checker.py`

**Purpose:** Query `study_annotations_v1` grouped by
`(category, target_entity_type, target_entity_id)`, count distinct `study_id`,
compare to thresholds from §3.6, return promotion candidates.

**Key functions:**

```python
@dataclass
class AccumulationCandidate:
    """An annotation cluster that has hit its accumulation threshold."""
    category: AnnotationCategory
    target_entity_type: str
    target_entity_id: str
    distinct_study_count: int
    threshold: int
    annotation_ids: list[str]
    proposed_action: str  # e.g., "Add to edge_relations_definitions_v1 as hypothesized"

def check_accumulation_thresholds(session: Session) -> list[AccumulationCandidate]:
    """Scan study_annotations_v1 for annotation clusters that hit promotion thresholds.

    Groups annotations by (category, target_entity_type, target_entity_id).
    Counts distinct study_id per group.
    Compares to config.ACCUM_* thresholds.
    Returns candidates that meet or exceed their threshold.

    This is the cross-paper self-improvement loop from PIMP §3.6.
    """

def promote_accumulated(
    session: Session,
    candidates: list[AccumulationCandidate],
    dry_run: bool = True,
) -> list[PromotionDecision]:
    """Execute promotion for accumulated annotation clusters.

    When dry_run=True: returns proposed promotions without DB writes.
    When dry_run=False: updates maturity → 'promoted', sets promoted_to.

    Per PIMP §3.6:
    - mechanism_hypothesis → new hypothesized row in edge_relations_definitions_v1
    - limitation_unmeasured_confounder → new σ² component
    - instrument_observation → updated SE multiplier in observation_noise_v1
    - adherence_data → updated logit(P_adhere) coefficients
    - adverse_event → new row in contraindication_rules_v1
    - temporal_onset/temporal_decay → updated kernel params
    - dose_response_qualitative → flag for Emax-vs-RCS comparison
    - research_gap → elevated to "critical gap" in sufficiency reporting
    """
```

### Task 4.3 — Wire accumulation checker into lifecycle

**File:** `crci/extraction/p1_extraction/annotation_lifecycle.py`  
**Action:** Import and call `check_accumulation_thresholds()` at the end of
`run_lifecycle()` (line 434), after per-paper promotion evaluation. Log results.

```python
# At end of run_lifecycle():
from crci.extraction.p1_extraction.accumulation_checker import (
    check_accumulation_thresholds,
)
accumulation_candidates = check_accumulation_thresholds(session)
if accumulation_candidates:
    logger.info(
        "LIFECYCLE: %d accumulation promotion candidates detected",
        len(accumulation_candidates),
    )
    for candidate in accumulation_candidates:
        logger.info(
            "  → %s on %s:%s (%d/%d studies)",
            candidate.category.value,
            candidate.target_entity_type,
            candidate.target_entity_id,
            candidate.distinct_study_count,
            candidate.threshold,
        )
```

**Verification:**
- [ ] Test with 3 annotations from different studies targeting same mechanism hypothesis
      → candidate returned
- [ ] Test with 2 annotations from same study → no candidate (distinct study_id check)
- [ ] dry_run=True produces decisions but doesn't write DB

---

## WP-5: Wire Remaining Consumer Read Paths

**Risk:** Low per consumer, but many touch points.  
**Files to modify:** 6–8 files across pipeline  
**Estimated scope:** ~150 lines total (across all consumers)

Each consumer below needs: (a) a query helper in `annotation_lifecycle.py` (most
already exist), and (b) a call site in the consuming module.

### Task 5.1 — `safety_rules` → contraindication evaluation

**Consumer:** `"safety_rules"` | **Category:** `ADVERSE_EVENT`  
**Query helper:** `get_safety_annotations(session)` — already exists at
`annotation_lifecycle.py:607`  
**Consuming module:** `crci/algorithm/safety/` or wherever `contraindication_rules_v1`
is evaluated at runtime.

**Action:** In the safety evaluation module, after loading `contraindication_rules_v1`
rows, also call `get_safety_annotations(session)` and log/flag any promoted adverse
event annotations that don't yet have a corresponding contraindication rule.
This is a review-trigger, not an automatic rule creation.

### Task 5.2 — `temporal_kernel` → kernel parameter calibration

**Consumer:** `"temporal_kernel"` | **Categories:** `TEMPORAL_ONSET`, `TEMPORAL_DECAY`  
**Query helper:** Needs new function in `annotation_lifecycle.py`:
```python
def get_temporal_kernel_annotations(
    session: Session, action_id: str | None = None
) -> list[StudyAnnotations]:
```

**Consuming module:** Wherever `intervention_kernels_v1` is loaded/compiled.  
**Action:** When compiling kernel parameters, query for promoted `temporal_onset`
and `temporal_decay` annotations. If N ≥ `ACCUM_TEMPORAL_ONSET_DECAY`, log a
calibration suggestion.

### Task 5.3 — `dose_bridge` → dose-response model selection

**Consumer:** `"dose_bridge"` | **Category:** `DOSE_RESPONSE_EVIDENCE`  
**Query helper:** Needs new function:
```python
def get_dose_response_annotations(
    session: Session, edge_relation_id: str | None = None
) -> list[StudyAnnotations]:
```

**Consuming module:** Dose-response compilation / Emax model fitting.  
**Action:** When fitting dose-response curves, check for qualitative dose annotations.
If ≥2 report non-monotonic patterns, flag the edge for RCS comparison instead of
default Emax.

### Task 5.4 — `scope_matching` → transportability scoring

**Consumer:** `"scope_matching"` | **Categories:** `POPULATION_SPECIFICITY`,
`GENERALIZABILITY_CONCERN`  
**Query helper:** Needs new function:
```python
def get_scope_annotations(
    session: Session, edge_relation_id: str | None = None
) -> list[StudyAnnotations]:
```

**Consuming module:** P3 scope weighting (`crci/extraction/p3_heterogeneity/layers.py`,
Layer 5 scope weights).  
**Action:** When computing `w_scope`, check for generalizability concern annotations.
If a promoted annotation says "no benefit observed in hormone-receptor-negative
breast cancer", the scope weight for that population should be penalized.

### Task 5.5 — `modifier_resolution` → effect modification routing

**Consumer:** `"modifier_resolution"` | **Categories:** `ADHERENCE_DATA`,
`EFFECT_MODIFICATION`  
**Query helper:** Needs new function.  
**Consuming module:** Modifier stack / adherence model.  
**Action:** Log promoted adherence annotations as calibration data.

### Task 5.6 — `dag_expansion` → curation queue

**Consumer:** `"dag_expansion"` | **Categories:** `MECHANISM_HYPOTHESIS`,
`BIOLOGICAL_PLAUSIBILITY`, `THEORY_SUPPORT`, `MECHANISM_INTERACTION`  
**Query helper:** Needs new function:
```python
def get_dag_expansion_annotations(session: Session) -> list[StudyAnnotations]:
```

**Consuming module:** No automated consumer yet (this is offline curation).  
**Action:** Create a simple report function that dumps accumulated mechanism
annotations to a curation review file. Called by `scripts/report_status.py`
or a new `scripts/review_dag_candidates.py`.

### Task 5.7 — `confidence_weighting` → replication assessment

**Consumer:** `"confidence_weighting"` | **Categories:** `REPLICATION_STATUS`,
`CROSS_VALIDATION`  
**Query helper:** Needs new function.  
**Consuming module:** P4 meta-analysis or chain-vs-direct validation.  
**Action:** Replication annotations could boost P_inclusion. Wire into
`compute_p_inclusion_adjustment()` alongside null_finding_context.

### Task 5.8 — `quality_assessment` → quality scoring

**Consumer:** `"quality_assessment"` | **Category:** `MODEL_DIAGNOSTIC` (new from WP-1)  
**Consuming module:** P2 harmonization quality scoring.  
**Action:** Model diagnostic annotations (heteroscedasticity, assumption violations)
can demote `quality_rating` for the affected evidence records.

**Verification for all of WP-5:**
- [ ] Each consumer has a query function in `annotation_lifecycle.py`
- [ ] Each consuming module calls its query function (even if the result is only logged)
- [ ] No consumer silently ignores annotations without at least logging

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

# §5.2 RCT Profile
RCT_PROFILE = PaperAnnotationProfile(...)

# §5.3 Mechanistic/Preclinical Profile
MECHANISTIC_PROFILE = PaperAnnotationProfile(...)

# Lookup
ANNOTATION_PROFILES: dict[PaperSubtype, PaperAnnotationProfile] = {
    PaperSubtype.META_ANALYSIS: META_ANALYSIS_PROFILE,
    PaperSubtype.PAIRWISE_MA: META_ANALYSIS_PROFILE,
    PaperSubtype.NMA: META_ANALYSIS_PROFILE,
    PaperSubtype.IPDMA: META_ANALYSIS_PROFILE,
    PaperSubtype.RCT_EXERCISE: RCT_PROFILE,
    PaperSubtype.RCT_COGNITIVE: RCT_PROFILE,
    # ... etc
}
```

### Task 6.2 — Post-extraction validation using profiles

**File:** `crci/extraction/p1_extraction/runner.py`  
**Action:** After all agents run and annotations are collected, validate
against the paper's annotation profile. If a HIGH-priority category yields
0 annotations, log a warning (not a gate failure — annotations are additive).

```python
def _validate_annotation_yield(
    paper_subtype: PaperSubtype,
    annotations: list[RawAnnotationEmission],
) -> list[str]:
    """Check extracted annotations against paper-type profile expectations."""
    from crci.extraction.p1_extraction.annotation_profiles import ANNOTATION_PROFILES
    profile = ANNOTATION_PROFILES.get(paper_subtype)
    if not profile:
        return []

    warnings = []
    category_counts = Counter(a.category for a in annotations)
    for cp in profile.profiles:
        if cp.expected_yield == "HIGH" and category_counts.get(cp.category.value, 0) == 0:
            warnings.append(
                f"Expected HIGH yield for {cp.category.value} from "
                f"{paper_subtype.value} but got 0"
            )
    return warnings
```

### Task 6.3 — Feed profile into agent prompts (optional enhancement)

**Action:** When constructing agent prompts, if the paper subtype maps to a
profile, include a preamble like: "This paper is a meta-analysis. Prioritize
extracting: research_gap (HIGH), limitation_unmeasured_confounder (MODERATE),
dose_response_qualitative (MODERATE)."

This is an LLM prompt enhancement that improves yield but is not strictly
required — the agents will find annotations regardless.

**Verification:**
- [ ] Profile exists for MA, RCT, and mechanistic paper types
- [ ] Runner logs warnings for HIGH-category misses
- [ ] No gate failures from profile validation (warnings only)

---

## WP-7: Database Index Optimization

**Risk:** Negligible — additive DDL only.  
**Files to modify:** 1 file  
**Estimated scope:** ~10 lines

### Task 7.1 — Add composite index for consumer queries

**File:** `crci/database/schema/008_v2_migration.sql` after existing indexes (~line 136)

**Action:** Add two indexes that the lifecycle promotion + consumer query
functions use:

```sql
-- Composite index for get_promoted_for_consumer() queries
CREATE INDEX IF NOT EXISTS idx_sa_consumer_maturity
    ON study_annotations_v1 (consumer, maturity)
    WHERE active = TRUE;

-- Composite index for accumulation checker cross-paper grouping
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

## WP-8: `structured_data_json` Schema Validation (AT-03 Enhancement)

**Risk:** Low — strengthens existing guardrails.  
**Files to modify:** 1 file  
**Estimated scope:** ~80 lines

### Task 8.1 — Add JSON schema validation for new categories

**File:** `crci/extraction/p1_extraction/annotation_trust_boundary.py`  
**Function:** `_check_at03_category_fields()` (line ~170)

**Current state:** Only validates 3 categories (`ADVERSE_EVENT` → severity required,
`NULL_FINDING_CONTEXT` → powered_adequately required, `LIMITATION_UNMEASURED_CONFOUNDER`
→ confounder_name not generic).

**Action:** Add validation for the protocol §3.3 structured_data_json schemas for
additional categories. Priority additions:

```python
# TEMPORAL_ONSET: onset_weeks required
elif category == AnnotationCategory.TEMPORAL_ONSET:
    onset = data.get("onset_weeks")
    if onset is None:
        return ATBRejection(...)

# TEMPORAL_DECAY: decay_half_life_weeks required
elif category == AnnotationCategory.TEMPORAL_DECAY:
    decay = data.get("decay_half_life_weeks")
    if decay is None:
        return ATBRejection(...)

# ADHERENCE_DATA: adherence_rate required
elif category == AnnotationCategory.ADHERENCE_DATA:
    rate = data.get("adherence_rate")
    if rate is None:
        return ATBRejection(...)

# MECHANISM_HYPOTHESIS: mechanism_type or pathway_id required
elif category == AnnotationCategory.MECHANISM_HYPOTHESIS:
    mtype = data.get("mechanism_type")
    pathway = data.get("pathway_id")
    if not mtype and not pathway:
        return ATBRejection(...)

# RESEARCH_GAP: gap_description required
elif category == AnnotationCategory.RESEARCH_GAP:
    desc = data.get("gap_description")
    if not desc:
        return ATBRejection(...)
```

**Verification:**
- [ ] Each validated category rejects on missing required fields
- [ ] Existing annotations not broken (categories without new rules still pass)

---

## Implementation Order

```
WP-1 (Enum + mappings)         ← Do first, everything depends on it
  ↓
WP-7 (DB indexes)              ← Quick, do alongside WP-1
  ↓
WP-2 (P4 runner annotation     ← Highest impact single change
       wiring)
  ↓
WP-8 (AT-03 JSON validation)   ← Strengthens data quality before WP-3/4
  ↓
WP-3 (P3 SE inflation)         ← Depends on WP-2 patterns
  ↓
WP-4 (Accumulation checker)    ← Depends on WP-1 categories
  ↓
WP-5 (Consumer read paths)     ← Can be done incrementally, consumer by consumer
  ↓
WP-6 (Annotation profiles)     ← Enhancement, lowest priority
```

## Total Estimated Scope

| WP | Lines | Files | Risk |
|----|-------|-------|------|
| WP-1 | ~60 | 5 | Low |
| WP-2 | ~40 | 1 | **Medium** |
| WP-3 | ~50 | 2 | Medium |
| WP-4 | ~200 | 2 (1 new) | Medium |
| WP-5 | ~150 | 8 | Low |
| WP-6 | ~120 | 3 (1 new) | Low |
| WP-7 | ~10 | 1 | Negligible |
| WP-8 | ~80 | 1 | Low |
| **Total** | **~710** | **~20** | |
