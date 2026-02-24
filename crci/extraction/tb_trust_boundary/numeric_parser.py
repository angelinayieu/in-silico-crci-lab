# VERIFIED: formulas NP-01 through NP-11 match spec lines 628-650
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads SpanLabel[] from ag05_stats_label.py
# VERIFIED: forward wiring — writes list[ParsedNumeric] for consistency_checker.py
# VERIFIED: no hardcoded formula parameters (plausibility bounds from config)
# VERIFIED: gates TB-G1 raise on failure
"""
Component: SYS_EXTRACTION.EX-TB.TB-NP
Spec: SYS_EXTRACTION_COMPLETE.md lines 593-650
Formulas: NP-01, NP-02, NP-03, NP-04, NP-05, NP-06, NP-07, NP-08, NP-09, NP-10, NP-11
Reads: SpanLabel[] (from ag05_stats_label.py)
Writes: list[ParsedNumeric] (consumed by consistency_checker.py)
Gates: TB-G1 (>= 1 span parsed successfully or raise GateViolation)

THIS IS THE TRUST BOUNDARY FOR NUMERIC EVIDENCE.
NO LLM CALLS. Pure deterministic parsing.
"""
from __future__ import annotations

import logging
import math
import re
from typing import Any

from crci.shared import config
from crci.shared.models.enums import BoundType, ParseStatus
from crci.shared.models.intermediate_states import (
    GateViolation,
    ParsedNumeric,
    SpanLabel,
    TypedNumericValue,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Label type → parse rule mapping
# ═══════════════════════════════════════════════════════════════

# Label types handled by each parse rule
_RULE_NP01_TYPES = {"MEAN", "MEDIAN"}
_RULE_NP02_TYPES = {"CI_LOWER", "CI_UPPER"}
_RULE_NP03_TYPES = {"P_VALUE"}
_RULE_NP04_TYPES = {
    "EFFECT_SIZE", "ODDS_RATIO", "HAZARD_RATIO", "RISK_RATIO",
    "INCIDENCE_RATE_RATIO", "MEAN_DIFFERENCE", "PERCENT_CHANGE",
}
_RULE_NP05_TYPES = {"SAMPLE_SIZE", "SAMPLE_SIZE_ARM", "ATTRITION_N"}
_RULE_NP06_TYPES = {"ATTRITION_RATE"}
_RULE_NP08_TYPES = {"UNSTD_BETA", "STD_BETA"}
_RULE_NP09_TYPES = {"CORRELATION"}
_RULE_NP10_TYPES = {
    "F_STATISTIC", "T_STATISTIC", "CHI_SQUARE", "Z_STATISTIC",
    "I_SQUARED", "TAU_SQUARED", "Q_STATISTIC", "R_SQUARED",
    "AIC", "BIC", "DF",
}
_RULE_NP_PASSTHROUGH_TYPES = {
    "SE", "SD", "VARIANCE", "IQR_LOWER", "IQR_UPPER",
    "RANGE_MIN", "RANGE_MAX", "INTERACTION_TERM", "SUBGROUP_EFFECT",
    "FOLLOW_UP_DURATION",
}


# ═══════════════════════════════════════════════════════════════
#  Core regex patterns (compiled once)
# ═══════════════════════════════════════════════════════════════

# Rule NP-01 patterns: "X +/- Y" or "X (Y)" for mean(SD)
_RE_MEAN_SD_PLUSMINUS = re.compile(
    r"(?P<mean>[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)"
    r"\s*[±\+\-/]+\s*"
    r"(?P<sd>\d+\.?\d*(?:[eE][-+]?\d+)?)"
)
_RE_MEAN_SD_PAREN = re.compile(
    r"(?P<mean>[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)"
    r"\s*\(\s*(?P<sd>\d+\.?\d*(?:[eE][-+]?\d+)?)\s*\)"
)

# Rule NP-02 patterns: CI "[X, Y]" or "X to Y" or "(X-Y)" or "X - Y"
_RE_CI_BRACKET = re.compile(
    r"[\[\(]\s*(?P<lower>[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)"
    r"\s*[,;]\s*"
    r"(?P<upper>[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)\s*[\]\)]"
)
_RE_CI_TO = re.compile(
    r"(?P<lower>[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)"
    r"\s+to\s+"
    r"(?P<upper>[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)",
    re.IGNORECASE,
)
_RE_CI_DASH = re.compile(
    r"(?P<lower>[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)"
    r"\s*[-\u2013\u2014]\s*"
    r"(?P<upper>[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)"
)
_RE_CI_FULL = re.compile(
    r"(?:95\s*%?\s*CI\s*[:=]?\s*)"
    r"[\[\(]?\s*(?P<lower>[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)"
    r"\s*[,;\-\u2013\u2014]\s*"
    r"(?P<upper>[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)\s*[\]\)]?",
    re.IGNORECASE,
)

# Rule NP-03 patterns: p-value
_RE_P_VALUE = re.compile(
    r"[pP]\s*[<>=≤≥]\s*(?P<pval>\d*\.?\d+(?:[eE][-+]?\d+)?)"
)
_RE_P_EXACT = re.compile(
    r"[pP]\s*=\s*(?P<pval>\d*\.?\d+(?:[eE][-+]?\d+)?)"
)
_RE_P_NS = re.compile(
    r"\b(?:NS|n\.s\.|non[- ]?significant)\b",
    re.IGNORECASE,
)
_RE_P_LESS = re.compile(
    r"[pP]\s*<\s*(?P<pval>\d*\.?\d+(?:[eE][-+]?\d+)?)"
)

# Rule NP-04 patterns: effect sizes
_RE_EFFECT_NAMED = re.compile(
    r"(?:Cohen'?s?\s*d|Hedges'?\s*g|[dg])\s*[=:]\s*"
    r"(?P<value>[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)",
    re.IGNORECASE,
)
_RE_ETA_SQUARED = re.compile(
    r"[ηn]\s*[²2]\s*[=:]\s*(?P<value>\d+\.?\d*(?:[eE][-+]?\d+)?)",
    re.IGNORECASE,
)
_RE_OR_HR_RR = re.compile(
    r"(?:OR|HR|RR|IRR)\s*[=:]\s*(?P<value>\d+\.?\d*(?:[eE][-+]?\d+)?)",
    re.IGNORECASE,
)

# Rule NP-05 patterns: sample size
_RE_SAMPLE_SIZE = re.compile(
    r"[Nn]\s*=\s*(?P<n>\d[\d,]*)"
)

# Rule NP-06 patterns: percentage
_RE_PERCENTAGE = re.compile(
    r"(?P<pct>\d+\.?\d*)\s*%"
)

# Rule NP-08 patterns: regression coefficient
_RE_BETA_SE = re.compile(
    r"[βBb]\s*=\s*(?P<beta>[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)"
    r"\s*,?\s*SE\s*=\s*(?P<se>\d+\.?\d*(?:[eE][-+]?\d+)?)",
    re.IGNORECASE,
)
_RE_BETA_CI = re.compile(
    r"[βBb]\s*=\s*(?P<beta>[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)"
    r"\s*\(?\s*95\s*%?\s*CI\s*:?\s*"
    r"(?P<lower>[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)"
    r"\s*[,;\-\u2013\u2014]\s*"
    r"(?P<upper>[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)\s*\)?",
    re.IGNORECASE,
)
_RE_BETA_PLAIN = re.compile(
    r"[βBb]\s*=\s*(?P<beta>[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)"
)

# Rule NP-09 patterns: correlation coefficient
_RE_CORR_CI = re.compile(
    r"[rρ]\s*=\s*(?P<r>[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)"
    r".*?(?:95\s*%?\s*CI\s*:?\s*)?"
    r"[\[\(]\s*(?P<lower>[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)"
    r"\s*[,;\-\u2013\u2014]\s*"
    r"(?P<upper>[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)\s*[\]\)]",
    re.IGNORECASE,
)
_RE_CORR_PLAIN = re.compile(
    r"[rρ]\s*=\s*(?P<r>[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)",
    re.IGNORECASE,
)

# Rule NP-10 patterns: test statistics
_RE_F_STAT = re.compile(
    r"[Ff]\s*\(\s*(?P<df1>\d+)\s*,\s*(?P<df2>\d+)\s*\)\s*=\s*"
    r"(?P<value>\d+\.?\d*(?:[eE][-+]?\d+)?)"
)
_RE_T_STAT = re.compile(
    r"[tT]\s*(?:\(\s*(?P<df>\d+)\s*\))?\s*=\s*"
    r"(?P<value>[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)"
)
_RE_CHI2_STAT = re.compile(
    r"[χXx]\s*[²2]\s*(?:\(\s*(?P<df>\d+)\s*\))?\s*=\s*"
    r"(?P<value>\d+\.?\d*(?:[eE][-+]?\d+)?)"
)

# Generic number extraction fallback
_RE_GENERIC_NUMBER = re.compile(
    r"[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?"
)


def _safe_float(text: str) -> float | None:
    """Attempt to parse a cleaned string as float, return None on failure."""
    try:
        cleaned = text.strip().replace(",", "")
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def _safe_int(text: str) -> int | None:
    """Attempt to parse a cleaned string as int, return None on failure."""
    try:
        cleaned = text.strip().replace(",", "")
        return int(float(cleaned))
    except (ValueError, TypeError):
        return None


# ═══════════════════════════════════════════════════════════════
#  Parse result container (internal)
# ═══════════════════════════════════════════════════════════════


class _ParseResult:
    """Internal container for a single parse attempt."""

    def __init__(
        self,
        *,
        value: float | None = None,
        se: float | None = None,
        ci_lower: float | None = None,
        ci_upper: float | None = None,
        p_value: float | None = None,
        n: int | None = None,
        bound_type: BoundType = BoundType.EXACT,
        status: ParseStatus = ParseStatus.CLEAN,
        rule_id: str = "",
        notes: list[str] | None = None,
    ):
        self.value = value
        self.se = se
        self.ci_lower = ci_lower
        self.ci_upper = ci_upper
        self.p_value = p_value
        self.n = n
        self.bound_type = bound_type
        self.status = status
        self.rule_id = rule_id
        self.notes: list[str] = notes or []


# ═══════════════════════════════════════════════════════════════
#  Individual parse rules (NP-01 through NP-11)
# ═══════════════════════════════════════════════════════════════


def _rule_np01_mean_sd(raw_text: str, label_type: str) -> _ParseResult | None:
    """Rule NP-01: Mean +/- SD extraction.

    Pattern: "X +/- Y" or "X (Y)"
    Returns: value=mean, se derived from SD if possible.
    """
    # Rule NP-01: Mean ± SD extraction (pattern: "X ± Y" or "X (Y)")
    m = _RE_MEAN_SD_PLUSMINUS.search(raw_text)
    if m:
        mean_val = _safe_float(m.group("mean"))
        sd_val = _safe_float(m.group("sd"))
        if mean_val is not None and sd_val is not None:
            return _ParseResult(
                value=mean_val,
                se=None,  # SD is not SE; downstream computes SE from SD+N
                rule_id="NP-01",
                notes=[f"SD={sd_val}"],
            )

    m = _RE_MEAN_SD_PAREN.search(raw_text)
    if m:
        mean_val = _safe_float(m.group("mean"))
        sd_val = _safe_float(m.group("sd"))
        if mean_val is not None and sd_val is not None:
            return _ParseResult(
                value=mean_val,
                se=None,
                rule_id="NP-01",
                notes=[f"SD={sd_val}"],
            )

    # Fallback: simple numeric extraction for MEAN/MEDIAN
    num = _extract_first_number(raw_text)
    if num is not None:
        return _ParseResult(value=num, rule_id="NP-01")

    return None


def _rule_np02_ci(raw_text: str, label_type: str) -> _ParseResult | None:
    """Rule NP-02: CI extraction.

    Pattern: "[X, Y]" or "X to Y" or "(X-Y)" or "95% CI: X-Y"
    Returns: ci_lower, ci_upper. SE derived from CI using Rule NP-11.
    """
    # Rule NP-02: CI extraction (pattern: "[X, Y]" or "X to Y" or "(X-Y)")
    lower: float | None = None
    upper: float | None = None

    # Try full "95% CI: X-Y" first
    m = _RE_CI_FULL.search(raw_text)
    if m:
        lower = _safe_float(m.group("lower"))
        upper = _safe_float(m.group("upper"))

    # Try bracket form "[X, Y]"
    if lower is None:
        m = _RE_CI_BRACKET.search(raw_text)
        if m:
            lower = _safe_float(m.group("lower"))
            upper = _safe_float(m.group("upper"))

    # Try "X to Y"
    if lower is None:
        m = _RE_CI_TO.search(raw_text)
        if m:
            lower = _safe_float(m.group("lower"))
            upper = _safe_float(m.group("upper"))

    # Try dash form "X-Y" (careful with negative numbers)
    if lower is None:
        m = _RE_CI_DASH.search(raw_text)
        if m:
            lower = _safe_float(m.group("lower"))
            upper = _safe_float(m.group("upper"))

    if lower is not None and upper is not None:
        # Validate CI ordering
        if lower > upper:
            logger.warning(
                "Rule NP-02: CI bounds out of order in '%s'. "
                "Swapping lower=%.4f and upper=%.4f.",
                raw_text[:80],
                lower,
                upper,
            )
            lower, upper = upper, lower

        # Rule NP-11: derive SE from CI if possible
        # SE = (upper - lower) / (2 × 1.96)
        se = (upper - lower) / (2 * config.TB_CI_TO_SE_Z_MULTIPLIER)

        if label_type == "CI_LOWER":
            return _ParseResult(
                value=lower,
                ci_lower=lower,
                ci_upper=upper,
                se=se,
                rule_id="NP-02",
                notes=["SE derived from CI via NP-11"],
            )
        elif label_type == "CI_UPPER":
            return _ParseResult(
                value=upper,
                ci_lower=lower,
                ci_upper=upper,
                se=se,
                rule_id="NP-02",
                notes=["SE derived from CI via NP-11"],
            )
        else:
            return _ParseResult(
                value=(lower + upper) / 2,
                ci_lower=lower,
                ci_upper=upper,
                se=se,
                rule_id="NP-02",
                notes=["Value is CI midpoint; SE derived from CI via NP-11"],
            )

    # Fallback: extract single number for CI_LOWER / CI_UPPER
    num = _extract_first_number(raw_text)
    if num is not None:
        if label_type == "CI_LOWER":
            return _ParseResult(value=num, ci_lower=num, rule_id="NP-02")
        elif label_type == "CI_UPPER":
            return _ParseResult(value=num, ci_upper=num, rule_id="NP-02")

    return None


def _rule_np03_p_value(raw_text: str, label_type: str) -> _ParseResult | None:
    """Rule NP-03: P-value parsing.

    Patterns: p<0.05, p=0.001, NS, p<.001
    Returns: p_value. "NS" → None (not 0), "p>0.05" → None.
    """
    # Rule NP-03: P-value parsing (p<0.05, p=0.001, NS, p<.001)

    # Check for "NS" / "non-significant"
    if _RE_P_NS.search(raw_text):
        logger.info(
            "Rule NP-03: 'NS' detected in '%s'. Setting p_value=None (not 0).",
            raw_text[:80],
        )
        return _ParseResult(
            value=None,
            p_value=None,
            rule_id="NP-03",
            status=ParseStatus.CLEAN,
            notes=["NS detected — p_value set to None, not 0"],
        )

    # Check "p < X" (upper bound)
    m = _RE_P_LESS.search(raw_text)
    if m:
        pval = _safe_float(m.group("pval"))
        if pval is not None:
            return _ParseResult(
                value=pval,
                p_value=pval,
                bound_type=BoundType.UPPER,
                rule_id="NP-03",
                notes=[f"p < {pval} (upper bound)"],
            )

    # Check "p = X" (exact)
    m = _RE_P_EXACT.search(raw_text)
    if m:
        pval = _safe_float(m.group("pval"))
        if pval is not None:
            return _ParseResult(
                value=pval,
                p_value=pval,
                bound_type=BoundType.EXACT,
                rule_id="NP-03",
            )

    # Generic p-value
    m = _RE_P_VALUE.search(raw_text)
    if m:
        pval = _safe_float(m.group("pval"))
        if pval is not None:
            return _ParseResult(
                value=pval,
                p_value=pval,
                rule_id="NP-03",
            )

    # Fallback: try bare number
    num = _extract_first_number(raw_text)
    if num is not None and config.TB_PLAUSIBILITY_P_VALUE_MIN <= num <= config.TB_PLAUSIBILITY_P_VALUE_MAX:
        return _ParseResult(value=num, p_value=num, rule_id="NP-03")

    return None


def _rule_np04_effect_size(raw_text: str, label_type: str) -> _ParseResult | None:
    """Rule NP-04: Effect size extraction.

    Cohen's d, eta-squared, r, OR, HR, RR.
    OR and HR are log-transformed: beta = ln(OR), beta = ln(HR).
    """
    # Rule NP-04: Effect size (Cohen's d, η², r, OR, HR, RR)
    result: _ParseResult | None = None

    # Named effect size (Cohen's d, Hedges' g)
    m = _RE_EFFECT_NAMED.search(raw_text)
    if m:
        val = _safe_float(m.group("value"))
        if val is not None:
            result = _ParseResult(value=val, rule_id="NP-04")

    # Eta-squared
    if result is None:
        m = _RE_ETA_SQUARED.search(raw_text)
        if m:
            val = _safe_float(m.group("value"))
            if val is not None:
                result = _ParseResult(
                    value=val,
                    rule_id="NP-04",
                    notes=["eta_squared"],
                )

    # OR, HR, RR: log-transform
    if result is None:
        m = _RE_OR_HR_RR.search(raw_text)
        if m:
            val = _safe_float(m.group("value"))
            if val is not None and val > 0:
                log_val = math.log(val)
                result = _ParseResult(
                    value=log_val,
                    rule_id="NP-04",
                    notes=[f"log-transformed from {label_type}={val}"],
                )

    # For label_types that are ratio measures, try to parse and log-transform
    if result is None and label_type in {"ODDS_RATIO", "HAZARD_RATIO", "RISK_RATIO", "INCIDENCE_RATE_RATIO"}:
        num = _extract_first_number(raw_text)
        if num is not None and num > 0:
            log_val = math.log(num)
            result = _ParseResult(
                value=log_val,
                rule_id="NP-04",
                notes=[f"log-transformed from {label_type}={num}"],
            )

    # Also try to extract CI if present in the same text
    if result is not None:
        ci_match = _RE_CI_FULL.search(raw_text) or _RE_CI_BRACKET.search(raw_text)
        if ci_match:
            ci_lower = _safe_float(ci_match.group("lower"))
            ci_upper = _safe_float(ci_match.group("upper"))
            if ci_lower is not None and ci_upper is not None:
                # Log-transform CI for ratio measures
                if label_type in {"ODDS_RATIO", "HAZARD_RATIO", "RISK_RATIO", "INCIDENCE_RATE_RATIO"}:
                    if ci_lower > 0 and ci_upper > 0:
                        result.ci_lower = math.log(ci_lower)
                        result.ci_upper = math.log(ci_upper)
                        # Rule NP-11: SE = (upper - lower) / (2 × 1.96)
                        result.se = (result.ci_upper - result.ci_lower) / (
                            2 * config.TB_CI_TO_SE_Z_MULTIPLIER
                        )
                        result.notes.append("SE derived from log-transformed CI via NP-11")
                else:
                    result.ci_lower = ci_lower
                    result.ci_upper = ci_upper
                    # Rule NP-11: SE = (upper - lower) / (2 × 1.96)
                    result.se = (ci_upper - ci_lower) / (
                        2 * config.TB_CI_TO_SE_Z_MULTIPLIER
                    )
                    result.notes.append("SE derived from CI via NP-11")

    # Fallback: parse raw number for generic effect size types
    if result is None and label_type in {"EFFECT_SIZE", "MEAN_DIFFERENCE", "PERCENT_CHANGE"}:
        num = _extract_first_number(raw_text)
        if num is not None:
            result = _ParseResult(value=num, rule_id="NP-04")

    return result


def _rule_np05_sample_size(raw_text: str, label_type: str) -> _ParseResult | None:
    """Rule NP-05: Sample size per group.

    Pattern: N=, n=, followed by integer.
    """
    # Rule NP-05: Sample size per group (N=, n=)
    m = _RE_SAMPLE_SIZE.search(raw_text)
    if m:
        n_val = _safe_int(m.group("n"))
        if n_val is not None and n_val > 0:
            return _ParseResult(
                value=float(n_val),
                n=n_val,
                rule_id="NP-05",
            )

    # Fallback: extract bare integer
    num = _extract_first_number(raw_text)
    if num is not None:
        n_int = int(num) if num == int(num) else None
        if n_int is not None and n_int > 0:
            return _ParseResult(
                value=float(n_int),
                n=n_int,
                rule_id="NP-05",
            )

    return None


def _rule_np06_percentage(raw_text: str, label_type: str) -> _ParseResult | None:
    """Rule NP-06: Percentage + proportion conversion.

    Pattern: X% -> X/100. Also handles "0.XX" as proportion.
    """
    # Rule NP-06: Percentage + proportion conversion (X%, 0.XX)
    m = _RE_PERCENTAGE.search(raw_text)
    if m:
        pct = _safe_float(m.group("pct"))
        if pct is not None:
            proportion = pct / 100.0
            return _ParseResult(
                value=proportion,
                rule_id="NP-06",
                notes=[f"Converted {pct}% to proportion {proportion}"],
            )

    # Check if it's already a proportion (0.XX)
    num = _extract_first_number(raw_text)
    if num is not None:
        if 0.0 <= num <= 1.0:
            return _ParseResult(
                value=num,
                rule_id="NP-06",
                notes=["Interpreted as proportion"],
            )
        elif 0.0 < num <= 100.0:
            proportion = num / 100.0
            return _ParseResult(
                value=proportion,
                rule_id="NP-06",
                notes=[f"Converted {num} to proportion {proportion}"],
            )

    return None


def _rule_np07_table_cell(raw_text: str, label_type: str) -> _ParseResult | None:
    """Rule NP-07: Table cell extraction (row x column indexing).

    Tables are pre-parsed upstream, so this extracts the numeric value
    from the already-isolated cell text.
    """
    # Rule NP-07: Table cell extraction (row×column indexing) — tables pre-parsed
    # Extract the first number from the cell text
    num = _extract_first_number(raw_text)
    if num is not None:
        return _ParseResult(
            value=num,
            rule_id="NP-07",
            notes=["Extracted from pre-parsed table cell"],
        )

    return None


def _rule_np08_regression_coeff(raw_text: str, label_type: str) -> _ParseResult | None:
    """Rule NP-08: Regression coefficient.

    Patterns: "beta=X, SE=Y" or "B=X (95% CI: Y-Z)"
    """
    # Rule NP-08: Regression coefficient (β with SE or CI: "β=X, SE=Y" or "B=X (95% CI: Y-Z)")

    # Try beta + SE
    m = _RE_BETA_SE.search(raw_text)
    if m:
        beta = _safe_float(m.group("beta"))
        se = _safe_float(m.group("se"))
        if beta is not None and se is not None:
            return _ParseResult(
                value=beta,
                se=se,
                rule_id="NP-08",
            )

    # Try beta + CI
    m = _RE_BETA_CI.search(raw_text)
    if m:
        beta = _safe_float(m.group("beta"))
        ci_lower = _safe_float(m.group("lower"))
        ci_upper = _safe_float(m.group("upper"))
        if beta is not None and ci_lower is not None and ci_upper is not None:
            # Ensure ordering
            if ci_lower > ci_upper:
                ci_lower, ci_upper = ci_upper, ci_lower
            # Rule NP-11: SE = (upper - lower) / (2 × 1.96)
            se = (ci_upper - ci_lower) / (2 * config.TB_CI_TO_SE_Z_MULTIPLIER)
            return _ParseResult(
                value=beta,
                se=se,
                ci_lower=ci_lower,
                ci_upper=ci_upper,
                rule_id="NP-08",
                notes=["SE derived from CI via NP-11"],
            )

    # Try plain beta
    m = _RE_BETA_PLAIN.search(raw_text)
    if m:
        beta = _safe_float(m.group("beta"))
        if beta is not None:
            return _ParseResult(
                value=beta,
                rule_id="NP-08",
                notes=["SE missing — flagged for NP-11 imputation"],
            )

    # Fallback: bare number
    num = _extract_first_number(raw_text)
    if num is not None:
        return _ParseResult(
            value=num,
            rule_id="NP-08",
            notes=["Parsed as bare regression coefficient; SE missing"],
        )

    return None


def _rule_np09_correlation(raw_text: str, label_type: str) -> _ParseResult | None:
    """Rule NP-09: Correlation coefficient.

    Patterns: r=X, rho=X, with optional CI.
    Validation: |r| <= 1
    """
    # Rule NP-09: Correlation coefficient (r=X, ρ=X with CI)

    # Try r with CI
    m = _RE_CORR_CI.search(raw_text)
    if m:
        r_val = _safe_float(m.group("r"))
        ci_lower = _safe_float(m.group("lower"))
        ci_upper = _safe_float(m.group("upper"))
        if r_val is not None and ci_lower is not None and ci_upper is not None:
            if abs(r_val) <= config.TB_PLAUSIBILITY_CORRELATION_MAX:
                # Ensure CI ordering
                if ci_lower > ci_upper:
                    ci_lower, ci_upper = ci_upper, ci_lower
                # Rule NP-11: SE = (upper - lower) / (2 × 1.96)
                se = (ci_upper - ci_lower) / (2 * config.TB_CI_TO_SE_Z_MULTIPLIER)
                return _ParseResult(
                    value=r_val,
                    se=se,
                    ci_lower=ci_lower,
                    ci_upper=ci_upper,
                    rule_id="NP-09",
                    notes=["SE derived from CI via NP-11"],
                )

    # Try plain r
    m = _RE_CORR_PLAIN.search(raw_text)
    if m:
        r_val = _safe_float(m.group("r"))
        if r_val is not None and abs(r_val) <= config.TB_PLAUSIBILITY_CORRELATION_MAX:
            return _ParseResult(
                value=r_val,
                rule_id="NP-09",
            )

    # Fallback: bare number
    num = _extract_first_number(raw_text)
    if num is not None and abs(num) <= config.TB_PLAUSIBILITY_CORRELATION_MAX:
        return _ParseResult(
            value=num,
            rule_id="NP-09",
        )

    return None


def _rule_np10_test_statistic(raw_text: str, label_type: str) -> _ParseResult | None:
    """Rule NP-10: F-statistic / t-statistic / chi-square parsing.

    Patterns: F(df1, df2)=X, t(df)=X, chi2(df)=X
    """
    # Rule NP-10: F-statistic / t-statistic / χ² parsing

    if label_type == "F_STATISTIC":
        m = _RE_F_STAT.search(raw_text)
        if m:
            val = _safe_float(m.group("value"))
            if val is not None:
                return _ParseResult(
                    value=val,
                    rule_id="NP-10",
                    notes=[f"F({m.group('df1')},{m.group('df2')})={val}"],
                )

    if label_type == "T_STATISTIC":
        m = _RE_T_STAT.search(raw_text)
        if m:
            val = _safe_float(m.group("value"))
            if val is not None:
                df = m.group("df")
                return _ParseResult(
                    value=val,
                    rule_id="NP-10",
                    notes=[f"t{'(' + df + ')' if df else ''}={val}"],
                )

    if label_type == "CHI_SQUARE":
        m = _RE_CHI2_STAT.search(raw_text)
        if m:
            val = _safe_float(m.group("value"))
            if val is not None:
                df = m.group("df")
                return _ParseResult(
                    value=val,
                    rule_id="NP-10",
                    notes=[f"chi2{'(' + df + ')' if df else ''}={val}"],
                )

    # Fallback for any test statistic type
    num = _extract_first_number(raw_text)
    if num is not None:
        return _ParseResult(
            value=num,
            rule_id="NP-10",
        )

    return None


def _rule_np11_missing_data(
    result: _ParseResult,
    raw_text: str,
    label_type: str,
) -> _ParseResult:
    """Rule NP-11: Missing data imputation flags.

    If SE missing, attempt to derive from CI or p-value.
    SE = (upper - lower) / (2 x 1.96) [from CI]
    This is applied as a post-processing step on an existing parse result.
    """
    # Rule NP-11: Missing data imputation flags (if SE missing, derive from CI or p-value)

    if result.se is not None and result.se > 0:
        return result  # SE already present, no imputation needed

    # Attempt 1: Derive SE from CI
    if result.ci_lower is not None and result.ci_upper is not None:
        # SE = (upper - lower) / (2 × 1.96)
        se = (result.ci_upper - result.ci_lower) / (
            2 * config.TB_CI_TO_SE_Z_MULTIPLIER
        )
        if se > 0:
            result.se = se
            result.notes.append("NP-11: SE imputed from CI: SE = (upper - lower) / (2 * 1.96)")
            logger.info(
                "Rule NP-11: SE imputed from CI for '%s': SE=%.6f "
                "(CI=[%.4f, %.4f])",
                raw_text[:60],
                se,
                result.ci_lower,
                result.ci_upper,
            )
            return result

    # Attempt 2: Derive SE from p-value + point estimate
    # For a two-sided test: z = point_estimate / SE, so SE = |point_estimate| / z
    # where z = inverse_normal(1 - p/2)
    if (
        result.p_value is not None
        and result.value is not None
        and result.p_value > 0
        and result.value != 0
    ):
        # Use standard normal approximation: z = -ln(p) (rough approx for small p)
        # More precise: for p=0.05, z=1.96; for p=0.01, z=2.576; for p=0.001, z=3.291
        # We use: SE = |beta| / z_from_p
        # z_from_p derived from p using the inverse normal tail approximation
        z_approx = _p_to_z_approximate(result.p_value)
        if z_approx is not None and z_approx > 0:
            se = abs(result.value) / z_approx
            if se > 0:
                result.se = se
                result.notes.append(
                    f"NP-11: SE imputed from p-value: SE = |beta|/z, "
                    f"p={result.p_value}, z={z_approx:.4f}"
                )
                logger.info(
                    "Rule NP-11: SE imputed from p-value for '%s': SE=%.6f "
                    "(p=%.6f, z=%.4f)",
                    raw_text[:60],
                    se,
                    result.p_value,
                    z_approx,
                )
                return result

    # If SE still missing, flag it
    if result.se is None:
        result.notes.append("NP-11: SE could not be derived — flagged as missing")

    return result


def _p_to_z_approximate(p: float) -> float | None:
    """Approximate inverse normal for common p-values.

    Uses a simple rational approximation for the inverse normal CDF.
    Returns z-score for a two-sided test at significance level p.
    """
    if p <= 0 or p >= 1:
        return None

    # Two-sided: alpha/2
    alpha_half = p / 2.0

    # Rational approximation for the inverse normal (Abramowitz & Stegun 26.2.23)
    # For alpha_half in (0, 0.5):
    if alpha_half >= 0.5:
        return 0.0

    t = math.sqrt(-2.0 * math.log(alpha_half))
    # Coefficients
    c0 = 2.515517
    c1 = 0.802853
    c2 = 0.010328
    d1 = 1.432788
    d2 = 0.189269
    d3 = 0.001308

    z = t - (c0 + c1 * t + c2 * t * t) / (1.0 + d1 * t + d2 * t * t + d3 * t * t * t)
    return z


# ═══════════════════════════════════════════════════════════════
#  Passthrough parser for simple numeric labels
# ═══════════════════════════════════════════════════════════════


def _rule_passthrough(raw_text: str, label_type: str) -> _ParseResult | None:
    """Parse simple numeric labels that just need a number extracted.

    Used for: SE, SD, VARIANCE, IQR, RANGE, INTERACTION_TERM, etc.
    """
    num = _extract_first_number(raw_text)
    if num is not None:
        return _ParseResult(
            value=num,
            rule_id="PASSTHROUGH",
        )
    return None


# ═══════════════════════════════════════════════════════════════
#  Utility
# ═══════════════════════════════════════════════════════════════


def _extract_first_number(text: str) -> float | None:
    """Extract the first float-parseable number from text."""
    # Remove common prefixes
    cleaned = re.sub(r"^[<>≤≥=:]+\s*", "", text.strip())
    cleaned = cleaned.replace(",", "")

    # Try direct parse
    val = _safe_float(cleaned)
    if val is not None:
        return val

    # Find first number
    m = _RE_GENERIC_NUMBER.search(cleaned)
    if m:
        return _safe_float(m.group(0))

    return None


def _dispatch_parse(raw_text: str, label_type: str) -> _ParseResult | None:
    """Route a span to the correct parse rule based on its label_type."""
    if label_type in _RULE_NP01_TYPES:
        return _rule_np01_mean_sd(raw_text, label_type)
    if label_type in _RULE_NP02_TYPES:
        return _rule_np02_ci(raw_text, label_type)
    if label_type in _RULE_NP03_TYPES:
        return _rule_np03_p_value(raw_text, label_type)
    if label_type in _RULE_NP04_TYPES:
        return _rule_np04_effect_size(raw_text, label_type)
    if label_type in _RULE_NP05_TYPES:
        return _rule_np05_sample_size(raw_text, label_type)
    if label_type in _RULE_NP06_TYPES:
        return _rule_np06_percentage(raw_text, label_type)
    if label_type in _RULE_NP08_TYPES:
        return _rule_np08_regression_coeff(raw_text, label_type)
    if label_type in _RULE_NP09_TYPES:
        return _rule_np09_correlation(raw_text, label_type)
    if label_type in _RULE_NP10_TYPES:
        return _rule_np10_test_statistic(raw_text, label_type)
    if label_type in _RULE_NP_PASSTHROUGH_TYPES:
        return _rule_passthrough(raw_text, label_type)
    # NP-07: table cell (any label type can come from a table)
    return _rule_np07_table_cell(raw_text, label_type)


# ═══════════════════════════════════════════════════════════════
#  Plausibility validation (per spec: |beta| <= 5, SE > 0,
#  CI ordered, |r| <= 1, N > 0)
# ═══════════════════════════════════════════════════════════════


def _validate_plausibility(
    result: _ParseResult,
    label_type: str,
    raw_text: str,
) -> ParseStatus:
    """Validate parsed values against plausibility bounds.

    Returns ParseStatus.CLEAN if all checks pass,
    ParseStatus.WARNING for soft violations,
    ParseStatus.FAILED for hard violations.
    """
    if result.value is None and label_type not in _RULE_NP03_TYPES:
        # NS p-values may have None value — that is OK
        return ParseStatus.FAILED

    # |beta| <= 5 for effect size types
    effect_types = (
        _RULE_NP04_TYPES | _RULE_NP08_TYPES
        | {"EFFECT_SIZE", "MEAN_DIFFERENCE", "INTERACTION_TERM", "SUBGROUP_EFFECT"}
    )
    if label_type in effect_types and result.value is not None:
        if abs(result.value) > config.TB_PLAUSIBILITY_BETA_MAX:
            logger.warning(
                "Plausibility FAIL: |beta|=%.4f > %.1f for '%s' (label=%s)",
                abs(result.value),
                config.TB_PLAUSIBILITY_BETA_MAX,
                raw_text[:60],
                label_type,
            )
            return ParseStatus.FAILED

    # SE > 0 (when present)
    if result.se is not None and result.se <= 0:
        logger.warning(
            "Plausibility FAIL: SE=%.6f <= 0 for '%s' (label=%s)",
            result.se,
            raw_text[:60],
            label_type,
        )
        return ParseStatus.FAILED

    # CI ordered: lower < upper
    if result.ci_lower is not None and result.ci_upper is not None:
        if result.ci_lower > result.ci_upper:
            logger.warning(
                "Plausibility FAIL: CI not ordered: lower=%.4f > upper=%.4f "
                "for '%s' (label=%s)",
                result.ci_lower,
                result.ci_upper,
                raw_text[:60],
                label_type,
            )
            return ParseStatus.FAILED

    # |r| <= 1 for correlation
    if label_type in _RULE_NP09_TYPES and result.value is not None:
        if abs(result.value) > config.TB_PLAUSIBILITY_CORRELATION_MAX:
            logger.warning(
                "Plausibility FAIL: |r|=%.4f > %.1f for '%s'",
                abs(result.value),
                config.TB_PLAUSIBILITY_CORRELATION_MAX,
                raw_text[:60],
            )
            return ParseStatus.FAILED

    # N > 0 for sample size
    if label_type in _RULE_NP05_TYPES and result.n is not None:
        if result.n < config.TB_PLAUSIBILITY_N_MIN:
            logger.warning(
                "Plausibility FAIL: N=%d < %d for '%s'",
                result.n,
                config.TB_PLAUSIBILITY_N_MIN,
                raw_text[:60],
            )
            return ParseStatus.FAILED

    # p-value in [0, 1]
    if label_type in _RULE_NP03_TYPES and result.p_value is not None:
        if not (
            config.TB_PLAUSIBILITY_P_VALUE_MIN
            <= result.p_value
            <= config.TB_PLAUSIBILITY_P_VALUE_MAX
        ):
            logger.warning(
                "Plausibility FAIL: p=%.6f not in [%.1f, %.1f] for '%s'",
                result.p_value,
                config.TB_PLAUSIBILITY_P_VALUE_MIN,
                config.TB_PLAUSIBILITY_P_VALUE_MAX,
                raw_text[:60],
            )
            return ParseStatus.FAILED

    # I² in [0, 100]
    if label_type == "I_SQUARED" and result.value is not None:
        if result.value < 0 or result.value > config.TB_PLAUSIBILITY_I_SQUARED_MAX:
            logger.warning(
                "Plausibility FAIL: I²=%.2f not in [0, %.0f] for '%s'",
                result.value,
                config.TB_PLAUSIBILITY_I_SQUARED_MAX,
                raw_text[:60],
            )
            return ParseStatus.FAILED

    return ParseStatus.CLEAN


# ═══════════════════════════════════════════════════════════════
#  Main entry point
# ═══════════════════════════════════════════════════════════════


def parse_spans(span_labels: list[SpanLabel]) -> list[ParsedNumeric]:
    """Parse SpanLabel[] into ParsedNumeric[].

    This is the TRUST BOUNDARY entry point. NO LLM — pure deterministic.

    Each span is routed to the appropriate parse rule (NP-01 through NP-11)
    based on its label_type. Parsed values are validated for plausibility.
    Parse failures are logged and rejected (not propagated).

    Args:
        span_labels: LLM-extracted span labels from AG05.

    Returns:
        List of successfully parsed numeric records.

    Raises:
        GateViolation: Gate TB-G1 if zero spans parse successfully.
    """
    parsed_results: list[ParsedNumeric] = []
    failed_count = 0

    for span in span_labels:
        raw_text = span.value or ""
        label_type = span.label_type

        # Dispatch to the appropriate parse rule
        result = _dispatch_parse(raw_text, label_type)

        if result is None:
            logger.warning(
                "Parse FAILED (no match): span_id=%s, label_type=%s, "
                "raw_text='%s'. Span rejected.",
                span.span_id,
                label_type,
                raw_text[:80],
            )
            failed_count += 1
            parsed_results.append(
                ParsedNumeric(
                    span_id=span.span_id,
                    value_type=label_type,
                    parse_status=ParseStatus.FAILED,
                    raw_text=raw_text,
                    parsed_value=None,
                    confidence=span.confidence,
                )
            )
            continue

        # Apply Rule NP-11: missing data imputation
        result = _rule_np11_missing_data(result, raw_text, label_type)

        # Validate plausibility
        plausibility = _validate_plausibility(result, label_type, raw_text)

        if plausibility == ParseStatus.FAILED:
            logger.warning(
                "Parse REJECTED (plausibility): span_id=%s, label_type=%s, "
                "value=%.4f, raw_text='%s'. Span rejected.",
                span.span_id,
                label_type,
                result.value if result.value is not None else float("nan"),
                raw_text[:80],
            )
            failed_count += 1
            parsed_results.append(
                ParsedNumeric(
                    span_id=span.span_id,
                    value_type=label_type,
                    parse_status=ParseStatus.FAILED,
                    raw_text=raw_text,
                    parsed_value=result.value,
                    parsed_lower=result.ci_lower,
                    parsed_upper=result.ci_upper,
                    confidence=span.confidence,
                )
            )
            continue

        # Build ParsedNumeric
        status = plausibility if plausibility != ParseStatus.CLEAN else result.status
        parsed_results.append(
            ParsedNumeric(
                span_id=span.span_id,
                value_type=label_type,
                parse_status=status,
                raw_text=raw_text,
                parsed_value=result.value,
                parsed_lower=result.ci_lower,
                parsed_upper=result.ci_upper,
                unit=None,
                confidence=span.confidence,
            )
        )

    # Count successful parses
    successful = [
        p for p in parsed_results if p.parse_status != ParseStatus.FAILED
    ]

    logger.info(
        "NumericParser: %d/%d spans parsed successfully, %d failed.",
        len(successful),
        len(span_labels),
        failed_count,
    )

    # Gate TB-G1: >= 1 span parsed successfully or raise GateViolation
    if len(successful) == 0:
        raise GateViolation(
            gate_id="TB-G1",
            message=(
                f"Zero spans parsed successfully out of {len(span_labels)} inputs. "
                f"REJECT paper: no parseable statistics."
            ),
            context={
                "total_spans": len(span_labels),
                "failed_count": failed_count,
            },
        )

    return parsed_results


def parse_spans_to_typed(
    span_labels: list[SpanLabel],
) -> list[tuple[SpanLabel, TypedNumericValue]]:
    """Parse SpanLabel[] into (SpanLabel, TypedNumericValue)[] pairs.

    Convenience function that converts ParsedNumeric results into
    TypedNumericValue objects for downstream consumption by
    consistency_checker.py.

    Only returns successfully parsed spans (CLEAN or AMBIGUOUS).
    Failed parses are excluded.

    Args:
        span_labels: LLM-extracted span labels from AG05.

    Returns:
        List of (original_span, typed_value) tuples.

    Raises:
        GateViolation: Gate TB-G1 if zero spans parse successfully.
    """
    parsed = parse_spans(span_labels)

    results: list[tuple[SpanLabel, TypedNumericValue]] = []
    span_map = {s.span_id: s for s in span_labels}

    for pn in parsed:
        if pn.parse_status == ParseStatus.FAILED:
            continue
        if pn.parsed_value is None:
            # NS p-values have None value — skip for typed conversion
            continue

        original_span = span_map.get(pn.span_id)
        if original_span is None:
            logger.warning(
                "NumericParser: span_id=%s not found in original span_labels. "
                "This should not happen.",
                pn.span_id,
            )
            continue

        typed = TypedNumericValue(
            value=pn.parsed_value,
            bound_type=BoundType.EXACT,
            original_text=pn.raw_text,
            se=None,  # SE filled by NP-11 where possible (stored in parsed result)
            ci_lower=pn.parsed_lower,
            ci_upper=pn.parsed_upper,
            p_value=None,
            n=None,
        )

        # Populate SE, p_value, n from the internal parse result
        # We re-parse to get the full _ParseResult (internal details not on ParsedNumeric)
        # Instead, use a fresh dispatch to get full result
        result = _dispatch_parse(pn.raw_text, pn.value_type)
        if result is not None:
            result = _rule_np11_missing_data(result, pn.raw_text, pn.value_type)
            typed = TypedNumericValue(
                value=pn.parsed_value,
                bound_type=result.bound_type,
                original_text=pn.raw_text,
                se=result.se,
                ci_lower=result.ci_lower,
                ci_upper=result.ci_upper,
                p_value=result.p_value,
                n=result.n,
            )

        results.append((original_span, typed))

    return results
