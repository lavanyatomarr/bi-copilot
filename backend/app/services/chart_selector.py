"""Picks the best chart for a result, then builds a Plotly spec.

Deterministic rules (no LLM): the choice depends on the SHAPE of the result
(how many columns, which are categorical vs numeric) and the INTENT of the
question. Fast, free, predictable. Falls back to a table when no chart fits.
"""
from datetime import date, datetime


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _looks_like_date(v) -> bool:
    if isinstance(v, (date, datetime)):
        return True
    if isinstance(v, str):
        # cheap check: "2024-01-01" style
        return len(v) >= 8 and v[:4].isdigit() and ("-" in v or "/" in v)
    return False


def choose_chart(question: str, rows: list[dict]) -> str:
    if not rows:
        return "table"
    cols = list(rows[0].keys())
    q = question.lower()

    # classify columns by looking at the first row's values
    sample = rows[0]
    numeric_cols = [c for c in cols if _is_number(sample[c])]
    date_cols = [c for c in cols if _looks_like_date(sample[c])]
    cat_cols = [c for c in cols if c not in numeric_cols and c not in date_cols]

    # intent keywords
    wants_trend = any(w in q for w in ["trend", "over time", "growth", "forecast", "monthly", "daily", "by month", "by year"])
    wants_share = any(w in q for w in ["share", "proportion", "percentage", "percent", "split", "distribution"])

    # rules (first match wins)
    if (wants_trend or date_cols) and numeric_cols:
        return "line"
    if wants_share and cat_cols and numeric_cols and len(rows) <= 8:
        return "pie"
    if cat_cols and numeric_cols:
        return "bar"
    if len(numeric_cols) >= 2 and not cat_cols:
        return "scatter"
    return "table"


def build_spec(chart_type: str, rows: list[dict]) -> dict:
    """Return a minimal Plotly figure spec the frontend can render directly."""
    if not rows or chart_type == "table":
        return {"type": "table", "data": [], "layout": {}}

    cols = list(rows[0].keys())
    sample = rows[0]
    numeric_cols = [c for c in cols if _is_number(sample[c])]
    date_cols = [c for c in cols if _looks_like_date(sample[c])]
    cat_cols = [c for c in cols if c not in numeric_cols and c not in date_cols]

    y = numeric_cols[0] if numeric_cols else cols[-1]
    x = (date_cols[0] if date_cols else (cat_cols[0] if cat_cols else cols[0]))

    xs = [r.get(x) for r in rows]
    ys = [r.get(y) for r in rows]

    if chart_type == "line":
        data = [{"type": "scatter", "mode": "lines+markers", "x": xs, "y": ys, "name": y}]
    elif chart_type == "pie":
        data = [{"type": "pie", "labels": xs, "values": ys}]
    elif chart_type == "scatter":
        x2 = numeric_cols[0]
        y2 = numeric_cols[1] if len(numeric_cols) > 1 else numeric_cols[0]
        data = [{"type": "scatter", "mode": "markers",
                 "x": [r.get(x2) for r in rows], "y": [r.get(y2) for r in rows]}]
        x, y = x2, y2
    else:  # bar
        data = [{"type": "bar", "x": xs, "y": ys, "name": y}]

    return {
        "type": chart_type,
        "data": data,
        "layout": {"title": f"{y} by {x}", "xaxis": {"title": x}, "yaxis": {"title": y}},
    }
