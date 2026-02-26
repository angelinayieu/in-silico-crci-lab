"""Boundary Contract Test: TB → TypedNumericValue.

Every TNV must have a primary effect measure + at least one precision
measure (SE or CI-derived SE).  Uses synthetic data only (no LLM).
"""
from __future__ import annotations

import pytest

from crci.shared.models.enums import BoundType
from crci.shared.models.intermediate_states import TypedNumericValue


# ═══════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════

PRIMARY_LABEL_TYPES = {
    "EFFECT_SIZE", "ODDS_RATIO", "HAZARD_RATIO", "RISK_RATIO",
    "MEAN_DIFFERENCE", "CORRELATION", "UNSTD_BETA", "STD_BETA",
    "PERCENT_CHANGE", "INCIDENCE_RATE_RATIO", "INTERACTION_TERM",
    "SUBGROUP_EFFECT", "F_STATISTIC",
}


def _make_tnv(
    value: float = 0.45,
    label_type: str | None = "EFFECT_SIZE",
    se: float | None = 0.12,
    ci_lower: float | None = None,
    ci_upper: float | None = None,
    p_value: float | None = None,
    n: int | None = None,
    edge_relation_id: str | None = "ER_COGACTIVITY_WORKMEM",
    grouping_id: str | None = "grp_001",
) -> TypedNumericValue:
    return TypedNumericValue(
        value=value,
        bound_type=BoundType.EXACT,
        original_text=str(value),
        label_type=label_type,
        se=se,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        p_value=p_value,
        n=n,
        edge_relation_id=edge_relation_id,
        grouping_id=grouping_id,
    )


def has_precision(tnv: TypedNumericValue) -> bool:
    """Check if TNV has at least one precision measure."""
    if tnv.se is not None:
        return True
    if tnv.ci_lower is not None and tnv.ci_upper is not None:
        return True
    return False


def has_primary(tnv: TypedNumericValue) -> bool:
    """Check if TNV has a primary effect measure label."""
    return tnv.label_type is not None and tnv.label_type in PRIMARY_LABEL_TYPES


# ═══════════════════════════════════════════════════════════════
#  Tests
# ═══════════════════════════════════════════════════════════════


class TestTNVPrimaryMeasure:
    """TB → TNV contract: every TNV should have a primary effect measure."""

    def test_tnv_with_effect_size_is_primary(self):
        tnv = _make_tnv(label_type="EFFECT_SIZE")
        assert has_primary(tnv)

    def test_tnv_with_odds_ratio_is_primary(self):
        tnv = _make_tnv(label_type="ODDS_RATIO", value=1.5)
        assert has_primary(tnv)

    def test_tnv_with_correlation_is_primary(self):
        tnv = _make_tnv(label_type="CORRELATION", value=0.3)
        assert has_primary(tnv)

    def test_tnv_without_label_type_not_primary(self):
        tnv = _make_tnv(label_type=None)
        assert not has_primary(tnv)

    def test_tnv_with_sample_size_not_primary(self):
        tnv = _make_tnv(label_type="SAMPLE_SIZE", value=100.0)
        assert not has_primary(tnv)


class TestTNVPrecision:
    """TB → TNV contract: should have SE or CI for downstream survival."""

    def test_tnv_with_se_has_precision(self):
        tnv = _make_tnv(se=0.12)
        assert has_precision(tnv)

    def test_tnv_with_ci_has_precision(self):
        tnv = _make_tnv(se=None, ci_lower=0.21, ci_upper=0.69)
        assert has_precision(tnv)

    def test_tnv_with_both_has_precision(self):
        tnv = _make_tnv(se=0.12, ci_lower=0.21, ci_upper=0.69)
        assert has_precision(tnv)

    def test_tnv_without_se_or_ci_no_precision(self):
        tnv = _make_tnv(se=None, ci_lower=None, ci_upper=None)
        assert not has_precision(tnv)

    def test_tnv_with_only_ci_lower_no_precision(self):
        tnv = _make_tnv(se=None, ci_lower=0.21, ci_upper=None)
        assert not has_precision(tnv)


class TestTNVComplete:
    """TB → TNV contract: ideal TNV has primary + precision + grouping."""

    def test_ideal_tnv_complete(self):
        tnv = _make_tnv(
            value=0.45,
            label_type="EFFECT_SIZE",
            se=0.12,
            grouping_id="grp_001",
            edge_relation_id="ER_COGACTIVITY_WORKMEM",
        )
        assert has_primary(tnv)
        assert has_precision(tnv)
        assert tnv.grouping_id is not None
        assert tnv.edge_relation_id is not None

    def test_minimal_tnv_missing_fields(self):
        tnv = _make_tnv(
            label_type=None,
            se=None,
            grouping_id=None,
            edge_relation_id=None,
        )
        assert not has_primary(tnv)
        assert not has_precision(tnv)
        assert tnv.grouping_id is None
        assert tnv.edge_relation_id is None

    def test_tnv_grouping_links_multiple(self):
        """Multiple TNVs with same grouping_id belong to same stat result."""
        tnv1 = _make_tnv(label_type="EFFECT_SIZE", grouping_id="grp_A")
        tnv2 = _make_tnv(label_type="SE", value=0.12, grouping_id="grp_A")
        assert tnv1.grouping_id == tnv2.grouping_id
