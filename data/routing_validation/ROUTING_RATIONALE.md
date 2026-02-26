# Model Routing Validation Report

**Generated:** 2026-02-25 23:25
**Total tasks validated:** 1

## Summary

| Task | Proposed Model | Accuracy | Gold Accuracy | Recommendation |
|------|---------------|----------|---------------|----------------|
| has_effect_size | 3 | 100.0% | 100.0% | ACCEPT |

## Detailed Rationale

### has_effect_size

- **Proposed model:** claude-3-5-haiku-20241022
- **Samples tested:** 5
- **Accuracy:** 5/5 (100.0%)
- **Gold accuracy:** 100.0%
- **Recommendation:** ACCEPT
- **Rationale:** HAIKU achieves 100.0% accuracy, exceeding 95% threshold. Safe for production use.

## Routing Configuration

Based on validation results, update `crci/llm/model_router.py`:

```python
# Tasks validated for Haiku (binary classification)
haiku_tasks = frozenset({
    "has_effect_size",
})
```

## Cost Impact

Routing binary tasks to Haiku reduces cost by ~60-70% for those tasks.
See `crci/llm/model_router.py:estimate_extraction_cost()` for details.