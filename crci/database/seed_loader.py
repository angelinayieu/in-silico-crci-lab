# VERIFIED: imports — csv, sqlalchemy, shared modules
# VERIFIED: downstream — called by setup scripts to populate Class A tables
"""
Component: Layer 0 — CSV Seed Loader
Spec: IMPLEMENTATION_BLUEPRINT Part 3 (seeds/ directory)
Purpose: Load CSV seed files into Class A tables, validate FKs.
Reads: CSV files from database/seeds/
Writes: Class A table rows via SQLAlchemy session
"""
from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from shared.db import get_session
from shared.models.tables import (
    ActionCatalog,
    Base,
    BiomarkerCorrelation,
    BiomarkerNodeDefinition,
    ContraindicationEscalationPolicy,
    ContraindicationRule,
    DerivedFeatureDefinition,
    DescriptionTemplate,
    EdgeOntology,
    EdgeRelationsDefinition,
    FeedbackLoop,
    HarmonizationRule,
    InstrumentDefinition,
    InterventionKernel,
    InterventionSynergy,
    LiteraryConstraint,
    LiteraryMechanisticPrior,
    MeasureDefinition,
    MIDThreshold,
    NormalizationRef,
    ObservationNoise,
    Pathway,
    PathwayInteraction,
    QuestionBank,
    QuestionObservationModel,
    RecoveryTrajectory,
    TriangulationMember,
    TriangulationSet,
    ValidationRule,
    VariableDefinition,
)
from shared.validators import run_class_a_validation

logger = logging.getLogger(__name__)

# Map CSV filenames to ORM model classes and their primary key column
SEED_TABLE_MAP: dict[str, tuple[type[Base], str]] = {
    "nodes.csv": (BiomarkerNodeDefinition, "node_id"),
    "edge_relations.csv": (EdgeRelationsDefinition, "edge_relation_id"),
    "edge_ontology.csv": (EdgeOntology, "ontology_id"),
    "instruments.csv": (InstrumentDefinition, "instrument_id"),
    "measures.csv": (MeasureDefinition, "measure_id"),
    "harmonization_rules.csv": (HarmonizationRule, "rule_id"),
    "literary_priors.csv": (LiteraryMechanisticPrior, "prior_id"),
    "literary_constraints.csv": (LiteraryConstraint, "rule_id"),
    "contraindication_escalation.csv": (ContraindicationEscalationPolicy, "escalation_id"),
    "contraindication_rules.csv": (ContraindicationRule, "rule_id"),
    "validation_rules.csv": (ValidationRule, "validation_rule_id"),
    "variables.csv": (VariableDefinition, "variable_id"),
    "modifiers.csv": (None, "modifier_id"),  # loaded separately
    "features.csv": (DerivedFeatureDefinition, "feature_id"),
    "triangulation_sets.csv": (TriangulationSet, "triangulation_id"),
    "triangulation_members.csv": (TriangulationMember, "member_id"),
    "description_templates.csv": (DescriptionTemplate, "template_id"),
    "actions.csv": (ActionCatalog, "action_id"),
    "question_bank.csv": (QuestionBank, "question_id"),
    "question_obs_models.csv": (QuestionObservationModel, "model_id"),
    "normalization_refs.csv": (NormalizationRef, "norm_id"),
    "observation_noise.csv": (ObservationNoise, "noise_id"),
    "pathways.csv": (Pathway, "pathway_id"),
    "pathway_interactions.csv": (PathwayInteraction, "interaction_id"),
    "synergy.csv": (InterventionSynergy, "synergy_id"),
    "recovery_trajectories.csv": (RecoveryTrajectory, "trajectory_id"),
    "biomarker_correlations.csv": (BiomarkerCorrelation, "correlation_id"),
    "feedback_loops.csv": (FeedbackLoop, "loop_id"),
    "intervention_kernels.csv": (InterventionKernel, "kernel_id"),
    "mid_thresholds.csv": (MIDThreshold, "domain_id"),
}

# Dependency order: ROOT tables first, then dependent tables
LOAD_ORDER: list[str] = [
    # ROOT tables (no FK dependencies)
    "nodes.csv",
    "description_templates.csv",
    "actions.csv",
    "contraindication_escalation.csv",
    "recovery_trajectories.csv",
    "harmonization_rules.csv",
    "validation_rules.csv",
    "mid_thresholds.csv",
    # Level 1 (depend on ROOT)
    "edge_relations.csv",
    "instruments.csv",
    "measures.csv",
    "variables.csv",
    "question_obs_models.csv",
    "pathways.csv",
    "normalization_refs.csv",
    "observation_noise.csv",
    "intervention_kernels.csv",
    "biomarker_correlations.csv",
    "feedback_loops.csv",
    # Level 2 (depend on Level 1)
    "edge_ontology.csv",
    "literary_priors.csv",
    "literary_constraints.csv",
    "contraindication_rules.csv",
    "features.csv",
    "triangulation_sets.csv",
    "pathway_interactions.csv",
    "synergy.csv",
    "question_bank.csv",
    # Level 3
    "triangulation_members.csv",
]


