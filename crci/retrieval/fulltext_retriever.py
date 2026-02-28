# ASSUMPTIONS:
#   - APSScoredCandidate has .candidate.doi or .candidate.pmid for lookup.
#   - Europe PMC and Unpaywall adapters return PDF bytes or None.
# TEST COVERAGE: None yet — needs tests/test_fulltext_retriever.py
# REVIEW:
#   - No retry logic on transient HTTP failures from source adapters.
"""
Component: SYS_EXTRACTION.EX-ACQ.FulltextRetriever
Spec: AUTOMATED_RETRIEVAL_PLAN.md Part 6, Step 4
Purpose: Full-text retrieval with 8-source priority chain.
         openalex_direct → europe_pmc → pmc_xml → unpaywall → arxiv
         → core → semantic_scholar → manual → abstract_only.
         Downloads PDFs/XML to retrieval_cache/{hash}.{ext}.
         stage_for_extraction() bridges to data/manual_uploads/pdfs/.
Reads: APSScoredCandidate[] from aps_scorer OR DOI string via retrieve_by_doi()
Writes: RetrievalResult + acquisition_queue_v1 rows + staged files
"""
from __future__ import annotations

import hashlib
import json
import logging
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from crci.shared import config
from crci.shared.models.tables import AcquisitionQueue
from crci.retrieval.models import (
    APSScoredCandidate,
    ContentValidation,
    ResolvedIdentifiers,
    RetrievalAttemptRecord,
    RetrievalResult,
    RetrievalStatus,
)
from crci.retrieval.adapters.base import SourceAdapter
from crci.retrieval.adapters.europe_pmc import EuropePMCAdapter
from crci.retrieval.adapters.unpaywall import UnpaywallAdapter

logger = logging.getLogger(__name__)

_CACHE_DIR = Path("data/retrieval_cache")
_STAGING_DIR = Path("data/manual_uploads/pdfs")


def _doi_to_slug(doi: str) -> str:
    """Convert DOI to filesystem-safe slug: '/' → '_'."""
    return doi.replace("/", "_")


