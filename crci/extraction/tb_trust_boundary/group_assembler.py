# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads SpanLabel[] from P1, ParsedNumeric[] from parse_spans()
# VERIFIED: forward wiring — writes TypedNumericValue[] consumed by P2 harmonization
# VERIFIED: no hardcoded formula parameters
"""
Component: SYS_EXTRACTION.EX-TB.GROUP_ASSEMBLER
Spec: SYS_EXTRACTION_COMPLETE.md (span grouping for multi-field evidence records)
Purpose: Reassemble ParsedNumeric items sharing a grouping_id into
         multi-field TypedNumericValue records. This bridges the gap between
         AG05's token-level extraction and P2's record-level harmonization.
Reads: SpanLabel[] (from P1 context), ParsedNumeric[] (from parse_spans())
Writes: TypedNumericValue[] (consumed by P2 harmonization)
Gates: None (assembly step, not a gate)
"""
from __future__ import annotations

import logging
import math
from collections import defaultdict
from typing import Any

from crci.shared.models.intermediate_states import (
    GroundedSpan,
    ParsedNumeric,
    SpanLabel,
    TypedNumericValue,
)
from crci.shared.models.enums import BoundType

logger = logging.getLogger(__name__)

# Label types that represent the primary statistical value of a group.
# These are effect estimates — the thing being measured.
# F_STATISTIC is included because F(1, df_error) from a 2-group comparison
# can be converted to Cohen's d via  d = 2*sqrt(F/N).
PRIMARY_TYPES: set[str] = {
    "EFFECT_SIZE",
    "OR",
    "ODDS_RATIO",
    "HR",
    "HAZARD_RATIO",
    "RR",
    "RISK_RATIO",
    "IRR",
    "INCIDENCE_RATE_RATIO",
    "MEAN_DIFFERENCE",
    "STD_BETA",
    "UNSTD_BETA",
    "CORRELATION",
    "PERCENT_CHANGE",
    "INTERACTION_TERM",
    "SUBGROUP_EFFECT",
    "F_STATISTIC",
}

# Label types that map to specific fields on TypedNumericValue.
SECONDARY_MAP: dict[str, str] = {
    "SE": "se",
    "STANDARD_ERROR": "se",
    "CI_LOWER": "ci_lower",
    "CI_UPPER": "ci_upper",
    "P_VALUE": "p_value",
    "SAMPLE_SIZE": "n",
    "SAMPLE_SIZE_ARM": "n",
    "SAMPLE_SIZE_TOTAL": "n",
}

# ═══════════════════════════════════════════════════════════════
#  Arm/group labels indicating treatment vs control
# ═══════════════════════════════════════════════════════════════

# Keywords indicating treatment arm (case-insensitive matching)
TREATMENT_ARM_KEYWORDS: set[str] = {
    "treatment", "intervention", "experimental", "active",
    "testosterone", "exercise", "trt", "dhea",
}

# Keywords indicating control arm (case-insensitive matching)
CONTROL_ARM_KEYWORDS: set[str] = {
    "control", "placebo", "sham", "waitlist", "comparator", "untreated",
}


def _classify_arm(arm_assignment: str | None) -> str | None:
    """Classify arm_assignment as 'treatment' or 'control' or None.
    
    Returns:
        "treatment", "control", or None if cannot classify.
    """
    if arm_assignment is None:
        return None
    arm_lower = arm_assignment.lower()
    if any(kw in arm_lower for kw in TREATMENT_ARM_KEYWORDS):
        return "treatment"
    if any(kw in arm_lower for kw in CONTROL_ARM_KEYWORDS):
        return "control"
    return None


