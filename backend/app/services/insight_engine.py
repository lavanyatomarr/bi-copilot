"""Turns query results into a plain-English insight, a confidence score,
and follow-up questions -- all in a single LLM call.
"""
import json

from .llm_adapter import get_llm

INSIGHT_SYSTEM = """You are a sharp business analyst.
Given a QUESTION and the QUERY RESULT rows, do three things:
1. Write ONE concise insight (max 2 sentences) that cites real numbers from the rows.
   If rows are empty, say no data matched -- never invent numbers.
2. Give a confidence from 0.0 to 1.0 for how well the result answers the question
   (consider: are there rows? do they directly answer it? any obvious gaps?).
   This is a rough self-assessment, not a guarantee.
3. Suggest 3 short follow-up questions answerable from the same dataset.

Return STRICT JSON only:
{"insight": <string>, "confidence": <number>, "follow_ups": [<string>, <string>, <string>]}"""


def _clamp(x, lo=0.0, hi=1.0):
    try:
        return max(lo, min(hi, float(x)))
    except (TypeError, ValueError):
        return 0.5


def generate_insight(question: str, rows: list[dict]) -> dict:
    # cap rows sent to the model to control token usage
    preview = rows[:50]
    user = f"QUESTION: {question}\n\nQUERY RESULT ({len(rows)} rows, showing up to 50):\n{json.dumps(preview, default=str)}"

    try:
        raw = get_llm().complete(INSIGHT_SYSTEM, user)
        parsed = json.loads(raw)
        return {
            "insight": str(parsed.get("insight", "")).strip() or "No insight available.",
            "confidence": _clamp(parsed.get("confidence", 0.5)),
            "follow_ups": [str(f) for f in (parsed.get("follow_ups") or [])][:3],
        }
    except Exception:
        # never let insight failure break the whole query -- degrade gracefully
        return {
            "insight": f"Returned {len(rows)} row(s).",
            "confidence": 0.5,
            "follow_ups": [],
        }