def _parse_csv_value(value: str, column_name: str) -> Any:
    """Parse a CSV string value to the appropriate Python type."""
    if value == "" or value.lower() == "null":
        return None

    # Boolean columns
    if column_name in ("active", "is_actionable_input_node", "is_decision_critical",
                       "binary_outcome_bridge_allowed", "condition_dependent"):
        return value.lower() in ("true", "1", "yes")

    # Integer columns
    int_cols = (
        "version", "recall_window_days", "default_window_days",
        "min_observation_window_days", "priority", "max_lag_steps",
        "min_required_samples", "effective_window_days",
        "default_effect_direction", "display_order", "member_order",
        "min_members_required", "year_published", "is_cancer_specific",
    )
    if column_name in int_cols:
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None

    # Float columns
    float_cols = (
        "burden_score", "adherence_estimate", "dose_min", "dose_max",
        "dose_default", "weight", "ref_mean", "ref_sd", "ref_n",
        "percentile_5", "percentile_25", "percentile_50", "percentile_75",
        "percentile_95", "reliability_alpha", "noise_variance",
        "se_multiplier", "proxy_r_squared", "rho", "rho_se",
        "loop_gain", "spectral_radius_contribution", "interaction_strength",
        "jpo", "ccs", "interaction_magnitude", "gamma_prior_alpha",
        "gamma_prior_beta", "gamma_cap", "r_infinity", "r_infinity_se",
        "tau_r_months", "tau_r_se", "gamma_r", "acc_factor",
        "loading_coefficient", "loading_se", "prior_mean", "prior_sd",
        "onset_weeks_min", "onset_weeks_max", "build_weeks",
        "steady_state_weeks_min", "steady_state_weeks_max",
        "decay_half_life_weeks", "se_inflation_factor",
        "cumulative_guard_min", "cumulative_guard_max",
        "burden_cost", "d_mid", "d_ce", "d_plateau",
    )
    if column_name in float_cols:
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    return value


def load_csv_to_table(
    session: Session,
    csv_path: Path,
    model_class: type[Base],
    pk_column: str,
    *,
    upsert: bool = False,
) -> int:
    """Load a single CSV file into a table.

    Args:
        session: Database session.
        csv_path: Path to the CSV file.
        model_class: SQLAlchemy model class.
        pk_column: Name of the primary key column.
        upsert: If True, update existing rows instead of skipping.

    Returns:
        Number of rows loaded/updated.
    """
    if not csv_path.exists():
        logger.warning("Seed file not found: %s (skipping)", csv_path)
        return 0

    loaded = 0
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            logger.warning("Empty CSV file: %s", csv_path)
            return 0

        for row in reader:
            # Parse values
            parsed = {}
            for col, val in row.items():
                col = col.strip()
                parsed[col] = _parse_csv_value(val.strip() if val else "", col)

            pk_value = parsed.get(pk_column)
            if pk_value is None:
                logger.warning(
                    "Skipping row with NULL PK (%s) in %s", pk_column, csv_path.name
                )
                continue

            # Check if row already exists
            existing = session.get(model_class, pk_value)
            if existing is not None:
                if upsert:
                    for col, val in parsed.items():
                        if hasattr(existing, col):
                            setattr(existing, col, val)
                    loaded += 1
                else:
                    logger.debug(
                        "Skipping existing %s=%s in %s",
                        pk_column, pk_value, csv_path.name,
                    )
                continue

            # Create new row — only set columns that exist on the model
            valid_cols = {
                col: val for col, val in parsed.items()
                if hasattr(model_class, col)
            }
            obj = model_class(**valid_cols)
            session.add(obj)
            loaded += 1

    logger.info("Loaded %d rows from %s into %s", loaded, csv_path.name, model_class.__tablename__)
    return loaded


def load_all_seeds(
    seeds_dir: Path | str,
    session: Session | None = None,
    *,
    validate: bool = True,
    upsert: bool = False,
) -> dict[str, int]:
    """Load all seed CSV files in dependency order.

    Args:
        seeds_dir: Path to the database/seeds/ directory.
        session: Database session (creates one if None).
        validate: Run Class A validation after loading.
        upsert: If True, update existing rows.

    Returns:
        Dict of {csv_filename: rows_loaded}.
    """
    seeds_dir = Path(seeds_dir)
    if not seeds_dir.is_dir():
        raise FileNotFoundError(f"Seeds directory not found: {seeds_dir}")

    results: dict[str, int] = {}

    if session is None:
        with get_session() as session:
            return _do_load(session, seeds_dir, results, validate, upsert)
    else:
        return _do_load(session, seeds_dir, results, validate, upsert)


def _do_load(
    session: Session,
    seeds_dir: Path,
    results: dict[str, int],
    validate: bool,
    upsert: bool,
) -> dict[str, int]:
    """Internal: load seeds in order."""
    for csv_name in LOAD_ORDER:
        entry = SEED_TABLE_MAP.get(csv_name)
        if entry is None:
            continue

        model_class, pk_column = entry
        if model_class is None:
            logger.info("Skipping %s (requires custom loader)", csv_name)
            continue

        csv_path = seeds_dir / csv_name
        count = load_csv_to_table(
            session, csv_path, model_class, pk_column, upsert=upsert
        )
        results[csv_name] = count

    session.flush()

    if validate:
        logger.info("Running Class A validation...")
        report = run_class_a_validation(session)
        logger.info(report.summary())
        if report.has_errors:
            for r in report.results:
                if not r.passed and r.severity == "error":
                    logger.error("  %s: %s", r.rule_id, r.message)

    total = sum(results.values())
    logger.info("Seed loading complete: %d total rows across %d files", total, len(results))
    return results
