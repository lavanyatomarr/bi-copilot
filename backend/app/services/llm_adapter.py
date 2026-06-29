"""LLM adapter -- one interface, swappable backend.

Lets us (a) call Groq's free API, (b) fall back to a deterministic mock so the
app/demo works with no key and no internet. Business logic never knows or cares
which backend is active.
"""
import json
from abc import ABC, abstractmethod

import httpx

from ..config import settings


class LLMBackend(ABC):
    @abstractmethod
    def complete(self, system: str, user: str) -> str: ...


class GroqBackend(LLMBackend):
    """Groq free tier. OpenAI-compatible endpoint."""
    URL = "https://api.groq.com/openai/v1/chat/completions"

    def complete(self, system: str, user: str) -> str:
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is not set")
        body = {
            "model": settings.groq_model,
            "temperature": 0,                       # deterministic -> reliable SQL
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        r = httpx.post(
            self.URL, json=body, timeout=30,
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


class MockBackend(LLMBackend):
    """Offline stub. Returns a simple, safe SELECT so the pipeline works without a key."""
    def complete(self, system: str, user: str) -> str:
        return json.dumps({
            "sql": "SELECT * FROM {{TABLE}} LIMIT 10",
            "explanation": "(offline mock) Returns the first 10 rows of the dataset.",
        })


def get_llm() -> LLMBackend:
    if settings.llm_provider == "groq" and settings.groq_api_key:
        return GroqBackend()
    return MockBackend()      # no key / provider=mock -> safe offline default