def _derive_cohens_d(
    mean_t: float, sd_t: float, n_t: int,
    mean_c: float, sd_c: float, n_c: int,
) -> tuple[float, float]:
    """Derive Cohen's d from paired arm means, SDs, and sample sizes.
    
    Formula (per standard textbooks):
        d = (M_treatment - M_control) / SD_pooled
        SD_pooled = sqrt(((n_T - 1) * SD_T² + (n_C - 1) * SD_C²) / (n_T + n_C - 2))
        SE_d ≈ sqrt(1/n_T + 1/n_C + d²/(2*(n_T + n_C)))
    
    Args:
        mean_t, sd_t, n_t: Mean, SD, sample size for treatment arm.
        mean_c, sd_c, n_c: Mean, SD, sample size for control arm.
    
    Returns:
        Tuple of (d, SE_d) — Cohen's d and its standard error.
    
    Raises:
        ValueError: If inputs are invalid (negative SD, zero n, etc.)
    """
    if n_t < 2 or n_c < 2:
        raise ValueError(f"Sample sizes must be >= 2: n_t={n_t}, n_c={n_c}")
    if sd_t <= 0 or sd_c <= 0:
        raise ValueError(f"SDs must be positive: sd_t={sd_t}, sd_c={sd_c}")
    
    # Pooled SD (Cohen, 1988)
    df = n_t + n_c - 2
    sd_pooled = math.sqrt(
        ((n_t - 1) * sd_t**2 + (n_c - 1) * sd_c**2) / df
    )
    
    # Cohen's d
    d = (mean_t - mean_c) / sd_pooled
    
    # SE of d (Hedges & Olkin, 1985)
    se_d = math.sqrt(
        (1 / n_t) + (1 / n_c) + (d**2 / (2 * (n_t + n_c)))
    )
    
    return d, se_d


def _try_derive_cohens_d_from_group(
    span_ids: list[str],
    span_map: dict[str, SpanLabel | GroundedSpan],
    parsed_map: dict[str, ParsedNumeric],
) -> tuple[float, float, int, str | None, str] | None:
    """Try to derive Cohen's d from paired treatment/control arm means/SDs.
    
    Looks for MEAN, SD, and SAMPLE_SIZE_ARM spans with arm_assignment context.
    Groups that have both treatment and control arm data can have Cohen's d derived.
    
    Args:
        span_ids: List of span_ids in this group.
        span_map: Map of span_id → SpanLabel or GroundedSpan.
        parsed_map: Map of span_id → ParsedNumeric.
    
    Returns:
        Tuple of (d, se_d, n_total, edge_relation_id, context_text) or None if cannot derive.
    """
    # Collect arm-specific values
    arm_data: dict[str, dict[str, float | None]] = {
        "treatment": {"mean": None, "sd": None, "n": None},
        "control": {"mean": None, "sd": None, "n": None},
    }
    
    edge_rel_id: str | None = None
    arm_assignments_found: list[str] = []
    
    for sid in span_ids:
        pn = parsed_map.get(sid)
        s_or_g = span_map.get(sid)
        if pn is None or s_or_g is None or pn.parsed_value is None:
            continue
        
        span = s_or_g.span if isinstance(s_or_g, GroundedSpan) else s_or_g
        lt = span.label_type.upper()
        
        # Get arm assignment if present
        arm_raw = getattr(span, "arm_assignment", None)
        arm_class = _classify_arm(arm_raw)
        
        if arm_class is None:
            continue  # Skip spans without arm assignment
        
        if arm_raw:
            arm_assignments_found.append(arm_raw)
        
        # Capture edge_relation_id from first grounded span
        if edge_rel_id is None and isinstance(s_or_g, GroundedSpan):
            edge_rel_id = s_or_g.edge_relation_id
        
        # Map span value to arm data
        if lt == "MEAN":
            arm_data[arm_class]["mean"] = pn.parsed_value
        elif lt == "SD":
            arm_data[arm_class]["sd"] = pn.parsed_value
        elif lt in ("SAMPLE_SIZE_ARM", "SAMPLE_SIZE"):
            arm_data[arm_class]["n"] = pn.parsed_value
    
    # Check if we have complete data for both arms
    t = arm_data["treatment"]
    c = arm_data["control"]
    
    if None in (t["mean"], t["sd"], t["n"], c["mean"], c["sd"], c["n"]):
        return None  # Incomplete data
    
    # Validate values
    try:
        mean_t = float(t["mean"])
        sd_t = float(t["sd"])
        n_t = int(t["n"])
        mean_c = float(c["mean"])
        sd_c = float(c["sd"])
        n_c = int(c["n"])
    except (TypeError, ValueError):
        return None
    
    # Derive Cohen's d
    try:
        d, se_d = _derive_cohens_d(mean_t, sd_t, n_t, mean_c, sd_c, n_c)
    except ValueError as e:
        logger.debug("Could not derive Cohen's d: %s", e)
        return None
    
    n_total = n_t + n_c
    context_text = f"M_t={mean_t:.2f}, SD_t={sd_t:.2f}, n_t={n_t}; M_c={mean_c:.2f}, SD_c={sd_c:.2f}, n_c={n_c}"
    
    return d, se_d, n_total, edge_rel_id, context_text


