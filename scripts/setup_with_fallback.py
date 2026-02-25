#!/usr/bin/env python3
"""
Simplified CRCI database setup using SQLite as fallback.
If PostgreSQL setup fails, uses SQLite for testing.
"""
import os
import sys
import subprocess

def setup_postgresql():
    """Try to set up PostgreSQL database."""
    print("Attempting PostgreSQL setup...")
    
    # Try connecting without password via peer auth
    sql_commands = """
DROP DATABASE IF EXISTS crci;
DROP ROLE IF EXISTS crci;
CREATE ROLE crci WITH LOGIN PASSWORD 'crci' SUPERUSER CREATEDB;
CREATE DATABASE crci OWNER crci;
"""
    
    # Write SQL to temp file
    with open('/tmp/crci_setup.sql', 'w') as f:
        f.write(sql_commands)
    
    # Try multiple connection methods
    methods = [
        ['psql', 'postgres', '-f', '/tmp/crci_setup.sql'],  # Local peer auth
        ['psql', '-U', 'codespace', 'postgres', '-f', '/tmp/crci_setup.sql'],  # As codespace user
    ]
    
    for method in methods:
        try:
            result = subprocess.run(
                method,
                capture_output=True,
                text=True,
                timeout=5,
                env={**os.environ, 'PGPASSWORD': ''}
            )
            if result.returncode == 0:
                print("✓ PostgreSQL setup successful!")
                print(result.stdout)
                return True
            else:
                print(f"  Method {' '.join(method[:2])} failed: {result.stderr[:100]}")
        except Exception as e:
            print(f"  Method failed: {e}")
            continue
    
    return False

def setup_sqlite_fallback():
    """Set up SQLite as fallback option."""
    print("\n" + "="*60)
    print("PostgreSQL setup requires sudo access.")
    print("Setting up SQLite fallback for development...")
    print("="*60)
    
    # Update .env to use SQLite
    env_path = '/workspaces/in-silico-crci-lab/.env'
    sqlite_url = 'sqlite:////workspaces/in-silico-crci-lab/crci.db'
    
    # Read current .env
    with open(env_path, 'r') as f:
        lines = f.readlines()
    
    # Update DATABASE_URL
    with open(env_path, 'w') as f:
        for line in lines:
            if line.startswith('DATABASE_URL='):
                f.write(f'DATABASE_URL={sqlite_url}\n')
                print(f"✓ Updated .env to use SQLite: {sqlite_url}")
            else:
                f.write(line)
    
    print("\nNOTE: SQLite is for development only. For production:")
    print("  1. In your Codespace, open a new terminal")
    print("  2. Run: sudo -u postgres psql")
    print("  3. Paste:")
    print("     CREATE ROLE crci WITH LOGIN PASSWORD 'crci' SUPERUSER;")
    print("     CREATE DATABASE crci OWNER crci;")
    print("     \\q")
    print("  4. Update .env back to PostgreSQL URL")
    
    return True

def main():
    print("╔══════════════════════════════════════════════════════════╗")
    print("║          CRCI Database Setup Utility                     ║")
    print("╚══════════════════════════════════════════════════════════╝\n")
    
    if setup_postgresql():
        print("\n✓ PostgreSQL ready! Now run:")
        print("  cd /workspaces/in-silico-crci-lab")
        print("  export DATABASE_URL='postgresql://crci:crci@localhost:5432/crci'")
        print("  export PYTHONPATH='/workspaces/in-silico-crci-lab'")
        print("  python scripts/setup_database.py --init --seed")
        return 0
    
    # Fallback to SQLite
    if setup_sqlite_fallback():
        print("\n✓ SQLite fallback configured!")
        print("  You can now run extraction (using SQLite for development):")
        print("  python scripts/run_extraction.py paper.pdf")
        return 0
    
    print("\n❌ Setup failed. Please contact support.")
    return 1

if __name__ == '__main__':
    sys.exit(main())
