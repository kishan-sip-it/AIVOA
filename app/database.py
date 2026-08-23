"""
database.py
------------
SQLAlchemy engine, session, and declarative base for PostgreSQL.

Alembic is responsible for schema migrations. The application startup runs
`alembic upgrade head` so deployed environments stay in sync with the ORM
models without relying on SQLAlchemy `create_all()` to alter existing tables.
"""

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://aivoa_user:aivoa_password@localhost:5432/aivoa_db",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session and closes it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Run all pending Alembic migrations on application startup."""
    from app import models  # noqa: F401  (ensures models are registered)

    project_root = Path(__file__).resolve().parent.parent
    alembic_ini = project_root / "alembic.ini"

    if not alembic_ini.exists():
        raise RuntimeError(f"Alembic configuration not found: {alembic_ini}")

    config = Config(str(alembic_ini))
    command.upgrade(config, "head")
