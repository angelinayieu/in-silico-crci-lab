# VERIFIED: formulas — none (structural parsing, no numeric formulas)
# VERIFIED: imports — all modules exist (shared.models.intermediate_states, llm.client)
# VERIFIED: backward wiring — reads str (canonical_text from pdf_ingestion)
# VERIFIED: forward wiring — writes PaperMap for all agents (base_agent.py)
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates P1-G1 raise on failure
"""
Component: SYS_EXTRACTION.EX-P1-CR
Spec: SYS_EXTRACTION_COMPLETE.md lines 292-380 (EX-P1 v2 overview + CR subsystem)
      SYS_EXTRACTION_COMPLETE.md lines 330-370 (PaperMap schema, 4 sub-steps)
      SYS_EXTRACTION_COMPLETE.md lines 428-447 (CR sub-steps detail)
Formulas: None (structural parsing, no numeric formulas)
Reads: canonical_text (str from pdf_ingestion.py), paper_id (str)
Writes: PaperMap (consumed by all agents AG1-AG10 via base_agent.py)
Gates: P1-G1 (PaperMap has >= 3 sections)
"""
from __future__ import annotations

import hashlib
import logging
import re
import uuid
from typing import Any

from pydantic import BaseModel, Field

from crci.llm.client import LLMClient
from crci.shared.models.intermediate_states import (
    CandidateSpan,
    FigureEntry,
    GateViolation,
    PaperMap,
    SectionSegment,
    TableEntry,
)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  LLM Response Schemas for Canonical Reader
# ═══════════════════════════════════════════════════════════════

# Section types per spec: 7+ structural section types
SECTION_TYPES: list[str] = [
    "title",
    "abstract",
    "introduction",
    "methods",
    "results",
    "discussion",
    "conclusion",
    "references",
    "supplementary",
    "acknowledgements",
    "affiliations",
    "limitations",
    "appendix",
]

# Minimum sections required for gate P1-G1
MIN_SECTIONS_GATE: int = 3


class SectionSegmentResponse(BaseModel):
    """LLM response for section segmentation (CR-a)."""

    class SegmentItem(BaseModel):
        section_type: str
        heading: str | None = None
        char_start: int
        char_end: int

    segments: list[SegmentItem] = Field(default_factory=list)


class TableFigureResponse(BaseModel):
    """LLM response for table/figure registry (CR-b)."""

    class TableItem(BaseModel):
        table_id: str
        caption: str | None = None
        char_start: int
        char_end: int

    class FigureItem(BaseModel):
        figure_id: str
        caption: str | None = None

    tables: list[TableItem] = Field(default_factory=list)
    figures: list[FigureItem] = Field(default_factory=list)


class BasicStudyObjectResponse(BaseModel):
    """LLM response for basic study object (CR-d)."""

    study_design: str | None = None
    n_total: int | None = None
    arms: list[str] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
#  Regex patterns for CR-c: Candidate Span Identifier
# ═══════════════════════════════════════════════════════════════

