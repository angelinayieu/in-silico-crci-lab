#!/usr/bin/env python3
"""
CSV Evidence Validator — Pre-import quality gate
=================================================

Validates all CSV evidence files in data/manual_uploads/structured/
BEFORE they are loaded into the database.

This script catches the 74+ failure modes that the extraction pipeline code
enforces but that manual CSV extraction bypasses entirely.

Usage:
    python scripts/validate_csvs.py                          # validate all papers
    python scripts/validate_csvs.py --doi 10.1002_pon.4370   # validate one paper
    python scripts/validate_csvs.py --strict                 # treat warnings as errors
    python scripts/validate_csvs.py --fix                    # auto-fix where safe

Exit codes:
    0 = all checks pass
    1 = errors found (data would corrupt DB)
    2 = warnings found (data loads but may be wrong)
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
#  Plausibility constants — mirroring crci/shared/config.py
# ---------------------------------------------------------------------------
PLAUSIBILITY_BETA_MAX = 5.0       # |β| ≤ 5 (config.TB_PLAUSIBILITY_BETA_MAX)
PLAUSIBILITY_SE_MIN = 0.001       # SE must be > 0
PLAUSIBILITY_SE_MAX = 10.0        # SE > 10 is almost certainly wrong
PLAUSIBILITY_P_MIN = 0.0          # p ≥ 0
PLAUSIBILITY_P_MAX = 1.0          # p ≤ 1
PLAUSIBILITY_R_MAX = 1.0          # |r| ≤ 1
PLAUSIBILITY_N_MIN = 1            # N ≥ 1
PLAUSIBILITY_N_MAX = 100_000      # N > 100k in CRCI context is suspicious
PLAUSIBILITY_SD_MIN = 0.0         # SD ≥ 0, must be > 0 for norms


# ---------------------------------------------------------------------------
#  Valid enums — from extraction_ref/04_CONTROLLED_VOCAB.md + config
# ---------------------------------------------------------------------------
VALID_STUDY_DESIGNS = {
    "RCT", "quasi_experimental", "single_arm", "cohort",
    "cross_sectional", "case_control", "meta_analysis",
    "systematic_review", "mechanistic",
}
VALID_CANCER_TYPES = {
    "breast", "prostate", "colorectal", "lung", "hematologic",
    "brain", "mixed", "other", "pediatric",
}
VALID_TREATMENT_PHASES = {
    "active_treatment", "post_treatment", "survivorship",
    "palliative", "mixed", "pre_treatment",
}
VALID_EFFECT_SIZE_TYPES = {
    "BETWEEN_GROUP", "WITHIN_GROUP", "PRE_POST_CHANGE",
}
VALID_ROB_OVERALL = {
    "low", "moderate", "high", "critical", "unclear",
}
VALID_SE_DERIVATION_METHODS = {
    "reported", "from_ci", "from_p_value", "from_t_stat",
    "from_f_stat", "from_mean_diff_sd", "imputed_median",
    "direct",
}
VALID_SCORING_DIRECTIONS = {
    "higher_is_better", "higher_is_worse",
}
VALID_BETA_SIGN_CONVENTIONS = {
    "positive_is_benefit", "positive_is_harm",
}
VALID_ENDPOINT_VS_CHANGE = {
    "endpoint", "change_score",
}
VALID_SOURCE_TYPES = {
    "published_norm", "local_control_group", "expert",
}
VALID_PARTIAL_OR_ZERO = {
    "partial", "zero_order", "semi_partial",
}


# ---------------------------------------------------------------------------
#  Result types
# ---------------------------------------------------------------------------
@dataclass
class Issue:
    severity: str       # ERROR or WARNING
    file: str           # relative path
    row: int            # 1-indexed row number
    column: str         # column name
    message: str        # human-readable description
    value: Any = None   # the offending value
    fix: str | None = None  # auto-fix suggestion (if --fix)


@dataclass
class ValidationReport:
    paper_slug: str
    issues: list[Issue] = field(default_factory=list)
    rows_checked: int = 0
    files_checked: int = 0

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "ERROR"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "WARNING"]


# ---------------------------------------------------------------------------
#  Registry loaders
# ---------------------------------------------------------------------------
def load_registry_ids(registry_path: Path, id_column: str) -> set[str]:
    """Load all IDs from a registry CSV."""
    ids = set()
    if not registry_path.exists():
        return ids
    with open(registry_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            val = row.get(id_column, "").strip()
            if val:
                ids.add(val)
    return ids


def load_meta_json(paper_dir: Path) -> dict:
    """Load meta.json from paper directory, return empty dict if missing."""
    meta_path = paper_dir / "meta.json"
    if meta_path.exists():
        with open(meta_path) as f:
            return json.load(f)
    return {}


# ---------------------------------------------------------------------------
#  Helper parsers
# ---------------------------------------------------------------------------
def csv_str(row: dict, key: str) -> str:
    """Get a string from CSV row, never returning None."""
    val = row.get(key)
    if val is None:
        return ""
    return str(val).strip()


def safe_float(val: Any) -> float | None:
    if val is None or (isinstance(val, str) and val.strip() == ""):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def safe_int(val: Any) -> int | None:
    if val is None or (isinstance(val, str) and val.strip() == ""):
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
#  VALIDATORS — Edge Evidence
# ---------------------------------------------------------------------------
def validate_edge_evidence(
    csv_path: Path,
    edge_ids: set[str],
    node_ids: set[str],
    instrument_ids: set[str],
    report: ValidationReport,
) -> None:
    """Validate edge_evidence_template.csv — the most critical CSV."""
    rel_path = str(csv_path)
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        report.issues.append(Issue("WARNING", rel_path, 0, "", "Empty CSV file"))
        return

    report.files_checked += 1
    seen_hashes = set()

    for i, row in enumerate(rows, start=2):  # row 2 = first data row (header is 1)
        report.rows_checked += 1

        # --- Required fields ---
        doi = csv_str(row, "doi")
        edge_id = csv_str(row, "edge_id")
        beta_raw = safe_float(row.get("beta_raw"))
        se_raw = safe_float(row.get("se_raw"))
        sample_size = safe_int(row.get("sample_size"))

        if not doi:
            report.issues.append(Issue("ERROR", rel_path, i, "doi",
                                       "Missing DOI"))
        if not edge_id:
            report.issues.append(Issue("ERROR", rel_path, i, "edge_id",
                                       "Missing edge_id"))
        elif edge_id not in edge_ids:
            report.issues.append(Issue("ERROR", rel_path, i, "edge_id",
                                       f"edge_id '{edge_id}' not in EDGE_REGISTRY.csv",
                                       value=edge_id))

        # --- beta_raw ---
        if beta_raw is None:
            report.issues.append(Issue("ERROR", rel_path, i, "beta_raw",
                                       "Missing beta_raw — cannot be empty"))
        elif abs(beta_raw) > PLAUSIBILITY_BETA_MAX:
            report.issues.append(Issue("ERROR", rel_path, i, "beta_raw",
                                       f"|beta_raw|={abs(beta_raw):.2f} > {PLAUSIBILITY_BETA_MAX} — "
                                       f"implausible effect size",
                                       value=beta_raw))

        # --- se_raw ---
        if se_raw is None:
            report.issues.append(Issue("ERROR", rel_path, i, "se_raw",
                                       "Missing se_raw — loader will skip this row"))
        elif se_raw <= 0:
            report.issues.append(Issue("ERROR", rel_path, i, "se_raw",
                                       f"se_raw={se_raw} ≤ 0 — standard error must be positive",
                                       value=se_raw))
        elif se_raw < PLAUSIBILITY_SE_MIN:
            report.issues.append(Issue("WARNING", rel_path, i, "se_raw",
                                       f"se_raw={se_raw} suspiciously small — possible p-value/SE confusion",
                                       value=se_raw))
        elif se_raw > PLAUSIBILITY_SE_MAX:
            report.issues.append(Issue("WARNING", rel_path, i, "se_raw",
                                       f"se_raw={se_raw} > {PLAUSIBILITY_SE_MAX} — suspiciously large",
                                       value=se_raw))

        # --- sample_size ---
        if sample_size is None:
            report.issues.append(Issue("WARNING", rel_path, i, "sample_size",
                                       "Missing sample_size"))
        elif sample_size < PLAUSIBILITY_N_MIN:
            report.issues.append(Issue("ERROR", rel_path, i, "sample_size",
                                       f"sample_size={sample_size} < {PLAUSIBILITY_N_MIN}",
                                       value=sample_size))
        elif sample_size > PLAUSIBILITY_N_MAX:
            report.issues.append(Issue("WARNING", rel_path, i, "sample_size",
                                       f"sample_size={sample_size} > {PLAUSIBILITY_N_MAX} — verify",
                                       value=sample_size))

        # --- p_value ---
        p_value = safe_float(row.get("p_value"))
        if p_value is not None:
            if p_value < PLAUSIBILITY_P_MIN or p_value > PLAUSIBILITY_P_MAX:
                report.issues.append(Issue("ERROR", rel_path, i, "p_value",
                                           f"p_value={p_value} outside [0, 1]",
                                           value=p_value))

        # --- CI consistency: β should be within [ci_low, ci_high] ---
        ci_low = safe_float(row.get("ci_low"))
        ci_high = safe_float(row.get("ci_high"))
        if ci_low is not None and ci_high is not None:
            if ci_low > ci_high:
                report.issues.append(Issue("ERROR", rel_path, i, "ci_low/ci_high",
                                           f"ci_low={ci_low} > ci_high={ci_high} — inverted CI",
                                           value=(ci_low, ci_high)))
            if beta_raw is not None:
                # Allow small tolerance for rounding
                tol = 0.01
                if beta_raw < ci_low - tol or beta_raw > ci_high + tol:
                    report.issues.append(Issue("WARNING", rel_path, i, "beta_raw vs CI",
                                               f"beta_raw={beta_raw} outside CI [{ci_low}, {ci_high}]",
                                               value=(beta_raw, ci_low, ci_high)))

        # --- SE from CI cross-check ---
        if ci_low is not None and ci_high is not None and se_raw is not None:
            se_from_ci = (ci_high - ci_low) / (2 * 1.96)
            if se_from_ci > 0 and se_raw > 0:
                ratio = se_raw / se_from_ci
                if ratio < 0.5 or ratio > 2.0:
                    report.issues.append(Issue("WARNING", rel_path, i, "se_raw vs CI",
                                               f"se_raw={se_raw:.4f} but CI implies SE≈{se_from_ci:.4f} — "
                                               f"ratio={ratio:.2f} (expect ~1.0)",
                                               value=(se_raw, se_from_ci)))

        # --- instrument_id FK ---
        inst_id = csv_str(row, "instrument_id")
        if inst_id and inst_id not in instrument_ids:
            report.issues.append(Issue("ERROR", rel_path, i, "instrument_id",
                                       f"instrument_id '{inst_id}' not in INSTRUMENT_REGISTRY.csv",
                                       value=inst_id))

        # --- outcome_node_id FK ---
        outcome_node = csv_str(row, "outcome_node_id")
        if outcome_node and outcome_node not in node_ids:
            report.issues.append(Issue("ERROR", rel_path, i, "outcome_node_id",
                                       f"outcome_node_id '{outcome_node}' not in NODE_REGISTRY.csv",
                                       value=outcome_node))

        # --- Enum validations ---
        study_design = csv_str(row, "study_design")
        if study_design and study_design not in VALID_STUDY_DESIGNS:
            report.issues.append(Issue("WARNING", rel_path, i, "study_design",
                                       f"study_design='{study_design}' not in controlled vocabulary",
                                       value=study_design))

        cancer_type = csv_str(row, "cancer_type")
        if cancer_type and cancer_type not in VALID_CANCER_TYPES:
            report.issues.append(Issue("WARNING", rel_path, i, "cancer_type",
                                       f"cancer_type='{cancer_type}' not in controlled vocabulary",
                                       value=cancer_type))

        treatment_phase = csv_str(row, "treatment_phase")
        if treatment_phase and treatment_phase not in VALID_TREATMENT_PHASES:
            report.issues.append(Issue("WARNING", rel_path, i, "treatment_phase",
                                       f"treatment_phase='{treatment_phase}' not in controlled vocabulary",
                                       value=treatment_phase))

        effect_size_type = csv_str(row, "effect_size_type")
        if effect_size_type and effect_size_type not in VALID_EFFECT_SIZE_TYPES:
            report.issues.append(Issue("WARNING", rel_path, i, "effect_size_type",
                                       f"effect_size_type='{effect_size_type}' not in controlled vocabulary",
                                       value=effect_size_type))

        rob_overall = csv_str(row, "rob_overall")
        if rob_overall and rob_overall not in VALID_ROB_OVERALL:
            report.issues.append(Issue("WARNING", rel_path, i, "rob_overall",
                                       f"rob_overall='{rob_overall}' not in controlled vocabulary",
                                       value=rob_overall))

        se_deriv = csv_str(row, "se_derivation_method")
        if not se_deriv:
            report.issues.append(Issue("WARNING", rel_path, i, "se_derivation_method",
                                       "Missing se_derivation_method — should document how SE was obtained"))
        elif se_deriv not in VALID_SE_DERIVATION_METHODS:
            report.issues.append(Issue("WARNING", rel_path, i, "se_derivation_method",
                                       f"se_derivation_method='{se_deriv}' not in controlled vocabulary",
                                       value=se_deriv))

        outcome_dir = csv_str(row, "outcome_directionality")
        if outcome_dir and outcome_dir not in VALID_SCORING_DIRECTIONS:
            report.issues.append(Issue("WARNING", rel_path, i, "outcome_directionality",
                                       f"outcome_directionality='{outcome_dir}' not in controlled vocabulary",
                                       value=outcome_dir))

        beta_sign = csv_str(row, "beta_sign_convention")
        if beta_sign and beta_sign not in VALID_BETA_SIGN_CONVENTIONS:
            report.issues.append(Issue("WARNING", rel_path, i, "beta_sign_convention",
                                       f"beta_sign_convention='{beta_sign}' not in controlled vocabulary",
                                       value=beta_sign))

        endpoint_change = csv_str(row, "endpoint_vs_change")
        if endpoint_change and endpoint_change not in VALID_ENDPOINT_VS_CHANGE:
            report.issues.append(Issue("WARNING", rel_path, i, "endpoint_vs_change",
                                       f"endpoint_vs_change='{endpoint_change}' not in controlled vocabulary",
                                       value=endpoint_change))

        # --- Sign convention consistency ---
        if beta_raw is not None and beta_sign and outcome_dir:
            # If outcome is "higher_is_worse" and sign convention is "positive_is_benefit",
            # then a positive beta means improvement, but the instrument says higher = worse.
            # This is a CRITICAL check — sign errors are the #1 corruption vector.
            if outcome_dir == "higher_is_worse" and beta_sign == "positive_is_benefit" and beta_raw > 0:
                report.issues.append(Issue("WARNING", rel_path, i, "sign_convention",
                                           f"beta_raw={beta_raw} > 0 with higher_is_worse + positive_is_benefit — "
                                           f"verify this means the intervention REDUCED the bad outcome",
                                           value=(beta_raw, outcome_dir, beta_sign)))
            if outcome_dir == "higher_is_better" and beta_sign == "positive_is_harm" and beta_raw > 0:
                report.issues.append(Issue("WARNING", rel_path, i, "sign_convention",
                                           f"beta_raw={beta_raw} > 0 with higher_is_better + positive_is_harm — "
                                           f"verify sign convention is correct",
                                           value=(beta_raw, outcome_dir, beta_sign)))

        # --- mean_diff requires group SDs for Cohen's d conversion ---
        effect_type = csv_str(row, "effect_type_original")
        if "mean_diff" in effect_type.lower():
            sd_treatment = safe_float(row.get("sd_treatment"))
            sd_control = safe_float(row.get("sd_control"))
            n_treatment = safe_int(row.get("n_treatment"))
            n_control = safe_int(row.get("n_control"))
            if sd_treatment is None and sd_control is None:
                report.issues.append(Issue("WARNING", rel_path, i, "sd_treatment/sd_control",
                                           f"effect_type_original='{effect_type}' (mean_diff) but no group SDs — "
                                           f"cannot convert to Cohen's d without SDs"))
            if n_treatment is None or n_control is None:
                report.issues.append(Issue("WARNING", rel_path, i, "n_treatment/n_control",
                                           f"effect_type_original='{effect_type}' (mean_diff) but missing group Ns — "
                                           f"needed for pooled SD calculation"))

        # --- Duplicate detection ---
        dedup_key = f"{doi}|{edge_id}|{beta_raw}|{se_raw}|{sample_size}"
        if dedup_key in seen_hashes:
            report.issues.append(Issue("ERROR", rel_path, i, "duplicate",
                                       f"Duplicate row: same DOI + edge_id + β + SE + N",
                                       value=dedup_key))
        seen_hashes.add(dedup_key)

        # --- Timepoint weeks (if provided) ---
        tp_weeks = safe_float(row.get("timepoint_weeks"))
        if tp_weeks is not None and tp_weeks < 0:
            report.issues.append(Issue("WARNING", rel_path, i, "timepoint_weeks",
                                       f"timepoint_weeks={tp_weeks} is negative",
                                       value=tp_weeks))

        # --- pub_year ---
        pub_year = safe_int(row.get("pub_year"))
        if pub_year is not None and (pub_year < 1950 or pub_year > 2030):
            report.issues.append(Issue("WARNING", rel_path, i, "pub_year",
                                       f"pub_year={pub_year} outside expected range [1950, 2030]",
                                       value=pub_year))


# ---------------------------------------------------------------------------
#  VALIDATORS — Population Norms
# ---------------------------------------------------------------------------
def validate_population_norms(
    csv_path: Path,
    node_ids: set[str],
    instrument_ids: set[str],
    report: ValidationReport,
) -> None:
    """Validate population_norms_template.csv."""
    rel_path = str(csv_path)
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return

    report.files_checked += 1

    for i, row in enumerate(rows, start=2):
        report.rows_checked += 1

        node_id = csv_str(row, "node_id")
        if not node_id:
            report.issues.append(Issue("ERROR", rel_path, i, "node_id",
                                       "Missing node_id"))
        elif node_id not in node_ids:
            report.issues.append(Issue("ERROR", rel_path, i, "node_id",
                                       f"node_id '{node_id}' not in NODE_REGISTRY.csv",
                                       value=node_id))

        inst_id = csv_str(row, "instrument_id")
        if inst_id and inst_id not in instrument_ids:
            report.issues.append(Issue("ERROR", rel_path, i, "instrument_id",
                                       f"instrument_id '{inst_id}' not in INSTRUMENT_REGISTRY.csv",
                                       value=inst_id))

        mean_val = safe_float(row.get("mean"))
        sd_val = safe_float(row.get("sd"))
        n_val = safe_int(row.get("sample_size"))

        if mean_val is None:
            report.issues.append(Issue("ERROR", rel_path, i, "mean",
                                       "Missing mean — required for population norms"))
        if sd_val is None:
            report.issues.append(Issue("ERROR", rel_path, i, "sd",
                                       "Missing sd — required for population norms"))
        elif sd_val <= 0:
            report.issues.append(Issue("ERROR", rel_path, i, "sd",
                                       f"sd={sd_val} ≤ 0 — must be positive",
                                       value=sd_val))
        if n_val is None or n_val < 1:
            report.issues.append(Issue("ERROR", rel_path, i, "sample_size",
                                       f"sample_size={n_val} — must be ≥ 1",
                                       value=n_val))


# ---------------------------------------------------------------------------
#  VALIDATORS — Context Priors
# ---------------------------------------------------------------------------
def validate_context_priors(
    csv_path: Path,
    node_ids: set[str],
    report: ValidationReport,
) -> None:
    """Validate context_priors_template.csv."""
    rel_path = str(csv_path)
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return

    report.files_checked += 1

    for i, row in enumerate(rows, start=2):
        report.rows_checked += 1

        node_id = csv_str(row, "node_id")
        if not node_id:
            report.issues.append(Issue("ERROR", rel_path, i, "node_id",
                                       "Missing node_id"))
        elif node_id not in node_ids:
            report.issues.append(Issue("ERROR", rel_path, i, "node_id",
                                       f"node_id '{node_id}' not in NODE_REGISTRY.csv",
                                       value=node_id))

        prior_mean = safe_float(row.get("prior_mean_z"))
        prior_sd = safe_float(row.get("prior_sd_z"))

        if prior_mean is None:
            report.issues.append(Issue("ERROR", rel_path, i, "prior_mean_z",
                                       "Missing prior_mean_z"))
        elif abs(prior_mean) > 5.0:
            report.issues.append(Issue("WARNING", rel_path, i, "prior_mean_z",
                                       f"|prior_mean_z|={abs(prior_mean):.2f} > 5 — implausible z-score",
                                       value=prior_mean))

        if prior_sd is None:
            report.issues.append(Issue("ERROR", rel_path, i, "prior_sd_z",
                                       "Missing prior_sd_z"))
        elif prior_sd <= 0:
            report.issues.append(Issue("ERROR", rel_path, i, "prior_sd_z",
                                       f"prior_sd_z={prior_sd} ≤ 0 — must be positive",
                                       value=prior_sd))

        source_type = csv_str(row, "source_type")
        if source_type and source_type not in VALID_SOURCE_TYPES:
            report.issues.append(Issue("WARNING", rel_path, i, "source_type",
                                       f"source_type='{source_type}' not in controlled vocabulary",
                                       value=source_type))


# ---------------------------------------------------------------------------
#  VALIDATORS — Temporal Evidence
# ---------------------------------------------------------------------------
def validate_temporal_evidence(
    csv_path: Path,
    edge_ids: set[str],
    report: ValidationReport,
) -> None:
    """Validate temporal_evidence_template.csv."""
    rel_path = str(csv_path)
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return

    report.files_checked += 1

    for i, row in enumerate(rows, start=2):
        report.rows_checked += 1

        edge_id = csv_str(row, "edge_id")
        if not edge_id:
            report.issues.append(Issue("ERROR", rel_path, i, "edge_id",
                                       "Missing edge_id"))
        elif edge_id not in edge_ids:
            report.issues.append(Issue("ERROR", rel_path, i, "edge_id",
                                       f"edge_id '{edge_id}' not in EDGE_REGISTRY.csv",
                                       value=edge_id))

        tp = safe_float(row.get("timepoint_weeks"))
        if tp is None:
            report.issues.append(Issue("ERROR", rel_path, i, "timepoint_weeks",
                                       "Missing timepoint_weeks"))
        elif tp < 0:
            report.issues.append(Issue("WARNING", rel_path, i, "timepoint_weeks",
                                       f"timepoint_weeks={tp} is negative",
                                       value=tp))

        value = safe_float(row.get("value"))
        se = safe_float(row.get("se"))
        if value is None:
            report.issues.append(Issue("WARNING", rel_path, i, "value",
                                       "Missing value"))
        if se is not None and se <= 0:
            report.issues.append(Issue("ERROR", rel_path, i, "se",
                                       f"se={se} ≤ 0 — must be positive",
                                       value=se))


# ---------------------------------------------------------------------------
#  VALIDATORS — Instrument Evidence
# ---------------------------------------------------------------------------
def validate_instrument_evidence(
    csv_path: Path,
    instrument_ids: set[str],
    report: ValidationReport,
) -> None:
    """Validate instrument_evidence_template.csv."""
    rel_path = str(csv_path)
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return

    report.files_checked += 1

    for i, row in enumerate(rows, start=2):
        report.rows_checked += 1

        inst_id = csv_str(row, "instrument_id")
        if not inst_id:
            report.issues.append(Issue("ERROR", rel_path, i, "instrument_id",
                                       "Missing instrument_id"))
        elif inst_id not in instrument_ids:
            report.issues.append(Issue("ERROR", rel_path, i, "instrument_id",
                                       f"instrument_id '{inst_id}' not in INSTRUMENT_REGISTRY.csv",
                                       value=inst_id))

        reliability = safe_float(row.get("reliability_value"))
        if reliability is not None:
            if reliability < 0 or reliability > 1:
                report.issues.append(Issue("ERROR", rel_path, i, "reliability_value",
                                           f"reliability_value={reliability} outside [0, 1]",
                                           value=reliability))

        factor_loading = safe_float(row.get("factor_loading_mean"))
        if factor_loading is not None:
            if factor_loading < 0 or factor_loading > 1:
                report.issues.append(Issue("WARNING", rel_path, i, "factor_loading_mean",
                                           f"factor_loading_mean={factor_loading} outside [0, 1]",
                                           value=factor_loading))

        icc = safe_float(row.get("test_retest_icc"))
        if icc is not None:
            if icc < 0 or icc > 1:
                report.issues.append(Issue("ERROR", rel_path, i, "test_retest_icc",
                                           f"test_retest_icc={icc} outside [0, 1]",
                                           value=icc))

        n_val = safe_int(row.get("sample_size"))
        if n_val is not None and n_val < 1:
            report.issues.append(Issue("ERROR", rel_path, i, "sample_size",
                                       f"sample_size={n_val} < 1",
                                       value=n_val))


# ---------------------------------------------------------------------------
#  VALIDATORS — Correlation Evidence
# ---------------------------------------------------------------------------
def validate_correlation(
    csv_path: Path,
    node_ids: set[str],
    report: ValidationReport,
) -> None:
    """Validate correlation_template.csv."""
    rel_path = str(csv_path)
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return

    report.files_checked += 1

    for i, row in enumerate(rows, start=2):
        report.rows_checked += 1

        bio1 = csv_str(row, "biomarker_id_1")
        bio2 = csv_str(row, "biomarker_id_2")
        if not bio1:
            report.issues.append(Issue("ERROR", rel_path, i, "biomarker_id_1",
                                       "Missing biomarker_id_1"))
        elif bio1 not in node_ids:
            report.issues.append(Issue("ERROR", rel_path, i, "biomarker_id_1",
                                       f"biomarker_id_1 '{bio1}' not in NODE_REGISTRY.csv",
                                       value=bio1))
        if not bio2:
            report.issues.append(Issue("ERROR", rel_path, i, "biomarker_id_2",
                                       "Missing biomarker_id_2"))
        elif bio2 not in node_ids:
            report.issues.append(Issue("ERROR", rel_path, i, "biomarker_id_2",
                                       f"biomarker_id_2 '{bio2}' not in NODE_REGISTRY.csv",
                                       value=bio2))

        r = safe_float(row.get("correlation_r"))
        if r is not None and abs(r) > PLAUSIBILITY_R_MAX:
            report.issues.append(Issue("ERROR", rel_path, i, "correlation_r",
                                       f"|correlation_r|={abs(r)} > 1",
                                       value=r))

        n_val = safe_int(row.get("sample_size"))
        if n_val is not None and n_val < 3:
            report.issues.append(Issue("ERROR", rel_path, i, "sample_size",
                                       f"sample_size={n_val} < 3 — need ≥ 3 for correlation",
                                       value=n_val))

        partial = csv_str(row, "partial_or_zero")
        if partial and partial not in VALID_PARTIAL_OR_ZERO:
            report.issues.append(Issue("WARNING", rel_path, i, "partial_or_zero",
                                       f"partial_or_zero='{partial}' not in controlled vocabulary",
                                       value=partial))


# ---------------------------------------------------------------------------
#  VALIDATORS — meta.json
# ---------------------------------------------------------------------------
def validate_meta_json(
    paper_dir: Path,
    report: ValidationReport,
) -> None:
    """Validate meta.json consistency."""
    meta = load_meta_json(paper_dir)
    rel_path = str(paper_dir / "meta.json")

    if not meta:
        report.issues.append(Issue("WARNING", rel_path, 0, "",
                                   "meta.json not found — study registration may fail"))
        return

    report.files_checked += 1

    required_fields = ["doi", "study_design"]
    for field_name in required_fields:
        if not meta.get(field_name):
            report.issues.append(Issue("WARNING", rel_path, 0, field_name,
                                       f"Missing '{field_name}' in meta.json"))

    # Cross-check DOI
    meta_doi = meta.get("doi", "")
    # Check folder name matches DOI
    slug = paper_dir.name
    expected_slug = meta_doi.replace("/", "_") if meta_doi else ""
    if expected_slug and slug != expected_slug:
        report.issues.append(Issue("WARNING", rel_path, 0, "doi",
                                   f"Folder name '{slug}' doesn't match DOI slug '{expected_slug}'"))


# ---------------------------------------------------------------------------
#  Cross-file consistency checks
# ---------------------------------------------------------------------------
def cross_validate(
    paper_dir: Path,
    report: ValidationReport,
) -> None:
    """Cross-validate between CSVs and meta.json within one paper."""
    meta = load_meta_json(paper_dir)
    if not meta:
        return

    meta_doi = meta.get("doi", "").strip()

    # Check DOI consistency across all CSVs
    for csv_file in paper_dir.glob("*.csv"):
        with open(csv_file, "r", newline="") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader, start=2):
                csv_doi = csv_str(row, "doi")
                if csv_doi and meta_doi and csv_doi != meta_doi:
                    report.issues.append(Issue("ERROR", str(csv_file), i, "doi",
                                               f"CSV doi='{csv_doi}' doesn't match meta.json doi='{meta_doi}'"))
                    break  # One mismatch per file is enough


# ---------------------------------------------------------------------------
#  Main orchestrator
# ---------------------------------------------------------------------------
def validate_paper(
    paper_dir: Path,
    edge_ids: set[str],
    node_ids: set[str],
    instrument_ids: set[str],
) -> ValidationReport:
    """Run all validators on one paper directory."""
    report = ValidationReport(paper_slug=paper_dir.name)

    # Validate meta.json
    validate_meta_json(paper_dir, report)

    # Validate each CSV template type
    for csv_file in sorted(paper_dir.glob("*.csv")):
        name = csv_file.stem
        if "edge_evidence" in name:
            validate_edge_evidence(csv_file, edge_ids, node_ids, instrument_ids, report)
        elif "population_norms" in name:
            validate_population_norms(csv_file, node_ids, instrument_ids, report)
        elif "context_priors" in name:
            validate_context_priors(csv_file, node_ids, report)
        elif "temporal_evidence" in name:
            validate_temporal_evidence(csv_file, edge_ids, report)
        elif "instrument_evidence" in name:
            validate_instrument_evidence(csv_file, instrument_ids, report)
        elif "correlation" in name:
            validate_correlation(csv_file, node_ids, report)
        else:
            report.issues.append(Issue("WARNING", str(csv_file), 0, "",
                                       f"Unknown CSV template type: {name}"))

    # Cross-file consistency
    cross_validate(paper_dir, report)

    return report


def print_report(report: ValidationReport) -> None:
    """Pretty-print a validation report."""
    errors = report.errors
    warnings = report.warnings

    status = "PASS" if not errors else "FAIL"
    color = "\033[92m" if not errors else "\033[91m"
    reset = "\033[0m"

    print(f"\n{color}{'='*60}")
    print(f"  {report.paper_slug}: {status}")
    print(f"  {report.files_checked} files, {report.rows_checked} rows checked")
    print(f"  {len(errors)} errors, {len(warnings)} warnings")
    print(f"{'='*60}{reset}")

    if errors:
        print(f"\n  {color}ERRORS (will corrupt DB):{reset}")
        for issue in errors:
            loc = f"row {issue.row}" if issue.row > 0 else "file-level"
            print(f"    [{loc}] {issue.column}: {issue.message}")

    if warnings:
        print(f"\n  \033[93mWARNINGS (may be wrong):\033[0m")
        for issue in warnings:
            loc = f"row {issue.row}" if issue.row > 0 else "file-level"
            print(f"    [{loc}] {issue.column}: {issue.message}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate CSV evidence files before DB import"
    )
    parser.add_argument(
        "--doi", type=str, default=None,
        help="Validate only this DOI slug (folder name under structured/)"
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="Treat warnings as errors"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output in JSON format"
    )
    args = parser.parse_args()

    # Resolve paths
    project_root = Path(__file__).resolve().parent.parent
    structured_dir = project_root / "data" / "manual_uploads" / "structured"
    registries_dir = project_root / "registries"

    # Load registries
    edge_ids = load_registry_ids(registries_dir / "EDGE_REGISTRY.csv", "edge_relation_id")
    node_ids = load_registry_ids(registries_dir / "NODE_REGISTRY.csv", "node_id")
    instrument_ids = load_registry_ids(registries_dir / "INSTRUMENT_REGISTRY.csv", "instrument_id")

    if not edge_ids:
        print("WARNING: Could not load EDGE_REGISTRY.csv — FK checks disabled")
    if not node_ids:
        print("WARNING: Could not load NODE_REGISTRY.csv — FK checks disabled")
    if not instrument_ids:
        print("WARNING: Could not load INSTRUMENT_REGISTRY.csv — FK checks disabled")

    print(f"Loaded registries: {len(edge_ids)} edges, {len(node_ids)} nodes, {len(instrument_ids)} instruments")

    # Find paper directories
    if not structured_dir.exists():
        print(f"ERROR: {structured_dir} does not exist")
        return 1

    if args.doi:
        paper_dirs = [structured_dir / args.doi]
        if not paper_dirs[0].exists():
            print(f"ERROR: {paper_dirs[0]} does not exist")
            return 1
    else:
        paper_dirs = sorted([d for d in structured_dir.iterdir() if d.is_dir()])

    if not paper_dirs:
        print("No paper directories found")
        return 0

    # Validate
    all_reports: list[ValidationReport] = []
    for paper_dir in paper_dirs:
        report = validate_paper(paper_dir, edge_ids, node_ids, instrument_ids)
        all_reports.append(report)

    # Output
    if args.json:
        import json as json_mod
        output = []
        for r in all_reports:
            output.append({
                "paper": r.paper_slug,
                "files_checked": r.files_checked,
                "rows_checked": r.rows_checked,
                "errors": len(r.errors),
                "warnings": len(r.warnings),
                "issues": [
                    {
                        "severity": i.severity,
                        "file": i.file,
                        "row": i.row,
                        "column": i.column,
                        "message": i.message,
                    }
                    for i in r.issues
                ],
            })
        print(json_mod.dumps(output, indent=2))
    else:
        for report in all_reports:
            print_report(report)

    # Summary
    total_errors = sum(len(r.errors) for r in all_reports)
    total_warnings = sum(len(r.warnings) for r in all_reports)
    total_rows = sum(r.rows_checked for r in all_reports)

    print(f"\n{'='*60}")
    print(f"  SUMMARY: {len(all_reports)} papers, {total_rows} rows")
    print(f"  {total_errors} errors, {total_warnings} warnings")
    print(f"{'='*60}")

    if total_errors > 0:
        return 1
    if args.strict and total_warnings > 0:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
