# VERIFIED: imports — sqlalchemy + os only
# VERIFIED: downstream — used by all DB-accessing modules
"""
Component: Layer 0 — Database Connection
Spec: IMPLEMENTATION_BLUEPRINT Part 3 (directory tree)
Purpose: PostgreSQL connection via SQLAlchemy, session factory.
Reads: DATABASE_URL from environment
Writes: Nothing (provides engine + session)
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

_DEFAULT_DATABASE_URL = "postgresql://crci:crci@localhost:5432/crci"


def get_database_url() -> str:
    """Return DATABASE_URL from environment, with sensible default."""
    url = os.environ.get("DATABASE_URL", _DEFAULT_DATABASE_URL)
    if not url:
        raise RuntimeError(
            "DATABASE_URL is empty. Set it in .env or environment."
        )
    return url


def create_db_engine(database_url: str | None = None, echo: bool = False) -> Engine:
    """Create a SQLAlchemy engine.

    Args:
        database_url: Override the default DATABASE_URL.
        echo: If True, log all SQL statements.
    """
    url = database_url or get_database_url()

    # SQLite doesn't support connection pooling parameters
    if url.startswith("sqlite"):
        engine = create_engine(url, echo=echo)
    else:
        engine = create_engine(
            url,
            echo=echo,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
    logger.info("Database engine created for %s", url.split("@")[-1] if "@" in url else url)
    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a session factory bound to the given engine."""
    return sessionmaker(bind=engine, expire_on_commit=False)


# ─── Module-level convenience ────────────────────────────────

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def init_db(database_url: str | None = None, echo: bool = False) -> Engine:
    """Initialize the module-level engine and session factory."""
    global _engine, _session_factory
    _engine = create_db_engine(database_url, echo=echo)
    _session_factory = create_session_factory(_engine)
    return _engine


def get_engine() -> Engine:
    """Return the module-level engine, initializing if needed."""
    if _engine is None:
        init_db()
    assert _engine is not None
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return the module-level session factory, initializing if needed."""
    if _session_factory is None:
        init_db()
    assert _session_factory is not None
    return _session_factory


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context manager for a database session with automatic commit/rollback."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def execute_sql_file(engine: Engine, filepath: str) -> None:
    """Execute a raw SQL file against the given engine.

    Used for running schema migration files (001_class_a_knowledge.sql, etc.).
    """
    logger.info("Executing SQL file: %s", filepath)
    with open(filepath, "r") as f:
        sql_content = f.read()

    with engine.begin() as conn:
        # Split on semicolons but respect multi-line statements
        for statement in sql_content.split(";"):
            statement = statement.strip()
            if statement:
                conn.execute(text(statement))

    logger.info("SQL file executed successfully: %s", filepath)
