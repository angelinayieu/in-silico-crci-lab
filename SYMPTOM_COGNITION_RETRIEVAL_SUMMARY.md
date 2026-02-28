# Symptom-Cognition Paper Retrieval Summary
## Session: February 28, 2026

### ✅ BATCH RETRIEVAL COMPLETE

**Total Papers Retrieved: 50 papers** (downloaded after 02:30)
**Total Files in Repository: 89 papers** (includes prior downloads)

---

## Retrieval Statistics

- **Format Distribution:**
  - XML format: ~35 papers (JATS XML from PMC, Frontiers, BMC, etc.)
  - PDF format: ~15 papers (from OpenAlex, publisher OA)

- **Success Rate:** ~70-80% (some paywalled papers could not be retrieved)

- **Sources:**
  - PubMed Central (PMC) ✓
  - Frontiers (open access) ✓
  - BMC (BioMed Central) ✓
  - Nature Scientific Reports ✓
  - JMIR (Journal of Medical Internet Research) ✓
  - Springer (hybrid OA) ✓
  - Elsevier (limited, some paywalled) ⚠️
  - Wiley (limited, some paywalled) ⚠️

---

## Papers Successfully Retrieved (Sample)

### Session 1 — Sleep & Insomnia
✓ PMC6640530 - Liou 2019: Insomnia → perceived cognitive impairment (breast cancer)
✓ PMC6122719 - Giffard PROSOM-K 2018: Sleep → memory (breast cancer)
✓ PMC12119337 - Pediatric CRCI

### Session 2 — Inflammation & Biomarkers
✓ PMC6792503 - Vardy 2022: Inflammation → attention/processing speed (breast cancer)
✓↓ 10.1093/annonc/mdv206 - Proinflammatory cytokines & chemotherapy-associated cognition

### Session 2 — Depression & Fatigue
✓ PMC12665909 - Onyedibe 2025: Depression/fatigue → FACT-Cog
✓ 10.1007/s10865-019-00084-7 - Symptom interconnectedness (path analysis)
✓ 10.1136/bmjopen-2018-026809 - Pain → anxiety/depression/fatigue (serial mediation)

### Session 2 — Network Analyses
✓ 10.1007/s11764-022-01246-4 - Dynamic network structure depression/symptoms (EMA)
✓ 10.1007/s11764-024-01543-0 - Symptom network analysis survivors
✓ 10.1002/cam4.70268 - Cancer-related fatigue network analysis (breast cancer)

### Session 2 — Lung Cancer
✓ 10.1016/j.apjon.2023.100200 - Luo 2023: Symptom clusters → cognitive impairment (lung)
✓ PMC10914843 - Lung cancer CRCI prevalence meta-analysis
✓ PMC12077423 - Lung cancer neuropsych protocol

### Session 2 — Other Cancer Types
✓ Colorectal: PMC4239806, PMC5683012 (Vardy 2014/2015 CRC cognition studies)
✓ Hematological: PMC7384931 (CLL), PMC10305842 (CML/TKI), PMC9046282 (Hodgkin)
✓ Gynecological: PMC6377208 (GYN CRCI review), PMC5425316 (ovarian)

### Session 2 — Reviews & Methods
✓ 10.3389/fpubh.2023.1079873 - Somatic symptom network (depression)
✓ 10.3389/fonc.2024.1380916 - GYN cancer distress trajectory

---

## Failed Retrievals (Paywalled / Not Available)

❌ Some Elsevier journals (paywalled)
❌ Some Wiley journals (paywalled)
❌ Journal of Clinical Oncology papers (JCO is paywalled)
❌ A few BMJ papers (institutional access required)

**Note:** Many paywalled papers can still be extracted if you have institutional access or can provide the PDF manually.

---

## Files Location

All retrieved papers are in:
```
/workspaces/in-silico-crci-lab/data/manual_uploads/pdfs/
```

Each paper has:
- **Main file:** `{doi_slug}.{pdf|xml}`
- **Metadata:** `{doi_slug}.meta.json` (DOI, PMID, PMCID, title, journal, year, OA status)

---

## Next Steps

### Option 1: Extract Individual Papers
```bash
# See the extraction procedure
cat extraction_ref/01_PROCEDURE.md

# Example: Extract one paper
# 1. Read the paper PDF/XML
# 2. Fill CSV templates in data/manual_uploads/structured/{doi_slug}/
# 3. Run load pipeline
```

### Option 2: Batch Process Multiple Papers
The system can process multiple papers if you:
1. Create structured folders for each paper
2. Fill edge_evidence_template.csv at minimum
3. Run batch loader

### Option 3: Search for Specific Papers
If you need specific papers that failed:
```bash
python3 scripts/retrieve_papers.py --doi "10.xxxx/xxxxx"
```

---

## Quality Notes

- **XML papers (JATS format):** Can be parsed directly for structured extraction
- **PDF papers:** Require manual reading and CSV filling (or OCR/LLM-assisted extraction)
- **All papers have metadata:** DOI, PMID, PMCID where available for provenance

---

## Attachment Note

The **fortier-brochu2012.pdf** you attached is already in:
```
/workspaces/in-silico-crci-lab/data/manual_uploads/symptoms+cognition/
```

This appears to be about insomnia/sleep therapy. Would you like me to:
1. Move it to the main pdfs/ folder?
2. Extract it as a priority paper?
3. Add it to the extraction queue?

---

**Retrieval System Status:** ✅ Fully Operational
**Total Paper Collection:** 89 papers ready for extraction
**Recommended Next Action:** Begin systematic extraction starting with high-priority RCTs and meta-analyses

Last updated: 2026-02-28 02:52:00 UTC
