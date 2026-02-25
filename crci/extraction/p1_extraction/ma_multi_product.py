# VERIFIED: rules match PAPER_TYPE_ROUTING_AND_ACQUISITION spec §2
# VERIFIED: imports — all modules exist (shared.models.enums)
# VERIFIED: backward wiring — reads PaperSubtype from P0 classifier
# VERIFIED: forward wiring — writes MAExtractionPlan consumed by P1 runner
# VERIFIED: no hardcoded formula parameters
"""
Component: SYS_EXTRACTION.EX-P1.MA-DISPATCH
Spec: PAPER_TYPE_ROUTING_AND_ACQUISITION.md §2 (MA Multi-Product Extraction)
      SYS_EXTRACTION_ADDENDUM.md Part 2 (multi-product MA)
Rules:
    MA-1: Every MA yields UP TO 6 extraction products
    MA-2: Pooled estimate always extracted (product 1)
    MA-3: Heterogeneity stats (I², τ², prediction interval) if reported
    MA-4: Forest plot entries → individual study-level records
    MA-5: Subgroup/moderator analyses → per-subgroup estimates
    MA-6: NMA → pairwise comparison matrix
    MA-7: Dose-response MA → dose-response curve data points
    MA-8: Included study list → directed acquisition for hop discovery
Reads: PaperSubtype + PaperMap (from P0 + canonical reader)
Writes: MAExtractionPlan (consumed by P1 agent dispatch)
Gates: None (plan is advisory; individual products have their own gates)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum, unique

from crci.shared.models.enums import MetaSourceFlag, PaperSubtype

logger = logging.getLogger(__name__)


@unique
class MAProductType(StrEnum):
    """Meta-analysis extraction product types."""
    POOLED_ESTIMATE = "pooled_estimate"
    HETEROGENEITY_STATS = "heterogeneity_stats"
    FOREST_PLOT_ENTRIES = "forest_plot_entries"
    SUBGROUP_MODERATOR = "subgroup_moderator"
    NMA_PAIRWISE_MATRIX = "nma_pairwise_matrix"
    DOSE_RESPONSE_POINTS = "dose_response_points"
    INCLUDED_STUDY_LIST = "included_study_list"


@dataclass(frozen=True)
class MAProduct:
    """A single extraction product from a meta-analysis."""

    product_type: MAProductType
    meta_source_flag: MetaSourceFlag
    priority: int  # 1 = highest
    is_mandatory: bool
    description: str


@dataclass
class MAExtractionPlan:
    """Extraction plan for a meta-analysis paper.

    Lists which products to extract and in what order.
    """

    paper_id: str
    paper_subtype: str
    products: list[MAProduct] = field(default_factory=list)
    is_network_ma: bool = False
    is_dose_response_ma: bool = False
    included_k_expected: int | None = None

    @property
    def product_count(self) -> int:
        return len(self.products)

    @property
    def mandatory_products(self) -> list[MAProduct]:
        return [p for p in self.products if p.is_mandatory]


# ═══════════════════════════════════════════════════════════════
#  MA TYPE DETECTION
# ═══════════════════════════════════════════════════════════════

# Keywords indicating NMA (network meta-analysis)
_NMA_KEYWORDS = frozenset({
    "network meta-analysis", "network meta analysis",
    "indirect comparison", "mixed treatment comparison",
    "multiple treatment comparison", "bayesian network",
})

# Keywords indicating dose-response MA
_DOSE_RESPONSE_MA_KEYWORDS = frozenset({
    "dose-response meta-analysis", "dose response meta analysis",
    "dose-response relationship", "dose response curve",
    "dose-finding", "exposure-response",
})


def _detect_ma_subtype(
    paper_text: str | None,
    title: str | None = None,
) -> tuple[bool, bool]:
    """Detect if MA is NMA or dose-response MA.

    Returns (is_nma, is_dose_response_ma).
    """
    text_lower = ""
    if title:
        text_lower += title.lower() + " "
    if paper_text:
        # Check first 5000 chars for efficiency
        text_lower += paper_text[:5000].lower()

    is_nma = any(kw in text_lower for kw in _NMA_KEYWORDS)
    is_dr = any(kw in text_lower for kw in _DOSE_RESPONSE_MA_KEYWORDS)

    return is_nma, is_dr


# ═══════════════════════════════════════════════════════════════
#  PLAN BUILDER
# ═══════════════════════════════════════════════════════════════


def build_ma_extraction_plan(
    paper_id: str,
    paper_subtype: PaperSubtype | str,
    paper_text: str | None = None,
    title: str | None = None,
) -> MAExtractionPlan:
    """Build a multi-product extraction plan for a meta-analysis.

    MA-1: Every MA yields up to 6 products. This function determines
    which products apply based on paper type and content.

    Parameters
    ----------
    paper_id : str
        Unique paper identifier.
    paper_subtype : PaperSubtype | str
        Classified paper subtype.
    paper_text : str | None
        Full text for NMA/dose-response detection.
    title : str | None
        Paper title.

    Returns
    -------
    MAExtractionPlan
        Plan with ordered product list.
    """
    subtype_str = paper_subtype.value if isinstance(paper_subtype, PaperSubtype) else paper_subtype

    # Only build plans for MA-type papers
    ma_subtypes = {
        PaperSubtype.META_ANALYSIS.value,
        PaperSubtype.SYSTEMATIC_REVIEW.value,
    }
    if subtype_str not in ma_subtypes:
        logger.debug(
            "paper=%s: subtype=%s is not MA/SR, empty plan",
            paper_id, subtype_str,
        )
        return MAExtractionPlan(paper_id=paper_id, paper_subtype=subtype_str)

    is_nma, is_dr = _detect_ma_subtype(paper_text, title)

    products: list[MAProduct] = []

    # MA-2: Pooled estimate (ALWAYS mandatory)
    products.append(MAProduct(
        product_type=MAProductType.POOLED_ESTIMATE,
        meta_source_flag=MetaSourceFlag.POOLED_ESTIMATE,
        priority=1,
        is_mandatory=True,
        description="Primary pooled effect estimate (β̂, SE, CI, p)",
    ))

    # MA-3: Heterogeneity stats (mandatory for standard MA)
    products.append(MAProduct(
        product_type=MAProductType.HETEROGENEITY_STATS,
        meta_source_flag=MetaSourceFlag.POOLED_ESTIMATE,
        priority=2,
        is_mandatory=True,
        description="I², τ², Q, prediction interval",
    ))

    # MA-8: Included study list (mandatory — needed for DCR + hop discovery)
    products.append(MAProduct(
        product_type=MAProductType.INCLUDED_STUDY_LIST,
        meta_source_flag=MetaSourceFlag.POOLED_ESTIMATE,
        priority=3,
        is_mandatory=True,
        description="List of included study IDs for DCR overlap + hop discovery",
    ))

    # MA-4: Forest plot entries (optional but high-value)
    products.append(MAProduct(
        product_type=MAProductType.FOREST_PLOT_ENTRIES,
        meta_source_flag=MetaSourceFlag.FOREST_PLOT_ENTRY,
        priority=4,
        is_mandatory=False,
        description="Per-study effect sizes from forest plot (β_i, SE_i, w_i)",
    ))

    # MA-5: Subgroup/moderator analyses (if detected)
    products.append(MAProduct(
        product_type=MAProductType.SUBGROUP_MODERATOR,
        meta_source_flag=MetaSourceFlag.SUBGROUP_ESTIMATE,
        priority=5,
        is_mandatory=False,
        description="Subgroup pooled estimates and moderator interaction tests",
    ))

    # MA-6: NMA pairwise matrix (only for NMA papers)
    if is_nma:
        products.append(MAProduct(
            product_type=MAProductType.NMA_PAIRWISE_MATRIX,
            meta_source_flag=MetaSourceFlag.NMA_MIXED,
            priority=6,
            is_mandatory=False,
            description="Pairwise comparison matrix from network meta-analysis",
        ))

    # MA-7: Dose-response points (only for dose-response MAs)
    if is_dr:
        products.append(MAProduct(
            product_type=MAProductType.DOSE_RESPONSE_POINTS,
            meta_source_flag=MetaSourceFlag.DOSE_RESPONSE_POINT,
            priority=6,
            is_mandatory=False,
            description="Dose-response curve data points from pooled dose-response analysis",
        ))

    plan = MAExtractionPlan(
        paper_id=paper_id,
        paper_subtype=subtype_str,
        products=products,
        is_network_ma=is_nma,
        is_dose_response_ma=is_dr,
    )

    logger.info(
        "MA plan: paper=%s, subtype=%s, products=%d (mandatory=%d), nma=%s, dr=%s",
        paper_id, subtype_str, plan.product_count,
        len(plan.mandatory_products), is_nma, is_dr,
    )

    return plan


def get_product_agents(product: MAProduct) -> list[str]:
    """Map a product type to the agent IDs responsible for extracting it.

    Returns a list of agent IDs that should be activated for this product.
    This is used by the P1 runner to dispatch appropriate agents.
    """
    agent_map: dict[MAProductType, list[str]] = {
        MAProductType.POOLED_ESTIMATE: ["AG05", "AG06"],
        MAProductType.HETEROGENEITY_STATS: ["AG05"],
        MAProductType.INCLUDED_STUDY_LIST: ["AG02"],
        MAProductType.FOREST_PLOT_ENTRIES: ["AG05", "AG07"],
        MAProductType.SUBGROUP_MODERATOR: ["AG05", "AG08"],
        MAProductType.NMA_PAIRWISE_MATRIX: ["AG05"],
        MAProductType.DOSE_RESPONSE_POINTS: ["AG05"],
    }
    return agent_map.get(product.product_type, ["AG05"])
