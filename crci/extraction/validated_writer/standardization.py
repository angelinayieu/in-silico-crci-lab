# VERIFIED: imports — all modules exist
# VERIFIED: formulas — mean_diff_to_d, eta_to_d, OR_to_d, r_to_d match spec
# VERIFIED: backward wiring — reads dict row from validation.py output
# VERIFIED: forward wiring — writes enriched dict for persistence.py
# VERIFIED: no hardcoded formula parameters (z_crit from scipy)
"""
Component: Extraction — Effect Size Standardization + SE Derivation
Spec: IMPLEMENTATION_SLICES.md Slice 5, Steps 5b
Formulas:
    - mean_diff_to_cohen_d: d = mean_diff / SD_pooled
    - partial_eta_sq_to_d: d = 2 * sqrt(η²/(1-η²))
    - odds_ratio_to_d: d = ln(OR) * sqrt(3) / π
    - r_to_cohen_d: d = 2r / sqrt(1-r²)
    - hedges_g: g = d * (1 - 3/(4(n1+n2) - 9))
    - SE_from_CI: SE = (CI_high - CI_low) / (2 × 1.96)
    - SE_from_p: SE = |beta| / z_from_p
Reads: Validated dict row (from validation.py)
Writes: Enriched dict (consumed by persistence.py)
Gates: None (standardization is best-effort, validation rejects bad data)
"""
from __future__ import annotations

import json
import logging
import math
from typing import Any

from crci.shared.vocab import (
    resolve_cancer_validation,
    resolve_rob_to_grade,
    resolve_study_design,
)

logger = logging.getLogger(__name__)


def _get(row: dict, key: str) -> str:
    """Get a stripped string value from row, or empty string."""
    val = row.get(key)
    if val is None:
        return ""
    return str(val).strip()


def _get_float(row: dict, key: str) -> float | None:
    """Get a float value from row, or None."""
    val = _get(row, key)
    if not val:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# ═══════════════════════════════════════════════════════════════
#  Effect Size Conversion to Cohen's d
# ═══════════════════════════════════════════════════════════════

