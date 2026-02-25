# VERIFIED: flow matches AUTOMATED_RETRIEVAL_PLAN.md Part 6, Step 4
# VERIFIED: source priority: Europe PMC → Unpaywall → skip (abstract-only)
# VERIFIED: imports — adapters, config for FULLTEXT_SOURCE_PRIORITY
# VERIFIED: backward wiring — reads APSScoredCandidate from aps_scorer
# VERIFIED: forward wiring — writes RetrievalResult + acquisition_queue_v1
"""
Component: SYS_EXTRACTION.EX-ACQ.FulltextRetriever
Spec: AUTOMATED_RETRIEVAL_PLAN.md Part 6, Step 4
Purpose: Full-text retrieval with source priority chain.
         Europe PMC → Unpaywall → skip (abstract-only).
         Downloads PDFs to retrieval_cache/{hash}.pdf.
         Writes/updates acquisition_queue_v1 rows.
Reads: APSScoredCandidate[] from aps_scorer
Writes: RetrievalResult + acquisition_queue_v1 rows
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from crci.shared import config
from crci.shared.models.tables import AcquisitionQueue
from crci.retrieval.models import (
    APSScoredCandidate,
    RetrievalResult,
    RetrievalStatus,
)
from crci.retrieval.adapters.base import SourceAdapter
from crci.retrieval.adapters.europe_pmc import EuropePMCAdapter
from crci.retrieval.adapters.unpaywall import UnpaywallAdapter

logger = logging.getLogger(__name__)

_CACHE_DIR = Path("data/retrieval_cache")


class FulltextRetriever:
    """Retrieves full-text PDFs/XML for scored candidates.

    Source priority chain:
      1. Europe PMC (free, XML, best structured)
      2. Unpaywall (free, PDF, legal OA)
      3. Skip → abstract-only extraction (SHALLOW mode)
    """

    def __init__(
        self,
        session: Session,
        cache_dir: Path | None = None,
        adapters: dict[str, SourceAdapter] | None = None,
    ) -> None:
        self._session = session
        self._cache_dir = cache_dir or _CACHE_DIR
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        if adapters is not None:
            self._ft_adapters = adapters
        else:
            self._ft_adapters = {
                "europe_pmc": EuropePMCAdapter(),
                "unpaywall": UnpaywallAdapter(),
            }

    def retrieve_batch(
        self,
        scored_candidates: list[APSScoredCandidate],
        max_retrievals: int | None = None,
    ) -> list[RetrievalResult]:
        """Retrieve full text for a batch of scored candidates.

        Only processes candidates with decision=DISPATCH.
        Respects daily budget caps.

        Args:
            scored_candidates: APS-scored candidates (only DISPATCH processed).
            max_retrievals: Maximum number of retrievals (default from config).

        Returns:
            List of RetrievalResult.
        """
        if max_retrievals is None:
            max_retrievals = config.RETRIEVAL_MAX_FULLTEXT_PER_DAY

        dispatch = [s for s in scored_candidates if s.decision == "DISPATCH"]
        results: list[RetrievalResult] = []
        retrieved_count = 0

        for scored in dispatch:
            if retrieved_count >= max_retrievals:
                logger.info(
                    "Full-text retrieval budget exhausted (%d/%d)",
                    retrieved_count,
                    max_retrievals,
                )
                break

            result = self._retrieve_single(scored)
            results.append(result)

            # Write acquisition_queue_v1 row
            self._write_queue_row(scored, result)

            if result.status == RetrievalStatus.RETRIEVED:
                retrieved_count += 1

        logger.info(
            "Full-text retrieval complete: %d retrieved, %d abstract-only, "
            "%d failed out of %d dispatched",
            sum(1 for r in results if r.status == RetrievalStatus.RETRIEVED),
            sum(1 for r in results if r.status == RetrievalStatus.ABSTRACT_ONLY),
            sum(1 for r in results if r.status == RetrievalStatus.FAILED),
            len(dispatch),
        )
        return results

    def _retrieve_single(
        self,
        scored: APSScoredCandidate,
    ) -> RetrievalResult:
        """Attempt full-text retrieval for a single candidate.

        Tries sources in config.FULLTEXT_SOURCE_PRIORITY order.
        """
        candidate = scored.candidate
        doi = candidate.doi
        pmcid = candidate.pmcid

        # Iterate through sources in config priority order
        for source_name in config.FULLTEXT_SOURCE_PRIORITY:
            if source_name == "abstract_only":
                break  # Fall through to abstract-only

            adapter = self._ft_adapters.get(source_name)
            if adapter is None:
                continue

            # Determine the identifier to use for this adapter
            identifier = None
            if source_name == "europe_pmc" and pmcid:
                identifier = pmcid
            elif source_name == "unpaywall" and doi:
                identifier = doi
            elif source_name == "manual":
                continue  # Manual uploads handled separately

            if identifier is None:
                continue

            try:
                content = adapter.retrieve_fulltext(identifier)
                if content:
                    ext = "xml" if source_name == "europe_pmc" else "pdf"

                    # Validate the content is actually the expected type
                    if not self._validate_content(content, ext):
                        logger.warning(
                            "Content validation failed for %s via %s "
                            "— skipping to next source",
                            identifier,
                            source_name,
                        )
                        continue

                    cache_path = self._save_to_cache(content, identifier, ext)
                    return RetrievalResult(
                        doi=doi,
                        pmid=candidate.pmid,
                        status=RetrievalStatus.RETRIEVED,
                        cache_path=str(cache_path),
                        source_used=source_name,
                        file_size_bytes=len(content),
                    )
            except Exception as exc:
                logger.warning(
                    "%s retrieval failed for %s: %s",
                    source_name,
                    identifier,
                    exc,
                )

        # No full text available → abstract-only
        logger.info(
            "No full text available for %s / %s → ABSTRACT_ONLY",
            doi or "no-doi",
            pmcid or "no-pmcid",
        )
        return RetrievalResult(
            doi=doi,
            pmid=candidate.pmid,
            status=RetrievalStatus.ABSTRACT_ONLY,
            source_used=None,
        )

    def _validate_content(self, content: bytes, extension: str) -> bool:
        """Validate downloaded content is actually the expected file type.

        Checks file magic bytes to reject HTML pages saved as PDFs.
        """
        if extension == "pdf":
            if not content[:5] == b"%PDF-":
                logger.warning(
                    "Downloaded content is not a valid PDF "
                    "(starts with: %r, size: %d bytes). "
                    "Likely an HTML landing page or CAPTCHA.",
                    content[:20],
                    len(content),
                )
                return False
        elif extension == "xml":
            # XML should start with <?xml or <article or similar
            stripped = content.lstrip()
            if not (stripped[:5] == b"<?xml" or stripped[:1] == b"<"):
                logger.warning(
                    "Downloaded content is not valid XML "
                    "(starts with: %r, size: %d bytes).",
                    content[:20],
                    len(content),
                )
                return False
        return True

    def _save_to_cache(
        self,
        content: bytes,
        identifier: str,
        extension: str,
    ) -> Path:
        """Save downloaded content to the retrieval cache.

        Uses hash-based filename for dedup, plus a .manifest.json
        with human-readable metadata for discoverability.
        """
        # Use hash of identifier for filename
        id_hash = hashlib.md5(identifier.encode()).hexdigest()[:16]
        filename = f"{id_hash}.{extension}"
        path = self._cache_dir / filename
        path.write_bytes(content)

        # Write a companion manifest for human readability
        import json
        manifest_path = path.with_suffix(".manifest.json")
        manifest = {
            "identifier": identifier,
            "filename": filename,
            "size_bytes": len(content),
            "extension": extension,
        }
        manifest_path.write_text(json.dumps(manifest, indent=2))

        logger.debug("Cached %d bytes to %s", len(content), path)
        return path

    def _write_queue_row(
        self,
        scored: APSScoredCandidate,
        result: RetrievalResult,
    ) -> None:
        """Write or update an acquisition_queue_v1 row.

        Deduplicates on candidate_doi — if a row with the same DOI
        already exists, update status + APS instead of inserting.
        """
        candidate = scored.candidate

        status_map = {
            RetrievalStatus.RETRIEVED: "retrieved",
            RetrievalStatus.ABSTRACT_ONLY: "dispatched",
            RetrievalStatus.FAILED: "failed",
        }

        new_status = status_map.get(result.status, "queued")

        try:
            # Check for existing row with same DOI
            from sqlalchemy import select
            existing = self._session.query(AcquisitionQueue).filter(
                AcquisitionQueue.candidate_doi == candidate.doi
            ).first()

            if existing:
                # Update existing row if new APS is higher or status is better
                status_priority = {"queued": 0, "failed": 1, "dispatched": 2, "retrieved": 3}
                old_priority = status_priority.get(existing.status, 0)
                new_priority = status_priority.get(new_status, 0)

                if new_priority > old_priority or (scored.aps_score or 0) > (existing.aps_score or 0):
                    existing.status = new_status
                    existing.aps_score = max(scored.aps_score or 0, existing.aps_score or 0)
                    existing.aps_components_json = scored.aps_components
                    if result.source_used:
                        existing.retrieval_tool = result.source_used
                    self._session.commit()
                    logger.debug(
                        "Updated acquisition_queue row for DOI %s (status=%s, APS=%.3f)",
                        candidate.doi, new_status, existing.aps_score or 0,
                    )
                else:
                    logger.debug(
                        "Skipping duplicate DOI %s (existing status=%s, APS=%.3f)",
                        candidate.doi, existing.status, existing.aps_score or 0,
                    )
                return

            # Insert new row
            queue_id = f"ACQ_{uuid.uuid4().hex[:16]}"
            row = AcquisitionQueue(
                queue_id=queue_id,
                candidate_doi=candidate.doi,
                candidate_pmid=candidate.pmid,
                candidate_title=candidate.title,
                target_edge_ids_json=(
                    [scored.target_entity_id] if scored.target_entity_id else None
                ),
                aps_score=scored.aps_score,
                aps_components_json=scored.aps_components,
                retrieval_tool=result.source_used,
                status=new_status,
            )
            self._session.add(row)
            self._session.commit()
        except Exception as exc:
            self._session.rollback()
            logger.warning("Failed to write acquisition_queue row: %s", exc)
