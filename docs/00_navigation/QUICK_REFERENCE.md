# CRCI Quick Reference Cheat Sheet

**One-page reference for common tasks and questions**

---

## 🎯 Your Current Task

**First time?** Start here:
1. Read [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) (15 min)
2. Open [PROMPT_SEQUENCE.md](PROMPT_SEQUENCE.md)
3. Execute Prompt 0.1

**Already started?** 
→ Check [PROMPT_SEQUENCE.md](PROMPT_SEQUENCE.md) for your next numbered prompt

---

## 📖 Document Quick Lookup

| I need to... | Open this file | Location |
|--------------|----------------|----------|
| **Know what to do next** | PROMPT_SEQUENCE.md | Root directory |
| **Understand a file** | FILE_CONTEXT_MANIFEST.md | Root directory |
| **Look up a formula** | SYS_EXTRACTION_COMPLETE.md or SYS_ALGORITHM_COMPLETE.md | Root directory |
| **See table columns** | 05_TABLE_SCHEMAS.md | Root directory |
| **Check an enum value** | 11_CONTROLLED_VOCABULARIES.md | Root directory |
| **Review quality rules** | CODE_QUALITY_ENFORCEMENT.md | Root directory |
| **See when table is filled** | TABLE_FILL_ORDER.md | Root directory |
| **View the big picture** | IMPLEMENTATION_BLUEPRINT_v1.1.md | Root directory |

---

## 🔢 The 7 Phases (In Order)

| Phase | What | Files | Duration |
|-------|------|-------|----------|
| **0** | Database + Shared | ~15 | 6-8 prompts |
| **1** | Triage + Extraction | ~12 | 6-8 prompts |
| **2** | Harmonization | ~8 | 5-6 prompts |
| **3** | Heterogeneity | ~10 | 7-9 prompts |
| **4** | Aggregation | ~8 | 6-8 prompts |
| **5** | Algorithm (CORE) | ~20 | 12-15 prompts |
| **6** | Presentation | ~10 | 6-8 prompts |
| **7** | Runtime | ~8 | 4-6 prompts |

**Total:** ~42 prompts across 7 phases

---

## ✅ Before Implementing ANY File

**The 6-Step Cycle:** (detailed in [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) Section 5)

1. ✅ **READ** manifest entry + spec lines + upstream + downstream
2. ✅ **PLAN** inputs, outputs, formulas, gates, config
3. ✅ **IMPLEMENT** following all 12 rules
4. ✅ **VERIFY** formulas, wiring, hardcodes, gates
5. ✅ **TEST** (if formula-dense)
6. ✅ **LOG** verification stamp

**Never skip these steps.**

---

## 🚫 The 12 Enforcement Rules (Never Violate)

| Rule | What | Example |
|------|------|---------|
| **1** | No hardcoded numbers | ✅ `config.SIGMA_DEFAULT` ❌ `0.25` |
| **2** | No invented formulas | ✅ `# Formula P4-1: ...` |
| **3** | No stubs/TODO | ✅ Full implementation or NotImplementedError |
| **4** | Explicit imports | ✅ Real modules only |
| **5** | Typed signatures | ✅ `func(x: HarmonizedClaim) -> CalibratedRecord` |
| **6** | Gates must raise | ✅ `raise GateViolation(...)` ❌ `logger.warning(...)` |
| **7** | Log defaults | ✅ `logger.info(f"defaulting to {val} because...")` |
| **8** | Specify DB columns | ✅ `select(Edge.beta, Edge.se)` ❌ `select(Edge)` |
| **9** | Validate DB writes | ✅ `assert hasattr(row, 'beta')` |
| **10** | Seed randomness | ✅ `def func(..., seed=42)` |
| **11** | File docstring | ✅ Component, Spec, Formulas, Reads, Writes, Gates |
| **12** | Exact column names | ✅ See Rule 8 |

---

## 🔍 Finding Information Fast

### "Where is the formula for X?"

**Extraction formulas (P0-P6):**
```bash
grep -n "Formula P[0-6]" SYS_EXTRACTION_COMPLETE.md
```

**Algorithm formulas (A-F chains):**
```bash
grep -n "Formula [A-F]" SYS_ALGORITHM_COMPLETE.md
```

**Or search by keyword:**
```bash
grep -n "SE_eff\|σ²_struct\|β̂_IVW" SYS_*.md
```

### "What columns are in table X?"

```bash
grep -A 50 "^### Table: x_table_v1" 05_TABLE_SCHEMAS.md
```

### "What does enum X contain?"

```bash
grep -A 20 "^## EnumName" 11_CONTROLLED_VOCABULARIES.md
```

### "Which file implements X?"

