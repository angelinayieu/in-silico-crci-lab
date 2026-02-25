#!/usr/bin/env bash
#
# Bootstrap PostgreSQL for CRCI extraction pipeline
# Run this once to set up the database
#

set -euo pipefail

echo "=== CRCI Database Bootstrap ==="

# Check if running as postgres
if [ "$EUID" -eq 0 ]; then 
    echo "Don't run this as root. Run as normal user."
    exit 1
fi

# Create SQL bootstrap file
cat > /tmp/crci_bootstrap.sql <<'EOF'
\set ON_ERROR_STOP on

-- Drop existing if present (for clean restarts)  
DROP DATABASE IF EXISTS crci;
DROP USER IF EXISTS crci;

-- Create user and database
CREATE USER crci WITH PASSWORD 'crci' CREATEDB SUPERUSER;
CREATE DATABASE crci OWNER crci;

-- Grant all privileges
GRANT ALL PRIVILEGES ON DATABASE crci TO crci;

\echo 'Bootstrap complete - user crci and database crci created'
EOF

echo "Running bootstrap SQL..."
# Method 1: Try with psql as current user via Unix socket
if psql -U postgres postgres -f /tmp/crci_bootstrap.sql 2>&1; then
    echo "✓ Bootstrap successful"
    rm /tmp/crci_bootstrap.sql
    exit 0
fi

# Method 2: Try as postgres system user (requires sudo or being postgres)
echo "First attempt failed, trying alternative method..."
if command -v sudo >/dev/null 2>&1; then
    if sudo -nu postgres psql -f /tmp/crci_bootstrap.sql 2>&1; then
        echo "✓ Bootstrap successful (via sudo)"
        rm /tmp/crci_bootstrap.sql
        exit 0
    fi
fi

echo "ERROR: Could not bootstrap database. Manual setup required:"
echo "1. Become postgres user: sudo -u postgres psql"
echo "2. Run: CREATE USER crci WITH PASSWORD 'crci' SUPERUSER;"
echo "3. Run: CREATE DATABASE crci OWNER crci;"

rm /tmp/crci_bootstrap.sql
exit 1
