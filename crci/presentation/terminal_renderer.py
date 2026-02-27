"""
Terminal renderer for CRCI presentation layer.

Wires all 12 presentation view-model modules into a human-readable
terminal output. Produces a rich ASCII report from a RecommendationReport.

Usage:
    from crci.presentation.terminal_renderer import render_terminal_report
    render_terminal_report(report)
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Formatting helpers
# ═══════════════════════════════════════════════════════════════

_WIDTH = 72

def _header(title: str) -> str:
    return f"\n{'━' * _WIDTH}\n  {title}\n{'━' * _WIDTH}"

def _subheader(title: str) -> str:
    return f"\n  ── {title} {'─' * max(1, _WIDTH - len(title) - 6)}"

def _bar(value: float, max_val: float = 1.0, width: int = 30) -> str:
    """Render a horizontal bar chart character."""
    filled = int(round((abs(value) / max(max_val, 0.001)) * width))
    filled = min(filled, width)
    if value >= 0:
        return "▓" * filled + "░" * (width - filled)
    else:
        empty = width - filled
        return "░" * empty + "▓" * filled

def _severity_icon(tier: str) -> str:
    tier_upper = tier.upper() if tier else ""
    icons = {
        "NORMAL": "🟢",
        "MILD_IMPAIRMENT": "🟡",
        "MODERATE_IMPAIRMENT": "🟠",
        "SEVERE_IMPAIRMENT": "🔴",
    }
    return icons.get(tier_upper, "⚪")

def _color_marker(color: str) -> str:
    markers = {
        "green": "🟢", "yellow": "🟡", "orange": "🟠",
        "red": "🔴", "blue": "🔵", "slate": "⚪",
    }
    return markers.get(color, "⚪")


# ═══════════════════════════════════════════════════════════════
#  Section renderers — each calls one presentation module
# ═══════════════════════════════════════════════════════════════

def _render_score_dashboard(report: Any) -> str:
    """Section 1: CRCI Composite Score Dashboard."""
    try:
        from crci.presentation.crci_dashboard import render_score_dashboard
        view = render_score_dashboard(report)
    except Exception as exc:
        return f"  [Score dashboard unavailable: {exc}]"

    if view.empty_state:
        return f"  {view.empty_message}"

    lines = [_header("CRCI COMPOSITE SCORE")]
    icon = _severity_icon(view.severity_tier)
    lines.append(f"  {icon} Composite Z-score:  {view.composite_z:+.3f}")
    lines.append(f"     Severity tier:    {view.severity_tier}")
    lines.append(f"     Percentile:       {view.percentile_text}")
    if view.delta_text:
        lines.append(f"     Change:           {view.delta_text}")

    if view.domain_bars:
        lines.append(_subheader("Domain Breakdown"))
        max_z = max(abs(d.z_score) for d in view.domain_bars) or 1.0
        for d in sorted(view.domain_bars, key=lambda x: x.z_score):
            bar = _bar(d.z_score, max_z, 25)
            marker = _color_marker(d.color)
            lines.append(
                f"  {marker} {d.domain_label:22s} {d.z_score:+6.2f}  {bar}"
            )

    return "\n".join(lines)


def _render_intervention_cards(report: Any) -> str:
    """Section 2: Top Intervention Recommendations."""
    try:
        from crci.presentation.intervention_cards import render_intervention_cards
        view = render_intervention_cards(report, max_display=5)
    except Exception as exc:
        return f"  [Intervention cards unavailable: {exc}]"

    if view.empty_state:
        return f"  {view.empty_message}"

    lines = [_header("TOP INTERVENTIONS")]
    lines.append(f"  Showing {view.showing} of {view.n_total} ranked interventions\n")

    for card in view.cards:
        rank_icon = "🥇🥈🥉"[card.rank - 1] if card.rank <= 3 else f"#{card.rank}"
        bundle_tag = " [BUNDLE]" if card.is_bundle else ""
        lines.append(f"  {rank_icon} {card.action_label}{bundle_tag}")
        lines.append(f"     Expected benefit: {card.expected_benefit_text}")
        lines.append(f"     Credible range:   {card.cri_text}")
        lines.append(f"     Claim level:      {_color_marker(card.claim_color)} {card.claim_level}")
        lines.append(f"     Stability:        {card.stability_indicator}")
        if card.dose_text:
            lines.append(f"     Dose:             {card.dose_text}")
        if card.duration_text:
            lines.append(f"     Duration:         {card.duration_text}")
        if card.bundle_members:
            lines.append(f"     Components:       {', '.join(card.bundle_members)}")
        lines.append("")

    return "\n".join(lines)


def _render_pathway_display(report: Any) -> str:
    """Section 3: Pathway Activation Heatmap."""
    try:
        from crci.presentation.pathway_display import render_pathway_display
        view = render_pathway_display(report)
    except Exception as exc:
        return f"  [Pathway display unavailable: {exc}]"

    if view.empty_state:
        return f"  {view.empty_message}"

    lines = [_header("PATHWAY ACTIVATION PROFILE")]
    lines.append(f"  Dominant pathway:  {view.dominant_pathway or 'none'}")
    lines.append(f"  Dysregulated:      {view.n_dysregulated}/{view.n_total}")
    lines.append(f"  Reference:         {view.reference_population}")
    lines.append("")

    if view.rows:
        max_z = max(abs(r.activation_z) for r in view.rows) or 1.0
        for r in sorted(view.rows, key=lambda x: -abs(x.activation_z)):
            flag = "⚠" if r.dysregulation_flag else " "
            bar = _bar(r.activation_z, max_z, 20)
            lines.append(
                f"  {flag} {r.pathway_label:28s} {r.direction}{abs(r.activation_z):5.2f}  "
                f"{_color_marker(r.color)}  {bar}"
            )

    return "\n".join(lines)


def _render_uncertainty_panel(report: Any) -> str:
    """Section 4: Uncertainty / Variance Decomposition."""
    try:
        from crci.presentation.variance_pie import render_uncertainty_panel
        view = render_uncertainty_panel(report)
    except Exception as exc:
        return f"  [Uncertainty panel unavailable: {exc}]"

    if view.empty_state:
        return f"  {view.empty_message}"

    lines = [_header("UNCERTAINTY ANALYSIS")]
    lines.append(f"  {view.confidence_statement}")
    lines.append(f"  Stability: {view.stability_class} (P(rank=1) = {view.p_rank_1:.1%})")
    if view.warning_banner:
        lines.append(f"  ⚠ {view.warning_banner}")
    lines.append("")

    if view.pie_slices:
        lines.append(_subheader("Variance Sources"))
        for s in sorted(view.pie_slices, key=lambda x: -x.fraction):
            pct = f"{s.fraction:.0%}"
            bar = "█" * int(s.fraction * 30) + "░" * (30 - int(s.fraction * 30))
            lines.append(f"  {s.label:24s} {pct:>5s}  {bar}")
        lines.append(f"\n  → {view.actionable_message}")

    return "\n".join(lines)


def _render_risk_dashboard(report: Any) -> str:
    """Section 5: Clinical Risk Assessment."""
    try:
        from crci.presentation.risk_dashboard import render_risk_dashboard
        view = render_risk_dashboard(report)
    except Exception as exc:
        return f"  [Risk dashboard unavailable: {exc}]"

    if view.empty_state:
        return f"  {view.empty_message}"

    g = view.gauge
    lines = [_header("CLINICAL RISK ASSESSMENT")]
    lines.append(f"  {_color_marker(g.tier_color)} Overall CRCI Risk: {g.risk_pct:.0f}%")
    lines.append(f"     Risk tier:          {g.risk_tier}")
    lines.append(f"     Range:              {g.risk_range_text}")
    lines.append(f"     Method:             {g.interval_method_label}")
    lines.append(f"     Criteria:           {g.criteria_label}")

    if view.domain_risk_bars:
        lines.append(_subheader("Domain-Level Risk"))
        for d in sorted(view.domain_risk_bars, key=lambda x: -x.marginal_risk_pct):
            obs = "📊" if d.is_observed else "📐"
            bar = _bar(d.marginal_risk_pct, 100.0, 20)
            lines.append(
                f"  {obs} {d.domain_label:22s} {d.marginal_risk_pct:5.1f}%  {bar}  "
                f"(z̄={d.mean_z:+.2f})"
            )

    c = view.coverage
    lines.append(f"\n  Coverage: {c.n_observed}/{c.n_total} domains observed ({c.coverage_pct:.0f}%)")
    if c.show_warning:
        lines.append(f"  ⚠ {c.warning_text}")

    return "\n".join(lines)


def _render_evidence_browser(report: Any) -> str:
    """Section 6: Evidence Gap Browser."""
    try:
        from crci.presentation.evidence_browser import render_evidence_browser
        view = render_evidence_browser(report)
    except Exception as exc:
        return f"  [Evidence browser unavailable: {exc}]"

    if view.empty_state:
        return f"  {view.empty_message}"

    lines = [_header("EVIDENCE GAP ANALYSIS")]
    lines.append(f"  {view.gap_summary}")
    lines.append(f"  Total edges: {view.n_total}  |  Gaps: {view.n_gaps}")
    lines.append("")

    # Show top 10 gaps by discovery score
    gaps = [r for r in view.rows if r.has_evidence_gap]
    for r in gaps[:10]:
        ds = f"DS={r.discovery_score:.2f}" if r.discovery_score else ""
        lines.append(
            f"  {_color_marker(r.severity_color)} {r.edge_label:35s} "
            f"{r.severity:12s} {ds}"
        )

    if len(gaps) > 10:
        lines.append(f"  ... and {len(gaps) - 10} more")

    return "\n".join(lines)


def _render_quality_disclosure(report: Any) -> str:
    """Section 7: Quality & Completeness Disclosure."""
    try:
        from crci.presentation.quality_disclosure import render_quality_disclosure
        view = render_quality_disclosure(report)
    except Exception as exc:
        return f"  [Quality disclosure unavailable: {exc}]"

    if view.empty_state:
        return f"  {view.empty_message}"

    lines = [_header("QUALITY & COMPLETENESS")]
    lines.append(
        f"  {_color_marker(view.tier_color)} Quality Tier: {view.quality_tier}  "
        f"({view.completeness_pct}% complete)"
    )
    lines.append(f"  Studies contributing: {view.study_count}")
    lines.append(f"  {view.overall_message}")

    if view.defaults_summary:
        lines.append(_subheader("Defaults Used"))
        for d in view.defaults_summary:
            lines.append(f"  • {d.label} ({d.layer}): {d.count} edges — {d.caveat}")

    if view.missing_data_warnings:
        lines.append(_subheader("Missing Data"))
        for w in view.missing_data_warnings:
            lines.append(f"  ⚠ {w}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
#  Main entry point
# ═══════════════════════════════════════════════════════════════

def render_terminal_report(report: Any, sections: list[str] | None = None) -> str:
    """Render a RecommendationReport as a formatted terminal string.

    Args:
        report: A RecommendationReport (or compatible object).
        sections: Optional list of section names to include.
                  Default: all sections.

    Available sections:
        score, interventions, pathways, uncertainty,
        risk, evidence, quality

    Returns:
        Formatted multi-line string suitable for terminal output.
    """
    all_sections = {
        "score": _render_score_dashboard,
        "interventions": _render_intervention_cards,
        "pathways": _render_pathway_display,
        "uncertainty": _render_uncertainty_panel,
        "risk": _render_risk_dashboard,
        "evidence": _render_evidence_browser,
        "quality": _render_quality_disclosure,
    }

    if sections is None:
        sections = list(all_sections.keys())

    parts = []
    parts.append(f"\n{'╔' + '═' * (_WIDTH - 2) + '╗'}")
    parts.append(f"{'║'} {'CRCI CLINICAL REPORT':^{_WIDTH - 4}} {'║'}")
    run_id = getattr(report, "run_id", "?")
    subject = getattr(report, "subject_ref", "?")
    parts.append(f"{'║'} {'Patient: ' + subject:^{_WIDTH - 4}} {'║'}")
    parts.append(f"{'╚' + '═' * (_WIDTH - 2) + '╝'}")

    for name in sections:
        renderer = all_sections.get(name)
        if renderer is None:
            parts.append(f"\n  [Unknown section: {name}]")
            continue
        try:
            rendered = renderer(report)
            parts.append(rendered)
        except Exception as exc:
            logger.warning("Renderer '%s' failed: %s", name, exc)
            parts.append(f"\n  [{name} section failed: {exc}]")

    # Safety flags
    safety_flags = getattr(report, "safety_flags", [])
    if safety_flags:
        parts.append(_header("SAFETY FLAGS"))
        for flag in safety_flags:
            parts.append(f"  🚨 {flag}")

    # Warnings
    warnings = getattr(report, "run_warnings", [])
    if warnings:
        parts.append(_subheader("Run Warnings"))
        for w in warnings:
            parts.append(f"  ⚠ {w}")

    parts.append(f"\n{'─' * _WIDTH}")
    ts = getattr(report, "timestamp", None) or "unknown"
    ver = getattr(report, "engine_version", None) or "dev"
    parts.append(f"  Generated: {ts}  |  Engine: {ver}")
    parts.append(f"{'─' * _WIDTH}\n")

    return "\n".join(parts)