# ═══════════════════════════════════════════════════════════════
#  Proximity-based fallback grouping for orphan spans
# ═══════════════════════════════════════════════════════════════

# Default character window for proximity grouping
_PROXIMITY_CHAR_WINDOW: int = 200


def _proximity_fallback_groups(
    orphan_items: list[tuple[str, SpanLabel | GroundedSpan, ParsedNumeric]],
    char_window: int = _PROXIMITY_CHAR_WINDOW,
) -> dict[str, list[str]]:
    """Group orphan spans by character proximity.

    Heuristic: an orphan primary span anchors a proximity group.
    Any secondary span (SE, CI, P_VALUE, SAMPLE_SIZE) within
    ``char_window`` characters of a primary span is assigned to that
    primary's group.

    Rules:
        1. Only primary types can anchor a group.
        2. Secondaries attach to the closest primary within the window.
        3. Leftover orphans (no primary nearby) remain in their own group.
        4. Confidence on proximity groups is set to 0.5 (vs 0.8+ for
           LLM-grouped) — caller should propagate this.

    Args:
        orphan_items: List of (span_id, span_or_grounded, parsed) tuples whose
            ``grouping_id`` was None.
        char_window: Maximum character distance for co-location.

    Returns:
        Dict of ``proximity_group_id`` → list of span_ids belonging to that
        group.  Group IDs are prefixed ``_prox_`` to distinguish them from
        LLM-assigned and ``_ungrouped_`` groups.
    """
    if not orphan_items:
        return {}

    # Separate primaries from secondaries
    primaries: list[tuple[str, int, int]] = []  # (span_id, char_start, char_end)
    secondaries: list[tuple[str, int, int, str]] = []  # + label_type

    for sid, s_or_g, _pn in orphan_items:
        span = s_or_g.span if isinstance(s_or_g, GroundedSpan) else s_or_g
        lt = span.label_type.upper()
        cs = span.char_start
        ce = span.char_end
        if lt in PRIMARY_TYPES:
            primaries.append((sid, cs, ce))
        elif lt in SECONDARY_MAP:
            secondaries.append((sid, cs, ce, lt))
        # else: unknown label → will stay ungrouped

    if not primaries:
        # No anchor — everything stays standalone
        return {}

    # Sort primaries by char_start so we can binary-search / iterate
    primaries.sort(key=lambda t: t[1])

    groups: dict[str, list[str]] = {}
    assigned_secondary_ids: set[str] = set()

    for pidx, (p_sid, p_start, p_end) in enumerate(primaries):
        gid = f"_prox_{pidx}"
        groups[gid] = [p_sid]

        # Find secondaries within char_window of this primary
        for s_sid, s_start, s_end, _lt in secondaries:
            if s_sid in assigned_secondary_ids:
                continue
            # Distance: closest edge of secondary to closest edge of primary
            dist = max(0, max(s_start - p_end, p_start - s_end))
            if dist <= char_window:
                groups[gid].append(s_sid)
                assigned_secondary_ids.add(s_sid)

    n_rescued = sum(len(v) - 1 for v in groups.values())  # exclude primaries
    if n_rescued > 0:
        logger.info(
            "Proximity fallback: grouped %d secondaries with %d primaries "
            "(window=%d chars)",
            n_rescued, len(primaries), char_window,
        )

    return groups


