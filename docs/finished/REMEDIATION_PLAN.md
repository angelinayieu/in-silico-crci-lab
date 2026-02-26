# Extraction Pipeline Remediation — Slice-by-Slice Plan

**Based on**: DEEP_AUDIT_FINDINGS.md (7 findings, 3 fatal)  
**Approach**: Dependency-ordered slices. Each slice is self-contained, testable, and
produces a measurably better pipeline before the next slice begins.  
**Constraint**: No slice may break an existing passing test or running pipeline.

---

## Dependency Graph

```
Slice 0: DB Cleanup (no code deps)
    ↓
Slice 1: AG05 Prompt Restructure (upstream of everything)
    ↓
Slice 2: TB Precision Gate (consumes AG05 output, guards P2)
    ↓
Slice 3: Concept Engine Hardening (parallel with Slice 2)
    ↓
Slice 4: Evidence Writer Validation (consumes Slice 2+3 outputs)
    ↓
Slice 5: P3 Provenance + SE Tag Storage (consumes Slice 4)
    ↓
Slice 6: Semantic Dedup (consumes Slice 4)
    ↓
Slice 7: Contextual Column Population (consumes Slice 4)
    ↓
Slice 8: DB Safety + Integrity Checks (standalone)
```

Slices 2 and 3 are independent and can be done in either order.
Slices 5, 6, 7 are independent of each other (all depend on Slice 4).

---

## Slice 0: DB Cleanup + WAL Safety

**Goal**: Remove corrupted/orphaned data and prevent WAL-related data loss.  
**Fixes**: Finding 3 (orphaned edge), Finding 5 (UNASSIGNED rows).  
**Risk**: LOW — cleanup only, no logic changes.  
**Estimated scope**: ~40 lines of code + 1 SQL script.

### Step 0.1: One-time DB cleanup script

Create `scripts/cleanup_db.py`:

```python
"""Remove orphaned edges and UNASSIGNED evidence rows.
Run once to fix current DB state."""

import sqlite3
conn = sqlite3.connect("crci_dev.db")
cur = conn.cursor()

# 1. Delete compiled edges with no backing evidence
orphaned = cur.execute("""
    SELECT e.edge_param_id, e.edge_relation_id
    FROM edges_v1 e
    LEFT JOIN edge_evidence_v1 ee 
        ON ee.edge_relation_id = e.edge_relation_id AND ee.active = 1
    WHERE ee.ler_id IS NULL
""").fetchall()
for ep_id, er_id in orphaned:
    cur.execute("DELETE FROM edges_v1 WHERE edge_param_id = ?", (ep_id,))
    print(f"DELETED orphaned edge: {ep_id} ({er_id})")

# 2. Delete compiled edges whose edge_relation_id is not in definitions
undefined = cur.execute("""
    SELECT e.edge_param_id, e.edge_relation_id
    FROM edges_v1 e
    LEFT JOIN edge_relations_definitions_v1 d
        ON d.edge_relation_id = e.edge_relation_id
    WHERE d.edge_relation_id IS NULL
""").fetchall()
for ep_id, er_id in undefined:
    cur.execute("DELETE FROM edges_v1 WHERE edge_param_id = ?", (ep_id,))
    print(f"DELETED undefined edge: {ep_id} ({er_id})")

# 3. Delete UNASSIGNED evidence rows
unassigned = cur.execute("""
    DELETE FROM edge_evidence_v1 WHERE edge_relation_id = 'UNASSIGNED'
""").rowcount
print(f"DELETED {unassigned} UNASSIGNED evidence rows")

# 4. Delete evidence rows with edge IDs not in definitions
dangling = cur.execute("""
    DELETE FROM edge_evidence_v1
    WHERE edge_relation_id NOT IN (
        SELECT edge_relation_id FROM edge_relations_definitions_v1
    )
""").rowcount
print(f"DELETED {dangling} evidence rows with undefined edge IDs")

conn.commit()
conn.close()
```

### Step 0.2: WAL checkpoint on every session commit

**File**: [crci/shared/db.py](crci/shared/db.py) (121 lines)  
**Change**: Add WAL checkpoint after commit in `get_session()`.

```python
# In get_session():
try:
    yield session
    session.commit()
    # Force WAL checkpoint so data survives process kill
    session.execute(text("PRAGMA wal_checkpoint(PASSIVE)"))
except Exception:
    session.rollback()
    raise
```

**Why `PASSIVE`**: Non-blocking. Won't interfere with concurrent reads. Moves committed
pages from WAL to main DB file. If the process is killed after `session.commit()` but
before checkpoint, data is still in the WAL — but it won't be lost by a subsequent
`rm *.wal` because we'll add a guard (Slice 8).

### Step 0.3: Post-compilation integrity check

**File**: [crci/extraction/p4_aggregation/runner.py](crci/extraction/p4_aggregation/runner.py) lines 240-250  
**Change**: After edge write, verify evidence rows exist.

