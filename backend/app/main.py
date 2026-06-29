from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import settings
from .db import ensure_pgvector, get_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once when the server starts up.
    ensure_pgvector()  # make sure the vector extension is available
    yield
    # (anything after yield would run on shutdown — nothing needed yet)


app = FastAPI(title=settings.app_name, lifespan=lifespan)


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
