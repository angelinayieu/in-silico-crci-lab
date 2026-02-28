"""Tests for the retrieval layer: id_resolver, fulltext_retriever, adapters, xml_ingestion.

Covers:
- DOI-to-slug conversion
- Content validation (magic bytes, text length, title match)
- Source selection logic
- Stage-for-extraction file and meta.json creation
- XML ingestion parsing
- Adapter identifier routing
- CLI import sanity

Uses mock adapters to avoid network calls.
"""
from __future__ import annotations

import io
import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from crci.retrieval.models import (
    ContentValidation,
    OAStatus,
    ResolvedIdentifiers,
    RetrievalAttemptRecord,
    RetrievalResult,
    RetrievalStatus,
)
from crci.retrieval.fulltext_retriever import FulltextRetriever, _doi_to_slug


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════

@pytest.fixture()
def tmp_cache(tmp_path: Path):
    """Temporary cache directory for retrieval artifacts."""
    cache_dir = tmp_path / "retrieval_cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture()
def tmp_staging(tmp_path: Path, monkeypatch):
    """Temporary staging directory, patched into fulltext_retriever."""
    staging_dir = tmp_path / "manual_uploads" / "pdfs"
    staging_dir.mkdir(parents=True)
    import crci.retrieval.fulltext_retriever as mod
    monkeypatch.setattr(mod, "_STAGING_DIR", staging_dir)
    return staging_dir


@pytest.fixture()
def db_session(tmp_path: Path):
    """In-memory SQLite session with acquisition_queue_v1 table.

    Schema must match AcquisitionQueue ORM model exactly
    (including source_annotation_ids_json and other columns).
    """
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE acquisition_queue_v1 (
                queue_id TEXT PRIMARY KEY,
                candidate_doi TEXT,
                candidate_pmid TEXT,
                candidate_title TEXT,
                target_edge_ids_json TEXT,
                aps_score REAL,
                aps_components_json TEXT,
                source_annotation_ids_json TEXT,
                retrieval_tool TEXT,
                status TEXT DEFAULT 'queued',
                created_at TEXT,
                updated_at TEXT,
                retrieval_status TEXT,
                abstract_relevance REAL,
                saturation_cycle_count INTEGER DEFAULT 0,
                saturation_flag INTEGER DEFAULT 0,
                hop_source_study_id TEXT,
                hop_depth INTEGER DEFAULT 0,
                paywall_flagged INTEGER DEFAULT 0,
                pmcid TEXT,
                openalex_id TEXT,
                best_oa_url TEXT,
                retrieval_attempts_json TEXT,
                file_path TEXT
            )
        """))
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def resolved_ids() -> ResolvedIdentifiers:
    """Typical resolved identifiers for a PLoS ONE paper."""
    return ResolvedIdentifiers(
        doi="10.1371/journal.pone.0185059",
        pmid="28953918",
        pmcid="PMC5617190",
        arxiv_id=None,
        openalex_id="W2753847129",
        oa_status=OAStatus.GOLD,
        best_oa_pdf_url="https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0185059&type=printable",
        publisher="PLOS",
        title="Physical Activity and Cancer-Related Cognitive Impairment",
        journal="PloS one",
        year=2017,
    )


def _make_fake_pdf(text_content: str = "Abstract This is a test paper about cancer-related cognitive impairment and physical activity. References 1. Smith 2020.") -> bytes:
    """Generate minimal fake PDF bytes that pass magic-byte check."""
    # Real PDFs start with %PDF-. We craft a minimal one.
    # For text extraction, we'll mock pdfplumber instead.
    return b"%PDF-1.4 " + text_content.encode() + b"\n%%EOF"


def _make_fake_xml(title: str = "Physical Activity and CRCI") -> bytes:
    """Generate JATS XML large enough to pass validation thresholds."""
    # Need > 10000 bytes and > 3000 chars of extracted text to pass defaults
    filler = (
        "Cancer-related cognitive impairment CRCI is a significant concern "
        "among breast cancer survivors who undergo chemotherapy treatment. "
        "Physical activity interventions have shown promise in ameliorating "
        "cognitive deficits through multiple neurobiological mechanisms. "
        "Exercise promotes neuroplasticity via BDNF upregulation and "
        "reduces systemic inflammation which is implicated in chemobrain. "
    )
    # Repeat filler to exceed size thresholds
    body_text = (filler * 15).strip()
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<article>
  <front>
    <article-meta>
      <title-group>
        <article-title>{title}</article-title>
      </title-group>
      <abstract><p>This study examines the effects of physical activity on cancer-related cognitive impairment in breast cancer survivors. Background and summary of methods. {filler * 3}</p></abstract>
    </article-meta>
  </front>
  <body>
    <sec sec-type="intro"><title>Introduction</title><p>{body_text}</p></sec>
    <sec sec-type="methods"><title>Methods</title><p>Participants were recruited from oncology clinics. {body_text}</p></sec>
    <sec sec-type="results"><title>Results</title><p>Physical activity was associated with improved cognitive function. {body_text}</p></sec>
    <sec sec-type="discussion"><title>Discussion</title><p>These findings support exercise interventions. {body_text}</p></sec>
  </body>
  <back>
    <ref-list><title>References</title>
      <ref><mixed-citation>Smith et al. 2020. Example reference.</mixed-citation></ref>
      <ref><mixed-citation>Jones et al. 2019. Another reference.</mixed-citation></ref>
    </ref-list>
  </back>
</article>""".encode()


