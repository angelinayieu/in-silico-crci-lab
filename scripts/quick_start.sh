#!/usr/bin/env bash
#
# Quick start script for CRCI extraction pipeline
#  Sets up PostgreSQL and runs a sample extraction
#

set -euo pipefail

PROJECT_ROOT=/workspaces/in-silico-crci-lab
cd "$PROJECT_ROOT"

echo "=== CRCI Extraction Pipeline Quick Start ==="
echo

# 1. Check PostgreSQL is running
echo "[1/5] Checking PostgreSQL..."
if ! pg_isready -h localhost -p 5432 >/dev/null 2>&1; then
    echo "  PostgreSQL not running. Starting..."
    pg_ctl -D /var/lib/postgresql/16/main start -l /tmp/postgresql.log >/dev/null 2>&1 && sleep 2
    if ! pg_isready -h localhost -p 5432 >/dev/null 2>&1; then
        echo "  ERROR: Could not start PostgreSQL. Check /tmp/postgresql.log"
        exit 1
    fi
    echo "  ✓ PostgreSQL started"
else
    echo "  ✓ PostgreSQL already running"
fi

# 2. Create database user and database  
echo "[2/5] Setting up database..."
# Try to create as current user (works if peer auth is enabled)
if psql postgres -c "CREATE USER crci WITH PASSWORD 'crci' SUPERUSER CREATEDB;" 2>/dev/null; then
    echo "  ✓ Created user 'crci'"
else
    echo "  User 'crci' already exists or couldn't create (continuing...)"
fi

if psql postgres -c "CREATE DATABASE crci OWNER crci;" 2>/dev/null; then
    echo "  ✓ Created database 'crci'"
else
    echo "  Database 'crci' already exists or couldn't create (continuing...)"
fi

# 3. Initialize schema
echo "[3/5] Initializing database schema..."
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
export DATABASE_URL="postgresql://crci:crci@localhost:5432/crci"

if python "$PROJECT_ROOT/scripts/setup_database.py" --init 2>&1 | grep -q "SUCCESS"; then
    echo "  ✓ Schema initialized"
else
    echo "  Schema initialization had issues (check logs above)"
fi

# 4. Load seed data
echo "[4/5] Loading seed data..."
if python "$PROJECT_ROOT/scripts/setup_database.py" --seed 2>&1 | grep -q "SUCCESS"; then
    echo "  ✓ Seed data loaded"
else
    echo "  Seed loading had issues (check logs above)"
fi

#5. Verify setup
echo "[5/5] Verifying setup..."
python "$PROJECT_ROOT/scripts/setup_database.py" --verify 2>&1 | tail -20

echo
echo "=== Setup Complete ==="
echo
echo "To run extraction on a paper:"
echo "  python scripts/run_extraction.py <path_to_paper.pdf>"
echo
echo "Example:"
echo "  python scripts/run_extraction.py examples/sample_paper.pdf"
echo
