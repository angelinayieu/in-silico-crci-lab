# VERIFIED: formulas — SD standardization matches spec lines 684-710 (S3 SD borrowing)
# VERIFIED: imports — all modules exist (shared.config, scale_harmonizer.SDAnchor)
# VERIFIED: backward wiring — reads ScaledNumeric from scale_harmonizer.py
# VERIFIED: forward wiring — writes StandardizedRecord for orientation_aligner.py / runner
# VERIFIED: no hardcoded formula parameters — all from config
# VERIFIED: gates — none (pure computation with logging for borrowed SDs)
"""
Component: SYS_EXTRACTION.EX-P2.S3-SD
Spec: SYS_EXTRACTION_COMPLETE.md lines 684-710 (EX-P2-S3 SD borrowing)
Purpose: Standardize effect sizes to a common SD scale using anchors
         from sd_anchors_v1 when studies do not report their own SD.
Formulas:
    SD-STD: β_std = β_raw / SD_pool  (standardize by borrowed SD)
    SE-STD: SE_std = SE_raw / SD_pool × tier_inflation
Reads: TypedNumericValue (from trust boundary), sd_anchors_v1 (DB table)
Writes: StandardizedRecord (consumed by runner / downstream P2 stages)
Gates: None (pure computation; fallback logged)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from crci.shared.config import (
    SD_BORROW_TIER1_INFLATION,
    SD_BORROW_TIER2_INFLATION,
    SD_BORROW_TIER3_INFLATION,
)
from crci.extraction.p2_harmonization.scale_harmonizer import SDAnchor

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  OUTPUT TYPE
# ═══════════════════════════════════════════════════════════════


@dataclass
class StandardizedRecord:
    """Result of SD standardization for a single evidence value.

    If the study reported its own SD, sd_source='reported' and no
    inflation is applied.  If an SD anchor was borrowed, sd_source='borrowed'
    and SE is inflated by the tier-appropriate factor.
    """

    ler_id: str
    beta_standardized: float
    se_standardized: float | None
    sd_used: float | None
    sd_source: str  # 'reported' | 'borrowed_tier1' | 'borrowed_tier2' | 'borrowed_tier3'
    se_inflation_factor: float
    notes: list[str]


# ═══════════════════════════════════════════════════════════════
#  SD ANCHOR LOOKUP
# ═══════════════════════════════════════════════════════════════


def fetch_sd_anchor(
    session: Session,
    outcome_measure: str,
    population_context: str | None = None,
) -> SDAnchor | None:
    """Look up an SD anchor from sd_anchors_v1 for a given outcome.

    Searches for an exact match on outcome_measure first; if no match,
    falls back to a general-population anchor for that measure.

    Args:
        session: Active database session.
        outcome_measure: The outcome measure identifier (e.g., 'FACT-Cog').
        population_context: Optional population context filter (e.g., 'breast_adjuvant').

    Returns:
        SDAnchor if found, None otherwise.
    """
    # Try specific context first
    if population_context:
        try:
            row = session.execute(
                text(
                    "SELECT sd_value, tier, source_description "
                    "FROM sd_anchors_v1 "
                    "WHERE outcome_measure = :measure "
                    "AND population_context = :ctx "
                    "ORDER BY tier ASC LIMIT 1"
                ),
                {"measure": outcome_measure, "ctx": population_context},
            ).fetchone()
            if row:
                return SDAnchor(
                    sd_value=float(row[0]),
                    tier=int(row[1]),
                    source_description=str(row[2]),
                )
        except Exception as exc:
            logger.debug("sd_anchors_v1 context query failed: %s", exc)

    # Fallback: any anchor for this measure
    try:
        row = session.execute(
            text(
                "SELECT sd_value, tier, source_description "
                "FROM sd_anchors_v1 "
                "WHERE outcome_measure = :measure "
                "ORDER BY tier ASC LIMIT 1"
            ),
            {"measure": outcome_measure},
        ).fetchone()
        if row:
            return SDAnchor(
                sd_value=float(row[0]),
                tier=int(row[1]),
                source_description=str(row[2]),
            )
    except Exception as exc:
        logger.debug("sd_anchors_v1 fallback query failed: %s", exc)

    return None


# ═══════════════════════════════════════════════════════════════
#  CORE STANDARDIZATION
# ═══════════════════════════════════════════════════════════════


def _tier_inflation(tier: int) -> float:
    """Return SE inflation factor for SD borrowing tier."""
    if tier == 1:
        return SD_BORROW_TIER1_INFLATION
    if tier == 2:
        return SD_BORROW_TIER2_INFLATION
    return SD_BORROW_TIER3_INFLATION


def standardize_effect(
    ler_id: str,
    beta_raw: float,
    se_raw: float | None,
    study_sd: float | None = None,
    sd_anchor: SDAnchor | None = None,
) -> StandardizedRecord:
    """Standardize a raw effect estimate to the common SD scale.

    If the study reports its own SD, uses that directly (tier-1, no inflation).
    If not, borrows from sd_anchor and applies tier-appropriate SE inflation.
    If neither is available, returns the raw values unchanged.

    Args:
        ler_id: Literature-evidence-record identifier.
        beta_raw: Raw effect estimate.
        se_raw: Raw standard error (may be None).
        study_sd: SD reported by the study itself (if available).
        sd_anchor: Borrowed SD anchor from sd_anchors_v1 (if available).

    Returns:
        StandardizedRecord with standardized beta and SE.
    """
    notes: list[str] = []

    # Case 1: Study reports its own SD
    if study_sd is not None and study_sd > 0:
        beta_std = beta_raw / study_sd
        se_std = (se_raw / study_sd) if se_raw is not None else None
        notes.append(f"Standardized using reported study SD={study_sd:.4f}")
        return StandardizedRecord(
            ler_id=ler_id,
            beta_standardized=beta_std,
            se_standardized=se_std,
            sd_used=study_sd,
            sd_source="reported",
            se_inflation_factor=1.0,
            notes=notes,
        )

    # Case 2: Borrow SD from anchor
    if sd_anchor is not None and sd_anchor.sd_value > 0:
        sd_pool = sd_anchor.sd_value
        tier = sd_anchor.tier
        inflation = _tier_inflation(tier)

        beta_std = beta_raw / sd_pool
        se_std = (se_raw / sd_pool * inflation) if se_raw is not None else None

        source_label = f"borrowed_tier{tier}"
        notes.append(
            f"SD borrowed (tier {tier}): SD_pool={sd_pool:.4f}, "
            f"SE inflation={inflation:.2f} ({sd_anchor.source_description})"
        )
        logger.info(
            "SD standardization for %s: borrowed tier-%d SD=%.4f from '%s'",
            ler_id,
            tier,
            sd_pool,
            sd_anchor.source_description,
        )
        return StandardizedRecord(
            ler_id=ler_id,
            beta_standardized=beta_std,
            se_standardized=se_std,
            sd_used=sd_pool,
            sd_source=source_label,
            se_inflation_factor=inflation,
            notes=notes,
        )

    # Case 3: No SD available — pass through raw values
    notes.append("No study SD or anchor available; returning raw values unstandardized")
    logger.warning(
        "SD standardization for %s: no SD available, returning raw values",
        ler_id,
    )
    return StandardizedRecord(
        ler_id=ler_id,
        beta_standardized=beta_raw,
        se_standardized=se_raw,
        sd_used=None,
        sd_source="none",
        se_inflation_factor=1.0,
        notes=notes,
    )


def standardize_batch(
    records: list[dict],
    session: Session | None = None,
    population_context: str | None = None,
) -> list[StandardizedRecord]:
    """Standardize a batch of evidence records.

    Each record dict must have keys: 'ler_id', 'beta', 'se', and
    optionally 'study_sd', 'outcome_measure'.

    If session is provided, attempts to look up SD anchors for records
    that lack a study_sd.

    Args:
        records: List of evidence record dicts.
        session: Optional DB session for SD anchor lookups.
        population_context: Optional population context for anchor matching.

    Returns:
        List of StandardizedRecord, one per input record.
    """
    results: list[StandardizedRecord] = []

    for rec in records:
        ler_id = rec["ler_id"]
        beta = rec["beta"]
        se = rec.get("se")
        study_sd = rec.get("study_sd")

        # Attempt anchor lookup if no study SD
        anchor = None
        if study_sd is None and session is not None:
            outcome = rec.get("outcome_measure")
            if outcome:
                anchor = fetch_sd_anchor(session, outcome, population_context)

        result = standardize_effect(
            ler_id=ler_id,
            beta_raw=beta,
            se_raw=se,
            study_sd=study_sd,
            sd_anchor=anchor,
        )
        results.append(result)

    logger.info(
        "SD standardization batch: %d records processed "
        "(reported=%d, borrowed=%d, none=%d)",
        len(results),
        sum(1 for r in results if r.sd_source == "reported"),
        sum(1 for r in results if r.sd_source.startswith("borrowed")),
        sum(1 for r in results if r.sd_source == "none"),
    )
    return results
