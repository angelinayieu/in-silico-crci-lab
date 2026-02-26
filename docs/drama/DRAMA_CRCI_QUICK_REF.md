# Quick Reference: Drama vs CRCI

**TL;DR** — One-page comparison for fast lookup

---

## System Goals

| Aspect | Drama | CRCI |
|:-------|:------|:-----|
| **Primary Goal** | Answer open-domain factual questions (claim verification, QA) with structured data | Compile Bayesian causal model of CRCI + predict patient-specific risk & interventions |
| **Domain** | General-purpose analytics | Biomedical evidence synthesis |
| **Input** | Natural language queries on arbitrary web data | Structured registries + peer-reviewed papers |
| **Output** | Boolean (claim) or Value (QA); Structured table; Executable code; Sources | Compiled model (β̂, SE, P_inclusion per edge); Patient state; CRCI score; Trajectories |
| **Time Horizon** | Real-time (minutes per query) | Batch (hours to days per SR) |

---

## Three-Stage Pipeline Comparison

### Stage 1: Collection

| Feature | Drama | CRCI |
|:--------|:------|:-----|
| **Strategy** | Multi-agent: web browser (fine-grained) + web augmenter (broad) | Multi-adapter: PubMed (precise) + OpenAlex (citation graph) + manual upload |
| **Data Sources** | HTML tables, PDFs, Excel, CSV from open web | Peer-reviewed papers from APIs (PubMed, Crossref, OpenAlex, Europe PMC) + user uploads |
| **Query Type** | Natural language → search terms | Deterministic templates from registries (nodes, edges, instruments, pathways) |
| **Result Ranking** | Implicit (web browser explores sequentially; web augmenter in parallel) | Explicit: APS (Acquisition Priority Score) based on research interest + quality |
| **Paywall Handling** | Browser navigation (simulates human browsing) | Explicit detection: Unpaywall API + PMC lookup → ABSTRACT_ONLY vs RETRIEVED |
| **Scope Discovery** | Web augmenter parallel search + user refinement | Hop discoverer: identifies cited & citing papers from systematic reviews |
| **Cost per Item** | Negligible (LLM-based browsing) | Variable: free (PMC OA) to $$ (paywalled) + API rate limits |
| **Accuracy** | Collection stage not separately measured; end-to-end 86.5% | Hop discovery tested on Cifu 2018 SR (planned test) |

### Stage 2: Transformation

| Feature | Drama | CRCI |
|:--------|:------|:-----|
| **Extraction Method** | MLLM (GPT-4o) page-by-page incremental | 11 domain-specialist NLP agents (genome, clinical, cohort, etc.) |
| **Extraction Scope** | All visible content on each page until adequate_info satisfied | Full-text + structured (tables, figures) → harmonize → aggregate |
| **Normalization** | Column renaming, schema alignment (ad-hoc per query) | Standardization (SD parsing, scope matching, conflation checks) |
| **Quality Assessment** | Schema similarity metrics (embedding-based + LLM-as-judge) | Trust boundary: confidence + provenance code + evidence trail per field |
| **Heterogeneity Handling** | No explicit classification (assumed homogeneous after merge) | Explicit: p3_heterogeneity/ stage classifies study types (animal/human, observational/RCT, etc.) |
| **Data Adequacy** | `check_adequate_info()`: can executable code be generated? | Custom per edge: N ≥ 3 studies? SE < 0.5? Meta-analysis feasible? |
| **Duplication Detection** | Implicit (LLM deduplicates during extraction) | Explicit: conflation_check.py flags redundant reports of same study |
| **Error Handling** | Log warning, skip, continue | Flag in trust boundary; propagate uncertainty through Bayesian chains |

### Stage 3: Analysis

| Feature | Drama | CRCI |
|:--------|:------|:-----|
| **Reasoning Type** | Retrieve → Filter → Aggregate (SQL-like) | Compile DAG → Meta-analyze → Infer patient state → Simulate interventions → Forecast |
| **Code Generation** | NL2SQL: LLM generates SQL + Python | Deterministic algorithms (6 chains A–F with 40+ formulas) |
| **Causal Reasoning** | None (descriptive analytics only) | Full causal model: confounding, mediation, collider handling |
| **Uncertainty Quantification** | Implicit in code correctness | Explicit: SE estimates, Bayesian posteriors, 95% credible intervals from MC samples |
| **Patient Customization** | None (stateless) | Yes: per-patient posterior state from observations + adaptive measurement scheduling |
| **Answer Format** | Boolean or literal value | Parameter estimates (β̂, SE, P_inclusion) + patient risk score + treatment rankings |
| **Validation Gates** | Code execution success + result plausibility | 6 enforcement gates (P2-G1, P2-G2, P4-G1, P4-G2, P6-G1, P6-G2) that raise on violation |
| **Explainability** | Via code (user can inspect generated SQL) | Via chain traces + provenance viewer + intervention effect breakdown |

---

## Key Metrics

| Metric | Drama | CRCI |
|:-------|:------|:-----|
| **Accuracy** | 86.5% (end-to-end task accuracy on DramaBench 200 instances) | 720 unit tests passing; not yet integrated end-to-end |
| **Data-Grounded Accuracy** | 82.5% (answers that are both correct AND traceable to retrieved data) | N/A (still in integration phase) |
| **Cost per Task** | $0.05 USD (LLM API calls only) | Variable ($0/paper if PMC OA; $$ if paywalled) |
| **System Latency** | ~1.5 min per task (real-time) | Hours to days per SR (batch) |
| **Code Quality** | 86.5% end-to-end accuracy speaks for itself | Phase completion: 7/7 phases complete; 720 tests pass; all formulas spec-verified |
| **Reproducibility** | Explicit sources + executed code | Provenance viewer + extraction trails + gate audit logs |

