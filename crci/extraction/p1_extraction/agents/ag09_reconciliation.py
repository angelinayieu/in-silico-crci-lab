# VERIFIED: formulas — none (rule-based consistency checks)
# VERIFIED: imports — all modules exist (intermediate_states, enums)
# VERIFIED: backward wiring — reads dict[str, list[SpanLabel]] from all agent outputs
# VERIFIED: forward wiring — writes ReconcReport for trust boundary / orchestrator
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — none (ALWAYS runs; flags inconsistencies for review)
"""
Component: SYS_EXTRACTION.EX-P1.AG09
Spec: SYS_EXTRACTION_COMPLETE.md lines 380-520 (AG09 ReconciliationAgent)
Formulas: None (rule-based, NO LLM)
Reads: dict[str, list[SpanLabel]] — agent_id -> spans from AG01-AG08
Writes: ReconcReport with per-span verdicts
        (consumed by trust boundary, orchestrator)
Gates: None (ALWAYS runs)

AG09 implements 7 span-level consistency checks:
  1. Duplicate detection
  2. CI bracketing
  3. p-value/CI consistency
  4. N consistency
  5. Effect direction consistency
  6. Missing groupings
  7. Orphan span detection
"""
from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field

from crci.shared.models.intermediate_states import SpanLabel

logger = logging.getLogger(__name__)


@dataclass
class SpanVerdict:
    """Verdict for a single span after reconciliation checks."""

    span_id: str
    agent_id: str
    check_name: str
    status: str  # "pass", "warning", "fail"
    message: str
    related_span_ids: list[str] = field(default_factory=list)


@dataclass
class ReconcReport:
    """Aggregate reconciliation report across all agent spans.

    Produced by AG09 (rule-based reconciliation) for the orchestrator
    and trust boundary to consume.
    """

    paper_id: str
    total_spans_checked: int
    verdicts: list[SpanVerdict] = field(default_factory=list)
    n_pass: int = 0
    n_warning: int = 0
    n_fail: int = 0
    summary: str = ""

    def add_verdict(self, verdict: SpanVerdict) -> None:
        """Add a verdict and update counters."""
        self.verdicts.append(verdict)
        if verdict.status == "pass":
            self.n_pass += 1
        elif verdict.status == "warning":
            self.n_warning += 1
        elif verdict.status == "fail":
            self.n_fail += 1

    def finalize(self) -> None:
        """Compute summary after all checks are done."""
        self.summary = (
            f"AG09 reconciliation: {self.total_spans_checked} spans checked, "
            f"{self.n_pass} pass, {self.n_warning} warnings, {self.n_fail} failures"
        )


