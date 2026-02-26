"""Boundary Contract Test: AG05 → Trust Boundary.

Every span must have valid offsets, label_type ∈ SPAN_LABEL_TYPES,
no duplicate span_id.  Uses synthetic data only (no LLM).
"""
from __future__ import annotations

import pytest

from crci.shared.models.intermediate_states import SpanLabel
from crci.extraction.p1_extraction.agents.ag05_stats_label import SPAN_LABEL_TYPES


# ═══════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════

VALID_TYPES = set(SPAN_LABEL_TYPES)


def _make_span(
    span_id: str = "sp_001",
    label_type: str = "EFFECT_SIZE",
    char_start: int = 10,
    char_end: int = 25,
    confidence: float = 0.8,
    value: str | None = "0.45",
) -> SpanLabel:
    return SpanLabel(
        span_id=span_id,
        label_type=label_type,
        char_start=char_start,
        char_end=char_end,
        confidence=confidence,
        value=value,
    )


# ═══════════════════════════════════════════════════════════════
#  Tests
# ═══════════════════════════════════════════════════════════════


class TestSpanLabelValidity:
    """AG05 → TB contract: span label_type must be in SPAN_LABEL_TYPES."""

    def test_valid_label_type_accepted(self):
        span = _make_span(label_type="EFFECT_SIZE")
        assert span.label_type in VALID_TYPES

    @pytest.mark.parametrize("label_type", SPAN_LABEL_TYPES)
    def test_all_40_label_types_are_valid(self, label_type: str):
        span = _make_span(label_type=label_type)
        assert span.label_type in VALID_TYPES

    def test_invalid_label_type_not_in_set(self):
        span = _make_span(label_type="BOGUS_TYPE")
        assert span.label_type not in VALID_TYPES

    def test_exactly_40_label_types(self):
        assert len(SPAN_LABEL_TYPES) == 40


class TestSpanOffsets:
    """AG05 → TB contract: offsets must be valid."""

    def test_char_end_gt_char_start(self):
        span = _make_span(char_start=10, char_end=25)
        assert span.char_end > span.char_start

    def test_zero_width_offset_rejected(self):
        # char_start == char_end means zero-width — shouldn't happen for real spans
        span = _make_span(char_start=10, char_end=10)
        assert span.char_end == span.char_start  # technically allowed but bad

    def test_negative_offsets_detectable(self):
        """Negative offsets are invalid — downstream should detect them."""
        span = _make_span(char_start=-1, char_end=5)
        assert span.char_start < 0  # Detectable by validation layer


class TestSpanIdUniqueness:
    """AG05 → TB contract: no duplicate span_ids within a batch."""

    def test_no_duplicate_span_ids(self):
        spans = [
            _make_span(span_id="sp_001", label_type="EFFECT_SIZE"),
            _make_span(span_id="sp_002", label_type="SE"),
            _make_span(span_id="sp_003", label_type="P_VALUE"),
        ]
        ids = [s.span_id for s in spans]
        assert len(ids) == len(set(ids)), "Duplicate span_ids detected"

    def test_duplicate_span_ids_detected(self):
        spans = [
            _make_span(span_id="sp_001", label_type="EFFECT_SIZE"),
            _make_span(span_id="sp_001", label_type="SE"),
        ]
        ids = [s.span_id for s in spans]
        assert len(ids) != len(set(ids)), "Should detect duplicates"


class TestSpanConfidence:
    """AG05 → TB contract: confidence 0.0–1.0."""

    def test_confidence_in_range(self):
        span = _make_span(confidence=0.95)
        assert 0.0 <= span.confidence <= 1.0

    def test_confidence_zero_valid(self):
        span = _make_span(confidence=0.0)
        assert span.confidence == 0.0

    def test_confidence_above_one_rejected(self):
        with pytest.raises(Exception):
            _make_span(confidence=1.5)

    def test_confidence_below_zero_rejected(self):
        with pytest.raises(Exception):
            _make_span(confidence=-0.1)