---

## Architectural Patterns

| Pattern | Drama's Solution | CRCI Could Adopt |
|:--------|:-----------------|:-----------------|
| **Multi-agent coordination** | Browser (precise) + Augmenter (broad) alternate → workload distribution | Dual adapters: PubMed (precision) + OpenAlex (recall) → complement each other |
| **Incremental adequacy** | `check_adequate_info()` → generate code → if fails, iterate | Per-edge sufficiency checks → guide NLP agent effort → stop early if adequate |
| **Source ranking** | `rank_website()` → score by contribution to answer | Acquisition Priority Score (APS) → already exists; formalize per Drama's ranking logic |
| **Fallback strategy** | Try precise method → if insufficient → try broad method | Tier 1 (abstract) → Tier 2 (fulltext) → Tier 3 (manual deep review) |
| **Gate validation** | Check: syntax → execution → type → plausibility | Already exists (P2-G1, etc.); formalize error messages per Drama's style |

---

## What Drama Gets Right

✓ **Simple, unified framework:** 3 stages apply to ANY analytical task  
✓ **Cost-effective:** $0.05/task via efficient LLM prompting  
✓ **Explainable:** User can inspect generated code & see source URLs  
✓ **Scalable:** Runs in-the-loop without state persistence  
✓ **Multi-agent:** Intelligent task distribution (precise vs. broad)  

**Lesson for CRCI:** Formalize retrieval orchestration (Drama's coordinator pattern) + adopt incremental adequacy checking.

---

## What CRCI Gets Right

✓ **Domain-specialized:** 11 agents trained on biomedical evidence extraction  
✓ **Causal reasoning:** Explicit DAG + heterogeneity + confounding modeling  
✓ **Quality gates:** Hard stops on model validity (spectral radius, condition number, P-inclusion)  
✓ **Trust-aware:** Every extracted value tagged with confidence + provenance  
✓ **Patient-personalized:** Per-patient state inference + treatment recommendations  
✓ **Temporal:** Predicts 3-month nadir + 12-month recovery trajectory  

**Lesson for Drama:** Add evidence quality modeling (sources ranked by credibility, not just relevance) + explicit uncertainty quantification per data cell.

---

## Future Integration Vision

### Unified "Evidence Pipeline v2"

```
Registry-Guided Retrieval (Drama's multi-agent + CRCI's APS scoring)
         ↓
Biomedical NLP Extraction (CRCI's 11 agents + Drama's incremental adequacy)
         ↓
Trust-Aware Transformation (CRCI's trust boundary + Drama's schema alignment)
         ↓
Bayesian Causal Compilation (CRCI's chains A–F)
         ↓
Patient-Specific Inference + Presentation (CRCI's runtime + presentation)
```

**Cost/Speed Tradeoff:**
- Drama: $0.05/task, 1.5 min → good for fact-checking
- CRCI: $$variable/paper, hours/days → necessary for causal model compilation
- **Hybrid:** Use Drama's retrieval for rapid literature scanning; CRCI's extraction for full evidence synthesis on priority papers

---

## Quick Decision Tree

**Should I adopt Drama's pattern?**

| Question | Yes → Do This | No → Keep CRCI |
|:---------|:-------------|:---------------|
| Do I need real-time Q&A on arbitrary data? | Use Drama (or Drama's retrieval module) | (CRCI is batch) |
| Do I need to model causal relationships? | Keep CRCI chains A–F | Drama can't do this |
| Do I need to rank evidence credibility? | Adopt Drama's `rank_website` pattern | CRCI's APS is sufficient |
| Do I need to explain every data point's origin? | Adopt CRCI's trust boundary | (Drama only shows code) |
| Do I need patient personalization? | Keep CRCI inference layer | (Drama is stateless) |

---

## Files Created

1. **[DRAMA_vs_CRCI_ANALYSIS.md](DRAMA_vs_CRCI_ANALYSIS.md)** — Long-form comparison (sections, mapping, lessons)
2. **[DRAMA_PATTERNS_for_CRCI.md](DRAMA_PATTERNS_for_CRCI.md)** — Concrete code patterns to retrofit
3. **[DRAMA_CRCI_QUICK_REF.md](DRAMA_CRCI_QUICK_REF.md)** — This file; quick lookup table

---

## Next Steps for CRCI Integration

### Phase 1: Lightweight Retrofits (1–2 weeks)
- [ ] Formalize `APS` scoring logic per Drama's `rank_website` pattern
- [ ] Add `check_adequate_info()` calls in extraction/p1/ to exit early when target_edges are satisfied
- [ ] Improve gate error messages (use Drama's format: gate ID + cause + action)

### Phase 2: Multi-Agent Coordination (2–4 weeks)
- [ ] Implement PubMed + OpenAlex dual-adapter orchestration (Drama's browser + augmenter pattern)
- [ ] Add Tier 1/2/3 adaptive extraction (fast → standard → deep)
- [ ] Test on 5 systematic reviews (Cifu 2018 + others)

### Phase 3: Metrics & Monitoring (2–3 weeks)
- [ ] Add dashboard showing: papers by tier, gates violated, source contribution
- [ ] Track end-to-end time: retrieval → extraction → compilation per SR
- [ ] Measure accuracy: compiled edge estimates vs. human-reviewed ground truth

