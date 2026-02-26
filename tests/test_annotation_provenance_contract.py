"""
Contract test: annotation → σ²_structural → compiled edge provenance.

WP-10 (PIMP v2): Verifies the complete annotation provenance chain:
  study_annotations_v1 (confounder annotation, PROMOTED)
    → get_sigma_structural_annotations()
    → get_structural_variance()  [shared_annotation_features.py]
    → AnnotationFeatures.sigma_sq_structural inflated above default
    → annotation_ids returned for param-build tracking

Uses in-memory SQLite — no external DB dependency.
"""
from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from crci.shared.models.tables import Base, StudyAnnotations
from crci.shared import config
from crci.extraction.shared_annotation_features import (
    AnnotationFeatures,
    get_structural_variance,
)


# ───────────────────────────────────────────────────────────────
# Fixtures
# ───────────────────────────────────────────────────────────────

@pytest.fixture
def in_memory_session():
    """Create an in-memory SQLite DB with all ORM tables and yield a session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    engine.dispose()


EDGE_ID = "edge_chemo_cog_001"


def _insert_annotation(
    session: Session,
    *,
    edge_relation_id: str = EDGE_ID,
    category: str = "LIMITATION_UNMEASURED_CONFOUNDER",
    severity: str = "high",
    confidence: float = 0.8,
    maturity: str = "promoted",
    promoted_to: str = "sigma_structural",
    annotation_id: str | None = None,
) -> str:
    """Insert a single promoted StudyAnnotation and return its ID."""
    ann_id = annotation_id or f"ann-{uuid.uuid4().hex[:12]}"
    ann = StudyAnnotations(
        annotation_id=ann_id,
        study_id=f"study-{uuid.uuid4().hex[:8]}",
        category=category,
        content="Unmeasured confounder: prior cognitive reserve",
        target_entity_type="edge",
        target_entity_id=edge_relation_id,
        structured_data_json=json.dumps({"severity": severity}),
        evidence_strength="moderate",
        reconciled_confidence=confidence,
        maturity=maturity,
        promoted_to=promoted_to,
        consumer=promoted_to,
        active=True,
        cross_agent_support_n=2,
        adjudication_status="auto_merged",
    )
    session.add(ann)
    session.flush()
    return ann_id


# ───────────────────────────────────────────────────────────────
# Tests
# ───────────────────────────────────────────────────────────────


class TestAnnotationSigmaFlow:
    """Prove σ²_structural is inflated when confounder annotations exist."""

    def test_annotation_sigma_sq_flows_to_computed_value(
        self, in_memory_session: Session
    ):
        """Insert confounder annotation → verify σ² inflated above default."""
        _insert_annotation(
            in_memory_session,
            severity="high",
            confidence=0.8,
        )

        features = get_structural_variance(in_memory_session, EDGE_ID)

        # σ²_struct = base + (w_high × confidence)
        # w_high = config.ANNOTATION_SEVERITY_WEIGHTS["high"] = 0.10
        # Adjustment = 0.10 × 0.8 = 0.08
        expected = config.SIGMA_SQ_STRUCTURAL_DEFAULT + 0.10 * 0.8
        assert isinstance(features, AnnotationFeatures)
        assert features.sigma_sq_structural == pytest.approx(expected, abs=1e-9)
        assert features.sigma_sq_structural > config.SIGMA_SQ_STRUCTURAL_DEFAULT

    def test_multiple_annotations_additive(
        self, in_memory_session: Session
    ):
        """Multiple annotations → σ² adjustments are summed."""
        _insert_annotation(
            in_memory_session, severity="high", confidence=0.9
        )
        _insert_annotation(
            in_memory_session, severity="moderate", confidence=0.7
        )

        features = get_structural_variance(in_memory_session, EDGE_ID)

        # Adjustment = (0.10 × 0.9) + (0.05 × 0.7) = 0.09 + 0.035 = 0.125
        expected = config.SIGMA_SQ_STRUCTURAL_DEFAULT + (0.10 * 0.9) + (0.05 * 0.7)
        assert features.sigma_sq_structural == pytest.approx(expected, abs=1e-9)
        assert features.n_annotations == 2


class TestAnnotationIdsReachParamBuild:
    """Prove annotation IDs are returned for downstream provenance tracking."""

    def test_annotation_ids_reach_param_build(
        self, in_memory_session: Session
    ):
        """Insert annotation → verify its ID appears in AnnotationFeatures."""
        ann_id = _insert_annotation(
            in_memory_session,
            annotation_id="ann-confounder-001",
        )

        features = get_structural_variance(in_memory_session, EDGE_ID)

        assert ann_id in features.annotation_ids
        assert features.n_annotations == 1

    def test_multiple_ids_tracked(
        self, in_memory_session: Session
    ):
        """Multiple annotations → all IDs present in features."""
        id1 = _insert_annotation(
            in_memory_session, annotation_id="ann-conf-aaa"
        )
        id2 = _insert_annotation(
            in_memory_session, annotation_id="ann-conf-bbb"
        )

        features = get_structural_variance(in_memory_session, EDGE_ID)

        assert set(features.annotation_ids) == {id1, id2}
        assert features.n_annotations == 2


class TestNoAnnotationsDefault:
    """Prove default σ² is used when no annotations exist."""

    def test_no_annotations_uses_default_sigma(
        self, in_memory_session: Session
    ):
        """No annotations → σ² = config.SIGMA_SQ_STRUCTURAL_DEFAULT."""
        features = get_structural_variance(in_memory_session, EDGE_ID)

        assert features.sigma_sq_structural == config.SIGMA_SQ_STRUCTURAL_DEFAULT
        assert features.annotation_ids == []
        assert features.n_annotations == 0

    def test_unpromoted_annotations_ignored(
        self, in_memory_session: Session
    ):
        """Raw (non-promoted) annotations should not affect σ²."""
        _insert_annotation(
            in_memory_session,
            maturity="raw",
            promoted_to=None,
            severity="critical",
            confidence=1.0,
        )

        features = get_structural_variance(in_memory_session, EDGE_ID)

        # Raw annotation should be filtered out by get_promoted_for_consumer
        assert features.sigma_sq_structural == config.SIGMA_SQ_STRUCTURAL_DEFAULT
        assert features.n_annotations == 0

    def test_wrong_edge_annotations_ignored(
        self, in_memory_session: Session
    ):
        """Annotations for a different edge should not affect this edge's σ²."""
        _insert_annotation(
            in_memory_session,
            edge_relation_id="edge_OTHER_999",
            severity="critical",
            confidence=1.0,
        )

        features = get_structural_variance(in_memory_session, EDGE_ID)

        assert features.sigma_sq_structural == config.SIGMA_SQ_STRUCTURAL_DEFAULT
        assert features.n_annotations == 0


