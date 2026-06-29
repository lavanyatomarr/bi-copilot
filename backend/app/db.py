from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

from .config import settings

# pool_pre_ping checks a connection is alive before using it (avoids stale-connection errors).
engine = create_engine(settings.database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# Base class that all our future ORM models (User, Dataset, ...) will inherit from.
Base = declarative_base()


def get_db():
    """FastAPI dependency: hands a DB session to an endpoint, then closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_pgvector():
    """Enable the pgvector extension once. Safe to call repeatedly."""
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