Add at end of `run_p4_aggregation()`:
```python
# Post-compilation integrity check
for ce in context.get("compiled_edges", []):
    edge_id = getattr(ce, "edge_relation_id", None)
    if edge_id:
        count = session.query(EdgeEvidence).filter(
            EdgeEvidence.edge_relation_id == edge_id,
            EdgeEvidence.active == 1,
        ).count()
        if count == 0:
            raise GateViolation(
                "P4-INTEGRITY",
                f"Compiled edge {edge_id} has zero backing evidence rows",
                context={"edge_relation_id": edge_id},
            )
```

### Verification criteria
```sql
-- After running cleanup:
SELECT COUNT(*) FROM edges_v1;                    -- Should be ≤ number of edges with evidence
SELECT COUNT(*) FROM edge_evidence_v1 
  WHERE edge_relation_id = 'UNASSIGNED';          -- Should be 0
SELECT e.edge_relation_id, COUNT(ee.ler_id) 
  FROM edges_v1 e 
  LEFT JOIN edge_evidence_v1 ee ON ee.edge_relation_id = e.edge_relation_id
  GROUP BY e.edge_relation_id
  HAVING COUNT(ee.ler_id) = 0;                    -- Should return 0 rows
```

---

## Slice 1: AG05 Prompt Restructure