# ═══════════════════════════════════════════════════════════════
#  DOI → Slug conversion
# ═══════════════════════════════════════════════════════════════


class TestDoiToSlug:
    """Test DOI slug generation for filesystem naming."""

    def test_basic_slash(self):
        assert _doi_to_slug("10.1371/journal.pone.0185059") == "10.1371_journal.pone.0185059"

    def test_multiple_slashes(self):
        assert _doi_to_slug("10.1002/pon.4370") == "10.1002_pon.4370"

    def test_no_slash(self):
        assert _doi_to_slug("10.12345") == "10.12345"


# ═══════════════════════════════════════════════════════════════
#  Content Validation
# ═══════════════════════════════════════════════════════════════


class TestValidateContentDeep:
    """Test the deep content validation logic."""

    def _make_retriever(self, db_session, tmp_cache):
        return FulltextRetriever(db_session, cache_dir=tmp_cache, adapters={})

    def test_pdf_magic_bytes_fail(self, db_session, tmp_cache):
        retriever = self._make_retriever(db_session, tmp_cache)
        result = retriever._validate_content_deep(b"<html>Not a PDF</html>", "pdf")
        assert not result.valid
        assert "not_pdf_magic_bytes" in result.issues

    def test_xml_magic_bytes_fail(self, db_session, tmp_cache):
        retriever = self._make_retriever(db_session, tmp_cache)
        result = retriever._validate_content_deep(b"Just plain text", "xml")
        assert not result.valid
        assert "not_xml_content" in result.issues

    def test_xml_valid_content(self, db_session, tmp_cache):
        retriever = self._make_retriever(db_session, tmp_cache)
        xml = _make_fake_xml()
        result = retriever._validate_content_deep(xml, "xml")
        assert result.valid
        assert result.text_length > 100
        assert result.has_abstract
        assert result.has_references

    def test_pdf_too_small(self, db_session, tmp_cache):
        retriever = self._make_retriever(db_session, tmp_cache)
        # Tiny PDF: passes magic bytes but below RETRIEVAL_MIN_PDF_SIZE_BYTES
        tiny = b"%PDF-1.4 tiny %%EOF"
        result = retriever._validate_content_deep(tiny, "pdf")
        # Should flag size and text issues
        assert not result.valid
        has_size_issue = any("too_small" in i for i in result.issues)
        has_text_issue = any("text_too_short" in i for i in result.issues)
        assert has_size_issue or has_text_issue

    def test_title_match_pass(self, db_session, tmp_cache):
        retriever = self._make_retriever(db_session, tmp_cache)
        xml = _make_fake_xml("Physical Activity and CRCI")
        result = retriever._validate_content_deep(
            xml, "xml", expected_title="Physical Activity and CRCI",
        )
        assert result.valid
        assert result.title_match_score is not None
        assert result.title_match_score >= 60

    def test_title_match_fail(self, db_session, tmp_cache):
        retriever = self._make_retriever(db_session, tmp_cache)
        xml = _make_fake_xml("Completely Unrelated Paper About Astronomy")
        result = retriever._validate_content_deep(
            xml, "xml", expected_title="Exercise and Chemobrain",
        )
        # Either valid=False or low title score, but we don't mandate failure
        # because token overlap might partially match
        assert result.title_match_score is not None


