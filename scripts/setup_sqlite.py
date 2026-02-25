#!/usr/bin/env python3
"""
SQLite-based setup for CRCI when PostgreSQL setup is blocked.
This allows you to run extractions for development/testing.
"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path("/workspaces/in-silico-crci-lab")
SQLITE_DB = PROJECT_ROOT / "crci_dev.db"

def setup_sqlite():
    """Set up SQLite database for development."""
    print("╔══════════════════════════════════════════════════════════╗")
    print("║   CRCI SQLite Development Setup                          ║")
    print("╚══════════════════════════════════════════════════════════╝\n")
    
    print("Since PostgreSQL setup requires sudo password, using SQLite...")
    print()
    
    # Update .env
    env_file = PROJECT_ROOT / ".env"
    
    # Read current content
    if env_file.exists():
        with open(env_file, 'r') as f:
            lines = f.readlines()
    else:
        lines = []
    
    # Update DATABASE_URL
    new_lines = []
    db_url_found = False
    sqlite_url = f"sqlite:///{SQLITE_DB}"
    
    for line in lines:
        if line.startswith('DATABASE_URL='):
            new_lines.append(f'DATABASE_URL={sqlite_url}\n')
            db_url_found = True
            print(f"✓ Updated DATABASE_URL to: {sqlite_url}")
        else:
            new_lines.append(line)
    
    if not db_url_found:
        new_lines.append(f'DATABASE_URL={sqlite_url}\n')
        print(f"✓ Added DATABASE_URL: {sqlite_url}")
    
    # Write back
    with open(env_file, 'w') as f:
        f.writelines(new_lines)
    
    print(f"✓ Configuration saved to {env_file}")
    print()
    
    # Set environment for this session
    os.environ['DATABASE_URL'] = sqlite_url
    os.environ['PYTHONPATH'] = str(PROJECT_ROOT)
    
    print("✓ SQLite database configured")
    print()
    
    # Initialize schema
    print("Initializing database schema...")
    sys.path.insert(0, str(PROJECT_ROOT))
    
    try:
        from crci.shared.db import init_db, get_session
        from sqlalchemy import text
        
        # Initialize database
        engine = init_db(sqlite_url)
        print(f"✓ Database engine initialized")
        
        # Import table models to create schema
        print("✓ Creating tables...")
        
        # Import all models
        from crci.shared.models import tables
        from sqlalchemy import MetaData
        
        # Create all tables
        metadata = MetaData()
        metadata.reflect(bind=engine)
        tables.Base.metadata.create_all(engine)
        
        print(f"✓ Schema created in {SQLITE_DB}")
        
    except Exception as e:
        print(f"⚠️  Schema initialization had issues: {e}")
        print("   You may need to run: python scripts/setup_database.py --init")
    
    print()
    print("═══════════════════════════════════════════════════════════")
    print("✅ Setup complete!")
    print()
    print("Run extraction with:")
    print(f"  export DATABASE_URL='{sqlite_url}'")
    print(f"  export PYTHONPATH='{PROJECT_ROOT}'")
    print("  python scripts/run_extraction.py /workspaces/in-silico-crci-lab/cherrier2013.pdf")
    print()
    print("NOTE: SQLite is for development only.")
    print("For production, you'll need PostgreSQL with proper admin access.")
    print("═══════════════════════════════════════════════════════════")

if __name__ == '__main__':
    setup_sqlite()
