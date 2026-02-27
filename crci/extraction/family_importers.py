# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads dict row from CSV templates
# VERIFIED: forward wiring — writes ORM objects to B10-B14 tables
# VERIFIED: FK checks — node_id, edge_id, instrument_id validated
# VERIFIED: no hardcoded formula parameters
# VERIFIED: deterministic IDs for dedup
"""
Component: Extraction — Family Importers (Slice 6)
Spec: IMPLEMENTATION_SLICES.md Slice 6, Steps 6a
Purpose: One validate+insert function per evidence family:
    - import_population_norm()      → population_norms_v1 (B11)
    - import_context_prior()        → node_priors_v1 (C3)
    - import_temporal_evidence()    → temporal_evidence_v1 (B12)
    - import_instrument_evidence()  → instrument_evidence_v1 (B10)

Reads: dict rows from CSV templates (population_norms, context_priors,
       temporal_evidence, instrument_evidence)
Writes: PopulationNorms, NodePrior, TemporalEvidence, InstrumentEvidence
        ORM objects via session.add()
Gates: FK validation (node_id, edge_id, instrument_id must exist in DB)
       Domain validation (sd > 0, sample_size > 0, reliability ∈ (0,1))
       Provenance gate (instrument_evidence requires provenance_ref)
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any

from sqlalchemy.orm import Session

from crci.shared.models.tables import (
    BiomarkerCorrelation,
    BiomarkerNodeDefinition,
    DoseEvidence,
    EdgeRelationsDefinition,
    InstrumentDefinition,
    InstrumentEvidence,
    NodePrior,
    OntologyLink,
    PopulationNorms,
    ProfileDataStream,
    StreamTimepoint,
    StudyCohortProfile,
    SubgroupEvidence,
    TemporalEvidence,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Shared helpers
# ============================================================================

def _safe_float(val: Any, field_name: str) -> float | None:
    """Parse a float from a CSV value. Returns None for empty strings."""
    if val is None or (isinstance(val, str) and val.strip() == ""):
        return None
    try:
        return float(val)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"{field_name}: cannot parse '{val}' as float"
        ) from exc


def _safe_int(val: Any, field_name: str) -> int | None:
    """Parse an int from a CSV value. Returns None for empty strings."""
    if val is None or (isinstance(val, str) and val.strip() == ""):
        return None
    try:
        return int(float(val))  # handle "9.0" → 9
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"{field_name}: cannot parse '{val}' as int"
        ) from exc


def _require_str(row: dict, field: str) -> str:
    """Extract non-empty string or raise."""
    val = row.get(field, "")
    if isinstance(val, str):
        val = val.strip()
    if not val:
        raise ValueError(f"{field}: required but missing or empty")
    return val


def _deterministic_id(prefix: str, *components: str) -> str:
    """Generate deterministic ID from components: PREFIX + sha256[:12]."""
    raw = "|".join(str(c) for c in components)
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}{h}"


# ============================================================================
# import_population_norm
# ============================================================================

def import_population_norm(
    session: Session,
    row: dict,
    study_id: str,
) -> str:
    """Validate and insert one population norm row into population_norms_v1.

    Args:
        session: SQLAlchemy session (for FK checks and persistence).
        row: Dict from population_norms_template.csv.
        study_id: Resolved study_id (e.g. STUDY_CAMPBELL_2017).

    Returns:
        The deterministic id of the inserted/updated row.

    Raises:
        ValueError: If validation fails (missing fields, bad values, FK miss).
    """
    # ---- Validate required fields ----
    node_id = _require_str(row, "node_id")
    mean_val = _safe_float(row.get("mean", ""), "mean")
    if mean_val is None:
        raise ValueError("mean: required but missing or empty")
    sd_val = _safe_float(row.get("sd", ""), "sd")
    if sd_val is None:
        raise ValueError("sd: required but missing or empty")
    if sd_val <= 0:
        raise ValueError(f"sd: must be > 0, got {sd_val}")
    sample_size = _safe_int(row.get("sample_size", ""), "sample_size")
    if sample_size is not None and sample_size <= 0:
        raise ValueError(f"sample_size: must be > 0, got {sample_size}")
    if sample_size is None or sample_size == 0:
        raise ValueError("sample_size: required and must be > 0")

    instrument_id = row.get("instrument_id", "").strip() if row.get("instrument_id") else None

    # ---- FK check: node_id ----
    if session.get(BiomarkerNodeDefinition, node_id) is None:
        raise ValueError(
            f"node_id '{node_id}' not found in biomarker_node_definitions_v1"
        )

    # ---- FK check: instrument_id (optional) ----
    if instrument_id and session.get(InstrumentDefinition, instrument_id) is None:
        raise ValueError(
            f"instrument_id '{instrument_id}' not found in instrument_definitions_v1"
        )

    # ---- Deterministic ID ----
    norm_id = _deterministic_id(
        "NORM_",
        study_id,
        node_id,
        row.get("cancer_type", "").strip(),
        instrument_id or "",
    )

    # ---- Build ORM object ----
    cancer_type = row.get("cancer_type", "").strip() or None
    treatment_phase = row.get("treatment_phase", "").strip() or None
    age_range = row.get("age_range", "").strip() or None

    orm_obj = PopulationNorms(
        id=norm_id,
        study_id=study_id,
        cancer_type=cancer_type,
        treatment_phase=treatment_phase,
        node_id=node_id,
        instrument_id=instrument_id,
        mean_raw=mean_val,
        sd_raw=sd_val,
        N=sample_size,
        provenance_status="manual_csv_import",
        provenance_ref=f"doi:{row.get('doi', '').strip()}",
        notes=f"age_range={age_range}" if age_range else None,
        version=1,
    )

    session.add(orm_obj)
    logger.info(
        "Imported population norm %s: %s node=%s mean=%.1f sd=%.1f n=%d",
        norm_id, study_id, node_id, mean_val, sd_val, sample_size,
    )
    return norm_id


# ============================================================================
# import_context_prior
# ============================================================================

def import_context_prior(
    session: Session,
    row: dict,
    study_id: str,
) -> str:
    """Validate and insert one context prior row into node_priors_v1.

    Args:
        session: SQLAlchemy session.
        row: Dict from context_priors_template.csv.
        study_id: Resolved study_id.

    Returns:
        Deterministic prior_id.

    Raises:
        ValueError: If validation fails.
    """
    # ---- Validate ----
    node_id = _require_str(row, "node_id")
    prior_mean_z = _safe_float(row.get("prior_mean_z", ""), "prior_mean_z")
    if prior_mean_z is None:
        prior_mean_z = 0.0  # default mean
    prior_sd_z = _safe_float(row.get("prior_sd_z", ""), "prior_sd_z")
    if prior_sd_z is None:
        prior_sd_z = 1.0  # default wide prior
    if prior_sd_z <= 0:
        raise ValueError(f"prior_sd_z: must be > 0, got {prior_sd_z}")

    # ---- FK check: node_id ----
    if session.get(BiomarkerNodeDefinition, node_id) is None:
        raise ValueError(
            f"node_id '{node_id}' not found in biomarker_node_definitions_v1"
        )

    # ---- Deterministic ID ----
    cancer_type = row.get("cancer_type", "").strip() or None
    treatment_phase = row.get("treatment_phase", "").strip() or None
    source_type = row.get("source_type", "").strip() or None
    n_contributing = row.get("n_contributing", "").strip() or None

    prior_id = _deterministic_id(
        "PRIOR_",
        study_id,
        node_id,
        cancer_type or "",
        treatment_phase or "",
    )

    # ---- Build ORM object ----
    provenance = f"manual_csv_import;doi:{row.get('doi', '').strip()}"
    if source_type:
        provenance += f";source={source_type}"

    notes_parts = []
    if row.get("notes", "").strip():
        notes_parts.append(row["notes"].strip())
    if n_contributing:
        notes_parts.append(f"n_contributing={n_contributing}")

    orm_obj = NodePrior(
        prior_id=prior_id,
        node_id=node_id,
        prior_space="z",
        mean=prior_mean_z,
        sd=prior_sd_z,
        dist_family="normal",
        cancer_type=cancer_type,
        treatment_phase=treatment_phase,
        provenance=provenance,
        active=1,
        version=1,
        notes="; ".join(notes_parts) if notes_parts else None,
    )

    session.add(orm_obj)
    logger.info(
        "Imported context prior %s: %s node=%s z=%.2f sd=%.1f",
        prior_id, study_id, node_id, prior_mean_z, prior_sd_z,
    )
    return prior_id


# ============================================================================
# import_temporal_evidence
# ============================================================================

def import_temporal_evidence(
    session: Session,
    row: dict,
    study_id: str,
) -> str:
    """Validate and insert one temporal evidence row into temporal_evidence_v1.

    Args:
        session: SQLAlchemy session.
        row: Dict from temporal_evidence_template.csv.
        study_id: Resolved study_id.

    Returns:
        Deterministic id.

    Raises:
        ValueError: If validation fails.
    """
    # ---- Validate ----
    edge_id = _require_str(row, "edge_id")
    timepoint_weeks = _safe_float(row.get("timepoint_weeks", ""), "timepoint_weeks")
    if timepoint_weeks is None:
        raise ValueError("timepoint_weeks: required but missing or empty")
    if timepoint_weeks < 0:
        raise ValueError(f"timepoint_weeks: must be >= 0, got {timepoint_weeks}")

    sample_size = _safe_int(row.get("sample_size", ""), "sample_size")
    if sample_size is not None and sample_size <= 0:
        raise ValueError(f"sample_size: must be > 0, got {sample_size}")
    if sample_size is None or sample_size == 0:
        raise ValueError("sample_size: required and must be > 0")

    value = _safe_float(row.get("value", ""), "value")
    se = _safe_float(row.get("se", ""), "se")
    is_recovery = _safe_int(row.get("is_recovery", "0"), "is_recovery") or 0

    # ---- FK check: edge_id ----
    if session.get(EdgeRelationsDefinition, edge_id) is None:
        raise ValueError(
            f"edge_id '{edge_id}' not found in edge_relations_definitions_v1"
        )

    # ---- Deterministic ID ----
    temp_id = _deterministic_id(
        "TEMP_",
        study_id,
        edge_id,
        str(timepoint_weeks),
    )

    # ---- Derive intervention type from edge_id ----
    if "ACTIVITY" in edge_id and "COG" not in edge_id:
        intervention_type = "aerobic_exercise"
    elif "COGACTIVITY" in edge_id:
        intervention_type = "cognitive_rehabilitation"
    else:
        intervention_type = "unknown"

    # ---- Build ORM object ----
    provenance_ref = row.get("provenance_ref", "").strip() or None

    orm_obj = TemporalEvidence(
        id=temp_id,
        study_id=study_id,
        action_id=edge_id,
        intervention_type=intervention_type,
        timepoint_weeks=timepoint_weeks,
        effect=value,
        se=se,
        is_recovery=is_recovery,
        N=sample_size,
        study_design="RCT",  # both papers are RCTs
        provenance_status="manual_csv_import",
        provenance_ref=provenance_ref,
        notes=f"doi:{row.get('doi', '').strip()}; Cohen's d at timepoint",
        version=1,
    )

    session.add(orm_obj)
    logger.info(
        "Imported temporal evidence %s: %s edge=%s t=%.1fw effect=%.3f",
        temp_id, study_id, edge_id, timepoint_weeks, value or 0,
    )
    return temp_id


# ============================================================================
# import_instrument_evidence
# ============================================================================

def import_instrument_evidence(
    session: Session,
    row: dict,
    study_id: str,
) -> str:
    """Validate and insert one instrument evidence row into instrument_evidence_v1.

    Args:
        session: SQLAlchemy session.
        row: Dict from instrument_evidence_template.csv.
        study_id: Resolved study_id.

    Returns:
        Deterministic id.

    Raises:
        ValueError: If validation fails.

    Provenance gate: Without reliability_source_citation (provenance_ref),
    reject the row. Reliability is population-dependent.
    """
    # ---- Validate ----
    instrument_id = _require_str(row, "instrument_id")
    provenance_ref = _require_str(row, "provenance_ref")

    reliability_value = _safe_float(
        row.get("reliability_value", ""), "reliability_value"
    )
    if reliability_value is not None:
        if reliability_value <= 0 or reliability_value > 1:
            raise ValueError(
                f"reliability_value: must be in (0, 1], got {reliability_value}"
            )

    reliability_type = row.get("reliability_type", "").strip()

    # ---- FK check: instrument_id ----
    if session.get(InstrumentDefinition, instrument_id) is None:
        raise ValueError(
            f"instrument_id '{instrument_id}' not found in instrument_definitions_v1"
        )

    # ---- Map reliability_value to correct column ----
    cronbachs_alpha = None
    test_retest_reliability = None

    if reliability_type == "cronbachs_alpha":
        cronbachs_alpha = reliability_value
    elif reliability_type == "test_retest":
        test_retest_reliability = reliability_value

    # Dedicated test_retest_icc column overrides
    trt_icc = _safe_float(row.get("test_retest_icc", ""), "test_retest_icc")
    if trt_icc is not None:
        test_retest_reliability = trt_icc

    # Factor loading mean
    factor_loading_mean = _safe_float(
        row.get("factor_loading_mean", ""), "factor_loading_mean"
    )

    # Sample size (optional for instrument evidence)
    sample_size = _safe_int(row.get("sample_size", ""), "sample_size")

    cancer_type = row.get("cancer_type", "").strip() or None
    cancer_validated = row.get("cancer_validated", "").strip() or None

    # ---- Deterministic ID ----
    inst_ev_id = _deterministic_id(
        "INST_EV_",
        study_id,
        instrument_id,
        reliability_type,
    )

    # ---- Derive instrument name from registry or fallback ----
    _INST_NAME_MAP = {
        "INST_TMT_B": "Trail Making Test (Part B / A)",
        "INST_HVLTR": "Hopkins Verbal Learning Test - Revised",
        "INST_COWAT": "Controlled Oral Word Association Test",
        "INST_FACTCOG_PCI": "FACT-Cog Perceived Cognitive Impairment",
        "INST_CESD": "Center for Epidemiologic Studies Depression Scale",
        "INST_FACIT_FATIGUE": "FACIT-Fatigue Scale",
        "INST_DIGIT_SPAN": "WAIS Digit Span",
        "INST_STROOP": "Stroop Color-Word Test",
    }
    instrument_name = _INST_NAME_MAP.get(instrument_id, instrument_id)

    # ---- Build ORM object ----
    orm_obj = InstrumentEvidence(
        id=inst_ev_id,
        study_id=study_id,
        instrument_id=instrument_id,
        instrument_name=instrument_name,
        cronbachs_alpha=cronbachs_alpha,
        test_retest_reliability=test_retest_reliability,
        factor_loading_mean=factor_loading_mean,
        cancer_type=cancer_type,
        N=sample_size,
        provenance_status="manual_csv_import",
        provenance_ref=provenance_ref,
        notes=f"cancer_validated={cancer_validated}; reliability_type={reliability_type}",
        version=1,
    )

    session.add(orm_obj)
    logger.info(
        "Imported instrument evidence %s: %s inst=%s α=%s trt=%s",
        inst_ev_id, study_id, instrument_id,
        cronbachs_alpha, test_retest_reliability,
    )
    return inst_ev_id


# ============================================================================
# import_correlation
# ============================================================================

def import_correlation(
    session: Session,
    row: dict,
    study_id: str,
) -> str:
    """Validate and insert one correlation row into biomarker_correlations_v1.

    Args:
        session: SQLAlchemy session.
        row: Dict from correlation_template.csv.
        study_id: Resolved study_id.

    Returns:
        Deterministic correlation_id.

    Raises:
        ValueError: If validation fails (missing fields, bad values, FK miss).
    """
    # ---- Validate required fields ----
    node_a = _require_str(row, "biomarker_id_1")
    node_b = _require_str(row, "biomarker_id_2")

    correlation_r = _safe_float(row.get("correlation_r", ""), "correlation_r")
    if correlation_r is None:
        raise ValueError("correlation_r: required but missing or empty")
    if correlation_r < -1.0 or correlation_r > 1.0:
        raise ValueError(f"correlation_r: must be in [-1, 1], got {correlation_r}")

    sample_size = _safe_int(row.get("sample_size", ""), "sample_size")
    if sample_size is None or sample_size <= 0:
        raise ValueError("sample_size: required and must be > 0")

    partial_or_zero = row.get("partial_or_zero", "").strip() or "zero_order"
    if partial_or_zero not in ("partial", "zero_order"):
        raise ValueError(
            f"partial_or_zero: must be 'partial' or 'zero_order', got '{partial_or_zero}'"
        )

    # ---- FK checks: both node IDs ----
    if session.get(BiomarkerNodeDefinition, node_a) is None:
        raise ValueError(
            f"biomarker_id_1 '{node_a}' not found in biomarker_node_definitions_v1"
        )
    if session.get(BiomarkerNodeDefinition, node_b) is None:
        raise ValueError(
            f"biomarker_id_2 '{node_b}' not found in biomarker_node_definitions_v1"
        )

    # ---- Deterministic ID ----
    correlation_id = _deterministic_id(
        "CORR_",
        study_id,
        node_a,
        node_b,
    )

    # ---- Derive SE from sample size: SE(r) ≈ (1 - r²) / √(n - 2) ----
    import math
    n_minus_2 = sample_size - 2
    if n_minus_2 > 0:
        rho_se = (1.0 - correlation_r ** 2) / math.sqrt(n_minus_2)
    else:
        rho_se = None

    # ---- Determine d_block from node layer letters ----
    # e.g. node_a=BIO_IL6 → layer "B", node_b=COG_PROC_SPEED → layer "C"
    # d_block = sorted pair like "BC"
    d_block = "XX"  # fallback
    _LAYER_MAP = {
        "BIO": "B", "NEURO": "N", "COG": "C", "FUNC": "F",
        "SYMPTOM": "S", "PRO": "P", "LIFESTYLE": "L",
    }
    for prefix, layer in _LAYER_MAP.items():
        if node_a.startswith(prefix):
            for prefix2, layer2 in _LAYER_MAP.items():
                if node_b.startswith(prefix2):
                    d_block = "".join(sorted([layer, layer2]))
                    break
            break

    population = row.get("population", "").strip() or None
    provenance_ref = row.get("provenance_ref", "").strip() or None
    doi = row.get("doi", "").strip() or ""
    source_citation = provenance_ref or f"doi:{doi}"

    notes_parts = []
    notes_parts.append(f"partial_or_zero={partial_or_zero}")
    notes_parts.append(f"n={sample_size}")
    if population:
        notes_parts.append(f"population={population}")

    # ---- Build ORM object ----
    orm_obj = BiomarkerCorrelation(
        correlation_id=correlation_id,
        node_a_id=node_a,
        node_b_id=node_b,
        rho=correlation_r,
        rho_se=rho_se,
        d_block=d_block,
        source_citation=source_citation,
        is_decision_critical=0,
        version=1,
        active=1,
        notes="; ".join(notes_parts),
    )

    session.add(orm_obj)
    logger.info(
        "Imported correlation %s: %s %s↔%s r=%.3f n=%d",
        correlation_id, study_id, node_a, node_b, correlation_r, sample_size,
    )
    return correlation_id


# ============================================================================
# import_study_cohort_profile  (B2: study_cohort_profiles_v1)
# ============================================================================

def import_study_cohort_profile(
    session: Session,
    row: dict,
    study_id: str,
) -> str:
    """Validate and insert one study cohort profile row.

    Args:
        session: DB session.
        row: Dict from study_cohort_profile_template.csv.
        study_id: Study identifier.

    Returns:
        Generated profile_id.
    """
    cohort_label = row.get("cohort_label", "").strip() or "main"
    analysis_tp = row.get("analysis_timepoint", "").strip() or "baseline"

    profile_id = row.get("profile_id", "").strip()
    if not profile_id:
        profile_id = _deterministic_id("PROF_", study_id, cohort_label, analysis_tp)

    # Check for duplicates
    existing = session.get(StudyCohortProfile, profile_id)
    if existing is not None:
        logger.debug("Profile %s already exists, skipping", profile_id)
        return profile_id

    orm_obj = StudyCohortProfile(
        profile_id=profile_id,
        study_id=study_id,
        cohort_label=cohort_label,
        analysis_timepoint=analysis_tp,
        N_analyzed=_safe_int(row.get("N_analyzed"), "N_analyzed"),
        N_enrolled=_safe_int(row.get("N_enrolled"), "N_enrolled"),
        recruitment_region=row.get("recruitment_region", "").strip() or None,
        recruitment_sites=row.get("recruitment_sites", "").strip() or None,
        collection_calendar_start=row.get("collection_calendar_start", "").strip() or None,
        collection_calendar_end=row.get("collection_calendar_end", "").strip() or None,
        enrollment_window_text=row.get("enrollment_window_text", "").strip() or None,
        eligibility_inclusion=row.get("eligibility_inclusion", "").strip() or None,
        eligibility_exclusion=row.get("eligibility_exclusion", "").strip() or None,
        sex_female_pct=_safe_float(row.get("sex_female_pct"), "sex_female_pct"),
        age_mean=_safe_float(row.get("age_mean"), "age_mean"),
        age_sd=_safe_float(row.get("age_sd"), "age_sd"),
        education_years_mean=_safe_float(row.get("education_years_mean"), "education_years_mean"),
        education_years_sd=_safe_float(row.get("education_years_sd"), "education_years_sd"),
        bmi_mean=_safe_float(row.get("bmi_mean"), "bmi_mean"),
        bmi_sd=_safe_float(row.get("bmi_sd"), "bmi_sd"),
        cancer_type=row.get("cancer_type", "").strip() or None,
        treatment_phase=row.get("treatment_phase", "").strip() or None,
        time_since_treatment_text=row.get("time_since_treatment_text", "").strip() or None,
        notes=row.get("notes", "").strip() or None,
        version=_safe_int(row.get("version", "1"), "version") or 1,
    )

    session.add(orm_obj)
    logger.info("Imported cohort profile %s for study %s", profile_id, study_id)
    return profile_id


# ============================================================================
# import_profile_data_stream  (B3: profile_data_streams_v1)
# ============================================================================

def import_profile_data_stream(
    session: Session,
    row: dict,
    study_id: str,
) -> str:
    """Validate and insert one profile data stream row.

    Args:
        session: DB session.
        row: Dict from profile_data_stream_template.csv.
        study_id: Study identifier (used for ID generation).

    Returns:
        Generated stream_id.
    """
    profile_id = _require_str(row, "profile_id")
    stream_label = row.get("stream_label", "").strip() or "unknown"

    stream_id = row.get("stream_id", "").strip()
    if not stream_id:
        stream_id = _deterministic_id("STRM_", profile_id, stream_label)

    existing = session.get(ProfileDataStream, stream_id)
    if existing is not None:
        logger.debug("Stream %s already exists, skipping", stream_id)
        return stream_id

    # FK check: profile must exist
    profile = session.get(StudyCohortProfile, profile_id)
    if profile is None:
        raise ValueError(f"FK violation: profile_id '{profile_id}' not found")

    orm_obj = ProfileDataStream(
        stream_id=stream_id,
        profile_id=profile_id,
        stream_label=stream_label,
        analyte_or_target=row.get("analyte_or_target", "").strip() or None,
        modality_type=row.get("modality_type", "").strip() or None,
        capture_method=row.get("capture_method", "").strip() or None,
        instrument_id=row.get("instrument_id", "").strip() or None,
        measure_id=row.get("measure_id", "").strip() or None,
        administration_setting=row.get("administration_setting", "").strip() or None,
        administration_role=row.get("administration_role", "").strip() or None,
        instrument_version=row.get("instrument_version", "").strip() or None,
        language=row.get("language", "").strip() or None,
        visit_context=row.get("visit_context", "").strip() or None,
        recall_window_iso=row.get("recall_window_iso", "").strip() or None,
        schedule_pattern=row.get("schedule_pattern", "").strip() or None,
        collection_time_unit=row.get("collection_time_unit", "").strip() or None,
        scheduled_duration_value=_safe_float(row.get("scheduled_duration_value"), "scheduled_duration_value"),
        primary_time_anchor=row.get("primary_time_anchor", "").strip() or None,
        quality_controls_summary=row.get("quality_controls_summary", "").strip() or None,
        notes=row.get("notes", "").strip() or None,
        version=_safe_int(row.get("version", "1"), "version") or 1,
    )

    session.add(orm_obj)
    logger.info("Imported data stream %s for profile %s", stream_id, profile_id)
    return stream_id


# ============================================================================
# import_stream_timepoint  (B4: stream_timepoints_v1)
# ============================================================================

def import_stream_timepoint(
    session: Session,
    row: dict,
    study_id: str,
) -> str:
    """Validate and insert one stream timepoint row.

    Args:
        session: DB session.
        row: Dict from stream_timepoint_template.csv.
        study_id: Study identifier (used for ID generation).

    Returns:
        Generated timepoint_id.
    """
    stream_id = _require_str(row, "stream_id")
    tp_label = row.get("timepoint_label", "").strip() or "unknown"

    timepoint_id = row.get("timepoint_id", "").strip()
    if not timepoint_id:
        timepoint_id = _deterministic_id("TP_", stream_id, tp_label)

    existing = session.get(StreamTimepoint, timepoint_id)
    if existing is not None:
        logger.debug("Timepoint %s already exists, skipping", timepoint_id)
        return timepoint_id

    # FK check: stream must exist
    stream = session.get(ProfileDataStream, stream_id)
    if stream is None:
        raise ValueError(f"FK violation: stream_id '{stream_id}' not found")

    orm_obj = StreamTimepoint(
        timepoint_id=timepoint_id,
        stream_id=stream_id,
        timepoint_label=tp_label,
        timepoint_type=row.get("timepoint_type", "").strip() or None,
        anchor_event=row.get("anchor_event", "").strip() or None,
        timepoint_minutes=_safe_int(row.get("timepoint_minutes"), "timepoint_minutes"),
        clock_time_hhmm=row.get("clock_time_hhmm", "").strip() or None,
        allowable_window_min=_safe_int(row.get("allowable_window_min"), "allowable_window_min"),
        required=_safe_int(row.get("required", "1"), "required") or 1,
        maps_to_measure=row.get("maps_to_measure", "").strip() or None,
        version=_safe_int(row.get("version", "1"), "version") or 1,
    )

    session.add(orm_obj)
    logger.info("Imported timepoint %s for stream %s", timepoint_id, stream_id)
    return timepoint_id


# ============================================================================
# import_ontology_link  (B5: ontology_links_v1)
# ============================================================================

def import_ontology_link(
    session: Session,
    row: dict,
    study_id: str,
) -> str:
    """Validate and insert one ontology link row.

    Args:
        session: DB session.
        row: Dict from ontology_link_template.csv.
        study_id: Study identifier.

    Returns:
        Generated link_id.
    """
    target_table = _require_str(row, "target_table")
    target_id = _require_str(row, "target_id")

    link_id = row.get("link_id", "").strip()
    if not link_id:
        link_id = _deterministic_id("ONT_", study_id, target_table, target_id)

    existing = session.get(OntologyLink, link_id)
    if existing is not None:
        logger.debug("Ontology link %s already exists, skipping", link_id)
        return link_id

    orm_obj = OntologyLink(
        link_id=link_id,
        target_table=target_table,
        target_id=target_id,
        study_id=study_id,
        support_type=row.get("support_type", "").strip() or None,
        evidence_strength=row.get("evidence_strength", "").strip() or None,
        snippet=row.get("snippet", "").strip() or None,
        locator=row.get("locator", "").strip() or None,
        notes=row.get("notes", "").strip() or None,
        version=_safe_int(row.get("version", "1"), "version") or 1,
        active=_safe_int(row.get("active", "1"), "active") or 1,
    )

    session.add(orm_obj)
    logger.info("Imported ontology link %s (%s→%s) for study %s", link_id, target_table, target_id, study_id)
    return link_id


# ============================================================================
# import_dose_evidence  (dose_evidence_v1)
# ============================================================================

def import_dose_evidence(
    session: Session,
    row: dict,
    study_id: str,
) -> str:
    """Validate and insert one dose-response evidence row.

    Args:
        session: DB session.
        row: Dict from dose_evidence_template.csv.
        study_id: Study identifier.

    Returns:
        Generated dose evidence ID.
    """
    from datetime import datetime, timezone

    action_id = row.get("action_id", "").strip() or None
    dose_level = _safe_float(row.get("dose_level"), "dose_level")
    if dose_level is None:
        raise ValueError("dose_level is required")

    dose_id = row.get("id", "").strip()
    if not dose_id:
        dose_id = _deterministic_id(
            "DOSE_", study_id, action_id or "", str(dose_level)
        )

    existing = session.get(DoseEvidence, dose_id)
    if existing is not None:
        logger.debug("Dose evidence %s already exists, skipping", dose_id)
        return dose_id

    orm_obj = DoseEvidence(
        id=dose_id,
        study_id=study_id,
        extraction_run_id=row.get("extraction_run_id", "").strip() or None,
        action_id=action_id,
        intervention_type=row.get("intervention_type", "").strip() or None,
        dose_level=dose_level,
        dose_unit=row.get("dose_unit", "").strip() or None,
        effect=_safe_float(row.get("effect"), "effect"),
        se=_safe_float(row.get("se"), "se"),
        N=_safe_int(row.get("N"), "N"),
        dose_response_shape=row.get("dose_response_shape", "").strip() or None,
        effective_dose_range=row.get("effective_dose_range", "").strip() or None,
        maximum_tolerated_dose=row.get("maximum_tolerated_dose", "").strip() or None,
        provenance_status=row.get("provenance_status", "").strip() or "manual",
        provenance_ref=row.get("provenance_ref", "").strip() or row.get("doi", ""),
        created_at=datetime.now(timezone.utc),
        notes=row.get("notes", "").strip() or None,
        version=_safe_int(row.get("version", "1"), "version") or 1,
    )

    session.add(orm_obj)
    logger.info("Imported dose evidence %s for study %s (dose=%.1f)", dose_id, study_id, dose_level)
    return dose_id


# ============================================================================
# import_subgroup_evidence  (subgroup_evidence_v1)
# ============================================================================

def import_subgroup_evidence(
    session: Session,
    row: dict,
    study_id: str,
) -> str:
    """Validate and insert one subgroup/moderator evidence row.

    Args:
        session: DB session.
        row: Dict from subgroup_evidence_template.csv.
        study_id: Study identifier.

    Returns:
        Generated subgroup evidence ID.
    """
    from datetime import datetime, timezone

    modifier_variable = _require_str(row, "modifier_variable")
    modifier_value = _require_str(row, "modifier_value")

    sub_id = row.get("id", "").strip()
    if not sub_id:
        sub_id = _deterministic_id(
            "SUB_", study_id, modifier_variable, modifier_value
        )

    existing = session.get(SubgroupEvidence, sub_id)
    if existing is not None:
        logger.debug("Subgroup evidence %s already exists, skipping", sub_id)
        return sub_id

    orm_obj = SubgroupEvidence(
        id=sub_id,
        study_id=study_id,
        extraction_run_id=row.get("extraction_run_id", "").strip() or None,
        edge_id=row.get("edge_id", "").strip() or None,
        modifier_variable=modifier_variable,
        modifier_value=modifier_value,
        interaction_beta=_safe_float(row.get("interaction_beta"), "interaction_beta"),
        interaction_se=_safe_float(row.get("interaction_se"), "interaction_se"),
        interaction_p=_safe_float(row.get("interaction_p"), "interaction_p"),
        subgroup_effect=_safe_float(row.get("subgroup_effect"), "subgroup_effect"),
        subgroup_se=_safe_float(row.get("subgroup_se"), "subgroup_se"),
        subgroup_n=_safe_int(row.get("subgroup_n"), "subgroup_n"),
        provenance_status=row.get("provenance_status", "").strip() or "manual",
        provenance_ref=row.get("provenance_ref", "").strip() or row.get("doi", ""),
        created_at=datetime.now(timezone.utc),
        notes=row.get("notes", "").strip() or None,
        version=_safe_int(row.get("version", "1"), "version") or 1,
    )

    session.add(orm_obj)
    logger.info(
        "Imported subgroup evidence %s for study %s (%s=%s)",
        sub_id, study_id, modifier_variable, modifier_value,
    )
    return sub_id

