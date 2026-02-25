# CRCI Bayesian Causal Model System

**A scientifically rigorous evidence-to-recommendation pipeline for Cancer-Related Cognitive Impairment**

> **Status:** v1.0 in development  
> **Last Updated:** February 25, 2026

---

## 🎯 What is This?

This system builds a **Bayesian causal model** to:
1. **Extract evidence** from research papers (~50-200 papers)
2. **Compile a causal graph** with 63 cognitive/physiological nodes and 118 causal edges
3. **Predict patient-specific CRCI risk** from questionnaire responses
4. **Rank intervention effectiveness** for each individual patient
5. **Generate scientific visualizations** for publication

**Science-first approach:** v1 focuses on producing rigorous predictions for scientific publication. Production automation comes in v2.

---

## 🚀 Getting Started

### New to This Project?

**Read these documents in order:**

1. **[INDEX.md](INDEX.md)** ← Table of contents for all documentation
2. **[IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)** ← Your complete roadmap (~15 min read)
3. **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** ← Cheat sheet for quick lookups
4. **[VISUAL_ROADMAP.md](VISUAL_ROADMAP.md)** ← Flowcharts and diagrams

**Then start implementing:**
- Open **[PROMPT_SEQUENCE.md](PROMPT_SEQUENCE.md)** 
- Execute the 42 prompts **one at a time** in order
- Follow the [6-step implementation cycle](IMPLEMENTATION_GUIDE.md#how-to-implement-each-file) for each file

### Already Started?

- Check your progress: [VISUAL_ROADMAP.md](VISUAL_ROADMAP.md#progress-tracking)
- Find your next task: [PROMPT_SEQUENCE.md](PROMPT_SEQUENCE.md)
- Look up a formula: [QUICK_REFERENCE.md](QUICK_REFERENCE.md#finding-information-fast)
- Troubleshoot an issue: [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md#troubleshooting--common-issues)

---

## 📖 Documentation Structure

### Essential Reading

| Document | Purpose | When to Read |
|----------|---------|--------------|
| **[IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)** | Complete roadmap with everything you need | First (15-20 min) |
| **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** | One-page cheat sheet | Skim & bookmark |
| **[VISUAL_ROADMAP.md](VISUAL_ROADMAP.md)** | Flowcharts, diagrams, progress tracking | Visual learners |
| **[INDEX.md](INDEX.md)** | Complete documentation catalog | When lost |

### Implementation Guides

| Document | Purpose | When to Use |
|----------|---------|-------------|
| **[PROMPT_SEQUENCE.md](PROMPT_SEQUENCE.md)** | 42 prompts across 7 phases | Execute sequentially |
| **[FILE_CONTEXT_MANIFEST.md](FILE_CONTEXT_MANIFEST.md)** | Per-file implementation specs | Before each file |
| **[CODE_QUALITY_ENFORCEMENT.md](CODE_QUALITY_ENFORCEMENT.md)** | 12 rules + verifications | Every file, every phase |

### Technical Specifications

| Document | Content | Used In |
|----------|---------|---------|
| **[SYS_EXTRACTION_COMPLETE.md](SYS_EXTRACTION_COMPLETE.md)** | Extraction chains (2,764 lines) | Phases 1-4 |
| **[SYS_ALGORITHM_COMPLETE.md](SYS_ALGORITHM_COMPLETE.md)** | Algorithm chains (4,418 lines) | Phase 5 |
| **[SYS_RUNTIME_COMPLETE.md](SYS_RUNTIME_COMPLETE.md)** | Runtime orchestration (752 lines) | Phase 7 |
| **[SYS_PRESENTATION_COMPLETE.md](SYS_PRESENTATION_COMPLETE.md)** | Visualization (541 lines) | Phase 6 |

### Database & Schema

| Document | Content | When to Use |
|----------|---------|-------------|
| **[05_TABLE_SCHEMAS.md](05_TABLE_SCHEMAS.md)** | All 56 table definitions | Phase 0, any DB work |
| **[06_FK_WIRING_MAP.md](06_FK_WIRING_MAP.md)** | Foreign key relationships | Phase 0, any DB work |
| **[11_CONTROLLED_VOCABULARIES.md](11_CONTROLLED_VOCABULARIES.md)** | All enum values | When defining enums |

**See [INDEX.md](INDEX.md) for complete documentation catalog.**

---

## 🏗️ System Architecture

```
Papers (PDFs) 
    → EXTRACTION (Phases 1-4)
        → edge_evidence_v1 (database)
            → ALGORITHM (Phase 5)
                → edges_v1 (compiled model: 118 edges)
                    → Patient Inference + Intervention Ranking
                        → PRESENTATION (Phase 6)
                            → Reports, Visualizations, Recommendations
```

### The 7 Implementation Phases

| Phase | What | Duration | Files |
|-------|------|----------|-------|
| **0** | Database + Shared Models | 6-8 prompts | ~15 files |
| **1** | Triage + Extraction | 6-8 prompts | ~12 files |
| **2** | Harmonization | 5-6 prompts | ~8 files |
| **3** | Heterogeneity | 7-9 prompts | ~10 files |
| **4** | Aggregation | 6-8 prompts | ~8 files |
| **5** | Algorithm (CORE) | 12-15 prompts | ~20 files |
| **6** | Presentation | 6-8 prompts | ~10 files |
| **7** | Runtime | 4-6 prompts | ~8 files |

**See [VISUAL_ROADMAP.md](VISUAL_ROADMAP.md) for detailed flow diagrams.**

---

## 📊 Key System Numbers

| Metric | Count | Location |
|--------|-------|----------|
| **Cognitive/Physiological Nodes** | 63 | `nodes_v1` table |
| **Causal Edges** | 118 | `edges_v1` table |
| **Assessment Instruments** | 23 | `instruments_v1` table |
| **Intervention Types** | ~40 | `intervention_kernels_v1` table |
| **CRCI Subdomains** | 11 | Composite scoring |
| **MC Simulation Draws** | 10,000 | Per patient inference |

---

## 🧪 Quick Commands

```bash
# Extract papers
python run_extraction.py data/papers/*.pdf

# Compile model
python compile_model.py

# Run patient inference
python run_inference.py --patient test_cases/patient_01.json

# Generate report
python generate_report.py --patient test_cases/patient_01.json

# Run phase verification
python scripts/verify_phase0.py  # After Phase 0
python scripts/verify_phase5.py  # After Phase 5 (CRITICAL)
python scripts/verify_final.py   # After Phase 7
```

---

## ✅ Quality Guarantees

Every implementation follows **12 strict enforcement rules**:

1. ✅ No hardcoded formula parameters (use `config.py`)
2. ✅ No invented formulas (every computation cites spec)
3. ✅ No stubs/TODO (full implementation or explicit NotImplementedError)
4. ✅ Typed signatures (Pydantic models throughout)
5. ✅ Gates raise exceptions (never silent failures)
6. ✅ All defaults logged with reasons
7. ✅ Explicit DB column selection (no `SELECT *`)
8. ✅ DB writes validated before commit
9. ✅ Seeded randomness for reproducibility
10. ✅ File docstrings with specs, formulas, dependencies
11. ✅ Verification stamps on every file
12. ✅ Hand-computable tests for formula-dense code

**See [CODE_QUALITY_ENFORCEMENT.md](CODE_QUALITY_ENFORCEMENT.md) for details.**

---

## 🎯 Success Criteria (v1 Complete When...)

✅ All 7 phases implemented  
✅ All verifications (V0, V1, V2, V5, V6, V-FINAL) pass  
✅ Can extract 50-200 papers end-to-end  
✅ `edges_v1` table populated with 118 edges  
✅ Patient inference produces CRCI scores  
✅ Intervention rankings with confidence intervals  
✅ All visualizations generate correctly  
✅ Mathematical spot-checks match hand calculations  
✅ No hardcoded constants anywhere  
✅ All formulas have spec ID citations  

**Then:** Ready for scientific publication 🎉

---

## 📂 Repository Structure

```
.
├── IMPLEMENTATION_GUIDE.md          ← START HERE
├── QUICK_REFERENCE.md               ← Cheat sheet
├── VISUAL_ROADMAP.md                ← Diagrams
├── INDEX.md                         ← Documentation catalog
├── PROMPT_SEQUENCE.md               ← 42 implementation prompts
├── FILE_CONTEXT_MANIFEST.md         ← Per-file specs
├── CODE_QUALITY_ENFORCEMENT.md      ← Quality rules
│
├── SYS_EXTRACTION_COMPLETE.md       ← Extraction spec (2,764 lines)
├── SYS_ALGORITHM_COMPLETE.md        ← Algorithm spec (4,418 lines)
├── SYS_RUNTIME_COMPLETE.md          ← Runtime spec (752 lines)
├── SYS_PRESENTATION_COMPLETE.md     ← Presentation spec (541 lines)
│
├── 05_TABLE_SCHEMAS.md              ← Database tables
├── 06_FK_WIRING_MAP.md              ← Foreign keys
├── 11_CONTROLLED_VOCABULARIES.md    ← Enums
│
├── NODE_REGISTRY.csv                ← 63 nodes
├── EDGE_REGISTRY.csv                ← 118 edges
├── PATHWAY_REGISTRY.csv             ← 21 pathways
│
├── crci/                            ← Main codebase
│   ├── extraction/                  ← Phases 1-4
│   ├── algorithm/                   ← Phase 5 (THE CORE)
│   ├── presentation/                ← Phase 6
│   ├── runtime/                     ← Phase 7
│   ├── database/                    ← Schemas & seeds
│   ├── shared/                      ← Config, models, utils
│   └── llm/                         ← LLM client
│
└── scripts/                         ← Utilities
    ├── run_extraction.py
    ├── compile_model.py
    ├── run_inference.py
    ├── generate_report.py
    └── verify_*.py
```

---

## 🔬 Scientific Foundation

**Based on:**
- CRCI Bayesian Causal Model paper (§2.1-§2.22, §4, §6)
- Greenland 2005 (multiple bias modeling)
- VanderWeele & Arah 2011 (bias analysis)
- Lash, Fox, Fink 2009 (quantitative bias analysis)
- DerSimonian & Laird 1986 (random effects meta-analysis)
- GRADE methodology (Guyatt et al. 2008)

**Key Innovation:**
Combines Bayesian causal inference with meta-analytic evidence compilation and 7-layer heterogeneity adjustments to produce patient-specific intervention recommendations.

---

## 🤝 Contributing

**Current Phase:** Initial v1 implementation

**To contribute:**
1. Read [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)
2. Check [PROMPT_SEQUENCE.md](PROMPT_SEQUENCE.md) for current status
3. Follow [CODE_QUALITY_ENFORCEMENT.md](CODE_QUALITY_ENFORCEMENT.md)
4. Submit changes with verification evidence

---

## 📝 Version History

- **v1.0** (In Development) — Science project: Manual extraction, local inference
- **v2.0** (Future) — Production: Automated retrieval, background workers, observability

---

## 📧 Support

**Questions?**
1. Check [QUICK_REFERENCE.md](QUICK_REFERENCE.md) "Finding Information Fast"
2. Search [INDEX.md](INDEX.md) for relevant document
3. Review [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) Section 7: Troubleshooting

**The answer is in the documentation.** These specifications are exhaustive.

---

## 📄 License

[License information to be added]

---

## 🚦 Current Status

**Phase:** Foundation (Phase 0)  
**Next Action:** Read [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md), then execute [PROMPT_SEQUENCE.md](PROMPT_SEQUENCE.md) Prompt 0.1

**Last updated:** February 25, 2026

---

**Ready to build?** → Start with [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)
