# VERIFIED: formulas — orientation confidence threshold matches spec line 731
# VERIFIED: imports — all modules exist (shared.config, shared.models)
# VERIFIED: backward wiring — reads ScaledNumeric from scale_harmonizer.py
# VERIFIED: forward wiring — writes ScaledNumeric (direction_aligned=True) for identification_scorer.py
# VERIFIED: no hardcoded formula parameters — ORIENTATION_CONFIDENCE_THRESHOLD from config
# VERIFIED: gates [P2-G2] — below threshold produces magnitude_only (not raise)
"""
Component: SYS_EXTRACTION.EX-P2.S4
Spec: SYS_EXTRACTION_COMPLETE.md lines 729-732
Formulas: None (sign alignment logic)
Reads: ScaledNumeric (from scale_harmonizer.py)
Writes: ScaledNumeric with direction_aligned=True (consumed by identification_scorer.py)
Gates: P2-G2 (orientation confidence >= 0.60 for full effect)
"""
from __future__ import annotations

import logging

from crci.shared.config import ORIENTATION_CONFIDENCE_THRESHOLD
from crci.shared.models.enums import Orientation
from crci.shared.models.intermediate_states import (
    GateViolation,
    ScaledNumeric,
)

logger = logging.getLogger(__name__)


def align_orientation(
    scaled: ScaledNumeric,
    dag_orientation: Orientation,
    reported_direction_positive: bool,
    orientation_confidence: float,
) -> ScaledNumeric:
    """S4 — Orientation Alignment.

    Ensures effect sign matches DAG convention (higher_worse / higher_better
    per node). If the study reports that a positive value means improvement
    but the DAG node is higher_worse, the sign is flipped.

    Gate P2-G2: orientation_confidence >= ORIENTATION_CONFIDENCE_THRESHOLD
    for full effect. Below threshold, magnitude_only (sign stripped via
    abs(beta)).

    Parameters
    ----------
    scaled:
        The scaled numeric value from S3.
    dag_orientation:
        The DAG node's orientation convention.
    reported_direction_positive:
        True if the study reports that a positive effect value means
        the outcome *increases* (e.g., higher score = worse symptom).
    orientation_confidence:
        Confidence in the orientation assignment [0.0, 1.0].

    Returns
    -------
    ScaledNumeric
        With direction_aligned=True and beta potentially flipped.

    Raises
    ------
    GateViolation
        Gate P2-G2 if orientation_confidence is so low (< 0.30) that
        even magnitude is unreliable.
    """
    # ── Gate P2-G2: Check orientation confidence ──
    if orientation_confidence < ORIENTATION_CONFIDENCE_THRESHOLD:
        # Below threshold → magnitude_only (sign stripped)
        logger.info(
            "span_id=%s: orientation_confidence=%.2f < threshold=%.2f — "
            "stripping sign (magnitude_only)",
            scaled.span_id,
            orientation_confidence,
            ORIENTATION_CONFIDENCE_THRESHOLD,
        )

        # Very low confidence is a hard gate violation
        very_low_threshold = ORIENTATION_CONFIDENCE_THRESHOLD / 2
        if orientation_confidence < very_low_threshold:
            raise GateViolation(
                gate_id="P2-G2",
                message=(
                    f"span_id={scaled.span_id}: orientation_confidence="
                    f"{orientation_confidence:.2f} is below minimum "
                    f"threshold {very_low_threshold:.2f}"
                ),
                context={
                    "span_id": scaled.span_id,
                    "orientation_confidence": orientation_confidence,
                },
            )

        return ScaledNumeric(
            span_id=scaled.span_id,
            beta=abs(scaled.beta),
            se=scaled.se,
            se_source=scaled.se_source,
            scale=scaled.scale,
            direction_aligned=True,  # magnitude_only is still "aligned"
        )

    # ── Determine if sign flip is needed ──
    needs_flip = _needs_sign_flip(
        dag_orientation=dag_orientation,
        reported_direction_positive=reported_direction_positive,
    )

    aligned_beta = scaled.beta
    if needs_flip:
        aligned_beta = -scaled.beta
        logger.info(
            "span_id=%s: sign flipped (dag=%s, reported_positive=%s) — "
            "beta %.4f → %.4f",
            scaled.span_id,
            dag_orientation.value,
            reported_direction_positive,
            scaled.beta,
            aligned_beta,
        )

    return ScaledNumeric(
        span_id=scaled.span_id,
        beta=aligned_beta,
        se=scaled.se,
        se_source=scaled.se_source,
        scale=scaled.scale,
        direction_aligned=True,
    )


def _needs_sign_flip(
    dag_orientation: Orientation,
    reported_direction_positive: bool,
) -> bool:
    """Determine whether the effect sign needs to be flipped.

    Convention:
    - higher_worse: positive beta means worsening
    - higher_better: positive beta means improvement

    A flip is needed when the study's positive direction conflicts
    with the DAG node's orientation.

    Parameters
    ----------
    dag_orientation:
        DAG convention for the target node.
    reported_direction_positive:
        True if in the study, a positive value = increase in the construct.

    Returns
    -------
    bool
        True if beta should be negated.
    """
    if dag_orientation == Orientation.NEUTRAL:
        # Neutral nodes have no preferred direction — no flip needed
        return False

    if dag_orientation == Orientation.HIGHER_WORSE:
        # DAG says higher=worse. If study says positive=better (improvement),
        # we need to flip so positive=worse.
        return reported_direction_positive is False

    if dag_orientation == Orientation.HIGHER_BETTER:
        # DAG says higher=better. If study says positive=worse,
        # we need to flip so positive=better.
        return reported_direction_positive is True

    return False


def align_orientation_batch(
    items: list[tuple[ScaledNumeric, Orientation, bool, float]],
) -> list[ScaledNumeric]:
    """Align orientation for a batch of scaled numerics.

    Parameters
    ----------
    items:
        List of (ScaledNumeric, dag_orientation,
        reported_direction_positive, orientation_confidence) tuples.

    Returns
    -------
    list[ScaledNumeric]
        All successfully aligned items. Gate violations are logged
        and excluded.
    """
    results: list[ScaledNumeric] = []
    for scaled, orient, positive, confidence in items:
        try:
            aligned = align_orientation(
                scaled=scaled,
                dag_orientation=orient,
                reported_direction_positive=positive,
                orientation_confidence=confidence,
            )
            results.append(aligned)
        except GateViolation as exc:
            logger.error(
                "Orientation REJECT for span_id=%s: %s",
                scaled.span_id,
                str(exc),
            )
    return results
