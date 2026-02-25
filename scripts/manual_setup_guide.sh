#!/usr/bin/env bash
#
# CRCI Database Manual Setup Helper
# Since automated setup requires sudo, this guides you through manual setup
#

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║        CRCI Database Manual Setup Instructions               ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo
echo "You need to run these commands manually (requires sudo password):"
echo
echo "────────────────────────────────────────────────────────────────"
echo "STEP 1: Create PostgreSQL user and database"
echo "────────────────────────────────────────────────────────────────"
echo
echo "Run the following commands (copy-paste them):"
echo
echo "sudo -u postgres psql << 'EOF'"
echo "DROP DATABASE IF EXISTS crci;"
echo "DROP USER IF EXISTS crci;"
echo "CREATE USER crci WITH PASSWORD 'crci' SUPERUSER;"
echo "CREATE DATABASE crci OWNER crci;"
echo "\q"
echo "EOF"
echo
echo "────────────────────────────────────────────────────────────────"
echo "STEP 2: After that succeeds, initialize the schema:"
echo "────────────────────────────────────────────────────────────────"
echo
echo "cd /workspaces/in-silico-crci-lab"
echo "export DATABASE_URL='postgresql://crci:crci@localhost:5432/crci'"
echo "export PYTHONPATH='/workspaces/in-silico-crci-lab:\$PYTHONPATH'"
echo "python scripts/setup_database.py --init --seed"
echo
echo "────────────────────────────────────────────────────────────────"
echo "STEP 3: Run extraction on a paper:"
echo "────────────────────────────────────────────────────────────────"
echo
echo "python scripts/run_extraction.py path/to/paper.pdf"
echo
echo "════════════════════════════════════════════════════════════════"
