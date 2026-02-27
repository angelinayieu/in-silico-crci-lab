"""
Production entry-point for the CRCI Presentation Layer.

Renders a RecommendationReport via either:
  1. Terminal (ASCII rich text)  — default
  2. JSON export                 — --format json
  3. Both                        — --format all

Usage:
    # From a saved report JSON:
    python -m crci.presentation.render_report --input report.json

    # Sections filter:
    python -m crci.presentation.render_report --input report.json --sections score,risk,evidence

    # JSON export:
    python -m crci.presentation.render_report --input report.json --format json --output report_out.json

    # Render specific view branch:
    python -m crci.presentation.render_report --input report.json --branch patient
    python -m crci.presentation.render_report --input report.json --branch scientist
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from crci.shared.models.output_contracts import RecommendationReport

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  Section → branch mapping (output_mode gating)
# ═══════════════════════════════════════════════════════════════

PATIENT_SECTIONS = ["score", "interventions", "pathways", "uncertainty", "quality"]
SCIENTIST_SECTIONS = ["score", "interventions", "pathways", "uncertainty", "risk", "evidence", "quality"]
ALL_SECTIONS = ["score", "interventions", "pathways", "uncertainty", "risk", "evidence", "quality"]

BRANCH_MAP = {
    "patient": PATIENT_SECTIONS,
    "scientist": SCIENTIST_SECTIONS,
    "all": ALL_SECTIONS,
}


def _resolve_sections(
    branch: str | None,
    sections_csv: str | None,
    output_mode: str | None,
) -> list[str]:
    """Determine which sections to render based on branch, explicit sections, or output_mode."""
    if sections_csv:
        return [s.strip() for s in sections_csv.split(",") if s.strip()]
    if branch:
        return BRANCH_MAP.get(branch, ALL_SECTIONS)
    # Auto-gate by output_mode from the report
    if output_mode and output_mode.upper() == "CLINICAL":
        return PATIENT_SECTIONS
    return ALL_SECTIONS


def render_from_json(
    input_path: str,
    output_format: str = "terminal",
    output_path: str | None = None,
    sections: list[str] | None = None,
) -> str | dict:
    """Load a RecommendationReport from JSON and render it.

    Args:
        input_path: Path to a JSON file containing a serialized RecommendationReport.
        output_format: "terminal", "json", or "all".
        output_path: Optional path to write output to file.
        sections: Optional list of section names to include.

    Returns:
        Rendered string (terminal) or dict (json).
    """
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Report file not found: {input_path}")

    with open(path) as f:
        data = json.load(f)

    report = RecommendationReport.model_validate(data)
    return render_report(report, output_format, output_path, sections)


def render_report(
    report: RecommendationReport,
    output_format: str = "terminal",
    output_path: str | None = None,
    sections: list[str] | None = None,
) -> str | dict:
    """Render a RecommendationReport.

    Args:
        report: The report object.
        output_format: "terminal", "json", or "all".
        output_path: Optional path to write output to file.
        sections: Optional list of section names to include.

    Returns:
        Rendered string (terminal) or dict (json).
    """
    result: str | dict = ""

    if output_format in ("terminal", "all"):
        from crci.presentation.terminal_renderer import render_terminal_report

        text = render_terminal_report(report, sections=sections)
        if output_format == "terminal":
            result = text
        if output_path and output_format == "terminal":
            Path(output_path).write_text(text, encoding="utf-8")
            logger.info("Terminal report written to %s", output_path)
        else:
            print(text)

    if output_format in ("json", "all"):
        report_dict = json.loads(report.model_dump_json(indent=2))
        if output_format == "json":
            result = report_dict
        if output_path:
            out = Path(output_path)
            if output_format == "all":
                out = out.with_suffix(".json")
            out.write_text(json.dumps(report_dict, indent=2), encoding="utf-8")
            logger.info("JSON report written to %s", out)
        elif output_format == "json":
            print(json.dumps(report_dict, indent=2))

    return result


# ═══════════════════════════════════════════════════════════════
#  View-model export (individual presentation modules)
# ═══════════════════════════════════════════════════════════════

def export_view_models(report: RecommendationReport) -> dict[str, dict]:
    """Run all presentation modules and export their view-models as dicts.

    This is the bridge from RecommendationReport → per-module JSON.
    Useful for API responses or frontend consumption.
    """
    views: dict[str, dict] = {}

    _module_map = {
        "score_dashboard": "crci.presentation.crci_dashboard",
        "intervention_cards": "crci.presentation.intervention_cards",
        "pathway_display": "crci.presentation.pathway_display",
        "uncertainty_panel": "crci.presentation.variance_pie",
        "risk_dashboard": "crci.presentation.risk_dashboard",
        "evidence_browser": "crci.presentation.evidence_browser",
        "quality_disclosure": "crci.presentation.quality_disclosure",
        "provenance_viewer": "crci.presentation.provenance_viewer",
        "model_inspection": "crci.presentation.model_inspection",
        "research_dashboard": "crci.presentation.research_dashboard",
        "trajectory_plot": "crci.presentation.trajectory_plot",
    }

    _render_fn_map = {
        "score_dashboard": "render_score_dashboard",
        "intervention_cards": "render_intervention_cards",
        "pathway_display": "render_pathway_display",
        "uncertainty_panel": "render_uncertainty_panel",
        "risk_dashboard": "render_risk_dashboard",
        "evidence_browser": "render_evidence_browser",
        "quality_disclosure": "render_quality_disclosure",
        "provenance_viewer": "render_provenance_chain",
        "model_inspection": "render_model_inspection",
        "research_dashboard": "render_research_dashboard",
        "trajectory_plot": "render_trajectory_chart",
    }

    import importlib

    for key, module_path in _module_map.items():
        fn_name = _render_fn_map[key]
        try:
            mod = importlib.import_module(module_path)
            fn = getattr(mod, fn_name)
            view = fn(report)
            # Pydantic or dataclass → dict
            if hasattr(view, "model_dump"):
                views[key] = view.model_dump()
            elif hasattr(view, "__dict__"):
                views[key] = view.__dict__
            else:
                views[key] = {"raw": str(view)}
        except Exception as exc:
            views[key] = {"error": str(exc), "available": False}
            logger.debug("View '%s' not available: %s", key, exc)

    return views


# ═══════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="CRCI Presentation Layer — render a RecommendationReport",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to a JSON file containing a serialized RecommendationReport",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["terminal", "json", "all"],
        default="terminal",
        help="Output format (default: terminal)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Write output to file instead of stdout",
    )
    parser.add_argument(
        "--sections", "-s",
        default=None,
        help="Comma-separated section names: score,interventions,pathways,uncertainty,risk,evidence,quality",
    )
    parser.add_argument(
        "--branch", "-b",
        choices=["patient", "scientist", "all"],
        default=None,
        help="Render only patient-facing or scientist-facing sections (auto-selects sections)",
    )
    parser.add_argument(
        "--view-models",
        action="store_true",
        help="Export all view-model JSON from all presentation modules",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    # Load report
    path = Path(args.input)
    if not path.exists():
        print(f"Error: file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    with open(path) as f:
        data = json.load(f)

    report = RecommendationReport.model_validate(data)

    # View-model export mode
    if args.view_models:
        views = export_view_models(report)
        out = json.dumps(views, indent=2, default=str)
        if args.output:
            Path(args.output).write_text(out, encoding="utf-8")
            print(f"View models written to {args.output}")
        else:
            print(out)
        return

    # Resolve sections
    output_mode = getattr(report, "output_mode", None)
    mode_str = output_mode.value if output_mode else None
    sections = _resolve_sections(args.branch, args.sections, mode_str)

    render_report(report, args.format, args.output, sections)


if __name__ == "__main__":
    main()
