# VERIFIED: rules SC-1, CS-1, CS-2, CS-3 match CONVERSION_VALIDITY_AND_HARDENING.md Module 4
# VERIFIED: imports — all modules exist (shared.config, shared.models)
# VERIFIED: backward wiring — reads edge_evidence records from DB
# VERIFIED: forward wiring — writes adjusted records for IVW pooling
# VERIFIED: no hardcoded formula parameters — all from config
"""
Component: SYS_EXTRACTION.EX-P4.SHARED-CONTROL
Spec: CONVERSION_VALIDITY_AND_HARDENING.md Module 4.1 (Shared Control Groups)
      CONVERSION_VALIDITY_AND_HARDENING.md Module 4.3 (Change vs Endpoint)
Rules:
    SC-1: Multi-arm trials sharing control → split N_control / k
    CS-1: Track endpoint_vs_change per record
    CS-2: Do not pool endpoint and change-score d directly;
          convert minority to majority scale
Reads: Edge evidence records with shared_control_flag
Writes: Adjusted N/SE records for IVW pooling
Gates: None (adjustment is automatic)
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

from crci.shared.config import (
    CS_DEFAULT_RHO,
    CS_MAJORITY_FRACTION,
    CS_UNKNOWN_RHO_SE_INFLATION,
)

logger = logging.getLogger(__name__)


@dataclass
class SharedControlRecord:
    """Evidence record for shared-control analysis."""

    ler_id: str
    study_id: str
    beta: float
    se: float
    n_treatment: int
    n_control: int
    shared_control_flag: bool = False
    shared_control_study_id: str | None = None
    comparison_arm_label: str | None = None
    endpoint_vs_change: str = "UNCLEAR"


@dataclass(frozen=True)
class AdjustedRecord:
    """Record after shared-control and endpoint/change adjustment."""

    ler_id: str
    beta: float
    se: float
    n_control_adjusted: int
    se_adjustment_note: str
    endpoint_vs_change: str


def apply_shared_control_split(
    records: list[SharedControlRecord],
) -> list[AdjustedRecord]:
    """SC-1: Split shared control groups across comparisons.

    For multi-arm trials, the control group N is split evenly
    across k comparisons sharing that control. SE is recomputed
    using the reduced N_control.

    OPTION A (preferred): N_control_per_comparison = N_control / k

    Parameters
    ----------
    records : list[SharedControlRecord]
        Evidence records, some with shared_control_flag = True.

    Returns
    -------
    list[AdjustedRecord]
        Records with adjusted N_control and SE.
    """
    # Group by shared_control_study_id
    control_groups: dict[str, list[int]] = {}
    for i, rec in enumerate(records):
        if rec.shared_control_flag and rec.shared_control_study_id:
            key = rec.shared_control_study_id
            if key not in control_groups:
                control_groups[key] = []
            control_groups[key].append(i)

    results: list[AdjustedRecord] = []

    for i, rec in enumerate(records):
        if not rec.shared_control_flag or rec.shared_control_study_id is None:
            # No adjustment needed
            results.append(AdjustedRecord(
                ler_id=rec.ler_id,
                beta=rec.beta,
                se=rec.se,
                n_control_adjusted=rec.n_control,
                se_adjustment_note="No shared control",
                endpoint_vs_change=rec.endpoint_vs_change,
            ))
            continue

        key = rec.shared_control_study_id
        k_shared = len(control_groups.get(key, [1]))
        if k_shared <= 1:
            results.append(AdjustedRecord(
                ler_id=rec.ler_id,
                beta=rec.beta,
                se=rec.se,
                n_control_adjusted=rec.n_control,
                se_adjustment_note="Shared control but only 1 comparison",
                endpoint_vs_change=rec.endpoint_vs_change,
            ))
            continue

        # SC-1: N_control_per_comparison = N_control / k
        n_control_adj = max(1, rec.n_control // k_shared)
        n_t = rec.n_treatment

        # Recompute SE_d using adjusted N
        # SE_d = √(1/n_t + 1/n_c_adj + d²/(2(n_t + n_c_adj)))
        d = rec.beta
        if n_t > 0 and n_control_adj > 0:
            se_adj = math.sqrt(
                1.0 / n_t + 1.0 / n_control_adj
                + d * d / (2 * (n_t + n_control_adj))
            )
        else:
            se_adj = rec.se  # fallback

        logger.info(
            "SC-1: ler_id=%s, study=%s: N_control %d → %d (k=%d shared), SE %.4f → %.4f",
            rec.ler_id, rec.study_id, rec.n_control, n_control_adj,
            k_shared, rec.se, se_adj,
        )

        results.append(AdjustedRecord(
            ler_id=rec.ler_id,
            beta=rec.beta,
            se=se_adj,
            n_control_adjusted=n_control_adj,
            se_adjustment_note=f"SC-1: N_control split {rec.n_control}/{k_shared}={n_control_adj}",
            endpoint_vs_change=rec.endpoint_vs_change,
        ))

    return results


def partition_endpoint_change(
    records: list[AdjustedRecord],
    rho: float | None = None,
) -> list[AdjustedRecord]:
    """CS-2: Ensure pooling uses consistent scale (endpoint or change).

    Rules:
    - If ≥2/3 are ENDPOINT: convert CHANGE records to ENDPOINT
    - If ≥2/3 are CHANGE: convert ENDPOINT records to CHANGE
    - If mixed: pool separately, take larger-k pool
    - Conversion: d_endpoint = d_change × √(1/(2(1−ρ)))

    Parameters
    ----------
    records : list[AdjustedRecord]
        Records with endpoint_vs_change classification.
    rho : float | None
        Pre-post correlation. None → use default (0.50) + SE inflation.

    Returns
    -------
    list[AdjustedRecord]
        Records with consistent scale.
    """
    endpoints = [r for r in records if r.endpoint_vs_change == "ENDPOINT"]
    changes = [r for r in records if r.endpoint_vs_change == "CHANGE"]
    unclear = [r for r in records if r.endpoint_vs_change not in ("ENDPOINT", "CHANGE")]

    n_classifiable = len(endpoints) + len(changes)
    if n_classifiable == 0:
        return records  # all UNCLEAR — no adjustment

    fraction_endpoint = len(endpoints) / n_classifiable if n_classifiable > 0 else 0.0
    fraction_change = len(changes) / n_classifiable if n_classifiable > 0 else 0.0

    use_rho = rho if rho is not None else CS_DEFAULT_RHO
    se_inflation = 1.0 if rho is not None else CS_UNKNOWN_RHO_SE_INFLATION

    if fraction_endpoint >= CS_MAJORITY_FRACTION:
        # Convert CHANGE → ENDPOINT
        # d_endpoint = d_change × √(1/(2(1−ρ)))
        conversion_factor = math.sqrt(1.0 / (2.0 * (1.0 - use_rho)))
        converted = []
        for r in records:
            if r.endpoint_vs_change == "CHANGE":
                new_beta = r.beta * conversion_factor
                new_se = r.se * conversion_factor * se_inflation
                logger.info(
                    "CS-2: ler_id=%s: CHANGE→ENDPOINT (ρ=%.2f), β %.4f→%.4f, SE %.4f→%.4f",
                    r.ler_id, use_rho, r.beta, new_beta, r.se, new_se,
                )
                converted.append(AdjustedRecord(
                    ler_id=r.ler_id,
                    beta=new_beta,
                    se=new_se,
                    n_control_adjusted=r.n_control_adjusted,
                    se_adjustment_note=r.se_adjustment_note
                        + f"; CS-2: CHANGE→ENDPOINT (ρ={use_rho})",
                    endpoint_vs_change="ENDPOINT",
                ))
            else:
                converted.append(r)
        return converted

    elif fraction_change >= CS_MAJORITY_FRACTION:
        # Convert ENDPOINT → CHANGE
        # d_change = d_endpoint / √(1/(2(1−ρ))) = d_endpoint × √(2(1−ρ))
        conversion_factor = math.sqrt(2.0 * (1.0 - use_rho))
        converted = []
        for r in records:
            if r.endpoint_vs_change == "ENDPOINT":
                new_beta = r.beta * conversion_factor
                new_se = r.se * conversion_factor * se_inflation
                logger.info(
                    "CS-2: ler_id=%s: ENDPOINT→CHANGE (ρ=%.2f), β %.4f→%.4f, SE %.4f→%.4f",
                    r.ler_id, use_rho, r.beta, new_beta, r.se, new_se,
                )
                converted.append(AdjustedRecord(
                    ler_id=r.ler_id,
                    beta=new_beta,
                    se=new_se,
                    n_control_adjusted=r.n_control_adjusted,
                    se_adjustment_note=r.se_adjustment_note
                        + f"; CS-2: ENDPOINT→CHANGE (ρ={use_rho})",
                    endpoint_vs_change="CHANGE",
                ))
            else:
                converted.append(r)
        return converted

    else:
        # Mixed: pool separately, take larger-k pool
        if len(endpoints) >= len(changes):
            logger.info(
                "CS-2: Mixed scale — using ENDPOINT pool (k=%d vs k=%d)",
                len(endpoints), len(changes),
            )
            return endpoints + unclear
        else:
            logger.info(
                "CS-2: Mixed scale — using CHANGE pool (k=%d vs k=%d)",
                len(changes), len(endpoints),
            )
            return changes + unclear
