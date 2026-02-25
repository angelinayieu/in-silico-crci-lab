#!/usr/bin/env bash
#
# Complete CRCI Setup - Run this in a FRESH terminal
#

set -e

echo "════════════════════════════════════════════════════════════"
echo "  CRCI Extraction Pipeline - Complete Setup"  
echo "════════════════════════════════════════════════════════════"
echo

# Step 1: Create PostgreSQL user and database
echo "[1/3] Creating PostgreSQL database..."
sudo -u postgres psql -c "DROP DATABASE IF EXISTS crci;" 2>/dev/null || true
sudo -u postgres psql -c "DROP ROLE IF EXISTS crci;" 2>/dev/null || true  
sudo -u postgres psql -c "CREATE ROLE crci WITH LOGIN PASSWORD 'crci' SUPERUSER CREATEDB;"
sudo -u postgres psql -c "CREATE DATABASE crci OWNER crci;"
echo "✓ Database created"
echo

# Step 2: Initialize schema
echo "[2/3] Initializing database schema and loading seeds..."
cd /workspaces/in-silico-crci-lab
export DATABASE_URL="postgresql://crci:crci@localhost:5432/crci"
export PYTHONPATH="/workspaces/in-silico-crci-lab:$PYTHONPATH"

python scripts/setup_database.py --init --seed
echo "✓ Schema and seeds loaded"
echo

# Step 3: Verify
echo "[3/3] Verifying setup..."
python scripts/setup_database.py --verify | tail -10
echo

echo "════════════════════════════════════════════════════════════"
echo "✓ Setup complete!"
echo  
echo "To run extraction on a paper:"
echo "  python scripts/run_extraction.py path/to/paper.pdf"
echo "════════════════════════════════════════════════════════════"
