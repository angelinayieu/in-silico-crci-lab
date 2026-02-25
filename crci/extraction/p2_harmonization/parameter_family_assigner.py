# VERIFIED: mapping matches CONVERSION_VALIDITY_AND_HARDENING.md Module 5.1
# VERIFIED: imports — all modules exist (shared.models.enums)
# VERIFIED: backward wiring — reads PaperSubtype + edge family from P0/P1
# VERIFIED: forward wiring — writes ParameterFamily consumed by freshness_policy
# VERIFIED: no hardcoded formula parameters
"""
Component: SYS_EXTRACTION.EX-P2.FAMILY-ASSIGN
Spec: CONVERSION_VALIDITY_AND_HARDENING.md Module 5.1
Purpose: Assigns a ParameterFamily to each evidence record based on
         paper subtype, edge family, and extraction context.
         This drives family-specific freshness decay in P3 L7.
Reads: PaperSubtype (from P0), edge_family (from P1/edge_relation_id)
Writes: ParameterFamily (consumed by freshness_policy.py / se_eff_assembly.py)
Gates: None (assignment is deterministic)
"""
from __future__ import annotations

import logging

from crci.shared.models.enums import MetaSourceFlag, ParameterFamily, PaperSubtype

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  SUBTYPE → FAMILY MAPPING
# ═══════════════════════════════════════════════════════════════

# Paper subtypes that primarily produce psychometric evidence
_PSYCHOMETRIC_SUBTYPES = frozenset({
    PaperSubtype.PSYCHOMETRIC_VALIDATION,
})

# Paper subtypes that primarily produce normative data
_NORMATIVE_SUBTYPES = frozenset({
    PaperSubtype.NORMATIVE_COHORT,
})

# Paper subtypes that primarily produce mechanistic/biological evidence
_MECHANISM_SUBTYPES = frozenset({
    PaperSubtype.MECHANISTIC_ANIMAL,
    PaperSubtype.MECHANISTIC_HUMAN,
    PaperSubtype.BIOMARKER_DISCOVERY,
    PaperSubtype.IMAGING_STRUCTURAL,
    PaperSubtype.IMAGING_FUNCTIONAL,
})

# Paper subtypes that produce intervention evidence
_INTERVENTION_SUBTYPES = frozenset({
    PaperSubtype.RCT_EXERCISE,
    PaperSubtype.RCT_COGNITIVE,
    PaperSubtype.RCT_PHARMACOLOGICAL,
    PaperSubtype.RCT_MULTIMODAL,
    PaperSubtype.LONGITUDINAL_FOLLOWUP,
})

# Paper subtypes that produce dose-response / temporal evidence
_TEMPORAL_SUBTYPES = frozenset({
    PaperSubtype.DOSE_RESPONSE,
    PaperSubtype.DOSE_RESPONSE_STUDY,
})


# ═══════════════════════════════════════════════════════════════
#  EDGE FAMILY → PARAMETER FAMILY MAPPING
# ═══════════════════════════════════════════════════════════════

# Edge families that indicate mechanism-to-mechanism relationships
_MECHANISM_EDGE_FAMILIES = frozenset({
    "biomarker_cognitive",
    "molecular_mechanism",
    "neuroinflammation",
    "oxidative_stress",
    "neurotrophic",
    "white_matter",
    "gray_matter",
    "hormonal",
})


def assign_parameter_family(
    *,
    paper_subtype: PaperSubtype | str | None = None,
    edge_family: str | None = None,
    meta_source_flag: MetaSourceFlag | str | None = None,
    extraction_context: str | None = None,
) -> ParameterFamily:
    """Assign a ParameterFamily to an evidence record.

    Decision hierarchy (first match wins):
    1. Extraction context override (if explicitly specified)
    2. Paper subtype mapping
    3. Edge family mapping
    4. Meta-source flag mapping
    5. Default: EDGE_INTERVENTION

    Parameters
    ----------
    paper_subtype : PaperSubtype | str | None
        Classified paper subtype from P0.
    edge_family : str | None
        Edge family from edge_relation_id lookup.
    meta_source_flag : MetaSourceFlag | str | None
        If the record came from a meta-analysis.
    extraction_context : str | None
        Explicit override context (e.g., "recovery_curve", "context_prior").

    Returns
    -------
    ParameterFamily
        Assigned family for freshness policy.
    """
    # 1. Explicit context override
    if extraction_context is not None:
        context_map: dict[str, ParameterFamily] = {
            "psychometric": ParameterFamily.PSYCHOMETRICS,
            "psychometrics": ParameterFamily.PSYCHOMETRICS,
            "normative": ParameterFamily.NORMATIVE_DATA,
            "normative_data": ParameterFamily.NORMATIVE_DATA,
            "biological_correlation": ParameterFamily.BIOLOGICAL_CORRELATIONS,
            "biological_correlations": ParameterFamily.BIOLOGICAL_CORRELATIONS,
            "intervention_kernel": ParameterFamily.INTERVENTION_KERNELS,
            "intervention_kernels": ParameterFamily.INTERVENTION_KERNELS,
            "temporal_kernel": ParameterFamily.INTERVENTION_KERNELS,
            "context_prior": ParameterFamily.CONTEXT_PRIORS,
            "context_priors": ParameterFamily.CONTEXT_PRIORS,
            "recovery_curve": ParameterFamily.RECOVERY_CURVES,
            "recovery_curves": ParameterFamily.RECOVERY_CURVES,
        }
        family = context_map.get(extraction_context.lower())
        if family is not None:
            return family

    # Normalize paper_subtype
    subtype: PaperSubtype | None = None
    if isinstance(paper_subtype, str):
        try:
            subtype = PaperSubtype(paper_subtype)
        except ValueError:
            pass
    elif isinstance(paper_subtype, PaperSubtype):
        subtype = paper_subtype

    # 2. Paper subtype mapping
    if subtype is not None:
        if subtype in _PSYCHOMETRIC_SUBTYPES:
            return ParameterFamily.PSYCHOMETRICS
        if subtype in _NORMATIVE_SUBTYPES:
            return ParameterFamily.NORMATIVE_DATA
        if subtype in _MECHANISM_SUBTYPES:
            return ParameterFamily.BIOLOGICAL_CORRELATIONS
        if subtype in _INTERVENTION_SUBTYPES:
            return ParameterFamily.EDGE_INTERVENTION
        if subtype in _TEMPORAL_SUBTYPES:
            return ParameterFamily.INTERVENTION_KERNELS
        if subtype == PaperSubtype.META_ANALYSIS:
            return ParameterFamily.META_ANALYSIS_POOLED

    # 3. Edge family mapping
    if edge_family is not None:
        edge_family_lower = edge_family.lower()
        if edge_family_lower in _MECHANISM_EDGE_FAMILIES:
            return ParameterFamily.EDGE_MECHANISM

    # 4. Meta-source flag mapping
    if meta_source_flag is not None:
        flag_str = (
            meta_source_flag.value
            if isinstance(meta_source_flag, MetaSourceFlag)
            else meta_source_flag
        )
        if flag_str in {
            MetaSourceFlag.POOLED_ESTIMATE.value,
            MetaSourceFlag.SUBGROUP_ESTIMATE.value,
            MetaSourceFlag.NMA_MIXED.value,
            MetaSourceFlag.NMA_DIRECT.value,
        }:
            return ParameterFamily.META_ANALYSIS_POOLED

    # 5. Default
    logger.info(
        "Parameter family: no specific match for subtype=%s, edge=%s → default EDGE_INTERVENTION",
        paper_subtype, edge_family,
    )
    return ParameterFamily.EDGE_INTERVENTION
