"""
Tests for R5 LLM Guardrails.

Covers:
- R5.1: UG-05 figure-only block
- R5.2: UG-08 sensitivity analysis flagging
- R5.3: MG-04 umbrella numeric rejection at TB
- R5.4: PG-01 RCT randomization verification
- R5.5: PG-04 animal species documentation (warn-log)
- R5.6: MG-02 random-effects default
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock


# ═══════════════════════════════════════════════════════════════
#  R5.1: UG-05 — FIGURE-ONLY BLOCK
# ═══════════════════════════════════════════════════════════════


def test_figure_only_blocked():
    """UG-05: Spans sourced only from figures are blocked."""
    from crci.extraction.tb_trust_boundary.runner import _check_figure_only

    span = MagicMock()
    span.source_section = "Figure 3"
    span.value = "0.45"
    assert _check_figure_only(span) is True


def test_figure_with_table_not_blocked():
    """UG-05: Figure + table reference is NOT blocked."""
    from crci.extraction.tb_trust_boundary.runner import _check_figure_only

    span = MagicMock()
    span.source_section = "Table 2 (see also Figure 3)"
    span.value = "0.45"
    assert _check_figure_only(span) is False


def test_no_figure_not_blocked():
    """UG-05: Regular text source is NOT blocked."""
    from crci.extraction.tb_trust_boundary.runner import _check_figure_only

    span = MagicMock()
    span.source_section = "Results section"
    span.value = "p=0.03"
    assert _check_figure_only(span) is False


def test_empty_source_not_blocked():
    """UG-05: Empty source section is NOT blocked."""
    from crci.extraction.tb_trust_boundary.runner import _check_figure_only

    span = MagicMock()
    span.source_section = None
    span.value = None
    assert _check_figure_only(span) is False


# ═══════════════════════════════════════════════════════════════
#  R5.2: UG-08 — SENSITIVITY ANALYSIS FLAGGING
# ═══════════════════════════════════════════════════════════════


def test_sensitivity_analysis_flagged():
    """UG-08: Sensitivity analysis span is flagged."""
    from crci.extraction.tb_trust_boundary.runner import _flag_sensitivity_analysis

    span = MagicMock()
    span.source_section = "sensitivity analysis"
    span.value = "0.32"
    assert _flag_sensitivity_analysis(span) is True


def test_robustness_check_flagged():
    """UG-08: Robustness check span is flagged."""
    from crci.extraction.tb_trust_boundary.runner import _flag_sensitivity_analysis

    span = MagicMock()
    span.source_section = "robustness check results"
    span.value = None
    assert _flag_sensitivity_analysis(span) is True


def test_primary_result_not_flagged():
    """UG-08: Primary result is NOT flagged."""
    from crci.extraction.tb_trust_boundary.runner import _flag_sensitivity_analysis

    span = MagicMock()
    span.source_section = "Results"
    span.value = "β=0.45"
    assert _flag_sensitivity_analysis(span) is False


def test_leave_one_out_flagged():
    """UG-08: Leave-one-out analysis span is flagged."""
    from crci.extraction.tb_trust_boundary.runner import _flag_sensitivity_analysis

    span = MagicMock()
    span.source_section = "leave-one-out sensitivity"
    span.value = None
    assert _flag_sensitivity_analysis(span) is True


# ═══════════════════════════════════════════════════════════════
#  R5.4: PG-01 — RCT RANDOMIZATION VERIFICATION
# ═══════════════════════════════════════════════════════════════


def test_rct_with_randomization_identified():
    """PG-01: RCT with randomization language is identified."""
    from crci.extraction.p2_harmonization.runner import _verify_rct_randomization
    from crci.shared.models.enums import PaperSubtype

    result = _verify_rct_randomization(
        PaperSubtype.RCT_EXERCISE.value,
        "Participants were randomly assigned to exercise or control."
    )
    assert result == "identified"


def test_rct_without_randomization_demoted():
    """PG-01: RCT without randomization language is demoted."""
    from crci.extraction.p2_harmonization.runner import _verify_rct_randomization
    from crci.shared.models.enums import PaperSubtype

    result = _verify_rct_randomization(
        PaperSubtype.RCT_EXERCISE.value,
        "Participants were assigned to the exercise group."
    )
    assert result == "partially_identified"


def test_rct_british_spelling_identified():
    """PG-01: British spelling 'randomised' is accepted."""
    from crci.extraction.p2_harmonization.runner import _verify_rct_randomization
    from crci.shared.models.enums import PaperSubtype

    result = _verify_rct_randomization(
        PaperSubtype.STANDARD_RCT.value,
        "A randomised controlled trial of cognitive intervention."
    )
    assert result == "identified"


def test_non_rct_subtype_returns_identified():
    """PG-01: Non-RCT subtypes always return identified."""
    from crci.extraction.p2_harmonization.runner import _verify_rct_randomization
    from crci.shared.models.enums import PaperSubtype

    result = _verify_rct_randomization(PaperSubtype.META_ANALYSIS.value, "Some text.")
    assert result == "identified"


# ═══════════════════════════════════════════════════════════════
#  R5.6: MG-02 — RANDOM-EFFECTS DEFAULT
# ═══════════════════════════════════════════════════════════════


def test_mg02_both_re_and_fe_flags():
    """MG-02: When both RE and FE mentioned, flag RE preferred."""
    from crci.extraction.p1_extraction.ma_multi_product import (
        enforce_random_effects_default,
    )

    row = {"random_effects_structure": "fixed effect"}
    result = enforce_random_effects_default(
        row, notes="Both random effects and fixed effect models reported."
    )
    assert result.get("mg02_re_preferred") is True


def test_mg02_only_fe_no_flag():
    """MG-02: When only FE mentioned, no RE preference flag."""
    from crci.extraction.p1_extraction.ma_multi_product import (
        enforce_random_effects_default,
    )

    row = {"random_effects_structure": "fixed effect"}
    result = enforce_random_effects_default(
        row, notes="Used fixed effect model."
    )
    assert result.get("mg02_re_preferred") is False


def test_mg02_only_re_no_flag():
    """MG-02: When only RE mentioned, no flag set."""
    from crci.extraction.p1_extraction.ma_multi_product import (
        enforce_random_effects_default,
    )

    row = {"random_effects_structure": "random effects (DerSimonian-Laird)"}
    result = enforce_random_effects_default(row, notes="Random effects model used.")
    # Both conditions match (random in structure, random in notes)
    # but fixed is absent, so no flag
    assert "mg02_re_preferred" not in result