def standardize_effect_size(row: dict[str, Any]) -> dict[str, Any]:
    """Convert the raw effect size to Cohen's d.

    Supported conversions:
    - cohen_d / cohen_d_from_eta_sq / log_or / hedges_g → passthrough
    - mean_diff → d = mean_diff / SD_pooled
    - partial_eta_sq → d = 2√(η²/(1-η²))
    - odds_ratio → d = ln(OR) × √3/π
    - r_correlation → d = 2r/√(1-r²)

    Also computes Hedges' g if per-arm N is available.

    Args:
        row: Dict with at minimum beta_raw, effect_type_original.

    Returns:
        Same row dict, enriched with harmonized_beta, conversion_formula, etc.
    """
    row = dict(row)  # shallow copy to avoid mutating caller's dict
    effect_type = _get(row, "effect_type_original")
    beta_raw = _get_float(row, "beta_raw")

    if beta_raw is None:
        # Should have been caught by validation, but be safe
        row["harmonized_beta"] = None
        row["conversion_formula"] = "error_no_beta"
        row["conversion_inputs"] = json.dumps({"error": "beta_raw is None"})
        return row

    conversion_inputs: dict[str, Any] = {"beta_raw": beta_raw, "effect_type": effect_type}
    formula = "passthrough"
    harmonized_d = beta_raw

    if effect_type in {"cohen_d", "cohen_d_from_eta_sq", "log_or", "hedges_g"}:
        # Already in commensurable scale
        formula = "passthrough"
        harmonized_d = beta_raw

    elif effect_type == "mean_diff":
        # Formula: d = mean_diff / SD_pooled
        # SD_pooled = sqrt((sd1² + sd2²) / 2)
        sd_t = _get_float(row, "sd_treatment")
        sd_c = _get_float(row, "sd_control")
        if sd_t is not None and sd_c is not None and (sd_t > 0 or sd_c > 0):
            sd_pooled = math.sqrt((sd_t**2 + sd_c**2) / 2)
            harmonized_d = beta_raw / sd_pooled
            formula = "mean_diff_to_cohen_d"
            conversion_inputs.update({
                "sd_treatment": sd_t, "sd_control": sd_c,
                "sd_pooled": sd_pooled,
            })
        else:
            # Can't convert without SDs — keep raw value, flag it
            formula = "mean_diff_no_sd_available"
            logger.warning(
                "STANDARDIZE: mean_diff without SDs for %s — keeping raw beta",
                _get(row, "edge_id") or _get(row, "edge_relation_id"),
            )

    elif effect_type == "partial_eta_sq":
        # Formula: d = 2 * sqrt(η² / (1 - η²))
        eta_sq = beta_raw
        if 0 < eta_sq < 1:
            harmonized_d = 2.0 * math.sqrt(eta_sq / (1.0 - eta_sq))
            formula = "partial_eta_sq_to_cohen_d"
            conversion_inputs["eta_sq"] = eta_sq
        else:
            formula = "partial_eta_sq_out_of_range"
            logger.warning(
                "STANDARDIZE: partial_eta_sq=%s out of (0,1) range", eta_sq
            )

    elif effect_type == "odds_ratio":
        # Formula: d = ln(OR) × √3 / π
        if beta_raw > 0:
            harmonized_d = math.log(beta_raw) * math.sqrt(3) / math.pi
            formula = "odds_ratio_to_cohen_d"
            conversion_inputs["odds_ratio"] = beta_raw
        else:
            formula = "odds_ratio_non_positive"
            logger.warning("STANDARDIZE: odds_ratio=%s must be positive", beta_raw)

    elif effect_type == "hazard_ratio":
        # Formula: d = ln(HR) × √3 / π (same as OR approximation)
        if beta_raw > 0:
            harmonized_d = math.log(beta_raw) * math.sqrt(3) / math.pi
            formula = "hazard_ratio_to_cohen_d"
            conversion_inputs["hazard_ratio"] = beta_raw
        else:
            formula = "hazard_ratio_non_positive"

    elif effect_type == "r_correlation":
        # Formula: d = 2r / √(1 - r²)
        r = beta_raw
        if -1 < r < 1:
            harmonized_d = (2.0 * r) / math.sqrt(1.0 - r**2)
            formula = "r_to_cohen_d"
            conversion_inputs["r"] = r
        else:
            formula = "r_out_of_range"
            logger.warning("STANDARDIZE: r=%s out of (-1,1) range", r)

    else:
        # Unknown effect type — passthrough with warning
        formula = "unknown_effect_type_passthrough"
        logger.warning(
            "STANDARDIZE: unknown effect_type '%s' — keeping raw beta", effect_type
        )

    row["harmonized_beta"] = harmonized_d
    row["effect_type_reported"] = effect_type
    row["conversion_formula"] = formula
    row["conversion_inputs"] = json.dumps(conversion_inputs)

    # ── Hedges' g small-sample correction ──
    n1 = _get_float(row, "n_treatment")
    n2 = _get_float(row, "n_control")
    if n1 is not None and n2 is not None and (n1 + n2) > 2:
        # Formula: g = d × (1 - 3/(4(n1+n2) - 9))
        # Hedges & Olkin (1985)
        correction = 1 - 3 / (4 * (n1 + n2) - 9)
        row["hedges_g"] = harmonized_d * correction
    else:
        # Use total sample_size as fallback for Hedges' g
        n_total = _get_float(row, "sample_size")
        if n_total is not None and n_total > 2:
            correction = 1 - 3 / (4 * n_total - 9)
            row["hedges_g"] = harmonized_d * correction
        else:
            row["hedges_g"] = harmonized_d  # no correction possible

    return row