# Patterns to detect numeric statistical claims in text
_NUMERIC_PATTERNS: list[tuple[str, str]] = [
    # Effect sizes with CIs: "0.35 (95% CI: 0.12-0.58)"
    (
        r"[-+]?\d+\.?\d*\s*\(\s*95%?\s*CI[:\s]*[-+]?\d+\.?\d*\s*[-–—to,]\s*[-+]?\d+\.?\d*\s*\)",
        "effect_with_ci",
    ),
    # p-values: "p = 0.003", "p < 0.001", "P-value = .05"
    (
        r"[Pp]\s*[-=<>]\s*\.?\d+\.?\d*",
        "p_value",
    ),
    # Odds/Hazard/Risk ratios: "OR = 1.5", "HR 2.3", "RR = 0.8"
    (
        r"(?:OR|HR|RR|aOR|aHR)\s*[=:]\s*[-+]?\d+\.?\d*",
        "ratio",
    ),
    # Mean +/- SD: "mean = 3.2 +/- 1.1", "M = 45.3, SD = 12.1"
    (
        r"(?:mean|[Mm])\s*[=:]\s*[-+]?\d+\.?\d*\s*[±+/-]+\s*\d+\.?\d*",
        "mean_sd",
    ),
    # Sample sizes: "N = 120", "n = 45", "(N=200)"
    (
        r"[Nn]\s*=\s*\d+",
        "sample_size",
    ),
    # Beta coefficients: "β = 0.35", "b = -0.12"
    (
        r"[βb]\s*=\s*[-+]?\d+\.?\d*",
        "beta",
    ),
    # Cohen's d or effect sizes: "d = 0.5", "η² = 0.12"
    (
        r"(?:d|η²|g|f²?)\s*=\s*[-+]?\d+\.?\d*",
        "effect_size",
    ),
    # F-statistics: "F(1,45) = 12.3"
    (
        r"[Ff]\s*\(\s*\d+\s*,\s*\d+\s*\)\s*=\s*\d+\.?\d*",
        "f_statistic",
    ),
    # t-statistics: "t(45) = 2.3", "t = -1.8"
    (
        r"[Tt]\s*(?:\(\s*\d+\s*\))?\s*=\s*[-+]?\d+\.?\d*",
        "t_statistic",
    ),
    # Chi-square: "χ²(1) = 4.5", "chi2 = 3.84"
    (
        r"(?:χ²|chi2?)\s*(?:\(\s*\d+\s*\))?\s*=\s*\d+\.?\d*",
        "chi_square",
    ),
    # Correlation: "r = 0.45", "r = -0.32"
    (
        r"[Rr]\s*=\s*[-+]?\d*\.?\d+",
        "correlation",
    ),
    # Percentage: "45.3%", "12%"
    (
        r"\d+\.?\d*\s*%",
        "percentage",
    ),
]

# Pre-compile patterns for performance
_COMPILED_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(pattern), label) for pattern, label in _NUMERIC_PATTERNS
]