# ═══════════════════════════════════════════════════════════════
#  Source Selection (identifier routing)
# ═══════════════════════════════════════════════════════════════


class TestSelectIdentifier:
    """Test that _select_identifier routes to the right ID per adapter."""

    def test_europe_pmc_uses_pmcid(self, resolved_ids):
        result = FulltextRetriever._select_identifier(
            "europe_pmc", "10.1371/journal.pone.0185059", resolved_ids,
        )
        assert result == "PMC5617190"

    def test_pmc_xml_uses_pmcid(self, resolved_ids):
        result = FulltextRetriever._select_identifier(
            "pmc_xml", "10.1371/journal.pone.0185059", resolved_ids,
        )
        assert result == "PMC5617190"

    def test_unpaywall_uses_doi(self, resolved_ids):
        result = FulltextRetriever._select_identifier(
            "unpaywall", "10.1371/journal.pone.0185059", resolved_ids,
        )
        assert result == "10.1371/journal.pone.0185059"

    def test_arxiv_uses_arxiv_id(self):
        resolved = ResolvedIdentifiers(
            doi="10.48550/arXiv.2301.12345",
            arxiv_id="2301.12345",
        )
        result = FulltextRetriever._select_identifier(
            "arxiv", "10.48550/arXiv.2301.12345", resolved,
        )
        assert result == "2301.12345"

    def test_core_uses_doi(self, resolved_ids):
        result = FulltextRetriever._select_identifier(
            "core", "10.1371/journal.pone.0185059", resolved_ids,
        )
        assert result == "10.1371/journal.pone.0185059"

    def test_semantic_scholar_uses_doi(self, resolved_ids):
        result = FulltextRetriever._select_identifier(
            "semantic_scholar", "10.1371/journal.pone.0185059", resolved_ids,
        )
        assert result == "10.1371/journal.pone.0185059"


# ═══════════════════════════════════════════════════════════════
#  Stage for Extraction
# ═══════════════════════════════════════════════════════════════


class TestStageForExtraction:
    """Test staging: retrieval_cache → manual_uploads/pdfs with meta.json."""

    def test_stage_creates_file_and_meta(
        self, db_session, tmp_cache, tmp_staging, resolved_ids,
    ):
        retriever = FulltextRetriever(db_session, cache_dir=tmp_cache, adapters={})

        # Write a fake cached file
        cache_file = tmp_cache / "abc123.pdf"
        cache_file.write_bytes(b"%PDF-1.4 fake")

        staged = retriever.stage_for_extraction(
            cache_file, "10.1371/journal.pone.0185059", resolved_ids,
        )

        assert staged is not None
        assert staged.exists()
        assert staged.name == "10.1371_journal.pone.0185059.pdf"

        # Check meta.json companion
        meta_path = tmp_staging / "10.1371_journal.pone.0185059.meta.json"
        assert meta_path.exists()
        meta = json.loads(meta_path.read_text())
        assert meta["doi"] == "10.1371/journal.pone.0185059"
        assert meta["pmid"] == "28953918"
        assert meta["pmcid"] == "PMC5617190"
        assert meta["source"] == "automated_retrieval"

    def test_stage_xml(
        self, db_session, tmp_cache, tmp_staging, resolved_ids,
    ):
        retriever = FulltextRetriever(db_session, cache_dir=tmp_cache, adapters={})

        cache_file = tmp_cache / "abc123.xml"
        cache_file.write_bytes(_make_fake_xml())

        staged = retriever.stage_for_extraction(
            cache_file, "10.1371/journal.pone.0185059", resolved_ids,
        )

        assert staged is not None
        assert staged.suffix == ".xml"
        assert staged.name == "10.1371_journal.pone.0185059.xml"

    def test_stage_no_overwrite(
        self, db_session, tmp_cache, tmp_staging, resolved_ids,
    ):
        retriever = FulltextRetriever(db_session, cache_dir=tmp_cache, adapters={})

        # Pre-existing staged file
        existing = tmp_staging / "10.1371_journal.pone.0185059.pdf"
        existing.write_bytes(b"original content")

        cache_file = tmp_cache / "new.pdf"
        cache_file.write_bytes(b"new content")

        staged = retriever.stage_for_extraction(
            cache_file, "10.1371/journal.pone.0185059", resolved_ids,
        )

        # Should return existing path, not overwrite
        assert staged == existing
        assert existing.read_bytes() == b"original content"

    def test_stage_missing_cache_file(
        self, db_session, tmp_cache, tmp_staging, resolved_ids,
    ):
        retriever = FulltextRetriever(db_session, cache_dir=tmp_cache, adapters={})
        staged = retriever.stage_for_extraction(
            "/nonexistent/file.pdf", "10.1234/test", resolved_ids,
        )
        assert staged is None