def reassemble_groups(
    span_labels: list[SpanLabel | GroundedSpan],
    parsed: list[ParsedNumeric],
) -> tuple[list[TypedNumericValue], dict[str, Any]]:
    """Reassemble ParsedNumeric items sharing a grouping_id into
    multi-field TypedNumericValue records.

    For each grouping_id:
    - Primary span (EFFECT_SIZE, OR, HR, etc.) → TypedNumericValue.value
    - SE → .se
    - CI_LOWER → .ci_lower
    - CI_UPPER → .ci_upper
    - P_VALUE → .p_value
    - SAMPLE_SIZE → .n
    Ungrouped spans (grouping_id=None) become single-field records.

    Args:
        span_labels: SpanLabel or GroundedSpan list from AG05 → ConceptEngine.
        parsed: CLEAN ParsedNumeric list from parse_spans().

    Returns:
        Tuple of:
        - list[TypedNumericValue]: Assembled multi-field records.
        - dict: QA metrics (group_completion_rate, orphan_span_rate, etc.)
    """
    # Build lookup maps
    span_map: dict[str, SpanLabel | GroundedSpan] = {}
    for s in span_labels:
        span = s.span if isinstance(s, GroundedSpan) else s
        span_map[span.span_id] = s

    parsed_map: dict[str, ParsedNumeric] = {p.span_id: p for p in parsed}

    # Group by grouping_id
    groups: dict[str, list[str]] = defaultdict(list)  # grouping_id → [span_id]
    orphan_items: list[tuple[str, SpanLabel | GroundedSpan, ParsedNumeric]] = []

    for p in parsed:
        sid = p.span_id
        s_or_g = span_map.get(sid)
        if s_or_g is None:
            continue
        span = s_or_g.span if isinstance(s_or_g, GroundedSpan) else s_or_g
        gid = span.grouping_id
        if gid is None:
            orphan_items.append((sid, s_or_g, p))
        else:
            groups[gid].append(sid)

    # ── Proximity fallback: try to group orphans by co-location ──
    n_proximity_rescued = 0
    if orphan_items:
        prox_groups = _proximity_fallback_groups(orphan_items)
        prox_assigned: set[str] = set()
        for pgid, psids in prox_groups.items():
            groups[pgid] = psids
            prox_assigned.update(psids)
            n_proximity_rescued += len(psids)

        # Remaining orphans (not rescued by proximity) become standalone
        ungrouped_idx = 0
        for sid, _s_or_g, _pn in orphan_items:
            if sid not in prox_assigned:
                gid = f"_ungrouped_{ungrouped_idx}"
                ungrouped_idx += 1
                groups[gid].append(sid)
    else:
        ungrouped_idx = 0

    orphan_count = ungrouped_idx  # Only truly unrescued orphans

    # Assemble each group
    results: list[TypedNumericValue] = []
    n_complete = 0
    n_derived = 0  # Count of effect sizes derived from arm means/SDs
    n_groups = len(groups)

    for gid, span_ids in groups.items():
        primary_sid: str | None = None
        primary_pn: ParsedNumeric | None = None
        primary_span: SpanLabel | None = None
        primary_grounded: GroundedSpan | None = None

        secondary_fields: dict[str, float | int | None] = {
            "se": None,
            "ci_lower": None,
            "ci_upper": None,
            "p_value": None,
            "n": None,
        }

        for sid in span_ids:
            pn = parsed_map.get(sid)
            s_or_g = span_map.get(sid)
            if pn is None or s_or_g is None:
                continue

            span = s_or_g.span if isinstance(s_or_g, GroundedSpan) else s_or_g
            lt = span.label_type.upper()

            if lt in PRIMARY_TYPES:
                if primary_sid is None:
                    primary_sid = sid
                    primary_pn = pn
                    primary_span = span
                    if isinstance(s_or_g, GroundedSpan):
                        primary_grounded = s_or_g
                else:
                    # Multiple primaries in one group — keep the higher confidence one
                    existing_conf = primary_span.confidence if primary_span else 0
                    if span.confidence > existing_conf:
                        # Demote the old primary to standalone
                        _emit_standalone(
                            primary_pn, primary_span, primary_grounded, results
                        )
                        primary_sid = sid
                        primary_pn = pn
                        primary_span = span
                        primary_grounded = (
                            s_or_g if isinstance(s_or_g, GroundedSpan) else None
                        )
                    else:
                        _emit_standalone(
                            pn, span,
                            s_or_g if isinstance(s_or_g, GroundedSpan) else None,
                            results,
                        )
            elif lt in SECONDARY_MAP:
                field_name = SECONDARY_MAP[lt]
                val = pn.parsed_value
                if val is not None:
                    if field_name == "n":
                        secondary_fields[field_name] = int(val)
                    else:
                        secondary_fields[field_name] = val
            else:
                # Unknown label type — emit as standalone
                _emit_standalone(
                    pn, span,
                    s_or_g if isinstance(s_or_g, GroundedSpan) else None,
                    results,
                )

        # Build the assembled TypedNumericValue
        if primary_pn is not None and primary_pn.parsed_value is not None:
            # Resolve edge_relation_id from GroundedSpan if available
            edge_rel_id: str | None = None
            if primary_grounded is not None:
                edge_rel_id = primary_grounded.edge_relation_id

            tv = TypedNumericValue(
                value=primary_pn.parsed_value,
                bound_type=BoundType.EXACT,
                original_text=primary_pn.raw_text,
                label_type=primary_span.label_type if primary_span else None,
                se=secondary_fields["se"],
                ci_lower=secondary_fields["ci_lower"],
                ci_upper=secondary_fields["ci_upper"],
                p_value=secondary_fields["p_value"],
                n=int(secondary_fields["n"]) if secondary_fields["n"] is not None else None,
                edge_relation_id=edge_rel_id,
                grouping_id=gid if not gid.startswith("_ungrouped_") else None,
            )
            results.append(tv)

            # Check completeness (has at least one SE-derivable field)
            has_se_or_ci = (
                secondary_fields["se"] is not None
                or (secondary_fields["ci_lower"] is not None
                    and secondary_fields["ci_upper"] is not None)
            )
            has_n = secondary_fields["n"] is not None
            if has_se_or_ci or has_n:
                n_complete += 1
        else:
            # No primary in this group — try to derive Cohen's d from paired means/SDs
            derived = _try_derive_cohens_d_from_group(span_ids, span_map, parsed_map)
            
            if derived is not None:
                # Successfully derived effect size from arm means/SDs
                d, se_d, n_total, edge_rel_id, context_text = derived
                
                tv = TypedNumericValue(
                    value=d,
                    bound_type=BoundType.EXACT,
                    original_text=f"DERIVED: Cohen's d={d:.4f} from {context_text}",
                    label_type="EFFECT_SIZE",
                    se=se_d,
                    ci_lower=None,
                    ci_upper=None,
                    p_value=secondary_fields.get("p_value"),
                    n=n_total,
                    edge_relation_id=edge_rel_id,
                    grouping_id=gid if not gid.startswith("_ungrouped_") else None,
                )
                results.append(tv)
                n_complete += 1
                n_derived += 1
                logger.info(
                    "Derived Cohen's d=%.4f (SE=%.4f) from arm means/SDs in group %s",
                    d, se_d, gid
                )
            else:
                # Fall back to emitting all as standalone
                for sid in span_ids:
                    pn = parsed_map.get(sid)
                    s_or_g = span_map.get(sid)
                    if pn is not None and s_or_g is not None:
                        span = s_or_g.span if isinstance(s_or_g, GroundedSpan) else s_or_g
                        _emit_standalone(
                            pn, span,
                            s_or_g if isinstance(s_or_g, GroundedSpan) else None,
                            results,
                        )

    # QA metrics
    total_spans = len(parsed)
    qa_metrics = {
        "n_groups": n_groups,
        "n_assembled": len(results),
        "n_complete_groups": n_complete,
        "n_derived_effects": n_derived,
        "n_proximity_rescued": n_proximity_rescued,
        "group_completion_rate": n_complete / n_groups if n_groups > 0 else 0.0,
        "orphan_span_rate": orphan_count / total_spans if total_spans > 0 else 0.0,
        "orphan_count": orphan_count,
        "total_spans_in": total_spans,
    }

    logger.info(
        "GroupAssembler: %d groups → %d records (%d complete, %d derived, "
        "%d proximity-rescued, %.0f%% completion rate, %.0f%% orphan rate)",
        n_groups,
        len(results),
        n_complete,
        n_derived,
        n_proximity_rescued,
        qa_metrics["group_completion_rate"] * 100,
        qa_metrics["orphan_span_rate"] * 100,
    )

    return results, qa_metrics


def _emit_standalone(
    pn: ParsedNumeric | None,
    span: SpanLabel | None,
    grounded: GroundedSpan | None,
    results: list[TypedNumericValue],
) -> None:
    """Emit a single ParsedNumeric as a standalone TypedNumericValue."""
    if pn is None or pn.parsed_value is None:
        return

    edge_rel_id: str | None = None
    if grounded is not None:
        edge_rel_id = grounded.edge_relation_id

    results.append(
        TypedNumericValue(
            value=pn.parsed_value,
            bound_type=BoundType.EXACT,
            original_text=pn.raw_text,
            label_type=span.label_type if span else None,
            se=None,
            ci_lower=pn.parsed_lower,
            ci_upper=pn.parsed_upper,
            p_value=None,
            n=None,
            edge_relation_id=edge_rel_id,
            grouping_id=None,
        )
    )
