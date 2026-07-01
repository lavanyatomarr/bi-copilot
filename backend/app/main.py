import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import settings
from .db import Base, engine, ensure_pgvector, ensure_rag, get_db
from .models.user import User  # noqa: F401  (import so the table is registered)
from .models.dataset import DatasetMetadata, UploadedDataset  # noqa: F401
from .routers import analytics, auth, datasets, history, query


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once when the server starts up.
    ensure_pgvector()                       # make sure the vector extension is available
    ensure_rag()                            # create the RAG semantic-cache table + indexes
    Base.metadata.create_all(bind=engine)   # create any tables that don't exist yet
    yield
    # (anything after yield would run on shutdown — nothing needed yet)


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# Allow the React dev server (and your future deployed frontend) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# All API routes live under /api so they never collide with the frontend's own
# client-side routes (e.g. the app's /datasets and /history pages).
app.include_router(auth.router, prefix="/api")
app.include_router(datasets.router, prefix="/api")
app.include_router(query.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(history.router, prefix="/api")


@app.get("/api")
def root():
    return {"ok": True, "service": settings.app_name, "message": "Backend is alive"}


# --- Serve the built React frontend (production only) ---
# In local dev the frontend runs on its own Vite server, so this directory
# won't exist and the whole block is skipped. In the deployed Docker image,
# the build is copied next to the app and FastAPI serves it.
def _find_static_dir():
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "static"),  # /app/static (Docker)
        "/app/static",                                            # absolute fallback
        os.path.join(os.getcwd(), "static"),                      # cwd fallback
    ]
    for c in candidates:
        if os.path.isdir(c) and os.path.isfile(os.path.join(c, "index.html")):
            return os.path.abspath(c)
    return None


STATIC_DIR = _find_static_dir()
print(f"[startup] STATIC_DIR = {STATIC_DIR}", flush=True)

if STATIC_DIR:
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

    @app.get("/")
    def spa_index():
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))

    # Any non-API path that isn't a real file falls back to the SPA shell so
    # client-side routes (e.g. /history) work on a hard refresh.
    @app.exception_handler(404)
    async def spa_fallback(request: Request, exc):
        path = request.url.path
        if request.method == "GET" and not path.startswith(("/api", "/docs", "/openapi", "/redoc", "/health")):
            return FileResponse(os.path.join(STATIC_DIR, "index.html"))
        return JSONResponse({"detail": "Not Found"}, status_code=404)


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
