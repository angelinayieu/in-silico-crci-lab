# CRCI Extraction Pipeline - Quick Start Guide

## Prerequisites Installed ✓
- Python 3.12
- PostgreSQL 16 (running on port 5432)
- Python packages: sqlalchemy, psycopg2-binary, pydantic, anthropic, pdfplumber, numpy, scipy, matplotlib

## Current Status

**Database**: PostgreSQL is running but needs authentication setup
**API Key**: Anthropic API key is configured in .env
**Code**: Extraction pipeline code is ready

## Setup Steps

### 1. Set up PostgreSQL Database (One-time setup)

You need to create the `crci` database user. Run ONE of these methods:

**Method A - Using psql with sudo:**
```bash
sudo -u postgres psql <<EOF
CREATE USER crci WITH PASSWORD 'crci' SUPERUSER;
CREATE DATABASE crci OWNER crci;
EOF
```

**Method B - Using createuser command:**
```bash
sudo -u postgres createuser -s crci
sudo -u postgres psql -c "ALTER USER crci PASSWORD 'crci';"
sudo -u postgres createdb -O crci crci
```

### 2. Initialize Database Schema

Once the database user exists:
```bash
cd /workspaces/in-silico-crci-lab
export DATABASE_URL="postgresql://crci:crci@localhost:5432/crci"
export PYTHONPATH=/workspaces/in-silico-crci-lab:$PYTHONPATH

# Create tables
python scripts/setup_database.py --init

# Load seed data (domain knowledge)
python scripts/setup_database.py --seed

# Verify
python scripts/setup_database.py --verify
```

### 3. Run Extraction on a Paper

```bash
cd /workspaces/in-silico-crci-lab
export DATABASE_URL="postgresql://crci:crci@localhost:5432/crci" 
export ANTHROPIC_API_KEY="<your-key-from-.env>"
export PYTHONPATH=/workspaces/in-silico-crci-lab:$PYTHONPATH

# Run on a single PDF
python scripts/run_extraction.py path/to/paper.pdf
```

## What the Extraction Pipeline Does

The pipeline processes research papers through multiple stages:

1. **P0-Triage**: Classifies paper type (RCT, cohort, meta-analysis, etc.)
2. **P1-Extraction**: Uses LLM agents to extract study data
3. **TB-Trust Boundary**: Validates and sanitizes extracted data
4. **P2-Harmonization**: Converts to standard units and formats
5. **P3-Heterogeneity**: Seven-layer heterogeneity assessment
6. **P4-Aggregation**: Meta-analysis and pooling
7. **P4B-Publication Bias**: Funnel plots, Egger's test
8. **P5-Sufficiency**: Evidence sufficiency checks
9. **P6-Deployment**: Writes to compiled evidence tables
10. **P7-Compilers**: Runs 6 specialized compilers for different evidence types

## Output

Extracted data goes into PostgreSQL tables:
- `edge_evidence_v1` - Causal relationships between CRCI nodes
- `harmonized_claims` - Individual study findings
- `pooled_estimates` - Meta-analytic summaries
- Plus ~50 more tables for complete provenance

## Troubleshooting

**"password authentication failed for user crci"**
→ The database user hasn't been created yet. Run Method A or B above.

**"connection refused"**
→ PostgreSQL isn't running. Start it with:
```bash
pg_ctl -D /var/lib/postgresql/16/main start
```

**"cannot import crci"**
→ Set PYTHONPATH:
```bash
export PYTHONPATH=/workspaces/in-silico-crci-lab:$PYTHONPATH
```

## Next Steps After Setup

1. Place PDF papers in a folder (e.g., `papers/`)
2. Run extraction on each:
   ```bash
   for pdf in papers/*.pdf; do
       python scripts/run_extraction.py "$pdf"
   done
   ```
3. Check results in database:
   ```bash
   psql -U crci -d crci -c "SELECT COUNT(*) FROM edge_evidence_v1;"
   ```

## Documentation

- Full system spec: `SYS_EXTRACTION_COMPLETE.md` (2,764 lines)
- Implementation guide: `IMPLEMENTATION_BLUEPRINT_v1.1.md`
- Build sequence: `PROMPT_SEQUENCE.md` (42 prompts)