```bash
grep -n "FILE:.*X" FILE_CONTEXT_MANIFEST.md
```

---

## 🧪 Common Commands

### Run Phase Verification

```bash
# After Phase 0
python scripts/verify_phase0.py

# After Phase 5 (CRITICAL)
python scripts/verify_phase5.py

# After Phase 7 (FINAL)
python scripts/verify_final.py
```

### Extract Papers

```bash
python run_extraction.py data/papers/*.pdf
```

### Compile Model

```bash
python compile_model.py
```

### Run Patient Inference

```bash
python run_inference.py --patient test_cases/patient_01.json
```

### Generate Report

```bash
python generate_report.py --patient test_cases/patient_01.json --output report.html
```

---

## 🐛 Quick Fixes for Common Errors

| Error | Likely Cause | Fix |
|-------|--------------|-----|
| **ImportError: shared.models** | Phase 0 incomplete | Complete Phase 0, set PYTHONPATH |
| **Gate P3-G1: SE_eff < SE_raw** | Layer multiplier < 1.0 | Check layer formulas, all M_i ≥ 1.0 |
| **Table X is empty** | Phase Y not run | Check TABLE_FILL_ORDER.md |
| **Formula result wrong** | Hardcoded constant | Run `grep "\b[0-9]*\.[0-9]\+" file.py` |
| **Bayesian update NaN** | Covariance matrix issue | Add `R + 1e-6 * I` for stability |
| **MC sampler slow** | n_draws too high | Start with 1000, increase after verify |
| **CRCI score always 50** | Weights not loaded | Check `instruments_v1.severity_weight` |
| **Review task missing** | Threshold check wrong | Verify confidence < AMBIGUOUS_THRESHOLD |

---

## 🎯 Phase Completion Checklist

### After Each Phase:

- [ ] All prompts in phase executed
- [ ] All files created
- [ ] Verification prompt run
- [ ] All checks passed
- [ ] Git committed
- [ ] Ready for next phase

### The Critical Ones:

- [ ] **After Phase 0:** V0 passes → everything depends on this
- [ ] **After Phase 5:** V5 passes → mathematical correctness verified
- [ ] **After Phase 7:** V-FINAL passes → system is v1 complete ✅

---

## 📊 Key System Numbers

| What | Count | Where |
|------|-------|-------|
| **Nodes** | 63 | `nodes_v1` table |
| **Edges** | 118 | `edges_v1` table |
| **Instruments** | 23 | `instruments_v1` table |
| **Pathways** | 21 | `pathway_map_v1` table |
| **Interventions** | ~40 | `intervention_kernels_v1` table |
| **Subdomains** | 11 | CRCI composite |
| **MC Draws** | 10,000 | Per intervention simulation |

---

## 🔬 Key Formulas (Quick Reference)

### P3: SE_eff Calculation
```
SE_eff = SE_raw × M_total
M_total = Π(M_i) for i=1..7
```

### P4: IVW Meta-Analysis
```
β̂_IVW = Σ(β_i/SE²_i) / Σ(1/SE²_i)
SE_pooled = sqrt(1 / Σ(1/SE²_i))
```

### P4: DerSimonian-Laird τ²
```
Q = Σ[w_i(β_i - β̂)²]
τ² = max(0, (Q - (k-1)) / c)
c = Σw_i - Σ(w²_i)/Σw_i
```

### C1: Bayesian Update (Kalman-like)
```
θ̂_post = θ̂_prior + K(y - Hθ̂_prior)
K = P_prior × H^T × (HPH^T + R)^(-1)
P_post = (I - KH)P_prior
```

### F1: CRCI Composite Score
```
CRCI = Σ(w_j × θ̂_j) where Σw_j = 1
```

---

## 🏆 Success Criteria

**v1 is complete when:**

✅ All 7 phases done  
✅ All verifications (V0, V1, V2, V5, V6, V-FINAL) pass  
✅ Extract → compile → infer → visualize pipeline works  
✅ 118 edges populated in `edges_v1`  
✅ Patient inference produces CRCI score  
✅ Intervention rankings generated  
✅ No hardcoded constants  
✅ All formulas have ID comments  
✅ All gates raise on violations  

**Then: Ready for science project! 🎉**

---

## 🆘 Still Stuck?

1. **Re-read the section** in [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)
2. **Check the manifest** in FILE_CONTEXT_MANIFEST.md for that file
3. **Read the spec lines** referenced in the manifest
4. **Look at upstream code** that produces your inputs
5. **Consult PROMPT_SEQUENCE.md** for context attachments

**The answer is in the documentation.** These specs are exhaustive.

---

**Last Updated:** 2026-02-25  
**For:** CRCI System v1 Implementation