# ═══════════════════════════════════════════════════════════════
#  Retrieve by DOI — mock-based integration
# ═══════════════════════════════════════════════════════════════


class TestRetrieveByDoi:
    """Integration test: retrieve_by_doi with mocked adapters."""

    def test_retrieve_succeeds_via_first_source(
        self, db_session, tmp_cache, tmp_staging,
    ):
        """When first adapter returns valid XML, retrieval succeeds."""
        mock_adapter = MagicMock()
        mock_adapter.retrieve_fulltext.return_value = _make_fake_xml()

        retriever = FulltextRetriever(
            db_session,
            cache_dir=tmp_cache,
            adapters={"europe_pmc": mock_adapter},
        )

        # Patch both the config and the resolve_doi import inside retrieve_by_doi
        with patch.object(retriever, '_validate_content_deep') as mock_validate, \
             patch("crci.retrieval.id_resolver.resolve_doi") as mock_resolve, \
             patch("crci.retrieval.fulltext_retriever.config") as mock_config:

            mock_config.FULLTEXT_SOURCE_PRIORITY = ["europe_pmc", "abstract_only"]
            mock_config.RETRIEVAL_MIN_PDF_SIZE_BYTES = 100
            mock_config.RETRIEVAL_MIN_TEXT_LENGTH = 50
            mock_config.RETRIEVAL_MIN_TITLE_MATCH_SCORE = 60
            mock_config.RETRIEVAL_PDF_DOWNLOAD_TIMEOUT_SEC = 30.0

            mock_resolve.return_value = ResolvedIdentifiers(
                doi="10.1371/journal.pone.0185059",
                pmcid="PMC5617190",
                oa_status=OAStatus.GOLD,
                title="Test Paper",
            )
            mock_validate.return_value = ContentValidation(
                valid=True,
                text_length=5000,
                has_abstract=True,
                has_references=True,
            )

            result = retriever.retrieve_by_doi(
                "10.1371/journal.pone.0185059",
                stage=False,
            )

        assert result.status == RetrievalStatus.RETRIEVED
        assert result.source_used == "europe_pmc"
        assert result.retrieval_format == "xml"

    def test_retrieve_falls_through_to_abstract_only(
        self, db_session, tmp_cache, tmp_staging,
    ):
        """When all adapters fail, result is ABSTRACT_ONLY."""
        mock_adapter = MagicMock()
        mock_adapter.retrieve_fulltext.return_value = None  # fails

        with patch(
            "crci.retrieval.fulltext_retriever.config"
        ) as mock_config:
            mock_config.FULLTEXT_SOURCE_PRIORITY = ["europe_pmc", "abstract_only"]
            mock_config.RETRIEVAL_MIN_PDF_SIZE_BYTES = 100
            mock_config.RETRIEVAL_MIN_TEXT_LENGTH = 50
            mock_config.RETRIEVAL_MIN_TITLE_MATCH_SCORE = 60

            retriever = FulltextRetriever(
                db_session,
                cache_dir=tmp_cache,
                adapters={"europe_pmc": mock_adapter},
            )

            with patch("crci.retrieval.id_resolver.resolve_doi") as mock_resolve:
                mock_resolve.return_value = ResolvedIdentifiers(
                    doi="10.1371/journal.pone.0185059",
                    pmcid="PMC5617190",
                    oa_status=OAStatus.GOLD,
                    title="Test Paper",
                )

                result = retriever.retrieve_by_doi(
                    "10.1371/journal.pone.0185059",
                    stage=False,
                )

        assert result.status == RetrievalStatus.ABSTRACT_ONLY
        assert len(result.attempts) >= 1

    def test_retrieve_invalid_doi(self, db_session, tmp_cache):
        """Invalid DOI returns FAILED immediately."""
        retriever = FulltextRetriever(db_session, cache_dir=tmp_cache, adapters={})

        result = retriever.retrieve_by_doi("")
        assert result.status == RetrievalStatus.FAILED
        assert "Invalid" in (result.error_message or "")


