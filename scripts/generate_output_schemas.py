#!/usr/bin/env python3
"""Generate JSON Schema artifacts from Pydantic output contracts.

Run after ANY change to output_contracts.py to keep committed schemas in sync.
CI can validate that generated schemas match committed files (drift detection).

Usage:
    python scripts/generate_output_schemas.py

Output:
    docs/outputs/schemas/recommendation_report_v{VERSION}.schema.json
    docs/outputs/schemas/clinical_risk_profile_v1.0.schema.json
    docs/outputs/schemas/subpopulation_comparison_v1.0.schema.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure project root is importable
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from crci.shared import config
from crci.shared.models.output_contracts import (
    ClinicalRiskProfile,
    RecommendationReport,
    SubpopulationComparisonSummary,
)


SCHEMA_DIR = project_root / "docs" / "outputs" / "schemas"

MODELS = [
    (
        RecommendationReport,
        "recommendation_report_v1.1.0.schema.json",
    ),
    (
        ClinicalRiskProfile,
        "clinical_risk_profile_v1.0.schema.json",
    ),
    (
        SubpopulationComparisonSummary,
        "subpopulation_comparison_v1.0.schema.json",
    ),
]


def main() -> None:
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)

    for model_cls, filename in MODELS:
        schema = model_cls.model_json_schema()
        path = SCHEMA_DIR / filename
        path.write_text(json.dumps(schema, indent=2) + "\n")
        print(f"  wrote {path.relative_to(project_root)}")

    print(f"\n{len(MODELS)} schemas written to {SCHEMA_DIR.relative_to(project_root)}/")


if __name__ == "__main__":
    main()