class FulltextRetriever:
    """Retrieves full-text PDFs/XML for scored candidates or raw DOIs.

    Source priority chain (8 sources, config.FULLTEXT_SOURCE_PRIORITY):
      1. openalex_direct — OA PDF URL from ID resolution
      2. europe_pmc      — free JATS XML (best structured)
      3. pmc_xml          — NCBI efetch JATS XML
      4. unpaywall        — legal OA PDF
      5. arxiv            — preprint PDF (always free)
      6. core             — institutional repository PDF
      7. semantic_scholar — sometimes has unique OA PDFs
      8. manual           — manual uploads (handled separately)
      9. abstract_only    — fallback, shallow extraction only

    Two entry points:
      - retrieve_batch() — for APS pipeline (existing)
      - retrieve_by_doi() — for CLI / ad-hoc DOI retrieval (new)
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
            self._ft_adapters = self._build_default_adapters()

    @staticmethod
    def _build_default_adapters() -> dict[str, SourceAdapter]:
        """Instantiate all available adapters.

        Adapter creation is lazy-safe: if a module fails to import
        or init (e.g. missing API key), we skip that adapter and log.
        """
        adapters: dict[str, SourceAdapter] = {}

        # Always-available adapters
        adapters["europe_pmc"] = EuropePMCAdapter()
        adapters["unpaywall"] = UnpaywallAdapter()

        # New adapters — import lazily so missing deps don't block init
        try:
            from crci.retrieval.adapters.arxiv import ArxivAdapter
            adapters["arxiv"] = ArxivAdapter()
        except Exception as exc:
            logger.warning("Failed to init ArxivAdapter: %s", exc)

        try:
            from crci.retrieval.adapters.pmc_xml import PmcXmlAdapter
            adapters["pmc_xml"] = PmcXmlAdapter()
        except Exception as exc:
            logger.warning("Failed to init PmcXmlAdapter: %s", exc)

        try:
            from crci.retrieval.adapters.core_api import CoreApiAdapter
            adapters["core"] = CoreApiAdapter()
        except Exception as exc:
            logger.warning("Failed to init CoreApiAdapter: %s", exc)

        try:
            from crci.retrieval.adapters.semantic_scholar import SemanticScholarAdapter
            adapters["semantic_scholar"] = SemanticScholarAdapter()
        except Exception as exc:
            logger.warning("Failed to init SemanticScholarAdapter: %s", exc)

        return adapters

    # ═══════════════════════════════════════════════════════════
    #  ENTRY POINT 1: DOI-BASED RETRIEVAL (NEW)
    # ═══════════════════════════════════════════════════════════

    def retrieve_by_doi(
        self,
        doi: str,
        title: str | None = None,
        stage: bool = True,
    ) -> RetrievalResult:
        """Retrieve full text for a single DOI.

        Pipeline: resolve IDs → try 8-source chain → validate → cache → stage.

        Args:
            doi: DOI string (may include URL prefix).
            title: Expected title for fuzzy-match validation.
            stage: If True, stage the retrieved file for P0 extraction.

        Returns:
            RetrievalResult describing what was retrieved (or why not).
        """
        from crci.retrieval.id_resolver import resolve_doi as _resolve_doi, _normalize_doi

        norm_doi = _normalize_doi(doi)
        if not norm_doi:
            return RetrievalResult(
                doi=doi,
                status=RetrievalStatus.FAILED,
                error_message="Invalid DOI",
            )

        # Step 1: Resolve all identifiers
        resolved = _resolve_doi(norm_doi)
        logger.info(
            "ID resolution for %s: pmid=%s pmcid=%s arxiv=%s oa_status=%s",
            norm_doi,
            resolved.pmid,
            resolved.pmcid,
            resolved.arxiv_id,
            resolved.oa_status.value,
        )

        # Use resolved title if caller didn't provide one
        effective_title = title or resolved.title

        # Step 2: Try the 8-source chain
        attempts: list[RetrievalAttemptRecord] = []
        for source_name in config.FULLTEXT_SOURCE_PRIORITY:
            if source_name in ("manual", "abstract_only"):
                break  # Skip manual and abstract_only in DOI retrieval

            attempt_start = time.monotonic()
            content, ext, attempt = self._try_source(
                source_name, norm_doi, resolved,
            )
            attempts.append(attempt)

            if content is None:
                continue

            # Step 3: Validate content
            validation = self._validate_content_deep(
                content, ext, effective_title,
            )
            if not validation.valid:
                logger.warning(
                    "Content from %s failed validation for %s: %s",
                    source_name,
                    norm_doi,
                    validation.issues,
                )
                attempts[-1] = attempt.model_copy(update={
                    "status": "failed",
                    "error": f"validation: {', '.join(validation.issues)}",
                })
                continue

            # Step 4: Save to cache
            cache_path = self._save_to_cache(content, norm_doi, ext)

            result = RetrievalResult(
                doi=norm_doi,
                pmid=resolved.pmid,
                status=RetrievalStatus.RETRIEVED,
                cache_path=str(cache_path),
                source_used=source_name,
                file_size_bytes=len(content),
                is_preprint=source_name == "arxiv",
                retrieval_format=ext,
                attempts=attempts,
                validation=validation,
            )

            # Step 5: Stage for extraction
            if stage:
                staged_path = self.stage_for_extraction(
                    cache_path, norm_doi, resolved,
                )
                if staged_path:
                    result = result.model_copy(
                        update={"cache_path": str(staged_path)},
                    )

            # Step 6: Update DB
            self._update_queue_from_doi(norm_doi, resolved, result)

            logger.info(
                "Successfully retrieved %s via %s (%d bytes, format=%s)",
                norm_doi,
                source_name,
                len(content),
                ext,
            )
            return result

        # All sources exhausted → abstract_only
        logger.info(
            "No full text available for %s after trying %d sources → ABSTRACT_ONLY",
            norm_doi,
            len(attempts),
        )
        result = RetrievalResult(
            doi=norm_doi,
            pmid=resolved.pmid,
            status=RetrievalStatus.ABSTRACT_ONLY,
            attempts=attempts,
        )
        self._update_queue_from_doi(norm_doi, resolved, result)
        return result

    def _try_source(
        self,
        source_name: str,
        doi: str,
        resolved: ResolvedIdentifiers,
    ) -> tuple[bytes | None, str, RetrievalAttemptRecord]:
        """Attempt retrieval from a single source.

        Returns (content_bytes, extension, attempt_record).
        content_bytes is None on failure.
        """
        start = time.monotonic()

        # openalex_direct: use best_oa_pdf_url from resolution
        if source_name == "openalex_direct":
            return self._try_openalex_direct(doi, resolved, start)

        # pmc_xml: needs PMCID
        if source_name == "pmc_xml":
            if not resolved.pmcid:
                return None, "", RetrievalAttemptRecord(
                    source=source_name,
                    status="not_applicable",
                    error="no PMCID",
                    duration_ms=int((time.monotonic() - start) * 1000),
                )

        # europe_pmc: needs PMCID
        if source_name == "europe_pmc":
            if not resolved.pmcid:
                return None, "", RetrievalAttemptRecord(
                    source=source_name,
                    status="not_applicable",
                    error="no PMCID",
                    duration_ms=int((time.monotonic() - start) * 1000),
                )

        # arxiv: needs arxiv_id
        if source_name == "arxiv":
            if not resolved.arxiv_id:
                return None, "", RetrievalAttemptRecord(
                    source=source_name,
                    status="not_applicable",
                    error="no arXiv ID",
                    duration_ms=int((time.monotonic() - start) * 1000),
                )

        adapter = self._ft_adapters.get(source_name)
        if adapter is None:
            return None, "", RetrievalAttemptRecord(
                source=source_name,
                status="not_applicable",
                error="adapter not available",
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        # Select identifier for this adapter
        identifier = self._select_identifier(source_name, doi, resolved)
        if not identifier:
            return None, "", RetrievalAttemptRecord(
                source=source_name,
                status="not_applicable",
                error="no suitable identifier",
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        try:
            content = adapter.retrieve_fulltext(identifier)
            duration_ms = int((time.monotonic() - start) * 1000)

            if content:
                ext = "xml" if source_name in ("europe_pmc", "pmc_xml") else "pdf"
                return content, ext, RetrievalAttemptRecord(
                    source=source_name,
                    status="success",
                    http_status=200,
                    duration_ms=duration_ms,
                    url_attempted=identifier,
                )
            else:
                return None, "", RetrievalAttemptRecord(
                    source=source_name,
                    status="failed",
                    error="no content returned",
                    duration_ms=duration_ms,
                    url_attempted=identifier,
                )
        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            return None, "", RetrievalAttemptRecord(
                source=source_name,
                status="failed",
                error=str(exc)[:200],
                duration_ms=duration_ms,
                url_attempted=identifier,
            )

    def _try_openalex_direct(
        self,
        doi: str,
        resolved: ResolvedIdentifiers,
        start: float,
    ) -> tuple[bytes | None, str, RetrievalAttemptRecord]:
        """Try downloading directly from OpenAlex's best_oa_pdf_url."""
        import requests as req

        if not resolved.best_oa_pdf_url:
            return None, "", RetrievalAttemptRecord(
                source="openalex_direct",
                status="not_applicable",
                error="no OA PDF URL from resolution",
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        url = resolved.best_oa_pdf_url
        try:
            resp = req.get(
                url,
                timeout=config.RETRIEVAL_PDF_DOWNLOAD_TIMEOUT_SEC,
                headers={"User-Agent": "CRCI-RetrievalBot/1.0"},
                allow_redirects=True,
            )
            resp.raise_for_status()
            duration_ms = int((time.monotonic() - start) * 1000)

            if not resp.content[:5] == b"%PDF-":
                return None, "", RetrievalAttemptRecord(
                    source="openalex_direct",
                    status="failed",
                    http_status=resp.status_code,
                    error="not PDF (magic bytes mismatch)",
                    duration_ms=duration_ms,
                    url_attempted=url,
                )

            return resp.content, "pdf", RetrievalAttemptRecord(
                source="openalex_direct",
                status="success",
                http_status=resp.status_code,
                duration_ms=duration_ms,
                url_attempted=url,
            )

        except req.RequestException as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            return None, "", RetrievalAttemptRecord(
                source="openalex_direct",
                status="failed",
                error=str(exc)[:200],
                duration_ms=duration_ms,
                url_attempted=url,
            )

    @staticmethod
    def _select_identifier(
        source_name: str,
        doi: str,
        resolved: ResolvedIdentifiers,
    ) -> str | None:
        """Choose the right identifier for a given adapter."""
        if source_name == "europe_pmc":
            return resolved.pmcid
        if source_name == "pmc_xml":
            return resolved.pmcid
        if source_name == "unpaywall":
            return doi
        if source_name == "arxiv":
            return resolved.arxiv_id
        if source_name in ("core", "semantic_scholar"):
            return doi
        return doi

    # ═══════════════════════════════════════════════════════════
    #  ENTRY POINT 2: BATCH RETRIEVAL (EXISTING — refactored)
    # ═══════════════════════════════════════════════════════════

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
        (Legacy method — kept for backward compatibility with retrieve_batch.)
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

    def _validate_content_deep(
        self,
        content: bytes,
        extension: str,
        expected_title: str | None = None,
    ) -> ContentValidation:
        """Deep content validation: magic bytes + text length + title match.

        Catches paywall landing pages, cover-page-only PDFs, and wrong papers.

        Args:
            content: Raw file bytes.
            extension: Expected file type ('pdf' or 'xml').
            expected_title: If provided, fuzzy-match extracted title.

        Returns:
            ContentValidation with valid flag, issues, and metrics.
        """
        issues: list[str] = []
        text_length: int | None = None
        title_match_score: float | None = None
        has_abstract = False
        has_references = False
        page_count: int | None = None

        # 1. Magic bytes check
        if extension == "pdf":
            if not content[:5] == b"%PDF-":
                issues.append("not_pdf_magic_bytes")
                return ContentValidation(
                    valid=False,
                    issues=issues,
                    text_length=0,
                )
        elif extension == "xml":
            stripped = content.lstrip()
            if not (stripped[:5] == b"<?xml" or stripped[:1] == b"<"):
                issues.append("not_xml_content")
                return ContentValidation(
                    valid=False,
                    issues=issues,
                    text_length=0,
                )

        # 2. Size check
        if len(content) < config.RETRIEVAL_MIN_PDF_SIZE_BYTES:
            issues.append(f"too_small_{len(content)}_bytes")

        # 3. Extract text for deeper checks
        extracted_text = ""
        if extension == "pdf":
            extracted_text = self._extract_text_from_pdf(content)
        elif extension == "xml":
            extracted_text = self._extract_text_from_xml(content)

        text_length = len(extracted_text)

        # 4. Text length check
        if text_length < config.RETRIEVAL_MIN_TEXT_LENGTH:
            issues.append(f"text_too_short_{text_length}_chars")

        # 5. Content markers
        lower_text = extracted_text.lower()
        has_abstract = any(
            marker in lower_text
            for marker in ("abstract", "summary", "background")
        )
        has_references = any(
            marker in lower_text
            for marker in ("references", "bibliography", "works cited")
        )

        # 6. Title fuzzy match (if title provided)
        if expected_title and extracted_text:
            title_match_score = self._fuzzy_title_match(
                expected_title, extracted_text[:3000],
            )
            if title_match_score < config.RETRIEVAL_MIN_TITLE_MATCH_SCORE:
                issues.append(
                    f"title_mismatch_score_{title_match_score:.0f}",
                )

        is_valid = len(issues) == 0
        return ContentValidation(
            valid=is_valid,
            issues=issues,
            text_length=text_length,
            title_match_score=title_match_score,
            has_abstract=has_abstract,
            has_references=has_references,
            page_count=page_count,
        )

    @staticmethod
    def _extract_text_from_pdf(content: bytes) -> str:
        """Extract text from PDF bytes using pdfplumber.

        Falls back to empty string if pdfplumber isn't available
        or extraction fails. This is only for validation, not for
        final extraction (P0 does that).
        """
        try:
            import io
            import pdfplumber
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                pages_text = []
                for page in pdf.pages[:10]:  # Only check first 10 pages for speed
                    text = page.extract_text() or ""
                    pages_text.append(text)
                return "\n".join(pages_text)
        except Exception as exc:
            logger.debug("PDF text extraction for validation failed: %s", exc)
            return ""

    @staticmethod
    def _extract_text_from_xml(content: bytes) -> str:
        """Extract text from JATS/NLM XML for validation."""
        import xml.etree.ElementTree as ET
        try:
            root = ET.fromstring(content)
            # Gather all text content
            parts: list[str] = []
            for elem in root.iter():
                if elem.text:
                    parts.append(elem.text.strip())
                if elem.tail:
                    parts.append(elem.tail.strip())
            return " ".join(p for p in parts if p)
        except ET.ParseError:
            return ""

    @staticmethod
    def _fuzzy_title_match(expected: str, text: str) -> float:
        """Fuzzy match expected title against beginning of text.

        Uses simple token overlap if rapidfuzz is not available.
        Returns score 0-100.
        """
        try:
            from rapidfuzz import fuzz
            return fuzz.partial_ratio(expected.lower(), text[:2000].lower())
        except ImportError:
            # Fallback: token overlap ratio
            expected_tokens = set(expected.lower().split())
            text_tokens = set(text[:2000].lower().split())
            if not expected_tokens:
                return 100.0
            overlap = expected_tokens & text_tokens
            return (len(overlap) / len(expected_tokens)) * 100.0

    # ═══════════════════════════════════════════════════════════
    #  STAGING: BRIDGE retrieval_cache → manual_uploads/pdfs
    # ═══════════════════════════════════════════════════════════

    def stage_for_extraction(
        self,
        cache_path: Path | str,
        doi: str,
        resolved: ResolvedIdentifiers,
    ) -> Path | None:
        """Copy a cached file to data/manual_uploads/pdfs/ with meta.json.

        This bridges the gap between the retrieval cache (hash filenames)
        and the P0 triage pipeline (which reads from manual_uploads/pdfs/).

        Naming convention: DOI slug with '/' → '_'
          - 10.1002/pon.4370 → 10.1002_pon.4370.pdf + 10.1002_pon.4370.meta.json

        Args:
            cache_path: Path to the cached file.
            doi: Raw DOI.
            resolved: ResolvedIdentifiers for meta.json population.

        Returns:
            Path to the staged file, or None on failure.
        """
        cache_path = Path(cache_path)
        if not cache_path.exists():
            logger.warning("Cache file does not exist: %s", cache_path)
            return None

        staging_dir = _STAGING_DIR
        staging_dir.mkdir(parents=True, exist_ok=True)

        doi_slug = _doi_to_slug(doi)
        ext = cache_path.suffix  # .pdf or .xml
        dest_path = staging_dir / f"{doi_slug}{ext}"

        # Don't overwrite existing files
        if dest_path.exists():
            logger.info("Staged file already exists: %s", dest_path)
            return dest_path

        try:
            shutil.copy2(str(cache_path), str(dest_path))
        except OSError as exc:
            logger.warning("Failed to stage file %s → %s: %s", cache_path, dest_path, exc)
            return None

        # Write companion meta.json
        meta = {
            "doi": doi,
            "pmid": resolved.pmid,
            "pmcid": resolved.pmcid,
            "title": resolved.title,
            "journal": resolved.journal,
            "year": resolved.year,
            "oa_status": resolved.oa_status.value,
            "publisher": resolved.publisher,
            "source": "automated_retrieval",
            "staged_at": datetime.now(timezone.utc).isoformat(),
            "arxiv_id": resolved.arxiv_id,
            "openalex_id": resolved.openalex_id,
        }
        meta_path = staging_dir / f"{doi_slug}.meta.json"
        try:
            meta_path.write_text(json.dumps(meta, indent=2, default=str))
        except OSError as exc:
            logger.warning("Failed to write meta.json for %s: %s", doi, exc)

        logger.info("Staged %s → %s", cache_path.name, dest_path)
        return dest_path

    def _update_queue_from_doi(
        self,
        doi: str,
        resolved: ResolvedIdentifiers,
        result: RetrievalResult,
    ) -> None:
        """Update or create acquisition_queue_v1 row from DOI retrieval."""
        status_map = {
            RetrievalStatus.RETRIEVED: "retrieved",
            RetrievalStatus.ABSTRACT_ONLY: "dispatched",
            RetrievalStatus.FAILED: "failed",
        }
        new_status = status_map.get(result.status, "queued")

        # Serialize attempts
        attempts_json = json.dumps(
            [a.model_dump() for a in result.attempts],
            default=str,
        ) if result.attempts else None

        try:
            existing = self._session.query(AcquisitionQueue).filter(
                AcquisitionQueue.candidate_doi == doi,
            ).first()

            if existing:
                existing.status = new_status
                if result.source_used:
                    existing.retrieval_tool = result.source_used
                existing.pmcid = resolved.pmcid
                existing.openalex_id = resolved.openalex_id
                existing.best_oa_url = resolved.best_oa_pdf_url
                existing.retrieval_attempts_json = attempts_json
                if result.cache_path:
                    existing.file_path = result.cache_path
                self._session.commit()
            else:
                queue_id = f"ACQ_{uuid.uuid4().hex[:16]}"
                row = AcquisitionQueue(
                    queue_id=queue_id,
                    candidate_doi=doi,
                    candidate_pmid=resolved.pmid,
                    candidate_title=resolved.title,
                    retrieval_tool=result.source_used,
                    status=new_status,
                    pmcid=resolved.pmcid,
                    openalex_id=resolved.openalex_id,
                    best_oa_url=resolved.best_oa_pdf_url,
                    retrieval_attempts_json=attempts_json,
                    file_path=result.cache_path,
                )
                self._session.add(row)
                self._session.commit()

        except Exception as exc:
            self._session.rollback()
            logger.warning("Failed to update acquisition_queue for %s: %s", doi, exc)

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
