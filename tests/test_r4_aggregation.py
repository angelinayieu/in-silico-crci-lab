"""Tests for Slice R4: Aggregation Pipeline Amendments.

R4.1: Heterogeneity passthrough
R4.2: NMA three-way overlap detection
R4.3: Dose-response point compilation (wiring exists, supplementary path tested)
"""
from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from crci.shared.models.enums import EffectScale, MetaSourceFlag, SESource
from crci.shared.models.intermediate_states import (
    HarmonizedClaim,
    PooledEstimate,
    ResolvedEvidence,
)

_HARM_STATUS = "FULL"
_EFFECT_SCALE = EffectScale.SD_SD


def _make_claim(
    ler_id: str,
    edge_id: str = "ER_EXERCISE_FATIGUE",
    beta: float = 0.3,
    se: float = 0.1,
    meta_flag: str | None = None,
    parent_ma: str | None = None,
    het_json: dict | None = None,
) -> HarmonizedClaim:
    """Helper to build a HarmonizedClaim."""
    return HarmonizedClaim(
        ler_id=ler_id,
        edge_relation_id=edge_id,
        profile_id="PROF_01",
        study_id=parent_ma or "STUDY_PRIMARY",
        harmonized_beta=beta,
        harmonized_se=se,
        harmonized_scale=_EFFECT_SCALE,
        harmonization_status=_HARM_STATUS,
        quality_rating="moderate",
        meta_source_flag=meta_flag,
        parent_meta_study_id=parent_ma,
        heterogeneity_json=het_json,
    )


# ═══════════════════════════════════════════════════════════════
#  R4.1: PUBLISHED HETEROGENEITY PASSTHROUGH
# ═══════════════════════════════════════════════════════════════


class TestHeterogeneityPassthrough:
    """R4.1: Published I²/τ² used when available."""

    def test_ma_claim_with_heterogeneity_returns_dict(self):
        """MA claim with heterogeneity_json → passthrough returns dict."""
        from crci.extraction.p4_aggregation.meta_analyzer import (
            _use_published_heterogeneity,
        )

        claims = [
            _make_claim(
                "LER_MA_001",
                meta_flag=MetaSourceFlag.POOLED_ESTIMATE.value,
                parent_ma="MA_CIFU_2018",
                het_json={"I2": 45.0, "tau2": 0.012},
            ),
            _make_claim("LER_PRIMARY_001"),
        ]
        het = _use_published_heterogeneity(claims)
        assert het is not None
        assert het["I2"] == 45.0
        assert het["tau2"] == 0.012

    def test_no_ma_claim_returns_none(self):
        """All primary claims → no published heterogeneity."""
        from crci.extraction.p4_aggregation.meta_analyzer import (
            _use_published_heterogeneity,
        )

        claims = [
            _make_claim("LER_001"),
            _make_claim("LER_002"),
        ]
        assert _use_published_heterogeneity(claims) is None

    def test_ma_claim_without_het_json_returns_none(self):
        """MA claim exists but no heterogeneity_json → returns None."""
        from crci.extraction.p4_aggregation.meta_analyzer import (
            _use_published_heterogeneity,
        )

        claims = [
            _make_claim(
                "LER_MA_001",
                meta_flag=MetaSourceFlag.POOLED_ESTIMATE.value,
                parent_ma="MA_CIFU_2018",
                het_json=None,
            ),
        ]
        assert _use_published_heterogeneity(claims) is None

    def test_pool_evidence_uses_published_heterogeneity(self):
        """pool_evidence overrides computed I² and τ² with published values."""
        from crci.extraction.p4_aggregation.meta_analyzer import pool_evidence

        claims = [
            _make_claim(
                "LER_001", beta=0.3, se=0.1,
                meta_flag=MetaSourceFlag.POOLED_ESTIMATE.value,
                parent_ma="MA_CIFU_2018",
                het_json={"I2": 82.5, "tau2": 0.035},
            ),
            _make_claim("LER_002", beta=0.5, se=0.15),
            _make_claim("LER_003", beta=0.2, se=0.12),
        ]
        resolved = ResolvedEvidence(
            edge_relation_id="ER_EXERCISE_FATIGUE",
            claims=claims,
            overlap_decisions=[],
            k=3,
        )
        result = pool_evidence(resolved)
        # Published values should override re-estimated ones
        assert result.pooled_estimate.i_squared == 82.5
        assert result.pooled_estimate.tau_squared == 0.035

    def test_pool_evidence_without_published_het_estimates_normally(self):
        """Without published heterogeneity, pipeline estimates normally."""
        from crci.extraction.p4_aggregation.meta_analyzer import pool_evidence

        claims = [
            _make_claim("LER_001", beta=0.3, se=0.1),
            _make_claim("LER_002", beta=0.5, se=0.15),
        ]
        resolved = ResolvedEvidence(
            edge_relation_id="ER_EXERCISE_FATIGUE",
            claims=claims,
            overlap_decisions=[],
            k=2,
        )
        result = pool_evidence(resolved)
        # Should compute I² and τ² normally (not 82.5 / 0.035)
        assert result.pooled_estimate.i_squared != 82.5
        assert result.pooled_estimate.tau_squared != 0.035