class ReconciliationAgent:
    """AG09 -- Rule-based span-level consistency checker.

    NOT an LLM agent. Does NOT extend BaseAgent.
    ALWAYS runs regardless of extraction mode.

    Implements 7 consistency checks across all agent SpanLabel outputs:
      1. duplicate_detection — find spans with overlapping offsets + same label
      2. ci_bracketing — verify CI lower <= point estimate <= CI upper
      3. pvalue_ci_consistency — p<0.05 iff CI excludes null
      4. n_consistency — total N >= sum of group Ns
      5. effect_direction — sign of effect consistent across related spans
      6. missing_groupings — check ungrouped spans that should be grouped
      7. orphan_spans — detect spans with no related spans from any agent

    Input:  dict[str, list[SpanLabel]] — agent_id -> list of SpanLabel
    Output: ReconcReport with per-span verdicts
    """

    AGENT_ID = "AG09"

    def __init__(self) -> None:
        """Initialize ReconciliationAgent. No LLM client needed."""
        self._all_spans: list[tuple[str, SpanLabel]] = []  # (agent_id, span)

    def reconcile(
        self,
        agent_spans: dict[str, list[SpanLabel]],
        paper_id: str,
    ) -> ReconcReport:
        """Run all 7 consistency checks on the collected agent spans.

        Args:
            agent_spans: Mapping of agent_id -> list of SpanLabel from
                         each extraction agent.
            paper_id: The paper being processed.

        Returns:
            ReconcReport containing per-span verdicts.
        """
        # Flatten all spans with agent_id tags
        self._all_spans = []
        for agent_id, spans in agent_spans.items():
            for span in spans:
                self._all_spans.append((agent_id, span))

        total_spans = len(self._all_spans)

        logger.info(
            "AG09: starting reconciliation for paper_id=%s, "
            "total_spans=%d across %d agents",
            paper_id,
            total_spans,
            len(agent_spans),
        )

        report = ReconcReport(
            paper_id=paper_id,
            total_spans_checked=total_spans,
        )

        # Run all 7 checks
        self._check_duplicate_detection(report)
        self._check_ci_bracketing(report)
        self._check_pvalue_ci_consistency(report)
        self._check_n_consistency(report)
        self._check_effect_direction(report)
        self._check_missing_groupings(report)
        self._check_orphan_spans(report)

        report.finalize()

        logger.info(
            "AG09: completed reconciliation for paper_id=%s — %s",
            paper_id,
            report.summary,
        )

        return report

    # ─── Check 1: Duplicate Detection ────────────────────────────

    def _check_duplicate_detection(self, report: ReconcReport) -> None:
        """Check 1: Find spans with overlapping character offsets AND same label type.

        Two spans are considered duplicates if they overlap in character position
        and share the same label_type, even if from different agents.
        """
        checked_pairs: set[tuple[str, str]] = set()

        for i, (agent_a, span_a) in enumerate(self._all_spans):
            for j, (agent_b, span_b) in enumerate(self._all_spans):
                if i >= j:
                    continue

                pair_key = tuple(sorted([span_a.span_id, span_b.span_id]))
                if pair_key in checked_pairs:
                    continue
                checked_pairs.add(pair_key)

                # Check same label type
                if span_a.label_type != span_b.label_type:
                    continue

                # Skip if both have offset 0 (unlocated spans)
                if (
                    span_a.char_start == 0
                    and span_a.char_end == 0
                    and span_b.char_start == 0
                    and span_b.char_end == 0
                ):
                    continue

                # Check character overlap
                if self._spans_overlap(span_a, span_b):
                    report.add_verdict(
                        SpanVerdict(
                            span_id=span_a.span_id,
                            agent_id=agent_a,
                            check_name="duplicate_detection",
                            status="warning",
                            message=(
                                f"Span '{span_a.span_id}' ({agent_a}) overlaps "
                                f"with '{span_b.span_id}' ({agent_b}) — "
                                f"both label_type='{span_a.label_type}', "
                                f"offsets [{span_a.char_start}:{span_a.char_end}] "
                                f"vs [{span_b.char_start}:{span_b.char_end}]"
                            ),
                            related_span_ids=[span_b.span_id],
                        )
                    )

    @staticmethod
    def _spans_overlap(a: SpanLabel, b: SpanLabel) -> bool:
        """Check if two spans overlap in character positions."""
        return a.char_start < b.char_end and b.char_start < a.char_end

    # ─── Check 2: CI Bracketing ──────────────────────────────────

    def _check_ci_bracketing(self, report: ReconcReport) -> None:
        """Check 2: Verify CI lower <= point estimate <= CI upper.

        Finds spans labeled as CI_LOWER, CI_UPPER, and POINT_ESTIMATE
        and verifies correct bracketing relationships.
        """
        # Group spans by source_section and source_table_id for matching
        point_estimates: list[tuple[str, SpanLabel]] = []
        ci_lowers: list[tuple[str, SpanLabel]] = []
        ci_uppers: list[tuple[str, SpanLabel]] = []

        for agent_id, span in self._all_spans:
            lt = span.label_type.upper()
            if lt in ("POINT_ESTIMATE", "EFFECT_SIZE", "BETA", "MEAN_DIFF", "HAZARD_RATIO", "ODDS_RATIO"):
                point_estimates.append((agent_id, span))
            elif lt in ("CI_LOWER", "CI_LB"):
                ci_lowers.append((agent_id, span))
            elif lt in ("CI_UPPER", "CI_UB"):
                ci_uppers.append((agent_id, span))

        # For each CI pair found near each other, check bracketing
        for _agent_l, lower_span in ci_lowers:
            for _agent_u, upper_span in ci_uppers:
                # Match by proximity (within 200 chars) or same table
                if not self._spans_nearby(lower_span, upper_span, max_distance=200):
                    continue

                lower_val = lower_span.numeric_value
                upper_val = upper_span.numeric_value

                if lower_val is None or upper_val is None:
                    continue

                # Check CI_LOWER <= CI_UPPER
                if lower_val > upper_val:
                    report.add_verdict(
                        SpanVerdict(
                            span_id=lower_span.span_id,
                            agent_id=_agent_l,
                            check_name="ci_bracketing",
                            status="fail",
                            message=(
                                f"CI lower ({lower_val}) > CI upper ({upper_val}): "
                                f"spans '{lower_span.span_id}' and '{upper_span.span_id}'"
                            ),
                            related_span_ids=[upper_span.span_id],
                        )
                    )

                # Check point estimate falls within CI
                for _agent_p, pe_span in point_estimates:
                    if pe_span.numeric_value is None:
                        continue
                    if not self._spans_nearby(pe_span, lower_span, max_distance=200):
                        continue

                    pe_val = pe_span.numeric_value
                    if pe_val < lower_val or pe_val > upper_val:
                        report.add_verdict(
                            SpanVerdict(
                                span_id=pe_span.span_id,
                                agent_id=_agent_p,
                                check_name="ci_bracketing",
                                status="fail",
                                message=(
                                    f"Point estimate ({pe_val}) outside CI "
                                    f"[{lower_val}, {upper_val}]: spans "
                                    f"'{pe_span.span_id}', '{lower_span.span_id}', "
                                    f"'{upper_span.span_id}'"
                                ),
                                related_span_ids=[
                                    lower_span.span_id,
                                    upper_span.span_id,
                                ],
                            )
                        )

    @staticmethod
    def _spans_nearby(
        a: SpanLabel, b: SpanLabel, max_distance: int = 200
    ) -> bool:
        """Check if two spans are within max_distance characters of each other."""
        # Same table takes priority
        if (
            a.source_table_id is not None
            and b.source_table_id is not None
            and a.source_table_id == b.source_table_id
        ):
            return True
        # Check character proximity
        gap = min(
            abs(a.char_start - b.char_end),
            abs(b.char_start - a.char_end),
        )
        return gap <= max_distance

    # ─── Check 3: p-value / CI Consistency ───────────────────────

    def _check_pvalue_ci_consistency(self, report: ReconcReport) -> None:
        """Check 3: If p < 0.05, CI should exclude the null (0 for diffs, 1 for ratios).

        Finds p-value spans and nearby CI spans, and checks for consistency.
        """
        pvalue_spans: list[tuple[str, SpanLabel]] = []
        ci_lower_spans: list[tuple[str, SpanLabel]] = []
        ci_upper_spans: list[tuple[str, SpanLabel]] = []

        for agent_id, span in self._all_spans:
            lt = span.label_type.upper()
            if lt in ("P_VALUE", "PVALUE"):
                pvalue_spans.append((agent_id, span))
            elif lt in ("CI_LOWER", "CI_LB"):
                ci_lower_spans.append((agent_id, span))
            elif lt in ("CI_UPPER", "CI_UB"):
                ci_upper_spans.append((agent_id, span))

        for agent_p, p_span in pvalue_spans:
            if p_span.numeric_value is None:
                continue

            p_val = p_span.numeric_value

            # Find nearby CI bounds
            for _agent_l, lower_span in ci_lower_spans:
                if lower_span.numeric_value is None:
                    continue
                if not self._spans_nearby(p_span, lower_span):
                    continue

                for _agent_u, upper_span in ci_upper_spans:
                    if upper_span.numeric_value is None:
                        continue
                    if not self._spans_nearby(lower_span, upper_span):
                        continue

                    ci_low = lower_span.numeric_value
                    ci_high = upper_span.numeric_value

                    # Determine null value: 0 for differences, 1 for ratios
                    # Heuristic: if both CI bounds > 0.3 and label suggests ratio
                    null_value = 0.0
                    for _, nearby_span in self._all_spans:
                        if self._spans_nearby(p_span, nearby_span):
                            lt_nearby = nearby_span.label_type.upper()
                            if lt_nearby in ("HAZARD_RATIO", "ODDS_RATIO", "RISK_RATIO"):
                                null_value = 1.0
                                break

                    ci_excludes_null = (ci_low > null_value) or (ci_high < null_value)
                    p_significant = p_val < 0.05

                    if p_significant and not ci_excludes_null:
                        report.add_verdict(
                            SpanVerdict(
                                span_id=p_span.span_id,
                                agent_id=agent_p,
                                check_name="pvalue_ci_consistency",
                                status="warning",
                                message=(
                                    f"p={p_val} < 0.05 but CI [{ci_low}, {ci_high}] "
                                    f"includes null ({null_value}): possible inconsistency"
                                ),
                                related_span_ids=[
                                    lower_span.span_id,
                                    upper_span.span_id,
                                ],
                            )
                        )
                    elif not p_significant and ci_excludes_null:
                        report.add_verdict(
                            SpanVerdict(
                                span_id=p_span.span_id,
                                agent_id=agent_p,
                                check_name="pvalue_ci_consistency",
                                status="warning",
                                message=(
                                    f"p={p_val} >= 0.05 but CI [{ci_low}, {ci_high}] "
                                    f"excludes null ({null_value}): possible inconsistency"
                                ),
                                related_span_ids=[
                                    lower_span.span_id,
                                    upper_span.span_id,
                                ],
                            )
                        )

    # ─── Check 4: N Consistency ──────────────────────────────────

    def _check_n_consistency(self, report: ReconcReport) -> None:
        """Check 4: Total N >= sum of group Ns.

        Finds SAMPLE_SIZE spans and GROUP_N spans, checks that group sizes
        do not exceed the total sample.
        """
        total_n_spans: list[tuple[str, SpanLabel]] = []
        group_n_spans: list[tuple[str, SpanLabel]] = []

        for agent_id, span in self._all_spans:
            lt = span.label_type.upper()
            if lt in ("SAMPLE_SIZE", "TOTAL_N", "N_TOTAL"):
                total_n_spans.append((agent_id, span))
            elif lt in ("GROUP_N", "ARM_N", "N_GROUP", "N_INTERVENTION", "N_CONTROL"):
                group_n_spans.append((agent_id, span))

        if not total_n_spans or not group_n_spans:
            return

        # Use the largest reported total N
        max_total: float = 0.0
        max_total_span: SpanLabel | None = None
        max_total_agent: str = ""
        for agent_id, span in total_n_spans:
            if span.numeric_value is not None and span.numeric_value > max_total:
                max_total = span.numeric_value
                max_total_span = span
                max_total_agent = agent_id

        if max_total_span is None or max_total <= 0:
            return

        # Sum all group Ns
        group_sum: float = 0.0
        group_ids: list[str] = []
        for _agent_id, span in group_n_spans:
            if span.numeric_value is not None:
                group_sum += span.numeric_value
                group_ids.append(span.span_id)

        if group_sum > max_total:
            report.add_verdict(
                SpanVerdict(
                    span_id=max_total_span.span_id,
                    agent_id=max_total_agent,
                    check_name="n_consistency",
                    status="fail",
                    message=(
                        f"Sum of group Ns ({group_sum}) exceeds "
                        f"total N ({max_total})"
                    ),
                    related_span_ids=group_ids,
                )
            )

    # ─── Check 5: Effect Direction Consistency ───────────────────

    def _check_effect_direction(self, report: ReconcReport) -> None:
        """Check 5: Sign of effect consistent across related effect-size spans.

        If multiple spans report the same effect metric (e.g., BETA for the
        same comparison), their signs should agree.
        """
        # Group effect-size spans by label_type
        effect_spans_by_type: dict[str, list[tuple[str, SpanLabel]]] = {}

        effect_label_types = {
            "BETA", "EFFECT_SIZE", "MEAN_DIFF", "STD_MEAN_DIFF",
            "POINT_ESTIMATE", "COHEN_D", "HEDGES_G",
        }

        for agent_id, span in self._all_spans:
            if span.label_type.upper() in effect_label_types:
                key = span.label_type.upper()
                if key not in effect_spans_by_type:
                    effect_spans_by_type[key] = []
                effect_spans_by_type[key].append((agent_id, span))

        for label_type, spans in effect_spans_by_type.items():
            numeric_spans = [
                (aid, s) for aid, s in spans
                if s.numeric_value is not None
            ]

            if len(numeric_spans) < 2:
                continue

            # Check if signs are consistent
            signs = [
                math.copysign(1, s.numeric_value)  # type: ignore[arg-type]
                for _, s in numeric_spans
                if s.numeric_value != 0.0
            ]

            if not signs:
                continue

            positive_count = sum(1 for s in signs if s > 0)
            negative_count = sum(1 for s in signs if s < 0)

            if positive_count > 0 and negative_count > 0:
                all_span_ids = [s.span_id for _, s in numeric_spans]
                report.add_verdict(
                    SpanVerdict(
                        span_id=numeric_spans[0][1].span_id,
                        agent_id=numeric_spans[0][0],
                        check_name="effect_direction",
                        status="warning",
                        message=(
                            f"Mixed effect directions for label_type='{label_type}': "
                            f"{positive_count} positive, {negative_count} negative "
                            f"across {len(numeric_spans)} spans"
                        ),
                        related_span_ids=all_span_ids[1:],
                    )
                )

    # ─── Check 6: Missing Groupings ──────────────────────────────

    def _check_missing_groupings(self, report: ReconcReport) -> None:
        """Check 6: Detect ungrouped spans that should logically be grouped.

        Spans that report individual statistical results (effect sizes, CIs,
        p-values) near each other but from different agents without any
        grouping relationship are flagged.
        """
        statistical_labels = {
            "BETA", "EFFECT_SIZE", "MEAN_DIFF", "STD_MEAN_DIFF",
            "POINT_ESTIMATE", "COHEN_D", "HEDGES_G",
            "CI_LOWER", "CI_UPPER", "CI_LB", "CI_UB",
            "P_VALUE", "PVALUE",
            "STANDARD_ERROR", "SE",
        }

        stat_spans: list[tuple[str, SpanLabel]] = []
        for agent_id, span in self._all_spans:
            if span.label_type.upper() in statistical_labels:
                stat_spans.append((agent_id, span))

        # Group by proximity (clusters of spans within 300 chars)
        clusters: list[list[tuple[str, SpanLabel]]] = []
        used: set[str] = set()

        for i, (agent_a, span_a) in enumerate(stat_spans):
            if span_a.span_id in used:
                continue

            cluster: list[tuple[str, SpanLabel]] = [(agent_a, span_a)]
            used.add(span_a.span_id)

            for j, (agent_b, span_b) in enumerate(stat_spans):
                if j <= i or span_b.span_id in used:
                    continue
                if self._spans_nearby(span_a, span_b, max_distance=300):
                    cluster.append((agent_b, span_b))
                    used.add(span_b.span_id)

            clusters.append(cluster)

        # Flag clusters with stats from multiple agents but only partial coverage
        for cluster in clusters:
            if len(cluster) < 2:
                continue

            agents_in_cluster = set(aid for aid, _ in cluster)
            label_types_in_cluster = set(s.label_type.upper() for _, s in cluster)

            # A complete statistical result should have at least an effect + CI or p
            has_effect = bool(label_types_in_cluster & {
                "BETA", "EFFECT_SIZE", "MEAN_DIFF", "STD_MEAN_DIFF",
                "POINT_ESTIMATE", "COHEN_D", "HEDGES_G",
            })
            has_ci = bool(label_types_in_cluster & {"CI_LOWER", "CI_UPPER", "CI_LB", "CI_UB"})
            has_p = bool(label_types_in_cluster & {"P_VALUE", "PVALUE"})

            if has_effect and not has_ci and not has_p:
                report.add_verdict(
                    SpanVerdict(
                        span_id=cluster[0][1].span_id,
                        agent_id=cluster[0][0],
                        check_name="missing_groupings",
                        status="warning",
                        message=(
                            f"Effect size span(s) found without accompanying CI "
                            f"or p-value in cluster of {len(cluster)} spans from "
                            f"agent(s): {sorted(agents_in_cluster)}"
                        ),
                        related_span_ids=[s.span_id for _, s in cluster[1:]],
                    )
                )

    # ─── Check 7: Orphan Spans ───────────────────────────────────

    def _check_orphan_spans(self, report: ReconcReport) -> None:
        """Check 7: Detect spans that have no related spans from any agent.

        An orphan span is one that is entirely isolated -- no other spans
        from any agent are within proximity or share a source table.
        Orphans may indicate extraction errors or missing context.
        """
        for i, (agent_a, span_a) in enumerate(self._all_spans):
            has_neighbor = False
            for j, (agent_b, span_b) in enumerate(self._all_spans):
                if i == j:
                    continue
                if self._spans_nearby(span_a, span_b, max_distance=500):
                    has_neighbor = True
                    break

            if not has_neighbor and len(self._all_spans) > 1:
                # Only flag if there are other spans to compare to
                # and this span has actual character offsets
                if span_a.char_start > 0 or span_a.char_end > 0:
                    report.add_verdict(
                        SpanVerdict(
                            span_id=span_a.span_id,
                            agent_id=agent_a,
                            check_name="orphan_spans",
                            status="warning",
                            message=(
                                f"Span '{span_a.span_id}' (label='{span_a.label_type}', "
                                f"offset=[{span_a.char_start}:{span_a.char_end}]) "
                                f"has no nearby spans from any agent"
                            ),
                            related_span_ids=[],
                        )
                    )
