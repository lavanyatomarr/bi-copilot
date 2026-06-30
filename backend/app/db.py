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


def ensure_rag():
    """Create the semantic-cache table + its vector (HNSW) and full-text (GIN) indexes.

    Done in raw SQL (not via ORM) because it uses pgvector's VECTOR type and a
    generated TSVECTOR column, which are awkward to express in SQLAlchemy models.
    """
    from .config import settings
    dim = settings.embedding_dim
    with engine.connect() as conn:
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS rag_query_cache (
                id            BIGSERIAL PRIMARY KEY,
                user_id       INTEGER NOT NULL,
                dataset_id    INTEGER NOT NULL,
                question      TEXT NOT NULL,
                validated_sql TEXT NOT NULL,
                embedding     VECTOR({dim}),
                fts           TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', question)) STORED,
                hit_count     INTEGER NOT NULL DEFAULT 0,
                created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ragcache_vec "
                          "ON rag_query_cache USING hnsw (embedding vector_cosine_ops)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ragcache_fts "
                          "ON rag_query_cache USING gin(fts)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ragcache_scope "
                          "ON rag_query_cache(user_id, dataset_id)"))
        conn.commit()
