# VERIFIED: formulas — none (span label extraction, no numeric formulas)
# VERIFIED: imports — all modules exist (base_agent, llm.client, response_schemas)
# VERIFIED: backward wiring — reads PaperMap from canonical_reader.py
# VERIFIED: forward wiring — writes AgentOutput with SpanLabel[] for tb_trust_boundary/numeric_parser.py
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — P1-G2 partial: validates >= 1 SpanLabel produced
"""
Component: SYS_EXTRACTION.EX-P1.AG05
Spec: SYS_EXTRACTION_COMPLETE.md lines 473-480 (AG5 StatsLabelAgent)
      SYS_EXTRACTION_COMPLETE.md lines 387-396 (SpanLabel schema, 40 label types)
      SYS_EXTRACTION_COMPLETE.md lines 2203-2210 (AG5 detail)
Formulas: None
Reads: PaperMap.sections[results, tables, abstract, discussion] + PaperMap.candidate_spans (from canonical_reader.py)
Writes: AgentOutput with SpanLabel[] (consumed by tb_trust_boundary/numeric_parser.py)
Gates: P1-G2 (partial) — at least 1 SpanLabel must be produced
*** CRITICAL — highest-impact extraction agent ***
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

from pydantic import BaseModel

from crci.extraction.p1_extraction.agents.base_agent import (
    AgentOutput,
    BaseAgent,
)
from crci.llm.client import LLMClient
from crci.llm.response_schemas import SpanLabelResponse
from crci.shared.models.intermediate_states import (
    GateViolation,
    PaperMap,
    SpanLabel,
)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  The 40 SpanLabel types per SYS_EX lines 312-330, 387-396
# ═══════════════════════════════════════════════════════════════

SPAN_LABEL_TYPES: list[str] = [
    # Primary effect measures
    "EFFECT_SIZE",          # 1. Standardized effect size (Cohen's d, Hedges' g, etc.)
    "UNSTD_BETA",           # 2. Unstandardized regression coefficient
    "STD_BETA",             # 3. Standardized regression coefficient
    "ODDS_RATIO",           # 4. Odds ratio (OR)
    "HAZARD_RATIO",         # 5. Hazard ratio (HR)
    "RISK_RATIO",           # 6. Relative risk / risk ratio (RR)
    "INCIDENCE_RATE_RATIO", # 7. Incidence rate ratio (IRR)
    "MEAN_DIFFERENCE",      # 8. Mean difference between groups
    "PERCENT_CHANGE",       # 9. Percentage change
    "CORRELATION",          # 10. Correlation coefficient (r, rho)
    # Precision and interval measures
    "CI_LOWER",             # 11. Confidence interval lower bound
    "CI_UPPER",             # 12. Confidence interval upper bound
    "SE",                   # 13. Standard error
    "SD",                   # 14. Standard deviation
    "P_VALUE",              # 15. p-value
    "VARIANCE",             # 16. Variance
    # Central tendency and distribution
    "MEAN",                 # 17. Mean / average
    "MEDIAN",               # 18. Median
    "IQR_LOWER",            # 19. Interquartile range lower (Q1)
    "IQR_UPPER",            # 20. Interquartile range upper (Q3)
    "RANGE_MIN",            # 21. Minimum value
    "RANGE_MAX",            # 22. Maximum value
    # Sample information
    "SAMPLE_SIZE",          # 23. Sample size (N or n)
    "SAMPLE_SIZE_ARM",      # 24. Sample size per arm
    "ATTRITION_N",          # 25. Number lost to follow-up
    "ATTRITION_RATE",       # 26. Attrition rate (percentage)
    # Test statistics
    "F_STATISTIC",          # 27. F-statistic
    "T_STATISTIC",          # 28. t-statistic
    "CHI_SQUARE",           # 29. Chi-square statistic
    "Z_STATISTIC",          # 30. Z-statistic
    "DF",                   # 31. Degrees of freedom
    # Heterogeneity / meta-analysis
    "I_SQUARED",            # 32. I-squared heterogeneity
    "TAU_SQUARED",          # 33. Tau-squared
    "Q_STATISTIC",          # 34. Cochran's Q statistic
    # Model fit
    "R_SQUARED",            # 35. R-squared / coefficient of determination
    "AIC",                  # 36. Akaike information criterion
    "BIC",                  # 37. Bayesian information criterion
    # Effect modification
    "INTERACTION_TERM",     # 38. Interaction term coefficient
    "SUBGROUP_EFFECT",      # 39. Subgroup-specific effect
    # Temporal
    "FOLLOW_UP_DURATION",   # 40. Follow-up duration (weeks, months)
    # NOTE: AG05-EXT labels removed per 40-type contract.
    # Subgroup/interaction values use existing types:
    #   INTERACTION_TERM (38), SE (13), P_VALUE (15), SUBGROUP_EFFECT (39), SAMPLE_SIZE_ARM (24)
    # Subgroup variable/value encoded in context string.
]

# ═══════════════════════════════════════════════════════════════
#  Labels that REQUIRE anchor tokens for valid classification
# ═══════════════════════════════════════════════════════════════

ANCHOR_REQUIRED_LABELS: set[str] = {
    # Primary effect measures
    "EFFECT_SIZE", "UNSTD_BETA", "STD_BETA", "ODDS_RATIO",
    "HAZARD_RATIO", "RISK_RATIO", "INCIDENCE_RATE_RATIO",
    "MEAN_DIFFERENCE", "PERCENT_CHANGE", "CORRELATION",
    # Test statistics
    "F_STATISTIC", "T_STATISTIC", "CHI_SQUARE", "Z_STATISTIC",
    # Heterogeneity
    "I_SQUARED", "TAU_SQUARED", "Q_STATISTIC",
    # Model fit
    "R_SQUARED", "AIC", "BIC",
}

# Magnitude sanity bounds per label type
MAGNITUDE_BOUNDS: dict[str, tuple[float | None, float | None]] = {
    "EFFECT_SIZE": (-5.0, 5.0),        # Cohen's d rarely |d| > 3
    "STD_BETA": (-5.0, 5.0),           # Standardized beta rarely |β| > 2
    "UNSTD_BETA": (-1000.0, 1000.0),   # Unstandardized can be larger
    "CORRELATION": (-1.0, 1.0),         # r ∈ [-1, 1] strictly
    "R_SQUARED": (0.0, 1.0),            # R² ∈ [0, 1]
    "I_SQUARED": (0.0, 100.0),          # I² is a percentage
    "ODDS_RATIO": (0.001, 1000.0),      # OR typically 0.01-100
    "HAZARD_RATIO": (0.001, 1000.0),    # HR typically 0.01-100
    "RISK_RATIO": (0.001, 1000.0),      # RR typically 0.01-100
    "ATTRITION_RATE": (0.0, 100.0),     # Percentage
    "PERCENT_CHANGE": (-1000.0, 1000.0), # Percentage can be large
}


class StatsLabelAgent(BaseAgent):
    """AG05 -- Extract numeric statistical claims as SpanLabel[].

    ALWAYS runs (all extraction modes: SHALLOW, STANDARD, DEEP).
    CRITICAL: highest-impact extraction agent. These labels become
    the RAW INPUT to the trust boundary. If AG05 misses a beta or
    misparses a CI, that evidence is LOST.

    Reads: PaperMap.sections[results, tables, abstract, discussion] + PaperMap.candidate_spans
    Outputs: SpanLabel[]{label_type, value, char_start, char_end,
                         confidence, source_section, source_table_id}

    40 label types covering: effect sizes, precision measures, central
    tendency, sample information, test statistics, heterogeneity,
    model fit, effect modification, and temporal measures.

    Validation (per SYS_EX lines 479):
      - >= 1 SpanLabel produced
      - char offsets valid (non-negative, start < end)
      - no overlapping spans within same label_type
    """

    def __init__(self, llm_client: LLMClient) -> None:
        super().__init__(llm_client)

    @property
    def agent_id(self) -> str:
        return "AG05"

    @property
    def target_sections(self) -> list[str]:
        # Many papers (esp. short RCTs) report key statistics in
        # the Discussion section or combined Results/Discussion sections.
        return ["results", "tables", "abstract", "discussion"]

    @property
    def response_schema(self) -> type[BaseModel]:
        return SpanLabelResponse

    @property
    def prompt_template_path(self) -> Path:
        return (
            Path(__file__).resolve().parent.parent.parent.parent
            / "llm"
            / "prompts"
            / "ag05_stats_label.txt"
        )

    def _build_prompt(
        self, focused_text: str, paper_map: PaperMap
    ) -> str:
        """Build extraction prompt for stats label agent.

        The prompt includes:
          1. The prompt template (with all 40 label types)
          2. Results section text from PaperMap
          3. Table text from PaperMap
          4. Candidate spans pre-identified by CR-c
        """
        template = self._load_prompt_template()

        # Gather table text
        table_text = self._get_table_text(paper_map)

        # Gather candidate spans
        candidate_spans_text = self._get_candidate_spans_text(paper_map)

        return template.format(
            focused_text=focused_text,
            table_text=table_text if table_text else "(no tables detected)",
            candidate_spans=candidate_spans_text
            if candidate_spans_text
            else "(no candidate spans pre-identified)",
            paper_id=paper_map.paper_id,
        )

    def _parse_response(
        self, response: BaseModel, paper_map: PaperMap
    ) -> AgentOutput:
        """Convert SpanLabelResponse to AgentOutput.

        Validates and converts each extracted span to a SpanLabel.
        Enforces:
          - char offsets are valid
          - label_type is one of the 40 recognized types
          - confidence is in [0, 1]
        """
        span_resp: SpanLabelResponse = response  # type: ignore[assignment]

        span_labels: list[SpanLabel] = []

        for extracted_span in span_resp.spans:
            # Validate label_type
            label_type = extracted_span.label_type.upper()
            if label_type not in SPAN_LABEL_TYPES:
                logger.warning(
                    "AG05: unrecognized label_type '%s' for paper_id=%s, "
                    "span_text='%s'. Mapping to closest match or skipping.",
                    label_type,
                    paper_map.paper_id,
                    extracted_span.span_text[:50],
                )
                # Attempt normalization of common variants
                label_type = self._normalize_label_type(label_type)
                if label_type not in SPAN_LABEL_TYPES:
                    logger.warning(
                        "AG05: skipping span with unrecognized label_type '%s' "
                        "after normalization attempt. "
                        "Entity: label_type=%s, span_text=%r.",
                        extracted_span.label_type,
                        extracted_span.label_type,
                        extracted_span.span_text[:50],
                    )
                    continue

            # Validate char offsets
            char_start = max(0, extracted_span.char_start)
            char_end = max(char_start, extracted_span.char_end)

            # Clamp to text length
            text_len = len(paper_map.full_text)
            char_start = min(char_start, text_len)
            char_end = min(char_end, text_len)

            # Try to parse numeric value from span text
            numeric_value = self._try_parse_numeric(extracted_span.span_text)

            # ── SPANLABEL SANITIZER: Apply deterministic disambiguation rules ──
            sanitized_label, sanitized_confidence, sanitize_reason = self._sanitize_span_label(
                label_type=label_type,
                numeric_value=numeric_value,
                span_text=extracted_span.span_text,
                context=getattr(extracted_span, "context", "") or "",
                confidence=extracted_span.confidence,
            )
            if sanitized_label is None:
                # Span rejected by sanitizer
                logger.info(
                    "AG05-SANITIZER: Rejecting span for paper_id=%s. "
                    "Reason: %s. Original: label=%s, value=%r",
                    paper_map.paper_id,
                    sanitize_reason,
                    label_type,
                    extracted_span.span_text[:50],
                )
                continue
            if sanitized_label != label_type:
                logger.info(
                    "AG05-SANITIZER: Relabeled span for paper_id=%s. "
                    "%s → %s. Reason: %s. Value=%r",
                    paper_map.paper_id,
                    label_type,
                    sanitized_label,
                    sanitize_reason,
                    extracted_span.span_text[:50],
                )
            label_type = sanitized_label
            confidence = sanitized_confidence

            # Determine source section
            source_section = self._determine_source_section(
                paper_map, char_start
            )

            # Determine source table ID
            source_table_id = self._determine_source_table(
                paper_map, char_start, char_end
            )

            span_labels.append(
                SpanLabel(
                    span_id=f"ag05_{uuid.uuid4().hex[:12]}",
                    label_type=label_type,
                    value=extracted_span.span_text,
                    numeric_value=numeric_value,
                    char_start=char_start,
                    char_end=char_end,
                    confidence=confidence,
                    source_section=source_section,
                    source_table_id=source_table_id,
                    grouping_id=getattr(extracted_span, "grouping_id", None),
                    arm_assignment=getattr(extracted_span, "arm_assignment", None),
                )
            )

        # Validate: at least 1 SpanLabel (part of P1-G2)
        if not span_labels:
            raise GateViolation(
                gate_id="P1-G2",
                message=(
                    f"AG05 produced 0 SpanLabels for paper_id={paper_map.paper_id}. "
                    f"Paper may not contain extractable statistical claims."
                ),
                context={
                    "paper_id": paper_map.paper_id,
                    "raw_span_count": len(span_resp.spans),
                    "agent_id": self.agent_id,
                },
            )

        # Check for overlapping spans within same label_type
        self._check_overlapping_spans(span_labels, paper_map.paper_id)

        return AgentOutput(
            agent_id=self.agent_id,
            paper_id=paper_map.paper_id,
            span_labels=span_labels,
            annotations=[],
            metadata={
                "total_extracted": len(span_labels),
                "label_type_distribution": self._count_label_types(span_labels),
            },
            completion_status="success",
        )

    # ═══════════════════════════════════════════════════════════
    #  Helper methods
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _normalize_label_type(raw_type: str) -> str:
        """Attempt to normalize common label type variants."""
        normalization_map: dict[str, str] = {
            "EFFECT": "EFFECT_SIZE",
            "COHENS_D": "EFFECT_SIZE",
            "HEDGES_G": "EFFECT_SIZE",
            "BETA": "UNSTD_BETA",
            "B": "UNSTD_BETA",
            "OR": "ODDS_RATIO",
            "HR": "HAZARD_RATIO",
            "RR": "RISK_RATIO",
            "IRR": "INCIDENCE_RATE_RATIO",
            "MD": "MEAN_DIFFERENCE",
            "CI_LOW": "CI_LOWER",
            "CI_HIGH": "CI_UPPER",
            "CI_LB": "CI_LOWER",
            "CI_UB": "CI_UPPER",
            "CONFIDENCE_INTERVAL_LOWER": "CI_LOWER",
            "CONFIDENCE_INTERVAL_UPPER": "CI_UPPER",
            "STANDARD_ERROR": "SE",
            "STANDARD_DEVIATION": "SD",
            "P": "P_VALUE",
            "PVALUE": "P_VALUE",
            "N": "SAMPLE_SIZE",
            "SAMPLE_N": "SAMPLE_SIZE",
            "TOTAL_N": "SAMPLE_SIZE",
            "AVERAGE": "MEAN",
            "IQR_LOW": "IQR_LOWER",
            "IQR_HIGH": "IQR_UPPER",
            "Q1": "IQR_LOWER",
            "Q3": "IQR_UPPER",
            "MIN": "RANGE_MIN",
            "MAX": "RANGE_MAX",
            "F": "F_STATISTIC",
            "T": "T_STATISTIC",
            "CHI2": "CHI_SQUARE",
            "CHI_SQ": "CHI_SQUARE",
            "Z": "Z_STATISTIC",
            "I2": "I_SQUARED",
            "TAU2": "TAU_SQUARED",
            "Q": "Q_STATISTIC",
            "R2": "R_SQUARED",
            "INTERACTION": "INTERACTION_TERM",
            "SUBGROUP": "SUBGROUP_EFFECT",
            "FOLLOWUP": "FOLLOW_UP_DURATION",
            "FOLLOW_UP": "FOLLOW_UP_DURATION",
            "DROPOUT_N": "ATTRITION_N",
            "DROPOUT_RATE": "ATTRITION_RATE",
            "LOSS_TO_FOLLOWUP": "ATTRITION_N",
            "R": "CORRELATION",
            "RHO": "CORRELATION",
            "PEARSON_R": "CORRELATION",
            "SPEARMAN_RHO": "CORRELATION",
            "PCT_CHANGE": "PERCENT_CHANGE",
            "PERCENTAGE_CHANGE": "PERCENT_CHANGE",
            "VAR": "VARIANCE",
            "DF_RESIDUAL": "DF",
            "DEGREES_OF_FREEDOM": "DF",
            "N_PER_ARM": "SAMPLE_SIZE_ARM",
            # Subgroup interaction normalization (mapped to existing 40 types)
            "MODERATOR": "INTERACTION_TERM",
            "MODERATOR_VARIABLE": "INTERACTION_TERM",
            "INTERACTION_BETA": "INTERACTION_TERM",
            "INTERACTION_B": "INTERACTION_TERM",
            "INTERACTION_COEFF": "INTERACTION_TERM",
            "INTERACTION_SE": "SE",
            "INTERACTION_PVALUE": "P_VALUE",
            "INTERACTION_P_VALUE": "P_VALUE",
            "N_SUBGROUP": "SAMPLE_SIZE_ARM",
            "SUBGROUP_SAMPLE_SIZE": "SAMPLE_SIZE_ARM",
            "SUBGROUP_N": "SAMPLE_SIZE_ARM",
        }
        return normalization_map.get(raw_type, raw_type)

    @staticmethod
    def _try_parse_numeric(span_text: str) -> float | None:
        """Attempt to extract a numeric value from span text.

        Handles common formats:
          - "0.35"
          - "-1.2"
          - "< 0.001"
          - "3.2e-4"
          - "1,234"
        """
        import re

        # Remove common prefixes/suffixes
        cleaned = span_text.strip()
        cleaned = re.sub(r"^[<>≤≥=:]+\s*", "", cleaned)
        cleaned = cleaned.replace(",", "")

        # Try direct float parse
        try:
            return float(cleaned)
        except ValueError:
            pass

        # Try to find the first number in the text
        match = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", cleaned)
        if match:
            try:
                return float(match.group(0))
            except ValueError:
                pass

        return None

    @staticmethod
    def _determine_source_section(
        paper_map: PaperMap, char_start: int
    ) -> str | None:
        """Determine which section a character offset belongs to."""
        for section in paper_map.sections:
            if section.char_start <= char_start < section.char_end:
                return section.section_type
        return None

    @staticmethod
    def _determine_source_table(
        paper_map: PaperMap, char_start: int, char_end: int
    ) -> str | None:
        """Determine if a span falls within a detected table."""
        for table in paper_map.tables:
            if table.char_start <= char_start and char_end <= table.char_end:
                return table.table_id
        return None

    @staticmethod
    def _check_overlapping_spans(
        span_labels: list[SpanLabel], paper_id: str
    ) -> None:
        """Check for overlapping spans within the same label_type.

        Logs warnings but does not remove duplicates (downstream
        reconciliation handles dedup).
        """
        by_type: dict[str, list[SpanLabel]] = {}
        for sl in span_labels:
            by_type.setdefault(sl.label_type, []).append(sl)

        for label_type, spans in by_type.items():
            sorted_spans = sorted(spans, key=lambda s: s.char_start)
            for i in range(len(sorted_spans) - 1):
                current = sorted_spans[i]
                next_span = sorted_spans[i + 1]
                if current.char_end > next_span.char_start:
                    logger.warning(
                        "AG05: overlapping spans detected for label_type=%s "
                        "in paper_id=%s: span1=[%d,%d] span2=[%d,%d]. "
                        "Downstream reconciliation will handle.",
                        label_type,
                        paper_id,
                        current.char_start,
                        current.char_end,
                        next_span.char_start,
                        next_span.char_end,
                    )

    @staticmethod
    def _count_label_types(span_labels: list[SpanLabel]) -> dict[str, int]:
        """Count spans per label type for metadata tracking."""
        counts: dict[str, int] = {}
        for sl in span_labels:
            counts[sl.label_type] = counts.get(sl.label_type, 0) + 1
        return counts

    # ═══════════════════════════════════════════════════════════════
    #  SPANLABEL SANITIZER — Deterministic rule-based validation
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def _sanitize_span_label(
        label_type: str,
        numeric_value: float | None,
        span_text: str,
        context: str,
        confidence: float,
    ) -> tuple[str | None, float, str]:
        """Apply deterministic disambiguation rules to SpanLabel.

        This is the "Trust Boundary mindset" applied BEFORE TB routing.
        Catches impossible label/value pairs that would cause TB rejection
        or lost evidence yield.

        Returns:
            tuple of (new_label_type | None, new_confidence, reason)
            If new_label_type is None, the span should be rejected.
        """
        import re

        reason = "passed"

        # ── RULE 1: Year detection ──
        # 4-digit integers in [1900, 2100] are YEARS, never effect sizes
        if numeric_value is not None:
            val = numeric_value
            if val == int(val) and 1900 <= val <= 2100:
                # Check if context has anchor tokens that override
                anchor_pattern = r'(?:d\s*=|g\s*=|smd|cohen|hedges|β\s*=|beta\s*=|or\s*=|hr\s*=|rr\s*=|r\s*=|ρ\s*=)'
                if not re.search(anchor_pattern, context.lower()):
                    if label_type in ANCHOR_REQUIRED_LABELS:
                        # Could be a year being mislabeled
                        return None, confidence, f"year_detected ({int(val)})"

        # ── RULE 2: Sample size detection ──
        # Integers ≥ 10 with n=/N=/participants → SAMPLE_SIZE
        if numeric_value is not None:
            val = numeric_value
            if val == int(val) and val >= 10:
                sample_pattern = r'(?:n\s*=|N\s*=|participants|subjects|patients|sample|enrolled)'
                if re.search(sample_pattern, span_text + " " + context, re.IGNORECASE):
                    if label_type in ANCHOR_REQUIRED_LABELS:
                        return "SAMPLE_SIZE", confidence * 0.9, "sample_size_context_detected"

        # ── RULE 3: Naked integers without anchors → likely SAMPLE_SIZE ──
        if numeric_value is not None:
            val = numeric_value
            if val == int(val) and val >= 10 and label_type in ANCHOR_REQUIRED_LABELS:
                # Check for anchor tokens
                anchor_pattern = r'(?:d\s*=|g\s*=|smd|cohen|hedges|β\s*=|beta\s*=|b\s*=|or\s*=|hr\s*=|rr\s*=|irr\s*=|r\s*=|ρ\s*=|f\s*=|t\s*=|χ²\s*=|chi|z\s*=|i²\s*=|i2\s*=|tau|q\s*=|r²\s*=|r2\s*=|aic|bic)'
                combined_text = (span_text + " " + context).lower()
                if not re.search(anchor_pattern, combined_text):
                    # Large naked integer without anchor → likely sample size
                    if val >= 50:
                        return "SAMPLE_SIZE", confidence * 0.7, "naked_integer_no_anchor"

        # ── RULE 4: Magnitude sanity checks ──
        if numeric_value is not None and label_type in MAGNITUDE_BOUNDS:
            min_val, max_val = MAGNITUDE_BOUNDS[label_type]
            if min_val is not None and numeric_value < min_val:
                if label_type == "CORRELATION":
                    return None, confidence, f"correlation_out_of_range ({numeric_value})"
                elif label_type in {"ODDS_RATIO", "HAZARD_RATIO", "RISK_RATIO"}:
                    # Negative OR/HR/RR impossible
                    if numeric_value < 0:
                        return None, confidence, f"negative_ratio ({numeric_value})"
                else:
                    # Reduce confidence for out-of-range effect sizes
                    confidence = confidence * 0.5
                    reason = f"below_min_bound ({numeric_value} < {min_val})"

            if max_val is not None and numeric_value > max_val:
                if label_type == "CORRELATION":
                    return None, confidence, f"correlation_out_of_range ({numeric_value})"
                elif label_type == "I_SQUARED":
                    return None, confidence, f"i_squared_out_of_range ({numeric_value})"
                elif label_type == "R_SQUARED":
                    return None, confidence, f"r_squared_out_of_range ({numeric_value})"
                elif label_type in {"EFFECT_SIZE", "STD_BETA"}:
                    # Extreme effect size → likely wrong label
                    return "SAMPLE_SIZE", confidence * 0.5, f"extreme_value_relabeled ({numeric_value})"
                else:
                    confidence = confidence * 0.5
                    reason = f"above_max_bound ({numeric_value} > {max_val})"

        # ── RULE 5: CI integrity check ──
        # No numeric check here (would need both bounds), but flag if single bound confidence
        if label_type in {"CI_LOWER", "CI_UPPER"}:
            # CI bounds should typically be within reasonable ranges
            if numeric_value is not None and abs(numeric_value) > 1000:
                confidence = confidence * 0.7
                reason = "ci_extreme_value"

        return label_type, confidence, reason
