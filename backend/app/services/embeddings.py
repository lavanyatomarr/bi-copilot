"""Turns text into a vector (embedding) using Google's free Gemini embeddings.

If no GEMINI_API_KEY is set, returns None -> the RAG cache simply stays off and
the rest of the app keeps working. No hard dependency.
"""
import httpx

from ..config import settings

_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent"


def embed(text: str) -> list[float] | None:
    if not settings.gemini_api_key:
        return None
    url = _URL.format(model=settings.embedding_model)
    body = {
        "model": f"models/{settings.embedding_model}",
        "content": {"parts": [{"text": text}]},
        "outputDimensionality": settings.embedding_dim,   # keep vectors small (768)
        "taskType": "SEMANTIC_SIMILARITY",                # we compare question-to-question
    }
    try:
        r = httpx.post(f"{url}?key={settings.gemini_api_key}", json=body, timeout=20)
        r.raise_for_status()
        values = r.json()["embedding"]["values"]
        return values if values else None
    except Exception:
        return None      # never let an embedding failure break a query


def to_pgvector(vec: list[float]) -> str:
    """pgvector accepts a string literal like '[0.1,0.2,...]'."""
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"
