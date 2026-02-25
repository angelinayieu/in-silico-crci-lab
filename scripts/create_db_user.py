#!/usr/bin/env python3
"""
Create CRCI database user and database programmatically.
Works around authentication issues by using different connection methods.
"""
import sys
import subprocess
import psycopg2
from psycopg2 import sql

def try_create_via_psql():
    """Try using psql command line via local socket (peer auth)."""
    commands = [
        "CREATE USER crci WITH PASSWORD 'crci' SUPERUSER;",
        "CREATE DATABASE crci OWNER crci;",
    ]
    
    for cmd in commands:
        try:
            result = subprocess.run(
                ["psql", "-U", "postgres", "-c", cmd],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                print(f"✓ {cmd.split()[1]} successful")
            else:
                print(f"  {cmd.split()[1]} may already exist or failed: {result.stderr[:100]}")
        except Exception as e:
            print(f"  Command failed: {e}")
            return False
    return True

def try_create_via_python():
    """Try using psycopg2 to connect and create user/db."""
    # Try connecting to postgres db as various users
    connection_attempts = [
        {"host": "/var/run/postgresql", "database": "postgres"},  # Unix socket
        {"host": "localhost", "port": 5432, "database": "postgres", "user": "postgres", "password": ""},
        {"host": "localhost", "port": 5432, "database": "postgres", "user": "codespace"},
    ]
    
    for conn_params in connection_attempts:
        try:
            conn = psycopg2.connect(**conn_params)
            conn.autocommit = True
            cur = conn.cursor()
            
            # Create user
            try:
                cur.execute("CREATE USER crci WITH PASSWORD 'crci' SUPERUSER;")
                print("✓ User 'crci' created")
            except psycopg2.errors.DuplicateObject:
                print("  User 'crci' already exists")
            except Exception as e:
                print(f"  Could not create user: {e}")
            
            # Create database
            try:
                cur.execute("CREATE DATABASE crci OWNER crci;")
                print("✓ Database 'crci' created")
            except psycopg2.errors.DuplicateDatabase:
                print("  Database 'crci' already exists")
            except Exception as e:
                print(f"  Could not create database: {e}")
            
            cur.close()
            conn.close()
            return True
            
        except Exception as e:
            continue
    
    return False

def main():
    print("=== Creating CRCI Database User ===\n")
    
    # Try psql first
    print("[Method 1] Trying psql command...")
    if try_create_via_psql():
        print("\n✓ Database setup complete!")
        return 0
    
    # Try Python/psycopg2
    print("\n[Method 2] Trying direct connection...")
    if try_create_via_python():
        print("\n✓ Database setup complete!")
        return 0
    
    print("\n❌ Automatic setup failed.")
    print("\nManual setup required:")
    print("1. You need to set your sudo password or")
    print("2. Modify PostgreSQL to allow local connections")
    print("\nTo set up manually, run:")
    print("  sudo -u postgres psql")
    print("Then in psql:")
    print("  CREATE USER crci WITH PASSWORD 'crci' SUPERUSER;")
    print("  CREATE DATABASE crci OWNER crci;")
    print("  \\q")
    
    return 1

if __name__ == "__main__":
    sys.exit(main())