class CanonicalReader:
    """Reads paper ONCE, creates PaperMap shared by all agents.

    Implements the 4 sub-steps defined in SYS_EX lines 428-447:
      CR-a: Section Segmenter - classify paper into structural sections (7+ types)
      CR-b: Table/Figure Registry - enumerate all tables + figures with captions
      CR-c: Candidate Span Identifier - pre-identify high-signal spans (regex)
      CR-d: Basic Study Object - quick parse: design, N, interventions, outcomes

    Uses LLM for section segmentation (CR-a) and table/figure detection (CR-b).
    Uses regex for candidate span identification (CR-c).
    Uses LLM for basic study object parsing (CR-d).
    """

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm_client = llm_client

    def read(self, paper_id: str, canonical_text: str) -> PaperMap:
        """Execute all 4 CR sub-steps and produce PaperMap.

        Args:
            paper_id: Unique paper identifier.
            canonical_text: Full canonical text of the paper.

        Returns:
            PaperMap with sections, tables, figures, candidate_spans,
            n_total, study_design, and arms populated.

        Raises:
            GateViolation: P1-G1 if PaperMap has < 3 sections.
        """
        logger.info(
            "CanonicalReader.read: starting for paper_id=%s, text_length=%d",
            paper_id,
            len(canonical_text),
        )

        # CR-a: Section Segmenter
        sections = self._segment_sections(canonical_text)

        # Gate P1-G1: PaperMap must have >= 3 sections
        if len(sections) < MIN_SECTIONS_GATE:
            raise GateViolation(
                gate_id="P1-G1",
                message=(
                    f"PaperMap has {len(sections)} sections, "
                    f"minimum required is {MIN_SECTIONS_GATE}. "
                    f"Paper may not be a valid research article."
                ),
                context={
                    "paper_id": paper_id,
                    "section_count": len(sections),
                    "min_required": MIN_SECTIONS_GATE,
                },
            )

        # CR-b: Table/Figure Registry
        tables, figures = self._detect_tables_and_figures(canonical_text, sections)

        # CR-c: Candidate Span Identifier (regex-based)
        candidate_spans = self._identify_candidate_spans(canonical_text, sections)

        # CR-d: Basic Study Object
        study_design, n_total, arms = self._parse_basic_study_object(
            canonical_text, sections
        )

        # Determine title from sections
        title: str | None = None
        for section in sections:
            if section.section_type == "title":
                title = section.text.strip()
                break

        paper_map = PaperMap(
            paper_id=paper_id,
            title=title,
            full_text=canonical_text,
            sections=sections,
            tables=tables,
            figures=figures,
            candidate_spans=candidate_spans,
            n_total=n_total,
            study_design=study_design,
            arms=arms,
        )

        logger.info(
            "CanonicalReader.read: completed paper_id=%s — "
            "sections=%d, tables=%d, figures=%d, candidate_spans=%d, "
            "n_total=%s, study_design=%s",
            paper_id,
            len(sections),
            len(tables),
            len(figures),
            len(candidate_spans),
            n_total,
            study_design,
        )

        return paper_map

    # ═══════════════════════════════════════════════════════════
    #  CR-a: Section Segmenter
    # ═══════════════════════════════════════════════════════════

    def _segment_sections(self, canonical_text: str) -> list[SectionSegment]:
        """CR-a: Classify paper into structural sections (7+ types).

        Uses LLM to identify section boundaries and types.
        Falls back to heuristic detection if LLM fails.
        """
        section_types_str = ", ".join(SECTION_TYPES)
        prompt = (
            "You are a scientific paper section segmenter. Analyze the following "
            "paper text and identify all structural sections.\n\n"
            f"Valid section types: {section_types_str}\n\n"
            "For each section, provide:\n"
            "- section_type: one of the valid types above\n"
            "- heading: the section heading text (if any)\n"
            "- char_start: character offset where the section begins\n"
            "- char_end: character offset where the section ends\n\n"
            "Sections must not overlap and must cover the entire text.\n"
            "Return JSON with a 'segments' array.\n\n"
            f"PAPER TEXT:\n{canonical_text}"
        )

        try:
            response = self._llm_client.call(
                prompt=prompt,
                response_schema=SectionSegmentResponse,
                system_prompt=(
                    "You are a precise scientific document parser. "
                    "Return valid JSON only."
                ),
            )
            sections = [
                SectionSegment(
                    section_type=seg.section_type.lower(),
                    heading=seg.heading,
                    char_start=seg.char_start,
                    char_end=min(seg.char_end, len(canonical_text)),
                    text=canonical_text[
                        seg.char_start : min(seg.char_end, len(canonical_text))
                    ],
                )
                for seg in response.segments
                if seg.char_start < len(canonical_text)
            ]
        except Exception:
            logger.warning(
                "CR-a: LLM section segmentation failed, "
                "falling back to heuristic detection."
            )
            sections = self._heuristic_section_detection(canonical_text)

        if not sections:
            logger.warning(
                "CR-a: No sections detected, creating single 'unknown' section "
                "covering entire text as fallback."
            )
            sections = [
                SectionSegment(
                    section_type="unknown",
                    heading=None,
                    char_start=0,
                    char_end=len(canonical_text),
                    text=canonical_text,
                )
            ]

        return sections

    def _heuristic_section_detection(
        self, canonical_text: str
    ) -> list[SectionSegment]:
        """Fallback heuristic section detection using heading patterns."""
        heading_patterns: list[tuple[str, re.Pattern[str]]] = [
            ("abstract", re.compile(r"(?i)^\s*abstract\s*$", re.MULTILINE)),
            ("introduction", re.compile(r"(?i)^\s*(?:1\.?\s+)?introduction\s*$", re.MULTILINE)),
            ("methods", re.compile(r"(?i)^\s*(?:2\.?\s+)?(?:methods?|materials?\s+and\s+methods?)\s*$", re.MULTILINE)),
            ("results", re.compile(r"(?i)^\s*(?:3\.?\s+)?results?\s*$", re.MULTILINE)),
            ("discussion", re.compile(r"(?i)^\s*(?:4\.?\s+)?discussion\s*$", re.MULTILINE)),
            ("conclusion", re.compile(r"(?i)^\s*(?:5\.?\s+)?conclusions?\s*$", re.MULTILINE)),
            ("references", re.compile(r"(?i)^\s*references?\s*$", re.MULTILINE)),
            ("acknowledgements", re.compile(r"(?i)^\s*acknowledgements?\s*$", re.MULTILINE)),
            ("limitations", re.compile(r"(?i)^\s*limitations?\s*$", re.MULTILINE)),
        ]

        found: list[tuple[str, str | None, int]] = []
        for section_type, pattern in heading_patterns:
            match = pattern.search(canonical_text)
            if match:
                found.append((section_type, match.group().strip(), match.start()))

        # Sort by position
        found.sort(key=lambda x: x[2])

        sections: list[SectionSegment] = []

        # If nothing found before the first heading, treat as title
        if found and found[0][2] > 0:
            sections.append(
                SectionSegment(
                    section_type="title",
                    heading=None,
                    char_start=0,
                    char_end=found[0][2],
                    text=canonical_text[: found[0][2]],
                )
            )

        for i, (section_type, heading, start) in enumerate(found):
            end = found[i + 1][2] if i + 1 < len(found) else len(canonical_text)
            sections.append(
                SectionSegment(
                    section_type=section_type,
                    heading=heading,
                    char_start=start,
                    char_end=end,
                    text=canonical_text[start:end],
                )
            )

        return sections

    # ═══════════════════════════════════════════════════════════
    #  CR-b: Table/Figure Registry
    # ═══════════════════════════════════════════════════════════

    def _detect_tables_and_figures(
        self, canonical_text: str, sections: list[SectionSegment]
    ) -> tuple[list[TableEntry], list[FigureEntry]]:
        """CR-b: Enumerate all tables + figures with captions.

        Uses LLM for detection, with regex fallback.
        """
        prompt = (
            "You are a scientific paper table and figure detector. "
            "Analyze the following paper text and identify all tables and figures.\n\n"
            "For each table, provide:\n"
            "- table_id: e.g., 'Table 1', 'Table 2'\n"
            "- caption: the table caption text\n"
            "- char_start: character offset where the table begins\n"
            "- char_end: character offset where the table ends\n\n"
            "For each figure, provide:\n"
            "- figure_id: e.g., 'Figure 1', 'Fig. 2'\n"
            "- caption: the figure caption text\n\n"
            "Return JSON with 'tables' and 'figures' arrays.\n\n"
            f"PAPER TEXT:\n{canonical_text}"
        )

        tables: list[TableEntry] = []
        figures: list[FigureEntry] = []

        try:
            response = self._llm_client.call(
                prompt=prompt,
                response_schema=TableFigureResponse,
                system_prompt=(
                    "You are a precise scientific document parser. "
                    "Return valid JSON only."
                ),
            )
            for t in response.tables:
                section_type = self._find_section_for_offset(sections, t.char_start)
                tables.append(
                    TableEntry(
                        table_id=t.table_id,
                        caption=t.caption,
                        section_type=section_type,
                        char_start=t.char_start,
                        char_end=min(t.char_end, len(canonical_text)),
                        raw_text=canonical_text[
                            t.char_start : min(t.char_end, len(canonical_text))
                        ],
                    )
                )
            for f in response.figures:
                figures.append(
                    FigureEntry(
                        figure_id=f.figure_id,
                        caption=f.caption,
                        section_type=None,
                    )
                )
        except Exception:
            logger.warning(
                "CR-b: LLM table/figure detection failed, "
                "falling back to regex detection."
            )
            tables, figures = self._heuristic_table_figure_detection(
                canonical_text, sections
            )

        logger.info(
            "CR-b: detected %d tables, %d figures", len(tables), len(figures)
        )
        return tables, figures

    def _heuristic_table_figure_detection(
        self, canonical_text: str, sections: list[SectionSegment]
    ) -> tuple[list[TableEntry], list[FigureEntry]]:
        """Fallback regex-based table/figure detection."""
        tables: list[TableEntry] = []
        figures: list[FigureEntry] = []

        # Detect tables: "Table 1.", "Table 1:", "TABLE 1"
        table_pattern = re.compile(
            r"(Table\s+\d+)[.:]\s*([^\n]*)", re.IGNORECASE
        )
        for match in table_pattern.finditer(canonical_text):
            table_id = match.group(1).strip()
            caption = match.group(2).strip() if match.group(2) else None
            section_type = self._find_section_for_offset(sections, match.start())
            tables.append(
                TableEntry(
                    table_id=table_id,
                    caption=caption,
                    section_type=section_type,
                    char_start=match.start(),
                    char_end=match.end(),
                    raw_text=match.group(0),
                )
            )

        # Detect figures: "Figure 1.", "Fig. 1:", "FIGURE 1"
        figure_pattern = re.compile(
            r"((?:Figure|Fig\.?)\s+\d+)[.:]\s*([^\n]*)", re.IGNORECASE
        )
        for match in figure_pattern.finditer(canonical_text):
            figure_id = match.group(1).strip()
            caption = match.group(2).strip() if match.group(2) else None
            figures.append(
                FigureEntry(
                    figure_id=figure_id,
                    caption=caption,
                    section_type=self._find_section_for_offset(
                        sections, match.start()
                    ),
                )
            )

        return tables, figures

    # ═══════════════════════════════════════════════════════════
    #  CR-c: Candidate Span Identifier
    # ═══════════════════════════════════════════════════════════

    def _identify_candidate_spans(
        self, canonical_text: str, sections: list[SectionSegment]
    ) -> list[CandidateSpan]:
        """CR-c: Pre-identify high-signal spans using regex.

        Scans for numeric results, statistical claims, and other
        high-signal text patterns. These candidate spans are used
        by AG5 (StatsLabelAgent) for targeted extraction.
        """
        candidate_spans: list[CandidateSpan] = []
        seen_ranges: set[tuple[int, int]] = set()

        for pattern, label in _COMPILED_PATTERNS:
            for match in pattern.finditer(canonical_text):
                span_range = (match.start(), match.end())
                # Skip exact duplicates
                if span_range in seen_ranges:
                    continue
                seen_ranges.add(span_range)

                section_type = self._find_section_for_offset(
                    sections, match.start()
                )
                span_id = f"cs_{uuid.uuid4().hex[:12]}"
                candidate_spans.append(
                    CandidateSpan(
                        span_id=span_id,
                        char_start=match.start(),
                        char_end=match.end(),
                        text=match.group(0),
                        section_type=section_type,
                        confidence=0.5,
                    )
                )

        # Sort by position for stable ordering
        candidate_spans.sort(key=lambda s: s.char_start)

        logger.info(
            "CR-c: identified %d candidate spans", len(candidate_spans)
        )
        return candidate_spans

    # ═══════════════════════════════════════════════════════════
    #  CR-d: Basic Study Object
    # ═══════════════════════════════════════════════════════════

    def _parse_basic_study_object(
        self, canonical_text: str, sections: list[SectionSegment]
    ) -> tuple[str | None, int | None, list[str]]:
        """CR-d: Quick parse for design, N, interventions, outcomes.

        NOT detailed extraction -- overview for agent routing.

        Returns:
            Tuple of (study_design, n_total, arms).
        """
        # Build focused text from abstract + methods
        focused_text = ""
        for section in sections:
            if section.section_type in ("abstract", "methods"):
                focused_text += section.text + "\n\n"

        # If no abstract/methods found, use first 3000 chars
        if not focused_text.strip():
            focused_text = canonical_text[:3000]
            logger.info(
                "CR-d: No abstract/methods sections found, "
                "using first 3000 characters as fallback."
            )

        prompt = (
            "You are extracting basic study metadata from a scientific paper. "
            "Analyze the following text and extract:\n\n"
            "1. study_design: The study design (e.g., 'RCT', 'longitudinal', "
            "'cross_sectional', 'meta', 'intensive', 'mechanistic', 'other')\n"
            "2. n_total: Total sample size (integer, or null if not found)\n"
            "3. arms: List of study arms/groups (e.g., ['exercise', 'control'])\n\n"
            "Return JSON with these three fields.\n\n"
            f"TEXT:\n{focused_text}"
        )

        try:
            response = self._llm_client.call(
                prompt=prompt,
                response_schema=BasicStudyObjectResponse,
                system_prompt=(
                    "You are a precise scientific metadata extractor. "
                    "Return valid JSON only."
                ),
            )
            return response.study_design, response.n_total, response.arms
        except Exception:
            logger.warning(
                "CR-d: LLM basic study object parsing failed, "
                "returning None/empty defaults."
            )
            return None, None, []

    # ═══════════════════════════════════════════════════════════
    #  Helper methods
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _find_section_for_offset(
        sections: list[SectionSegment], char_offset: int
    ) -> str | None:
        """Find which section contains the given character offset."""
        for section in sections:
            if section.char_start <= char_offset < section.char_end:
                return section.section_type
        return None