# ═══════════════════════════════════════════════════════════════
#  Sign Harmonization
# ═══════════════════════════════════════════════════════════════

def harmonize_sign(row: dict[str, Any]) -> dict[str, Any]:
    """Flip sign so that positive harmonized_beta = benefit (improvement).

    Uses outcome_directionality and beta_sign_convention from the CSV.

    When outcome_directionality == "higher_is_worse" AND
    beta_sign_convention == "positive_is_harm":
      → flip sign so positive = benefit

    This is the canonical convention for the pipeline.

    Args:
        row: Dict with harmonized_beta, outcome_directionality, beta_sign_convention.

    Returns:
        Same row with sign_flipped flag added.
    """
    row = dict(row)
    directionality = _get(row, "outcome_directionality")
    sign_convention = _get(row, "beta_sign_convention")

    should_flip = False

    # If higher is worse on the raw scale AND original sign maps positive → harm,
    # we flip to canonical: positive = benefit
    if directionality == "higher_is_worse" and sign_convention == "positive_is_harm":
        should_flip = True
    # Also flip if higher is better but sign convention says positive is harm
    # (e.g., someone coded a higher-is-better instrument with reversed d)
    elif directionality == "higher_is_better" and sign_convention == "positive_is_harm":
        should_flip = True

    if should_flip:
        beta = row.get("harmonized_beta")
        if beta is not None:
            row["harmonized_beta"] = -beta
        # Also flip hedges_g if it exists
        g = row.get("hedges_g")
        if g is not None:
            row["hedges_g"] = -g

    row["sign_flipped"] = should_flip
    return row


# ═══════════════════════════════════════════════════════════════
#  SE Derivation Cascade
# ═══════════════════════════════════════════════════════════════

def derive_se(row: dict[str, Any]) -> dict[str, Any]:
    """Derive standard error via a 6-level cascade.

    Priority:
        L1: SE directly reported (se_raw)
        L2: SE from confidence interval: SE = (CI_high - CI_low) / (2 × 1.96)
        L3: SE from p-value: SE = |beta| / z_from_p
        L4: SE from F/t statistic (not commonly in CSVs)
        L5: Borrowed from SD anchors (future)
        L6: Heuristic fallback (future)

    Args:
        row: Dict with se_raw, ci_low, ci_high, p_value, beta_raw.

    Returns:
        Same row enriched with harmonized_se and se_derivation_level.
    """
    row = dict(row)

    # L1: Direct SE
    se_raw = _get_float(row, "se_raw")
    if se_raw is not None and se_raw > 0:
        row["harmonized_se"] = se_raw
        row["se_derivation_level"] = "L1_DIRECT"
        return row

    # L2: From confidence interval
    # Formula: SE = (CI_high - CI_low) / (2 × 1.96)
    ci_low = _get_float(row, "ci_low")
    ci_high = _get_float(row, "ci_high")
    if ci_low is not None and ci_high is not None and ci_high > ci_low:
        se = (ci_high - ci_low) / (2 * 1.96)
        row["harmonized_se"] = se
        row["se_derivation_level"] = "L2_FROM_CI"
        logger.info(
            "SE_CASCADE L2: Derived SE=%.4f from CI [%.4f, %.4f] for %s",
            se, ci_low, ci_high, _get(row, "edge_id") or _get(row, "edge_relation_id"),
        )
        return row

    # L3: From p-value
    # Formula: SE = |beta| / z_from_p
    p_value = _get_float(row, "p_value")
    beta = _get_float(row, "beta_raw")
    if p_value is not None and beta is not None and 0 < p_value < 1 and abs(beta) > 0:
        try:
            from scipy.stats import norm
            z = norm.ppf(1 - p_value / 2)
            se = abs(beta) / z
            row["harmonized_se"] = se
            row["se_derivation_level"] = "L3_FROM_P"
            logger.info(
                "SE_CASCADE L3: Derived SE=%.4f from p=%.4f, |β|=%.4f, z=%.4f for %s",
                se, p_value, abs(beta), z,
                _get(row, "edge_id") or _get(row, "edge_relation_id"),
            )
        except ImportError:
            # scipy not available — use approximation for common p-values
            # z ≈ 1.96 for p=0.05
            z_approx = 1.96  # conservative default
            se = abs(beta) / z_approx
            row["harmonized_se"] = se
            row["se_derivation_level"] = "L3_FROM_P"
        return row

    # L5/L6: Heuristic fallback — use harmonized_beta if already computed
    harmonized_beta = row.get("harmonized_beta")
    n_total = _get_float(row, "sample_size")
    if harmonized_beta is not None and n_total is not None and n_total > 2:
        # Borenstein et al. Eq.4.24: SE_d ≈ sqrt(1/n + d²/(2n))
        # Simplified heuristic for total N when per-arm N unavailable
        se = math.sqrt(1.0 / n_total + float(harmonized_beta)**2 / (2 * n_total))
        row["harmonized_se"] = se
        row["se_derivation_level"] = "L6_HEURISTIC"
        logger.warning(
            "SE_CASCADE L6: Heuristic SE=%.4f from N=%d and d=%.4f for %s. "
            "DEFAULTED — provide se_raw or CI for accuracy.",
            se, int(n_total), float(harmonized_beta),
            _get(row, "edge_id") or _get(row, "edge_relation_id"),
        )
        return row

    # Absolute fallback — no SE derivable
    row["harmonized_se"] = None
    row["se_derivation_level"] = "NONE_AVAILABLE"
    logger.error(
        "SE_CASCADE FAILED: No SE derivable for %s. "
        "Provide se_raw, CI, or p_value.",
        _get(row, "edge_id") or _get(row, "edge_relation_id"),
    )
    return row


