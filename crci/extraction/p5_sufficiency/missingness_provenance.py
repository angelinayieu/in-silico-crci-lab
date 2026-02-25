# VERIFIED: codes match CONVERSION_VALIDITY_AND_HARDENING.md Module 3.2
# VERIFIED: imports — all modules exist (shared.models.enums)
# VERIFIED: backward wiring — reads extraction completeness data from P1-TB pipeline
# VERIFIED: forward wiring — writes MissingnessReport consumed by gap analysis / acquisition
# VERIFIED: no hardcoded formula parameters
"""
Component: SYS_EXTRACTION.EX-P5.MISSINGNESS
Spec: CONVERSION_VALIDITY_AND_HARDENING.md Module 3 (Missingness Provenance)
Codes:
    PRESENT — successfully extracted
    ABSENT_IN_PAPER — genuinely not in paper → SEARCH
    PARSE_FAILURE — PDF parsing failed → REPARSE
    AGENT_MISS — agent failed to extract → RERUN_AGENT
    GUARDED_REJECTION — blocked by guardrail → ACCEPT
    TB_REJECTION — failed trust boundary → REVIEW_RULE
    PARTIAL — partially extracted (e.g., β but no SE) → usable with inflated SE
Integration (Module 3.4):
    - AGENT_MISS for ≥3 papers → agent prompt revision needed
    - PARSE_FAILURE for ≥3 papers → parser issue, try alternate PDF
    - ABSENT_IN_PAPER for ≥3 papers → genuine evidence gap, acquire
Reads: Per-component extraction results from P1 agents + TB
Writes: MissingnessReport consumed by P5 gap analysis + acquisition loop
Gates: None (diagnostic/routing only)
"""
from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field

from crci.shared.models.enums import CorrectiveAction, MissingnessCode

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ComponentMissingness:
    """Missingness classification for a single extraction component."""

    paper_id: str
    component_id: str
    component_label: str
    code: MissingnessCode
    detail: str
    agent_id: str | None = None
    corrective_action: CorrectiveAction = CorrectiveAction.SEARCH


@dataclass
class MissingnessReport:
    """Aggregated missingness report for a set of papers.

    Used by P5 gap analysis and acquisition loop to determine
    whether to search for more papers, reparse, or revise agents.
    """

    entries: list[ComponentMissingness] = field(default_factory=list)

    @property
    def total_components(self) -> int:
        return len(self.entries)

    @property
    def present_count(self) -> int:
        return sum(1 for e in self.entries if e.code == MissingnessCode.PRESENT)

    @property
    def missing_count(self) -> int:
        return self.total_components - self.present_count

    def completeness_fraction(self) -> float:
        if self.total_components == 0:
            return 0.0
        return self.present_count / self.total_components


# ═══════════════════════════════════════════════════════════════
#  CLASSIFICATION HELPERS
# ═══════════════════════════════════════════════════════════════


def classify_missing_component(
    *,
    paper_id: str,
    component_id: str,
    component_label: str,
    was_detected_in_inventory: bool,
    agent_returned_empty: bool,
    parse_section_failed: bool,
    guardrail_blocked: bool,
    guardrail_rule: str | None = None,
    tb_rejected: bool,
    tb_reason: str | None = None,
    partial_extraction: bool,
    agent_id: str | None = None,
) -> ComponentMissingness:
    """Classify why a component is missing from extraction.

    Applies the decision tree from Module 3.2 to determine
    the appropriate MissingnessCode and CorrectiveAction.
    """
    # TB rejection takes precedence (data existed but was rejected)
    if tb_rejected:
        return ComponentMissingness(
            paper_id=paper_id,
            component_id=component_id,
            component_label=component_label,
            code=MissingnessCode.TB_REJECTION,
            detail=f"Trust boundary rejected: {tb_reason or 'unknown reason'}",
            agent_id=agent_id,
            corrective_action=CorrectiveAction.REVIEW_RULE,
        )

    # Guardrail blocked (figure-only, sensitivity analysis, umbrella review)
    if guardrail_blocked:
        return ComponentMissingness(
            paper_id=paper_id,
            component_id=component_id,
            component_label=component_label,
            code=MissingnessCode.GUARDED_REJECTION,
            detail=f"Guardrail block: {guardrail_rule or 'unknown rule'}",
            agent_id=agent_id,
            corrective_action=CorrectiveAction.ACCEPT,
        )

    # Parse failure (section/table couldn't be parsed)
    if parse_section_failed:
        return ComponentMissingness(
            paper_id=paper_id,
            component_id=component_id,
            component_label=component_label,
            code=MissingnessCode.PARSE_FAILURE,
            detail="PDF parsing failed for relevant section/table",
            agent_id=agent_id,
            corrective_action=CorrectiveAction.REPARSE,
        )

    # Agent miss (component detected but agent returned empty)
    if was_detected_in_inventory and agent_returned_empty:
        return ComponentMissingness(
            paper_id=paper_id,
            component_id=component_id,
            component_label=component_label,
            code=MissingnessCode.AGENT_MISS,
            detail="Component detected in inventory but agent returned empty",
            agent_id=agent_id,
            corrective_action=CorrectiveAction.RERUN_AGENT,
        )

    # Partial extraction (β extracted but SE missing, etc.)
    if partial_extraction:
        return ComponentMissingness(
            paper_id=paper_id,
            component_id=component_id,
            component_label=component_label,
            code=MissingnessCode.PARTIAL,
            detail="Partially extracted (usable with inflated SE)",
            agent_id=agent_id,
            corrective_action=CorrectiveAction.SEARCH,
        )

    # Absent in paper (genuinely not reported)
    return ComponentMissingness(
        paper_id=paper_id,
        component_id=component_id,
        component_label=component_label,
        code=MissingnessCode.ABSENT_IN_PAPER,
        detail="Component not found in paper (confirmed by inventory + agent)",
        agent_id=agent_id,
        corrective_action=CorrectiveAction.SEARCH,
    )


