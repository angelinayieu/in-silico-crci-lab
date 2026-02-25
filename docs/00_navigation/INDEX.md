# CRCI System Documentation Index

**Your complete guide to all implementation documentation**

Last Updated: February 25, 2026

---

## 🎯 Quick Navigation

| I want to... | Go to |
|--------------|-------|
| **Get started (first time)** | [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) Section 1 |
| **See what I'm building** | [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) Section 2 |
| **Find a specific document** | [Section below](#documentation-catalog) |
| **Look up a formula** | [QUICK_REFERENCE.md](QUICK_REFERENCE.md) "Finding Information Fast" |
| **See the big picture** | [VISUAL_ROADMAP.md](VISUAL_ROADMAP.md) |
| **Know what to do next** | [PROMPT_SEQUENCE.md](PROMPT_SEQUENCE.md) |
| **Understand a specific file** | [FILE_CONTEXT_MANIFEST.md](FILE_CONTEXT_MANIFEST.md) |
| **Review quality rules** | [CODE_QUALITY_ENFORCEMENT.md](CODE_QUALITY_ENFORCEMENT.md) |
| **Check my progress** | [VISUAL_ROADMAP.md](VISUAL_ROADMAP.md) Section "Progress Tracking" |

---

## 📖 Documentation Catalog

### Level 1: Getting Started (Read First)

| Document | Lines | Purpose | Read Time |
|----------|-------|---------|-----------|
| **[IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)** | ~900 | Complete implementation roadmap | 15-20 min |
| **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** | ~400 | One-page cheat sheet | 3-5 min |
| **[VISUAL_ROADMAP.md](VISUAL_ROADMAP.md)** | ~600 | Flowcharts and diagrams | 5-10 min |

**Action:** Read all three, then proceed to Level 2.

---

### Level 2: Planning & Execution

| Document | Lines | Purpose | When to Use |
|----------|-------|---------|-------------|
| **[PROMPT_SEQUENCE.md](PROMPT_SEQUENCE.md)** | 1,412 | 42 prompts in order | Execute sequentially |
| **[IMPLEMENTATION_BLUEPRINT_v1.1.md](IMPLEMENTATION_BLUEPRINT_v1.1.md)** | 768 | Architecture, v1 scope | Reference frequently |
| **[FILE_CONTEXT_MANIFEST.md](FILE_CONTEXT_MANIFEST.md)** | 885 | Per-file specifications | Before each file |
| **[CODE_QUALITY_ENFORCEMENT.md](CODE_QUALITY_ENFORCEMENT.md)** | 445 | 12 rules + verifications | Append to every prompt |

**Action:** Follow PROMPT_SEQUENCE.md. Consult others as needed.

---

### Level 3: Technical Specifications

**System Specs** (detailed implementation requirements)

| Document | Lines | Content | When to Use |
|----------|-------|---------|-------------|
| **[SYS_EXTRACTION_COMPLETE.md](SYS_EXTRACTION_COMPLETE.md)** | 2,764 | Extraction chains P0-P6 | Phases 1-4 |
| **[SYS_ALGORITHM_COMPLETE.md](SYS_ALGORITHM_COMPLETE.md)** | 4,418 | Algorithm chains A-F | Phase 5 |
| **[SYS_RUNTIME_COMPLETE.md](SYS_RUNTIME_COMPLETE.md)** | 752 | Runtime orchestration | Phase 7 |
| **[SYS_PRESENTATION_COMPLETE.md](SYS_PRESENTATION_COMPLETE.md)** | 541 | UI & visualization | Phase 6 |

**Database Specs**

| Document | Lines | Content | When to Use |
|----------|-------|---------|-------------|
| **[05_TABLE_SCHEMAS.md](05_TABLE_SCHEMAS.md)** | 2,334 | All 56 table definitions | Phase 0, any DB work |
| **[06_FK_WIRING_MAP.md](06_FK_WIRING_MAP.md)** | 618 | Foreign key relationships | Phase 0, any DB work |
| **[11_CONTROLLED_VOCABULARIES.md](11_CONTROLLED_VOCABULARIES.md)** | 344 | All enum values | When defining enums |

**Action:** Read only the sections referenced by FILE_CONTEXT_MANIFEST.md for each file.

---

### Level 4: Supporting Documentation

**Data Management**

| Document | Lines | Content | When to Use |
|----------|-------|---------|-------------|
| **[TABLE_FILL_ORDER.md](TABLE_FILL_ORDER.md)** | 378 | When tables get populated | Before reading/writing tables |
| **[INTERFACE_SCHEMA_LOCK.md](INTERFACE_SCHEMA_LOCK.md)** | 377 | Intermediate state schemas | When passing data between modules |
| **[PARAMETER_PROVENANCE_AND_CURATION.md](PARAMETER_PROVENANCE_AND_CURATION.md)** | 488 | GREEN/YELLOW/RED parameters | Phase 0, manual curation |

**Advanced Extraction** (v2 features, defer until v1 complete)

| Document | Lines | Content | When to Use |
|----------|-------|---------|-------------|
| **[SYS_EXTRACTION_ADDENDUM.md](SYS_EXTRACTION_ADDENDUM.md)** | 635 | Extended agents, compilers | Advanced extraction scenarios |
| **[AUTOMATED_RETRIEVAL_PLAN.md](AUTOMATED_RETRIEVAL_PLAN.md)** | 1,057 | Paper retrieval system | v2 only |
| **[CONVERSION_VALIDITY_AND_HARDENING.md](CONVERSION_VALIDITY_AND_HARDENING.md)** | 786 | Conversion verification | When implementing P2 conversions |

**Legacy/Reference**

| Document | Lines | Content | When to Use |
|----------|-------|---------|-------------|
| **[CRCI_Master_Spec_v2.0.md](CRCI_Master_Spec_v2.0.md)** | 988 | Original master spec | Historical reference |
| **[CRCI_Implementation_Playbook_v2.0.md](CRCI_Implementation_Playbook_v2.0.md)** | 201 | Original playbook | Historical reference |
| **[CRCI_Engineering_Appendix_v2.0.md](CRCI_Engineering_Appendix_v2.0.md)** | 333 | Engineering notes | Historical reference |
| **[CRCI_Checklists_Templates_v2.0.md](CRCI_Checklists_Templates_v2.0.md)** | 116 | Original checklists | Historical reference |

---

## 🚀 Recommended Reading Path

### For First-Time Implementation

**Week 1: Orientation**
1. [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) — Full read (20 min)
2. [VISUAL_ROADMAP.md](VISUAL_ROADMAP.md) — Full read (10 min)
3. [QUICK_REFERENCE.md](QUICK_REFERENCE.md) — Skim, bookmark (5 min)
4. [PROMPT_SEQUENCE.md](PROMPT_SEQUENCE.md) — Read Phases 0-1 (20 min)
5. [CODE_QUALITY_ENFORCEMENT.md](CODE_QUALITY_ENFORCEMENT.md) — Memorize 12 rules (15 min)

**Week 2-3: Phase 0 (Foundation)**
1. Execute [PROMPT_SEQUENCE.md](PROMPT_SEQUENCE.md) Prompts 0.1-0.8
2. Consult [05_TABLE_SCHEMAS.md](05_TABLE_SCHEMAS.md) for each table
3. Consult [FILE_CONTEXT_MANIFEST.md](FILE_CONTEXT_MANIFEST.md) for each file
4. Run V0 verification from [CODE_QUALITY_ENFORCEMENT.md](CODE_QUALITY_ENFORCEMENT.md)

**Week 4-6: Phases 1-4 (Extraction)**
1. Execute [PROMPT_SEQUENCE.md](PROMPT_SEQUENCE.md) Prompts 1.1-4.last
2. Reference [SYS_EXTRACTION_COMPLETE.md](SYS_EXTRACTION_COMPLETE.md) for formulas
3. Run V1, V2 verifications

**Week 7-9: Phase 5 (Algorithm — THE CORE)**
1. Execute [PROMPT_SEQUENCE.md](PROMPT_SEQUENCE.md) Prompts 5.1-5.15
2. Reference [SYS_ALGORITHM_COMPLETE.md](SYS_ALGORITHM_COMPLETE.md) extensively
3. Run V5 verification (CRITICAL)

**Week 10: Phases 6-7 (Presentation + Runtime)**
1. Execute [PROMPT_SEQUENCE.md](PROMPT_SEQUENCE.md) Prompts 6.1-7.last
2. Reference [SYS_PRESENTATION_COMPLETE.md](SYS_PRESENTATION_COMPLETE.md)
3. Reference [SYS_RUNTIME_COMPLETE.md](SYS_RUNTIME_COMPLETE.md)
4. Run V6, V-FINAL verifications

**Week 11: Testing & Validation**
1. Extract 50-200 real papers
2. Compile model (118 edges)
3. Run patient inference tests
4. Generate visualizations
5. Verify mathematical correctness

---

## 🔍 Finding Specific Information

### "I need to know about [topic]..."

| Topic | Where to Look |
|-------|---------------|
| **What v1 includes/excludes** | [IMPLEMENTATION_BLUEPRINT_v1.1.md](IMPLEMENTATION_BLUEPRINT_v1.1.md) Part 1 |
| **Data flow diagram** | [VISUAL_ROADMAP.md](VISUAL_ROADMAP.md) "Data Flow Diagram" |
| **Phase structure** | [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) Section 4 |
| **Formula location** | [QUICK_REFERENCE.md](QUICK_REFERENCE.md) "Finding Information Fast" |
| **Table columns** | [05_TABLE_SCHEMAS.md](05_TABLE_SCHEMAS.md) |
| **Enum values** | [11_CONTROLLED_VOCABULARIES.md](11_CONTROLLED_VOCABULARIES.md) |
| **File dependencies** | [FILE_CONTEXT_MANIFEST.md](FILE_CONTEXT_MANIFEST.md) |
| **When table is filled** | [TABLE_FILL_ORDER.md](TABLE_FILL_ORDER.md) |
| **Intermediate state fields** | [INTERFACE_SCHEMA_LOCK.md](INTERFACE_SCHEMA_LOCK.md) |
| **Quality rules** | [CODE_QUALITY_ENFORCEMENT.md](CODE_QUALITY_ENFORCEMENT.md) Section 1 |
| **Verification steps** | [CODE_QUALITY_ENFORCEMENT.md](CODE_QUALITY_ENFORCEMENT.md) Section 2 |
| **Common errors** | [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) Section 7 |
| **Extraction formulas** | [SYS_EXTRACTION_COMPLETE.md](SYS_EXTRACTION_COMPLETE.md) |
| **Algorithm formulas** | [SYS_ALGORITHM_COMPLETE.md](SYS_ALGORITHM_COMPLETE.md) |
| **System architecture** | [IMPLEMENTATION_BLUEPRINT_v1.1.md](IMPLEMENTATION_BLUEPRINT_v1.1.md) Part 2 |
| **Key outputs** | [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) Section 2 |

### "I have a specific question..."

| Question | Answer Location |
|----------|-----------------|
| **"What prompt am I on?"** | [PROMPT_SEQUENCE.md](PROMPT_SEQUENCE.md) |
| **"How do I implement file X?"** | [FILE_CONTEXT_MANIFEST.md](FILE_CONTEXT_MANIFEST.md) → Find file → Read manifest entry |
| **"What does formula P4-1 mean?"** | [SYS_EXTRACTION_COMPLETE.md](SYS_EXTRACTION_COMPLETE.md) → Search "P4-1" |
| **"What columns in edges_v1?"** | [05_TABLE_SCHEMAS.md](05_TABLE_SCHEMAS.md) → Search "edges_v1" |
| **"What's StudyDesign enum?"** | [11_CONTROLLED_VOCABULARIES.md](11_CONTROLLED_VOCABULARIES.md) → Search "StudyDesign" |
| **"When is table X filled?"** | [TABLE_FILL_ORDER.md](TABLE_FILL_ORDER.md) → Search table name |
| **"What's in HarmonizedClaim?"** | [INTERFACE_SCHEMA_LOCK.md](INTERFACE_SCHEMA_LOCK.md) → Search "HarmonizedClaim" |
| **"What are the 12 rules?"** | [CODE_QUALITY_ENFORCEMENT.md](CODE_QUALITY_ENFORCEMENT.md) Section 1 |
| **"How to fix error X?"** | [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) Section 7 "Troubleshooting" |
| **"Is v1 complete?"** | [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) Section "Success Criteria" |

---

## 📊 Document Dependencies

```
IMPLEMENTATION_GUIDE.md (START HERE)
    │
    ├─→ VISUAL_ROADMAP.md (visual learners)
    │
    ├─→ QUICK_REFERENCE.md (fast lookup)
    │
    └─→ PROMPT_SEQUENCE.md (execute this)
            │
            ├─→ FILE_CONTEXT_MANIFEST.md (per file)
            │       │
            │       └─→ SYS_EXTRACTION_COMPLETE.md (Phases 1-4)
            │       └─→ SYS_ALGORITHM_COMPLETE.md (Phase 5)
            │       └─→ SYS_PRESENTATION_COMPLETE.md (Phase 6)
            │       └─→ SYS_RUNTIME_COMPLETE.md (Phase 7)
            │
            ├─→ CODE_QUALITY_ENFORCEMENT.md (every prompt)
            │
            ├─→ 05_TABLE_SCHEMAS.md (Phase 0, DB work)
            │
            ├─→ 06_FK_WIRING_MAP.md (Phase 0, DB work)
            │
            ├─→ 11_CONTROLLED_VOCABULARIES.md (enums)
            │
            ├─→ TABLE_FILL_ORDER.md (when needed)
            │
            └─→ INTERFACE_SCHEMA_LOCK.md (when needed)
```

---

## ✅ Quality Control Documents

| Checkpoint | Document | Section | Required |
|------------|----------|---------|----------|
| **Before each file** | [FILE_CONTEXT_MANIFEST.md](FILE_CONTEXT_MANIFEST.md) | Find file entry | Yes |
| **During implementation** | [CODE_QUALITY_ENFORCEMENT.md](CODE_QUALITY_ENFORCEMENT.md) | Section 1 (12 rules) | Yes |
| **After each file** | [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) | Section 5.4 (Verify) | Yes |
| **After Phase 0** | [CODE_QUALITY_ENFORCEMENT.md](CODE_QUALITY_ENFORCEMENT.md) | V0 prompt | Yes |
| **After Phase 1** | [CODE_QUALITY_ENFORCEMENT.md](CODE_QUALITY_ENFORCEMENT.md) | V1 prompt | Yes |
| **After Phases 2-4** | [CODE_QUALITY_ENFORCEMENT.md](CODE_QUALITY_ENFORCEMENT.md) | V2 prompt | Yes |
| **After Phase 5** | [CODE_QUALITY_ENFORCEMENT.md](CODE_QUALITY_ENFORCEMENT.md) | V5 prompt | Yes (CRITICAL) |
| **After Phase 6** | [CODE_QUALITY_ENFORCEMENT.md](CODE_QUALITY_ENFORCEMENT.md) | V6 prompt | Yes |
| **After Phase 7** | [CODE_QUALITY_ENFORCEMENT.md](CODE_QUALITY_ENFORCEMENT.md) | V-FINAL prompt | Yes |

---

## 🎯 Success Milestones

| Milestone | How to Verify | Document Reference |
|-----------|---------------|-------------------|
| **Phase 0 Complete** | V0 passes | [CODE_QUALITY_ENFORCEMENT.md](CODE_QUALITY_ENFORCEMENT.md) |
| **Can extract papers** | 5 papers → edge_evidence_v1 | [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) Phase 1-4 |
| **Can compile model** | edges_v1 has 118 rows | [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) Phase 5 |
| **Can infer patient** | Posterior θ̂ for 63 nodes | [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) Phase 5 |
| **Can rank interventions** | Top 5 with SAFE_A/B | [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) Phase 5 |
| **Can visualize** | DAG + cards + plots | [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) Phase 6 |
| **v1 Complete** | V-FINAL passes | [CODE_QUALITY_ENFORCEMENT.md](CODE_QUALITY_ENFORCEMENT.md) |

---

## 📚 Additional Resources

**Quick Reference Files** (in workspace root):
- `NODE_REGISTRY.csv` — 63 nodes
- `EDGE_REGISTRY.csv` — 118 edges
- `PATHWAY_REGISTRY.csv` — 21 pathways
- `MEASURE_REGISTRY.csv` — Measurement instruments
- `INSTRUMENT_REGISTRY.csv` — Assessment tools

**Scripts** (in `scripts/`):
- `run_extraction.py` — Extract papers
- `compile_model.py` — Build edges_v1
- `run_inference.py` — Patient inference
- `generate_report.py` — Create visualizations
- `verify_phase*.py` — Run verifications

---

## 🆘 Still Lost?

**Start here in this exact order:**

1. Open [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)
2. Read Section 1 (Quick Start)
3. Read Section 2 (What You're Building)
4. Skim Section 4 (The 7-Phase Build Sequence)
5. Open [PROMPT_SEQUENCE.md](PROMPT_SEQUENCE.md)
6. Execute Prompt 0.1

**You will know what to do next after reading IMPLEMENTATION_GUIDE.md.**

---

## 📝 Document Version History

| Date | Change |
|------|--------|
| 2026-02-25 | Created INDEX.md linking new structured guides |
| 2026-02-25 | Created IMPLEMENTATION_GUIDE.md (comprehensive) |
| 2026-02-25 | Created QUICK_REFERENCE.md (cheat sheet) |
| 2026-02-25 | Created VISUAL_ROADMAP.md (diagrams) |

---

**Your Next Action:** Read [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) from the top.
