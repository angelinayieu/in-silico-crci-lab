"""
EX-P2: Harmonization & Gating Pipeline.

7-stage pipeline (S1-S7) for harmonizing evidence records:
    S1: Plausibility Check (Gate P2-G1)
    S2: Conversion Appropriateness (CG1-CG4)
    S3: Scale Harmonization
    S4: Orientation Alignment (Gate P2-G2)
    S5: Identification Status Assignment
    S6: Scope Matching (separate module)
    S7: Composability Check (separate module)
"""
from crci.extraction.p2_harmonization.plausibility_checker import (
    check_plausibility,
    check_plausibility_batch,
)
from crci.extraction.p2_harmonization.conversion_router import (
    route_conversion,
    route_conversion_batch,
)
from crci.extraction.p2_harmonization.scale_harmonizer import (
    harmonize_scale,
    convert_correlation_to_d,
    SDAnchor,
)
from crci.extraction.p2_harmonization.orientation_aligner import (
    align_orientation,
    align_orientation_batch,
)
from crci.extraction.p2_harmonization.identification_scorer import (
    score_identification,
    score_identification_batch,
    IdentificationResult,
)

__all__ = [
    # S1
    "check_plausibility",
    "check_plausibility_batch",
    # S2
    "route_conversion",
    "route_conversion_batch",
    # S3
    "harmonize_scale",
    "convert_correlation_to_d",
    "SDAnchor",
    # S4
    "align_orientation",
    "align_orientation_batch",
    # S5
    "score_identification",
    "score_identification_batch",
    "IdentificationResult",
]