# ═══════════════════════════════════════════════════════════════
#  ACQUISITION LOOP INTEGRATION (Module 3.4)
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class GapDiagnosis:
    """Diagnosis of why a component is missing across multiple papers.

    Used to route the correct corrective action in the acquisition loop.
    """

    component_id: str
    dominant_code: MissingnessCode
    count: int
    recommended_action: CorrectiveAction
    explanation: str


def diagnose_systematic_gaps(
    report: MissingnessReport,
    *,
    threshold: int = 3,
) -> list[GapDiagnosis]:
    """Module 3.4: Analyze missingness codes across papers to diagnose gaps.

    Rules:
    - AGENT_MISS for ≥threshold papers → agent prompt needs revision
    - PARSE_FAILURE for ≥threshold papers → parser issue
    - ABSENT_IN_PAPER for ≥threshold papers → genuine evidence gap

    Parameters
    ----------
    report : MissingnessReport
        Aggregated missingness report across papers.
    threshold : int
        Minimum count for systematic gap diagnosis.

    Returns
    -------
    list[GapDiagnosis]
        Diagnoses for components with systematic missingness.
    """
    # Group by component_id + code
    component_codes: dict[str, Counter[MissingnessCode]] = {}
    component_labels: dict[str, str] = {}

    for entry in report.entries:
        if entry.code == MissingnessCode.PRESENT:
            continue
        if entry.component_id not in component_codes:
            component_codes[entry.component_id] = Counter()
        component_codes[entry.component_id][entry.code] += 1
        component_labels[entry.component_id] = entry.component_label

    diagnoses: list[GapDiagnosis] = []

    for comp_id, code_counts in component_codes.items():
        dominant_code, count = code_counts.most_common(1)[0]
        if count < threshold:
            continue

        if dominant_code == MissingnessCode.AGENT_MISS:
            action = CorrectiveAction.RERUN_AGENT
            explanation = (
                f"Agent failed to extract '{component_labels.get(comp_id, comp_id)}' "
                f"in {count} papers. Agent prompt revision needed."
            )
        elif dominant_code == MissingnessCode.PARSE_FAILURE:
            action = CorrectiveAction.REPARSE
            explanation = (
                f"PDF parsing failed for '{component_labels.get(comp_id, comp_id)}' "
                f"in {count} papers. Try alternate PDF sources or parser settings."
            )
        elif dominant_code == MissingnessCode.ABSENT_IN_PAPER:
            action = CorrectiveAction.SEARCH
            explanation = (
                f"'{component_labels.get(comp_id, comp_id)}' genuinely absent "
                f"in {count} papers. Generate acquisition query."
            )
        elif dominant_code == MissingnessCode.GUARDED_REJECTION:
            action = CorrectiveAction.ACCEPT
            explanation = (
                f"'{component_labels.get(comp_id, comp_id)}' blocked by guardrails "
                f"in {count} papers (likely figure-only). Accept block."
            )
        elif dominant_code == MissingnessCode.TB_REJECTION:
            action = CorrectiveAction.REVIEW_RULE
            explanation = (
                f"'{component_labels.get(comp_id, comp_id)}' rejected by trust boundary "
                f"in {count} papers. Review if rule is too strict."
            )
        else:
            action = CorrectiveAction.SEARCH
            explanation = (
                f"'{component_labels.get(comp_id, comp_id)}' has code {dominant_code.value} "
                f"in {count} papers."
            )

        logger.info("Gap diagnosis: %s — %s (action: %s)", comp_id, explanation, action.value)

        diagnoses.append(GapDiagnosis(
            component_id=comp_id,
            dominant_code=dominant_code,
            count=count,
            recommended_action=action,
            explanation=explanation,
        ))

    return diagnoses
