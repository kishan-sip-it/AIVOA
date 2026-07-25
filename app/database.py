"""
database.py
------------
SQLAlchemy engine, session, and declarative base for PostgreSQL.

This file is a small addition beyond the requested list (main.py, models.py,
graph.py, schemas.py) because SQLAlchemy needs an engine/session factory
somewhere — keeping it isolated here keeps models.py focused purely on
table definitions.
"""

import os
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
    """Create all tables. Called once on app startup."""
    from app import models  # noqa: F401  (ensures models are registered)
    Base.metadata.create_all(bind=engine)