# ═══════════════════════════════════════════════════════════════
#  R4.2: NMA THREE-WAY OVERLAP DETECTION
# ═══════════════════════════════════════════════════════════════


class TestNMAPairwiseOverlap:
    """R4.2: NMA + pairwise MA overlap → warning."""

    def test_nma_and_pairwise_triggers_warning(self):
        """Both NMA_MIXED and POOLED_ESTIMATE for same edge → warning."""
        from crci.extraction.p4_aggregation.double_counting import (
            detect_nma_pairwise_overlap,
        )

        claims = [
            _make_claim("LER_NMA_001", meta_flag="NMA_MIXED"),
            _make_claim("LER_PW_001", meta_flag="POOLED_ESTIMATE"),
        ]
        warnings = detect_nma_pairwise_overlap(claims, "ER_EXERCISE_FATIGUE")
        assert len(warnings) == 1
        assert "R4-NMA3" in warnings[0]

    def test_only_pairwise_no_warning(self):
        """Only pairwise MA claims → no NMA overlap warning."""
        from crci.extraction.p4_aggregation.double_counting import (
            detect_nma_pairwise_overlap,
        )

        claims = [
            _make_claim("LER_PW_001", meta_flag="POOLED_ESTIMATE"),
            _make_claim("LER_PW_002", meta_flag="POOLED_ESTIMATE"),
        ]
        warnings = detect_nma_pairwise_overlap(claims, "ER_EXERCISE_FATIGUE")
        assert len(warnings) == 0

    def test_only_nma_no_warning(self):
        """Only NMA claims → no overlap warning."""
        from crci.extraction.p4_aggregation.double_counting import (
            detect_nma_pairwise_overlap,
        )

        claims = [
            _make_claim("LER_NMA_001", meta_flag="NMA_MIXED"),
        ]
        warnings = detect_nma_pairwise_overlap(claims, "ER_EXERCISE_FATIGUE")
        assert len(warnings) == 0

    def test_primary_only_no_warning(self):
        """All primary claims → no NMA overlap warning."""
        from crci.extraction.p4_aggregation.double_counting import (
            detect_nma_pairwise_overlap,
        )

        claims = [
            _make_claim("LER_001"),
            _make_claim("LER_002"),
        ]
        warnings = detect_nma_pairwise_overlap(claims, "ER_EXERCISE_FATIGUE")
        assert len(warnings) == 0

    def test_dcr_logs_nma_overlap_warning(self, caplog):
        """Integration: resolve_double_counting logs R4-NMA3 warning."""
        from crci.extraction.p4_aggregation.double_counting import (
            resolve_double_counting,
        )
        from crci.shared.models.intermediate_states import GroupedEvidence

        claims = [
            _make_claim("LER_NMA_001", meta_flag="NMA_MIXED"),
            _make_claim("LER_PW_001", meta_flag="POOLED_ESTIMATE"),
            _make_claim("LER_PRIMARY_001"),
        ]
        grouped = GroupedEvidence(
            edge_relation_id="ER_EXERCISE_FATIGUE",
            claims=claims,
            overlap_decisions=[],
            k=3,
        )

        with caplog.at_level(logging.WARNING):
            result = resolve_double_counting(grouped)

        assert any("R4-NMA3" in record.message for record in caplog.records)


# ═══════════════════════════════════════════════════════════════
#  R4.3: DOSE-RESPONSE COMPILATION WIRING
# ═══════════════════════════════════════════════════════════════


class TestDoseResponseWiring:
    """R4.3: Dose-response compilation path exists."""

    def test_compiler_function_exists(self):
        """Dose-response compiler is importable."""
        from crci.extraction.p7_compilers.dose_response_compiler import (
            compile_dose_response,
        )

        assert callable(compile_dose_response)

    def test_p7_runner_fetches_dose_evidence(self):
        """P7 runner has dose-response fetch and compile path."""
        from crci.extraction.p7_compilers.runner import _run_dose_response_compiler

        assert callable(_run_dose_response_compiler)
