#!/bin/bash
# Create PostgreSQL roles and database for CRCI
set -e

echo "Creating PostgreSQL setup..."

# Create SQL commands
cat > /tmp/crci_db_setup.sql << 'EOSQL'
-- Create codespace role if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'codespace') THEN
        CREATE ROLE codespace WITH LOGIN SUPERUSER;
    END IF;
END $$;

-- Create crci role
DROP DATABASE IF EXISTS crci;
DROP ROLE IF EXISTS crci;
CREATE ROLE crci WITH LOGIN PASSWORD 'crci' SUPERUSER CREATEDB;
CREATE DATABASE crci OWNER crci;

-- Verify
\echo 'Setup complete!'
\l crci
EOSQL

# Run as postgres user
sudo -u postgres psql -f /tmp/crci_db_setup.sql

echo "✓ Database setup complete!"
echo ""
echo "Now run:"
echo "  cd /workspaces/in-silico-crci-lab"
echo "  export DATABASE_URL='postgresql://crci:crci@localhost:5432/crci'"
echo "  export PYTHONPATH='/workspaces/in-silico-crci-lab'"
echo "  python scripts/setup_database.py --init --seed"
echo "  python scripts/run_extraction.py cherrier2013.pdf"