class TestSeverityWeights:
    """Verify config.ANNOTATION_SEVERITY_WEIGHTS are applied correctly."""

    @pytest.mark.parametrize(
        "severity,expected_weight",
        [
            ("moderate", 0.05),
            ("high", 0.10),
            ("critical", 0.15),
        ],
    )
    def test_severity_weight_applied(
        self,
        in_memory_session: Session,
        severity: str,
        expected_weight: float,
    ):
        """Each severity level uses its config weight."""
        confidence = 1.0
        _insert_annotation(
            in_memory_session,
            severity=severity,
            confidence=confidence,
        )

        features = get_structural_variance(in_memory_session, EDGE_ID)
        expected = config.SIGMA_SQ_STRUCTURAL_DEFAULT + expected_weight * confidence
        assert features.sigma_sq_structural == pytest.approx(expected, abs=1e-9)

    def test_unknown_severity_falls_back_to_moderate(
        self, in_memory_session: Session
    ):
        """Unknown severity string → uses 'moderate' weight (0.05)."""
        _insert_annotation(
            in_memory_session,
            severity="unknown_level",
            confidence=1.0,
        )

        features = get_structural_variance(in_memory_session, EDGE_ID)
        # Falls back to 0.05 (moderate default in ANNOTATION_SEVERITY_WEIGHTS.get())
        expected = config.SIGMA_SQ_STRUCTURAL_DEFAULT + 0.05 * 1.0
        assert features.sigma_sq_structural == pytest.approx(expected, abs=1e-9)

    def test_missing_severity_falls_back(
        self, in_memory_session: Session
    ):
        """No severity in structured_data_json → uses 'moderate' default."""
        ann = StudyAnnotations(
            annotation_id="ann-no-severity",
            study_id="study-test",
            category="LIMITATION_UNMEASURED_CONFOUNDER",
            content="Some confounder",
            target_entity_type="edge",
            target_entity_id=EDGE_ID,
            structured_data_json=json.dumps({}),  # No severity key
            reconciled_confidence=1.0,
            maturity="promoted",
            promoted_to="sigma_structural",
            consumer="sigma_structural",
            active=True,
            cross_agent_support_n=1,
            adjudication_status="unreviewed",
        )
        in_memory_session.add(ann)
        in_memory_session.flush()

        features = get_structural_variance(in_memory_session, EDGE_ID)
        expected = config.SIGMA_SQ_STRUCTURAL_DEFAULT + 0.05 * 1.0
        assert features.sigma_sq_structural == pytest.approx(expected, abs=1e-9)