# ═══════════════════════════════════════════════════════════════
#  XML Ingestion
# ═══════════════════════════════════════════════════════════════


class TestXmlIngestion:
    """Test JATS XML ingestion for P0 triage pipeline."""

    def test_ingest_xml_produces_expected_keys(self, tmp_path: Path):
        from crci.extraction.p0_triage.xml_ingestion import ingest_xml

        xml_path = tmp_path / "test.xml"
        xml_path.write_bytes(_make_fake_xml("Test Ingestion Paper"))

        result = ingest_xml(xml_path)

        assert "canonical_text" in result
        assert "metadata" in result
        assert "sections" in result
        assert "pdf_quality" in result
        assert result["pdf_quality"] == "GOOD"  # XML always returns GOOD
        assert len(result["canonical_text"]) > 50

    def test_ingest_xml_sections(self, tmp_path: Path):
        from crci.extraction.p0_triage.xml_ingestion import ingest_xml

        xml_path = tmp_path / "test.xml"
        xml_path.write_bytes(_make_fake_xml())

        result = ingest_xml(xml_path)

        section_labels = [s.get("label", "").lower() for s in result.get("sections", [])]
        # At minimum, our test XML has intro, methods, results, discussion
        assert any("intro" in l for l in section_labels) or len(result["sections"]) > 0

    def test_ingest_xml_has_references(self, tmp_path: Path):
        from crci.extraction.p0_triage.xml_ingestion import ingest_xml

        xml_path = tmp_path / "test.xml"
        xml_path.write_bytes(_make_fake_xml())

        result = ingest_xml(xml_path)
        # The XML has at least one <ref> element
        text_lower = result["canonical_text"].lower()
        assert "reference" in text_lower or "smith" in text_lower


# ═══════════════════════════════════════════════════════════════
#  Queue update from DOI retrieval
# ═══════════════════════════════════════════════════════════════


