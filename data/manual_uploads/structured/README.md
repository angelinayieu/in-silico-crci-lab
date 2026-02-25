# Manual Upload: Structured CSVs

## Folder Convention

Each paper gets its own subfolder named after its DOI with `/` replaced by `_`:

```
structured/
  10.1016_j.lfs.2013.08.011/    ← Cherrier et al. 2013
    edge_evidence_template.csv
    population_norms_template.csv
    context_priors_template.csv
  10.1016_j.bbi.2024.01.005/    ← next paper
    edge_evidence_template.csv
    ...
```

## Fill Order (per paper)

1. **edge_evidence_template.csv** — REQUIRED for every paper with effect sizes  
2. **population_norms_template.csv** — fills context priors (control group baseline)
3. **context_priors_template.csv** — node-level z-score priors  
4. **temporal_evidence_template.csv** — only if paper has ≥2 timepoints
5. **instrument_evidence_template.csv** — only if paper reports Cronbach's α / ICC
6. **correlation_template.csv** — only if paper reports inter-domain correlations

## Import Command

```bash
python scripts/run_manual_import.py --type csv --verbose
```

The import script uses `rglob("*.csv")` — finds all CSVs recursively across all
paper subfolders.

## Blank Templates

Copy blank templates from `data/templates/` as the starting point. Never edit
the blanks in `data/templates/`.
