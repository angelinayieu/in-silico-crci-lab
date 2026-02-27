# SE Derivation Rules

> Every effect size needs a standard error. Use these formulas when SE is not directly reported.

---

## Method 1 — From Confidence Interval

```
SE = (CI_upper − CI_lower) / (2 × 1.96)
```

**Use when:** Paper reports 95% CI around an effect size.  
**Spec:** SYS_EXTRACTION §EX-P1.1  
**Example:** CI = [−24.6, −3.9] → SE = (−3.9 − (−24.6)) / 3.92 = 5.28

---

## Method 2 — From p-value (Two-Tailed)

```
z = −Φ⁻¹(p/2)          # inverse normal CDF
SE = |effect| / z
```

**Use when:** Paper reports exact p-value and effect size.  
**Example:** d = 0.79, p = 0.03 → z = 2.17 → SE = 0.79/2.17 = 0.36

---

## Method 3 — From t-statistic

```
SE = effect / t
```

**Use when:** Paper reports t-statistic.  
**Example:** β = 2.5, t = 3.2 → SE = 2.5/3.2 = 0.78

---

## Method 4 — From F-statistic (df₁ = 1)

```
t = √F
SE = effect / t
```

**Use when:** Paper reports F(1, df₂) for group comparison.

---

## Method 5 — From SD + N (Cohen's d SE Approximation)

```
SE(d) = √( (n₁ + n₂)/(n₁ × n₂) + d²/(2(n₁ + n₂)) )
```

**Use when:** You computed Cohen's d and know group sizes.  
**Spec:** Standard approximation (Hedges & Olkin, 1985)

**Quick reference for common group sizes:**

| n₁ | n₂ | d=0.5 SE | d=0.8 SE | d=1.0 SE |
|----|----|----------|----------|----------|
| 6  | 6  | 0.60     | 0.61     | 0.61     |
| 10 | 10 | 0.46     | 0.47     | 0.47     |
| 15 | 15 | 0.38     | 0.38     | 0.39     |
| 20 | 20 | 0.33     | 0.33     | 0.33     |
| 50 | 50 | 0.21     | 0.21     | 0.21     |

---

## Method 6 — Fallback (Large-Sample Approximation)

```
SE(d) ≈ √(4/N)       where N = total sample size
```

**Use when:** Only total N is known.  
**Example:** N = 28 → SE ≈ √(4/28) ≈ 0.38

---

## Computing Cohen's d When Not Reported

### From Group Means ± SD

```
SD_pooled = √[(SD_tx² + SD_ctrl²) / 2]
d = (Mean_tx − Mean_ctrl) / SD_pooled
```

### From Pre-Post Change Scores

```
d = (Δmean_tx − Δmean_ctrl) / SD_pooled_baseline
```

Where Δmean = post − pre within each group.

### From Group Means ± SE (per group)

```
SD = SE × √n                      (per group, convert first)
SD_pooled = √[(SD_tx² + SD_ctrl²) / 2]
d = (Mean_tx − Mean_ctrl) / SD_pooled
```

---

## Converting Other Effect Types to Cohen's d

### From Odds Ratio (OR)

```
d = ln(OR) × √3 / π
SE(d) = SE(ln(OR)) × √3 / π
```

### From Correlation (r)

```
d = 2r / √(1 − r²)
SE(d) = 2 × SE(r) / (1 − r²)^(3/2)
```

### From Eta-Squared (η²)

```
d = 2√(η² / (1 − η²))
```

### From Mean Difference (raw)

```
d = mean_diff / SD_pooled
SE(d) = SE(mean_diff) / SD_pooled
```

---

## SE Derivation Method Codes

Record which method was used in `se_derivation_method` column:

| Code | Method |
|------|--------|
| `from_ci` | Method 1 — From CI |
| `from_p_value` | Method 2 — From p-value |
| `from_t_stat` | Method 3 — From t-statistic |
| `from_f_stat` | Method 4 — From F-statistic |
| `from_sd_n` | Method 5 — From SD + N |
| `fallback_4_over_n` | Method 6 — Fallback √(4/N) |
| `reported` | SE directly reported by paper |
| `computed_from_lmm` | Derived from linear mixed model output |

---

## Decision Tree

```
Paper reports SE directly?
  → YES: Use it. se_derivation_method = "reported"
  → NO:
    Paper reports 95% CI?
      → YES: Method 1 (from_ci)
      → NO:
        Paper reports exact p-value?
          → YES: Method 2 (from_p_value)
          → NO:
            Paper reports t or F statistic?
              → YES: Method 3 or 4 (from_t_stat / from_f_stat)
              → NO:
                You computed d from group SDs?
                  → YES: Method 5 (from_sd_n)
                  → NO: Method 6 (fallback_4_over_n)
```

---

## Always Document

In `confidence_note`, record:
1. Which formula was used
2. What raw values went into it
3. Any approximations or assumptions

Example: `"SE derived from 95% CI [-24.6, -3.9] via (upper-lower)/(2×1.96)"`
