"""
Database connection, session management, and migrations.
Supports both PostgreSQL (with pgvector) and SQLite fallback for system independence.
"""

import os
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session as DBSession
from app.config import settings
from app.models.entities import Base

# Ensure data directory exists for SQLite fallback
os.makedirs("data", exist_ok=True)

# Normalize SQLite or Postgres database URL
db_url = settings.database_url
is_sqlite = db_url.startswith("sqlite")

connect_args = {"check_same_thread": False} if is_sqlite else {}

# Pool configuration: tuned for single-demo-user scale per PRD §2
_pool_kwargs = {} if is_sqlite else {
    "pool_size": 10,
    "max_overflow": 20,
    "pool_timeout": 30,
    "pool_recycle": 1800,
}

engine = create_engine(
    db_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    **_pool_kwargs
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Initialize database tables and extensions."""
    if not is_sqlite:
        # Create vector extension if on Postgres
        try:
            with engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                conn.commit()
        except Exception:
            pass  # May already exist or permissions handled externally
            
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_db_context() -> Generator[DBSession, None, None]:
    """Context manager for non-FastAPI tasks and CLI scripts."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db() -> Generator[DBSession, None, None]:
    """FastAPI dependency for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_health() -> bool:
    """Validate database connectivity."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