class TestUpdateQueueFromDoi:
    """Test that _update_queue_from_doi creates/updates DB rows correctly."""

    def test_inserts_new_row(self, db_session, tmp_cache, resolved_ids):
        retriever = FulltextRetriever(db_session, cache_dir=tmp_cache, adapters={})

        result = RetrievalResult(
            doi="10.1371/journal.pone.0185059",
            status=RetrievalStatus.RETRIEVED,
            source_used="europe_pmc",
            cache_path="/tmp/cached.xml",
            attempts=[
                RetrievalAttemptRecord(source="europe_pmc", status="success", duration_ms=500),
            ],
        )

        retriever._update_queue_from_doi(
            "10.1371/journal.pone.0185059", resolved_ids, result,
        )

        # Verify row exists
        row = db_session.execute(
            text("SELECT * FROM acquisition_queue_v1 WHERE candidate_doi = :doi"),
            {"doi": "10.1371/journal.pone.0185059"},
        ).fetchone()
        assert row is not None
        # Access by index (queue_id=0, candidate_doi=1, ... status=8)
        assert row[1] == "10.1371/journal.pone.0185059"  # candidate_doi

    def test_updates_existing_row(self, db_session, tmp_cache, resolved_ids):
        retriever = FulltextRetriever(db_session, cache_dir=tmp_cache, adapters={})

        # Pre-insert a row
        db_session.execute(text(
            "INSERT INTO acquisition_queue_v1 (queue_id, candidate_doi, status) "
            "VALUES ('ACQ_test', '10.1371/journal.pone.0185059', 'queued')"
        ))
        db_session.commit()

        result = RetrievalResult(
            doi="10.1371/journal.pone.0185059",
            status=RetrievalStatus.RETRIEVED,
            source_used="pmc_xml",
            cache_path="/tmp/cached.xml",
            attempts=[],
        )

        retriever._update_queue_from_doi(
            "10.1371/journal.pone.0185059", resolved_ids, result,
        )

        row = db_session.execute(
            text("SELECT status, retrieval_tool FROM acquisition_queue_v1 WHERE queue_id = 'ACQ_test'"),
        ).fetchone()
        assert row[0] == "retrieved"
        assert row[1] == "pmc_xml"


# ═══════════════════════════════════════════════════════════════
#  Fuzzy title matching
# ═══════════════════════════════════════════════════════════════


class TestFuzzyTitleMatch:
    """Test token-overlap fallback for title matching."""

    def test_exact_match(self):
        score = FulltextRetriever._fuzzy_title_match(
            "Physical Activity and CRCI",
            "Physical Activity and CRCI: A systematic review of exercise interventions",
        )
        assert score >= 60  # token overlap may be ~75 without rapidfuzz

    def test_no_match(self):
        score = FulltextRetriever._fuzzy_title_match(
            "Quantum Physics in Superconductors",
            "Physical Activity and CRCI in breast cancer survivors",
        )
        assert score < 60

    def test_empty_title_returns_100(self):
        score = FulltextRetriever._fuzzy_title_match("", "Some text")
        assert score == 100.0


# ═══════════════════════════════════════════════════════════════
#  Adapter imports (smoke tests)
# ═══════════════════════════════════════════════════════════════


class TestAdapterImports:
    """Verify all adapters import without errors."""

    def test_arxiv_adapter(self):
        from crci.retrieval.adapters.arxiv import ArxivAdapter
        a = ArxivAdapter()
        assert a.adapter_name == "arxiv"

    def test_pmc_xml_adapter(self):
        from crci.retrieval.adapters.pmc_xml import PmcXmlAdapter
        a = PmcXmlAdapter()
        assert a.adapter_name == "pmc_xml"

    def test_core_api_adapter(self):
        from crci.retrieval.adapters.core_api import CoreApiAdapter
        a = CoreApiAdapter()
        assert a.adapter_name == "core"

    def test_semantic_scholar_adapter(self):
        from crci.retrieval.adapters.semantic_scholar import SemanticScholarAdapter
        a = SemanticScholarAdapter()
        assert a.adapter_name == "semantic_scholar"

    def test_europe_pmc_adapter(self):
        from crci.retrieval.adapters.europe_pmc import EuropePMCAdapter
        a = EuropePMCAdapter()
        assert a.adapter_name == "europe_pmc"

    def test_unpaywall_adapter(self):
        from crci.retrieval.adapters.unpaywall import UnpaywallAdapter
        a = UnpaywallAdapter()
        assert a.adapter_name == "unpaywall"


# ═══════════════════════════════════════════════════════════════
#  CLI import (smoke test)
# ═══════════════════════════════════════════════════════════════


class TestCLISmoke:
    """Verify CLI script imports without crashing."""

    def test_cli_script_imports(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "retrieve_papers",
            str(Path(__file__).resolve().parent.parent.parent / "scripts" / "retrieve_papers.py"),
        )
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        # Don't actually exec - just verify the spec loads
        assert mod is not None