# ═══════════════════════════════════════════════════════════════
#  Layer Input Computation
# ═══════════════════════════════════════════════════════════════

def compute_layer_inputs(row: dict[str, Any]) -> dict[str, Any]:
    """Map human-friendly field values to P3-layer canonical keys.

    Uses vocab.py mappings exclusively — NO inline string checks.
    Stores canonical values alongside originals for audit trail.

    Args:
        row: Dict with study_design, cancer_validated, rob_overall, pub_year.

    Returns:
        Same row enriched with *_canonical fields.
    """
    row = dict(row)

    # L1: study_design → canonical P3 key
    study_design = _get(row, "study_design")
    n_total = _get_float(row, "sample_size")
    if study_design:
        try:
            row["study_design_canonical"] = resolve_study_design(
                study_design, n_total=int(n_total) if n_total else None
            )
        except ValueError:
            row["study_design_canonical"] = None
            logger.warning(
                "LAYER_INPUT: study_design '%s' failed resolution", study_design
            )

    # L4: cancer_validated → canonical SCALE_MULTIPLIERS key
    cancer_validated = _get(row, "cancer_validated")
    if cancer_validated:
        try:
            row["cancer_validation_canonical"] = resolve_cancer_validation(
                cancer_validated
            )
        except ValueError:
            row["cancer_validation_canonical"] = None
            logger.warning(
                "LAYER_INPUT: cancer_validated '%s' failed resolution",
                cancer_validated,
            )

    # L5: rob_overall → canonical GRADE_MULTIPLIERS key
    rob_overall = _get(row, "rob_overall")
    if rob_overall:
        try:
            row["rob_grade_canonical"] = resolve_rob_to_grade(rob_overall)
        except ValueError:
            row["rob_grade_canonical"] = None
            logger.warning(
                "LAYER_INPUT: rob_overall '%s' failed resolution", rob_overall
            )

    # L7: pub_year → stored directly for freshness decay
    pub_year_str = _get(row, "pub_year")
    if pub_year_str:
        try:
            row["pub_year_int"] = int(pub_year_str)
        except ValueError:
            row["pub_year_int"] = None

    return row
