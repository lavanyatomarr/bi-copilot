from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import settings
from .db import Base, engine, ensure_pgvector, ensure_rag, get_db
from .models.user import User  # noqa: F401  (import so the table is registered)
from .models.dataset import DatasetMetadata, UploadedDataset  # noqa: F401
from .routers import analytics, auth, datasets, query


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once when the server starts up.
    ensure_pgvector()                       # make sure the vector extension is available
    ensure_rag()                            # create the RAG semantic-cache table + indexes
    Base.metadata.create_all(bind=engine)   # create any tables that don't exist yet
    yield
    # (anything after yield would run on shutdown — nothing needed yet)


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.include_router(auth.router)             # mounts /auth/register, /auth/login, /auth/me
app.include_router(datasets.router)         # mounts /datasets/upload, /datasets, ...
app.include_router(query.router)            # mounts /query
app.include_router(analytics.router)        # mounts /analytics/anomalies, /forecast, /kpis


@app.get("/")
def root():
    return {"ok": True, "service": settings.app_name, "message": "Backend is alive"}


@app.get("/health")
def health(db: Session = Depends(get_db)):
    """Proves three things at once: server runs, DB is reachable, pgvector is enabled."""
    db.execute(text("SELECT 1"))  # raises if the DB is unreachable
    has_vector = db.execute(
        text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
    ).first()
    return {
        "ok": True,
        "database": "connected",
        "pgvector": "enabled" if has_vector else "missing",
    }