**Goal**: Get the LLM to reliably produce `grouping_id` for related statistics.  
**Fixes**: Finding 1 (0% group completion — the #1 cascading root cause).  
**Risk**: MEDIUM — prompt changes affect LLM behavior unpredictably.  
**Estimated scope**: Rewrite ~200 lines of ag05_stats_label.txt.

### Problem analysis

The current prompt is 334 lines with 40 label types. The `grouping_id` instruction
appears at line ~162 in a section labeled "### GROUPING:" — deeply buried after
40 label definitions, anchor-gating rules, and disambiguation rules.

The LLM's attention budget is spent on label taxonomy and anchor-token rules
before it even reaches the grouping instruction. When extracting 20+ spans,
the LLM's working memory for grouping is exhausted.

### Step 1.1: Restructure prompt — grouping-first architecture

**File**: [crci/llm/prompts/ag05_stats_label.txt](crci/llm/prompts/ag05_stats_label.txt) (334 lines)

**Structural changes**:

1. **Move GROUPING to the top** — immediately after task description (line ~6)
2. **Reduce to 15 core labels** — cut the 40 to the ones that actually appear in our papers:
   - PRIMARY (6): EFFECT_SIZE, ODDS_RATIO, HAZARD_RATIO, MEAN_DIFFERENCE, UNSTD_BETA, STD_BETA
   - PRECISION (5): SE, CI_LOWER, CI_UPPER, P_VALUE, SD
   - SAMPLE (3): SAMPLE_SIZE, SAMPLE_SIZE_ARM, FOLLOW_UP_DURATION
   - TEST (1): F_STATISTIC
   - Keep the other 25 available as "EXTENDED LABELS (use if applicable)" at the end
3. **Add 3 concrete grouping examples up front** — show the complete JSON for a grouped result
4. **Add explicit rule**: "Every EFFECT_SIZE/OR/HR MUST have at least one of: SE, CI pair, or P_VALUE
   in the same group. If you cannot find a precision measure, state so in the context field."
5. **Simplify anchor-gating** — merge the per-label anchor lists into a single table

**New prompt structure** (target: ~200 lines):

```
LINE 1-5:   Task description
LINE 6-25:  GROUPING RULES (CRITICAL — READ FIRST)
            - Every result = one group with shared grouping_id
            - Group MUST contain: primary + ≥1 precision measure
            - Example: "d=0.79, 95% CI [0.12, 1.46], p=0.02" → 4 spans, same grp_001
LINE 26-40: 15 CORE LABEL TYPES (table format)
LINE 41-55: ANCHOR TOKEN TABLE (single table, all labels)
LINE 56-70: DISAMBIGUATION RULES (years, sample sizes, magnitude)
LINE 71-90: EXTRACTION RULES (what to extract, what not to)
LINE 91-110: OUTPUT FORMAT with complete grouped example
LINE 111-130: EXTENDED LABELS (25 additional types for special cases)
LINE 131-145: CRITICAL REMINDERS
```

### Step 1.2: Add a grouping-quality check to the response parser

**File**: [crci/llm/response_schemas.py](crci/llm/response_schemas.py)

Add a post-parse validation:
```python
def validate_grouping_quality(response: SpanLabelResponse) -> dict[str, Any]:
    """Check that AG05's output has meaningful grouping."""
    spans = response.spans
    groups = defaultdict(list)
    for s in spans:
        if s.grouping_id:
            groups[s.grouping_id].append(s.label_type)
    
    # Count groups that have both a primary and a precision measure
    complete = 0
    for gid, labels in groups.items():
        has_primary = any(l in PRIMARY_EFFECT_TYPES for l in labels)
        has_precision = any(l in {"SE", "CI_LOWER", "CI_UPPER", "P_VALUE"} for l in labels)
        if has_primary and has_precision:
            complete += 1
    
    return {
        "total_spans": len(spans),
        "n_groups": len(groups),
        "n_complete_groups": complete,
        "grouping_rate": complete / max(len(groups), 1),
        "ungrouped_spans": sum(1 for s in spans if not s.grouping_id),
    }
```

### Step 1.3: Add retry logic for zero-grouping responses

**File**: [crci/extraction/p1_extraction/runner.py](crci/extraction/p1_extraction/runner.py)

If `validate_grouping_quality()` shows 0 complete groups and ≥5 total spans:
- Log warning: "AG05 returned 0 complete groups — retrying with grouping emphasis"
- Retry with an additional system message: "CRITICAL: You returned {n} spans but none
  share a grouping_id with their precision measures. Please re-extract and group
  every effect size with its SE, CI, or p-value using shared grouping_ids."
- Limit to 1 retry to avoid cost explosion

### Verification criteria
```
Run pipeline on Cherrier 2013:
  - AG05 should produce ≥4 grp_* groups (WM, Attn, CogComplaints, EpiMem)
  - Each group should have EFFECT_SIZE + at least SE or CI
  - group_completion_rate in QA metrics should be >50% (vs current 0%)
  - TypedNumericValue.se should be non-None for ≥50% of records
```

---

## Slice 2: TB Precision Gate

**Goal**: Hard-reject records that have no precision source. Stop SE=None from propagating.  
**Fixes**: Finding 4 (L6 fallback produces meaningless estimates).  
**Risk**: LOW — adds a gate, reduces volume of bad data, doesn't change good data.  
**Estimated scope**: ~30 lines in TB runner, ~20 lines in P3 runner.  
**Prerequisite**: Slice 1 should be done first (otherwise the gate rejects everything).

### Step 2.1: Add precision gate in TB runner

**File**: [crci/extraction/tb_trust_boundary/runner.py](crci/extraction/tb_trust_boundary/runner.py) lines 207-220

After group assembly (line ~207), before consistency check:

```python
# ── TB-S1c: Precision Gate ──
# HARD REQUIREMENT: Every TypedNumericValue must have a derivable SE.
# Records without ANY precision source (SE, CI pair, p+N, or N+beta)
# will produce L6 fallback SE=1.0 which makes IVW meaningless.
precision_passed = []
precision_rejected = 0
for tv in grouped_evidence:
    has_se = tv.se is not None
    has_ci = (tv.ci_lower is not None and tv.ci_upper is not None)
    has_p_and_n = (tv.p_value is not None and tv.n is not None and tv.n > 2)
    has_n_for_derivation = (tv.n is not None and tv.n > 2 and tv.value is not None)
    
    if has_se or has_ci or has_p_and_n or has_n_for_derivation:
        precision_passed.append(tv)
    else:
        precision_rejected += 1
        logger.info(
            "TB-PRECISION-GATE: Rejected record (β=%.4f, label=%s) — "
            "no SE, CI, p+N, or N available for SE derivation",
            tv.value, tv.label_type,
        )

if precision_rejected > 0:
    logger.warning(
        "TB-PRECISION-GATE: Rejected %d/%d records lacking precision source",
        precision_rejected, len(grouped_evidence),
    )

grouped_evidence = precision_passed
context["grouped_evidence"] = precision_passed
context.setdefault("qa_metrics", {})["precision_rejected"] = precision_rejected
```

### Step 2.2: Downgrade L6 fallback from silent default to gate failure

**File**: [crci/extraction/p3_heterogeneity/runner.py](crci/extraction/p3_heterogeneity/runner.py) lines 180-193

Change the L6 block from a `logger.warning()` + assignment to a `GateViolation`:

```python
# BEFORE (current):
if se_raw is None:
    se_raw = config.SE_DERIVATION_FALLBACK
    se_derivation_tag = "L6_QUALITATIVE"
    logger.warning("P3: Using conservative default SE=%.2f ...", se_raw, ...)

# AFTER:
if se_raw is None:
    raise GateViolation(
        "P3-PRECISION",
        f"Record {getattr(rec, 'ler_id', '?')} reached P3 with no SE, "
        f"CI, p-value, or N. This should have been caught by TB precision "
        f"gate. Record cannot be calibrated.",
        context={"ler_id": getattr(rec, "ler_id", "?")},
    )
```

**Why raise instead of fallback**: With Slice 1 (better grouping) and Slice 2.1 (TB gate),
records reaching P3 without SE should be extremely rare. If they do arrive, it means
the pipeline has a bug that needs fixing, not a graceful fallback.

**Escape hatch**: Keep a config flag `ALLOW_L6_FALLBACK: bool = False` in config.py.
During initial testing of the new prompt (Slice 1), set to `True` temporarily to
measure improvement without crashing. Set to `False` once group_completion_rate > 50%.

### Step 2.3: Remove L6 code path behind config flag

```python
if se_raw is None:
    if config.ALLOW_L6_FALLBACK:
        se_raw = config.SE_DERIVATION_FALLBACK
        se_derivation_tag = "L6_QUALITATIVE"
        logger.warning(
            "P3: L6 FALLBACK SE=%.2f for %s (config.ALLOW_L6_FALLBACK=True)",
            se_raw, getattr(rec, "ler_id", "?"),
        )
    else:
        raise GateViolation(
            "P3-PRECISION",
            f"Record {getattr(rec, 'ler_id', '?')} has no derivable SE. "
            f"Set config.ALLOW_L6_FALLBACK=True to permit L6 qualitative fallback.",
            context={"ler_id": getattr(rec, "ler_id", "?")},
        )
```

### Verification criteria
```python
# Unit test: TB precision gate
tv_good = TypedNumericValue(value=0.5, se=0.1, ...)   # passes
tv_ci   = TypedNumericValue(value=0.5, ci_lower=0.2, ci_upper=0.8, ...)  # passes
tv_pn   = TypedNumericValue(value=0.5, p_value=0.03, n=100, ...)  # passes
tv_bad  = TypedNumericValue(value=0.5, ...)            # REJECTED

# Integration: Run pipeline with L6 fallback disabled
# - If Slice 1 is working: pipeline should pass with >0 evidence rows
# - If Slice 1 is not yet working: pipeline fails at TB gate (expected)
```

---

## Slice 3: Concept Engine Hardening

**Goal**: Reduce UNASSIGNED rate from 35-80% to <10%.  
**Fixes**: Finding 2 (concept engine grounding fails).  
**Risk**: MEDIUM — changes grounding logic, could over-match or under-match.  
**Estimated scope**: ~100 lines in concept_engine.py, ~20 lines in evidence_writer.py.

### Step 3.1: Validate target_edges IDs against definitions

**File**: [crci/extraction/p1_extraction/concept_engine.py](crci/extraction/p1_extraction/concept_engine.py) lines 189-204

```python
def _get_target_edges(self, context: dict[str, Any]) -> list[str]:
    """Extract target edge IDs from meta.json, validated against DB."""
    meta = context.get("companion_meta") or {}
    target_edges = meta.get("target_edges") or meta.get("targeted_edges")
    if not isinstance(target_edges, list):
        return []
    
    # Validate each ID exists in edge_relations_definitions_v1
    valid_ids = {e["edge_relation_id"] for e in self._edges}
    validated = []
    for eid in target_edges:
        if not isinstance(eid, str):
            continue
        if eid in valid_ids:
            validated.append(eid)
        else:
            # Try fuzzy match: EDGE_CORTISOL_DEPRESSION → ER_CORTISOL_DEPRESSION
            fuzzy = eid.replace("EDGE_", "ER_")
            if fuzzy in valid_ids:
                logger.warning(
                    "ConceptEngine: meta.json target_edge '%s' not found, "
                    "auto-corrected to '%s'", eid, fuzzy,
                )
                validated.append(fuzzy)
            else:
                logger.error(
                    "ConceptEngine: meta.json target_edge '%s' does NOT exist "
                    "in edge_relations_definitions_v1 — SKIPPING",
                    eid,
                )
    
    if not validated and target_edges:
        logger.error(
            "ConceptEngine: ALL %d target_edges from meta.json were invalid: %s",
            len(target_edges), target_edges,
        )
    
    return validated
```

### Step 3.2: Improve keyword matching with node labels

**File**: [crci/extraction/p1_extraction/concept_engine.py](crci/extraction/p1_extraction/concept_engine.py) lines 298-325

Current keyword match requires ≥2 overlapping words between span section text and
edge canonical_statement. Problem: paper sections say "cognitive outcomes" while
edge statements say "working memory".

**Enhancement**: Also match against **node labels** (which contain domain terms):

```python
def _match_from_keywords(self, span: SpanLabel) -> str | None:
    """Keyword match using edge descriptions AND node labels."""
    section = (span.source_section or "").lower()
    span_text = (span.value or "").lower()
    context_text = (getattr(span, "context", "") or "").lower()
    combined = section + " " + span_text + " " + context_text
    
    if not combined.strip():
        return None
    
    combined_keywords = set(_extract_keywords(combined))
    
    best_edge: str | None = None
    best_score = 0
    
    for e in self._edges:
        score = 0
        # Match against edge canonical_statement + relation_label
        desc = (e["relation_label"] + " " + e["canonical_statement"]).lower()
        desc_keywords = set(_extract_keywords(desc))
        score += len(combined_keywords & desc_keywords)
        
        # Match against source and target NODE LABELS
        src_label = self._node_labels.get(e["source_node"], "").lower()
        tgt_label = self._node_labels.get(e["target_node"], "").lower()
        node_keywords = set(_extract_keywords(src_label + " " + tgt_label))
        score += len(combined_keywords & node_keywords)
        
        if score > best_score and score >= 2:
            best_score = score
            best_edge = e["edge_relation_id"]
    
    return best_edge
```

**Key change**: We now also match against context field (AG05 provides context like
"Cohen's d for working memory") AND against node labels (NODE_COG_WORKING_MEM →
"working memory"). This dramatically increases keyword overlap.

### Step 3.3: Block UNASSIGNED from entering DB

**File**: [crci/extraction/evidence_writer.py](crci/extraction/evidence_writer.py) line 169

```python
# BEFORE:
edge_relation_id = _get_attr(record, "edge_id") or _get_attr(record, "edge_relation_id") or "UNASSIGNED"

# AFTER:
edge_relation_id = _get_attr(record, "edge_id") or _get_attr(record, "edge_relation_id")
if not edge_relation_id or edge_relation_id == "UNASSIGNED":
    logger.debug("Skipping record: no valid edge_relation_id (UNASSIGNED or None)")
    skipped += 1
    continue
```

### Step 3.4: Add edge existence validation in evidence_writer

After resolving `edge_relation_id`, verify it exists in definitions:

```python
# Validate edge exists in definitions (prevent orphaned evidence)
if not hasattr(write_evidence_rows, '_valid_edge_ids'):
    rows = session.execute(
        text("SELECT edge_relation_id FROM edge_relations_definitions_v1 WHERE active = 1")
    ).fetchall()
    write_evidence_rows._valid_edge_ids = {r[0] for r in rows}

if edge_relation_id not in write_evidence_rows._valid_edge_ids:
    logger.warning(
        "Skipping evidence row: edge_relation_id '%s' not in definitions",
        edge_relation_id,
    )
    skipped += 1
    continue
```

### Verification criteria
```python
# Unit test: EDGE_* → ER_* auto-correction
engine = ConceptEngine(session)
target = engine._get_target_edges({"companion_meta": {"target_edges": ["EDGE_CORTISOL_DEPRESSION"]}})
assert target == ["ER_CORTISOL_DEPRESSION"]  # Auto-corrected

# Unit test: Invalid edge blocked
target = engine._get_target_edges({"companion_meta": {"target_edges": ["NONEXISTENT_EDGE"]}})
assert target == []

# Integration: UNASSIGNED count in DB should decrease to 0
# SELECT COUNT(*) FROM edge_evidence_v1 WHERE edge_relation_id = 'UNASSIGNED';  → 0
```

---

## Slice 4: Evidence Writer Validation Layer

**Goal**: Unified validation for all evidence writes. No junk enters the DB.  
**Fixes**: Finding 5 (UNASSIGNED pollution), Finding 7 (empty columns), ISSUE-8 from PIPELINE_AUDIT.md.  
**Risk**: LOW — adds validation, existing data paths either pass or get rejected.  
**Estimated scope**: ~80 lines new validation function in evidence_writer.py.  
**Prerequisite**: Slices 2+3 (otherwise validation rejects everything).

### Step 4.1: Create `_validate_evidence_row()` function

**File**: [crci/extraction/evidence_writer.py](crci/extraction/evidence_writer.py)

Add before `write_evidence_rows()`:

```python
def _validate_evidence_row(
    edge_relation_id: str | None,
    beta: float | None,
    se: float | None,
    valid_edge_ids: set[str],
) -> tuple[bool, str]:
    """Validate an evidence row before DB insertion.
    
    Returns:
        (is_valid, rejection_reason)
    """
    # V1: edge_relation_id must exist and be in definitions
    if not edge_relation_id or edge_relation_id == "UNASSIGNED":
        return False, "missing or UNASSIGNED edge_relation_id"
    if edge_relation_id not in valid_edge_ids:
        return False, f"edge_relation_id '{edge_relation_id}' not in definitions"
    
    # V2: beta must be a finite number
    if beta is None:
        return False, "beta is None"
    if not math.isfinite(beta):
        return False, f"beta is not finite: {beta}"
    
    # V3: if SE is present, it must be positive and finite
    if se is not None:
        if not math.isfinite(se) or se <= 0:
            return False, f"SE is invalid: {se}"
    
    # V4: beta plausibility (SMD scale)
    if abs(beta) > 10.0:
        return False, f"beta={beta} exceeds plausibility bound |β| < 10"
    
    return True, ""
```

### Step 4.2: Wire validation into write loop

In `write_evidence_rows()`, call `_validate_evidence_row()` before the UPSERT:

```python
# Load valid edge IDs once per call
valid_edge_ids = set(
    r[0] for r in session.execute(
        text("SELECT edge_relation_id FROM edge_relations_definitions_v1 WHERE active = 1")
    ).fetchall()
)

for record in harmonized_records:
    # ... extract fields ...
    
    is_valid, reason = _validate_evidence_row(edge_relation_id, beta, se, valid_edge_ids)
    if not is_valid:
        logger.info("Evidence validation failed: %s (study=%s, edge=%s)", reason, study_id, edge_relation_id)
        skipped += 1
        continue
    
    # ... proceed with UPSERT ...
```

### Verification criteria
```
- UNASSIGNED rows: impossible to insert
- Invalid edge IDs: impossible to insert
- beta=None rows: impossible to insert
- SE=-1 rows: impossible to insert
- Pipeline still writes valid rows successfully
```

---

## Slice 5: P3 SE Derivation Provenance

**Goal**: Store `se_derivation_tag` so downstream consumers know how SE was derived.  
**Fixes**: Finding 4 dead code (`se_derivation_tag` computed but never stored).  
**Risk**: LOW — adds data, doesn't change behavior.  
**Estimated scope**: ~30 lines across 3 files.

### Step 5.1: Thread `se_derivation_tag` into the record

**File**: [crci/extraction/p3_heterogeneity/runner.py](crci/extraction/p3_heterogeneity/runner.py) lines 197-240

After computing `se_derivation_tag`, attach it to the record:

```python
# After se_eff_result = compute_se_eff(inp):

# Store SE derivation provenance on the record
if hasattr(rec, "model_copy"):
    rec = rec.model_copy(update={
        "harmonized_se": se_eff_result.se_effective,
        "se_derivation_level": se_derivation_tag,
    })
elif hasattr(rec, "se_derivation_level"):
    rec.se_derivation_level = se_derivation_tag
```

### Step 5.2: Ensure HarmonizedClaim carries se_derivation_level

**File**: [crci/shared/models/intermediate_states.py](crci/shared/models/intermediate_states.py)

Check if `HarmonizedClaim` has an `se_derivation_level` field. If not, add it:
```python
@dataclass
class HarmonizedClaim:
    ...
    se_derivation_level: str | None = None  # L1_EXACT, L2_CI, L4B_N_DERIVED, etc.
```

### Step 5.3: P2 runner propagates se_derivation_level to HarmonizedClaim

**File**: [crci/extraction/p2_harmonization/runner.py](crci/extraction/p2_harmonization/runner.py) lines 420-440

In the `HarmonizedClaim(...)` constructor in the P2 runner, add:
```python
se_derivation_level=getattr(record, "se_derivation_level", None),
```

### Step 5.4: Evidence writer stores se_derivation_level

Already exists in evidence_writer.py (line 173): `se_derivation_level = _get_attr(record, "se_derivation_level")`.
This field already maps to the DB column. Just need to ensure the upstream
chain propagates a non-None value.

### Verification criteria
```sql
-- After re-extraction:
SELECT se_derivation_level, COUNT(*) 
FROM edge_evidence_v1 
WHERE active = 1 
GROUP BY se_derivation_level;
-- Should show L1_EXACT, L2_CI, etc. — NOT all NULL
```

---

## Slice 6: Semantic Dedup

**Goal**: Prevent 12 betas for the same study × edge × conceptual result.  
**Fixes**: Finding 6 (beta duplication).  
**Risk**: MEDIUM — need to define "same conceptual result" correctly.  
**Estimated scope**: ~60 lines in evidence_writer.py + DB migration.

### Step 6.1: Add semantic uniqueness check

**File**: [crci/extraction/evidence_writer.py](crci/extraction/evidence_writer.py)

Before the UPSERT, check if a row already exists for this study × edge:

```python
# Semantic dedup: one beta per study × edge × effect_type × endpoint
existing_semantic = session.query(EdgeEvidence).filter(
    EdgeEvidence.study_id == study_id,
    EdgeEvidence.edge_relation_id == edge_relation_id,
    EdgeEvidence.active == 1,
).first()

if existing_semantic:
    # Compare SE quality: keep the row with better SE
    existing_se = existing_semantic.se_reported
    new_se = se
    
    if existing_se is not None and new_se is None:
        # Existing row has better precision — skip new
        logger.info("Semantic dedup: keeping existing row (has SE) over new (no SE) for %s/%s", study_id, edge_relation_id)
        skipped += 1
        continue
    elif existing_se is None and new_se is not None:
        # New row has better precision — update existing
        logger.info("Semantic dedup: updating existing row (no SE) with new (has SE) for %s/%s", study_id, edge_relation_id)
        # Fall through to UPSERT which will update
    elif existing_se is not None and new_se is not None:
        # Both have SE — keep the one closer to manually-entered values if any
        # For now: keep the first one (don't overwrite)
        logger.info("Semantic dedup: keeping existing row for %s/%s (both have SE)", study_id, edge_relation_id)
        skipped += 1
        continue
    else:
        # Both lack SE — keep existing
        skipped += 1
        continue
```

### Step 6.2: Add run-level dedup

Within a single pipeline run, prevent extracting multiple betas for the same edge.
Track seen `(study_id, edge_relation_id)` pairs:

```python
# At top of write_evidence_rows():
seen_edges: set[tuple[str, str]] = set()

# In loop, before UPSERT:
dedup_key = (study_id, edge_relation_id)
if dedup_key in seen_edges:
    logger.info("Run-level dedup: skipping duplicate for %s/%s", study_id, edge_relation_id)
    skipped += 1
    continue
seen_edges.add(dedup_key)
```

### Step 6.3: Resolve existing duplicates

Create `scripts/dedup_evidence.py`:
```python
"""For each (study_id, edge_relation_id), keep only the row with:
1. Highest SE quality (non-None SE preferred)
2. Earliest entered_at (manual imports preferred over pipeline)
3. Best se_derivation_level (L1 > L2 > L3 > L4 > L5 > L6)
Deactivate (active=0) all other rows."""
```

### Verification criteria
```sql
-- No study × edge combination should have >1 active row:
SELECT study_id, edge_relation_id, COUNT(*) as cnt
FROM edge_evidence_v1
WHERE active = 1
GROUP BY study_id, edge_relation_id
HAVING cnt > 1;
-- Should return 0 rows
```

---

## Slice 7: Contextual Column Population

**Goal**: Populate study_design, cancer_type, instrument_id, rob_overall, pub_year
so the 7-layer calibration uses correct multipliers instead of catastrophic defaults.  
**Fixes**: Finding 7 (70/96 columns empty → 4.875× SE inflation).  
**Risk**: LOW — adds data, doesn't change logic.  
**Estimated scope**: ~80 lines in evidence_writer.py + P2 runner.

### Step 7.1: Thread study-level metadata from P0/context to evidence_writer

**File**: [crci/extraction/p2_harmonization/runner.py](crci/extraction/p2_harmonization/runner.py) lines 459-472

`write_evidence_rows()` already receives `session` and `run`. Add study metadata:

```python
# Gather study-level metadata from pipeline context
study_metadata = {
    "study_design": study_design_str,
    "cancer_type": classified_paper.get("cancer_type"),
    "treatment_phase": classified_paper.get("treatment_phase"),
    "pub_year": (context.get("companion_meta") or {}).get("pub_year"),
}

evidence_count = write_evidence_rows(
    session=session,
    run=run,
    harmonized_records=aligned_list,
    study_id=study_id,
    paper_subtype=subtype_str,
    study_metadata=study_metadata,  # NEW PARAMETER
)
```

### Step 7.2: Apply metadata in evidence_writer

**File**: [crci/extraction/evidence_writer.py](crci/extraction/evidence_writer.py)

Add `study_metadata: dict[str, Any] | None = None` parameter to `write_evidence_rows()`.
Then in the evidence row construction:

```python
evidence_row = EdgeEvidence(
    ...
    # Study-level contextual columns (from P0/meta.json)
    study_design=study_metadata.get("study_design") if study_metadata else None,
    cancer_type=study_metadata.get("cancer_type") if study_metadata else None,
    treatment_phase=study_metadata.get("treatment_phase") if study_metadata else None,
    pub_year=study_metadata.get("pub_year") if study_metadata else None,
    ...
)
```

### Step 7.3: Populate node_x, node_y from edge definitions

In `write_evidence_rows()`, after resolving `edge_relation_id`, look up edge definition:

```python
# Populate node_x, node_y from edge definition
if edge_relation_id in edge_definitions:
    defn = edge_definitions[edge_relation_id]
    node_x = defn["node_x"]
    node_y = defn["node_y"]
else:
    node_x = None
    node_y = None
```

Where `edge_definitions` is loaded once at top:
```python
edge_definitions = {}
for row in session.execute(text(
    "SELECT edge_relation_id, node_x, node_y FROM edge_relations_definitions_v1 WHERE active = 1"
)).fetchall():
    edge_definitions[row[0]] = {"node_x": row[1], "node_y": row[2]}
```

### Verification criteria
```sql
-- After re-extraction:
SELECT study_design, cancer_type, pub_year, COUNT(*)
FROM edge_evidence_v1
WHERE active = 1
GROUP BY study_design, cancer_type, pub_year;
-- Should show non-NULL values for pipeline-extracted rows
```

---

## Slice 8: DB Safety + Monitoring

**Goal**: Prevent future data loss and add completeness monitoring.  
**Fixes**: Finding 3 prevention, ISSUE-2 from PIPELINE_AUDIT.md.  
**Risk**: LOW — adds guards, doesn't change pipeline logic.  
**Estimated scope**: ~100 lines new file + ~20 lines in db.py.

### Step 8.1: WAL protection warning

**File**: [crci/shared/db.py](crci/shared/db.py)

Add to `init_db()`:
```python
# Warn if WAL file doesn't exist (possible data loss from deletion)
import os
db_path = config.DATABASE_URL.replace("sqlite:///", "")
wal_path = db_path + "-wal"
if os.path.exists(wal_path):
    logger.info("WAL file exists: %s (uncommitted data may be pending)", wal_path)
```

### Step 8.2: Create `scripts/db_guard.py`

```python
"""Database safety guard. Run before any destructive operation.

Functions:
    check_evidence_exists(db_path) -> dict[str, int]
    backup_db(db_path) -> Path
    guard_before_reset(db_path) -> bool  # False = blocked
"""
```

### Step 8.3: Post-pipeline integrity report

Add to `run_extraction()` or pipeline.py — after all stages complete:

```python
def _post_pipeline_integrity_check(session, context):
    """Post-pipeline sanity check. Logs warnings but doesn't block."""
    compiled = context.get("compiled_edges", [])
    for ce in compiled:
        eid = getattr(ce, "edge_relation_id", None)
        if eid:
            # Check evidence backing
            count = session.query(EdgeEvidence).filter(
                EdgeEvidence.edge_relation_id == eid,
                EdgeEvidence.active == 1,
            ).count()
            if count == 0:
                logger.error("INTEGRITY: compiled edge %s has ZERO evidence rows", eid)
            
            # Check edge exists in definitions
            defn = session.execute(text(
                "SELECT 1 FROM edge_relations_definitions_v1 WHERE edge_relation_id = :eid"
            ), {"eid": eid}).fetchone()
            if defn is None:
                logger.error("INTEGRITY: compiled edge %s NOT in definitions", eid)
```

### Verification criteria
```
- rm crci_dev.db-wal → script warns before allowing
- scripts/db_guard.py blocks setup_database.py when evidence exists
- Post-pipeline log shows integrity check results
```

---

## Implementation Timeline

| Slice | Effort | Depends On | Impact |
|-------|--------|------------|--------|
| 0: DB Cleanup | 30 min | Nothing | Removes corrupted data |
| 1: AG05 Prompt | 2 hr | Nothing | Fixes root cause (SE=None) |
| 2: TB Gate | 30 min | Slice 1 | Prevents garbage propagation |
| 3: Concept Engine | 1 hr | Nothing | Fixes UNASSIGNED (parallel with 2) |
| 4: Evidence Validation | 45 min | Slices 2+3 | Unified write validation |
| 5: SE Provenance | 20 min | Slice 4 | Tracks SE derivation method |
| 6: Semantic Dedup | 45 min | Slice 4 | Prevents beta duplication |
| 7: Column Population | 45 min | Slice 4 | Fixes 7-layer inflation |
| 8: DB Safety | 30 min | Nothing | Prevents future data loss |

**Total**: ~7 hours of focused implementation.

**Critical path**: Slice 0 → Slice 1 → Slice 2 → Slice 4 → (5|6|7 in parallel)

Slice 3 and Slice 8 are independent and can be done at any point.

---

## Testing Strategy

### Per-slice validation
Each slice has specific verification criteria listed above. Run these after each slice.

### End-to-end validation after all slices
```bash
# 1. Clean DB
python scripts/cleanup_db.py

# 2. Re-extract Cherrier 2013
python scripts/run_extraction.py --pdf data/manual_uploads/pdfs/cherrier_2013.pdf

# 3. Verify:
#    a. group_completion_rate > 50% (Slice 1)
#    b. 0 UNASSIGNED rows (Slices 3+4)
#    c. evidence rows have SE != None (Slices 1+2)
#    d. evidence rows have study_design, cancer_type (Slice 7)
#    e. ≤1 row per study×edge (Slice 6)
#    f. se_derivation_level is populated (Slice 5)
#    g. compiled edge has matching evidence rows (Slice 0)
#    h. compiled edge SE < 1.0 for a real RCT (all slices working)
python scripts/report_status.py
```

### Success metrics
| Metric | Current | Target | Slice |
|--------|---------|--------|-------|
| group_completion_rate | 0% | >50% | 1 |
| UNASSIGNED rows | 11 | 0 | 3, 4 |
| Evidence rows with SE=None | 13/31 | 0 | 1, 2 |
| Duplicate betas per edge | 12 | 1 | 6 |
| Columns populated per row | 11/96 | ≥20/96 | 7 |
| Compiled edges with evidence | 1/3 | 3/3 | 0 |
| L6 fallback usage | 100% | <10% | 1, 2 |
| Pooled SE for RCT | 1.2-2.3 | <0.5 | All |
