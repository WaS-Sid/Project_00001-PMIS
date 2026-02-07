"""
Database configuration for Celery worker.
Mirrors app/database.py for consistent DB access.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Import models from API app
# The worker and API share the same DB schema
try:
    from app.tools.models import Base
except ImportError:
    # Fallback: define Base locally if app not available
    from sqlalchemy.ext.declarative import declarative_base
    Base = declarative_base()

# Database URL from environment or default to SQLite
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./test.db"
)

# For PostgreSQL in production:
# DATABASE_URL = "postgresql://user:password@localhost/pmis"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """Get a database session."""
    return SessionLocal()


def init_db():
    """Initialize database (create all tables)."""
    Base.metadata.create_all(bind=engine)
