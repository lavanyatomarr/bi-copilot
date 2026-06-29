"""Looks at an uploaded DataFrame and figures out what it means.

For each column it decides a *semantic role*:
  - datetime  : a date/time column (good for trends)
  - measure   : a number you'd aggregate (revenue, units...) -> what we MEASURE
  - dimension : a category you'd group by (region, product...) -> how we SLICE
  - id        : an identifier (order_id) -> usually not analyzed directly

Then it flags business KPIs and writes a few starter questions.
"""
import re

import pandas as pd
from pandas.api import types as ptypes

# Numeric columns whose names look like these are likely business KPIs.
KPI_HINTS = (
    "revenue", "sales", "profit", "amount", "cost", "price", "units",
    "quantity", "qty", "total", "count", "churn", "margin", "spend", "income",
)
# Names that look like identifiers rather than things to measure.
ID_HINTS = ("id", "code", "number", "no", "uuid", "key")
# Names that hint a column is a date even if stored as text.
DATE_HINTS = ("date", "time", "month", "year", "day", "timestamp", "period")


def _looks_like(name: str, hints) -> bool:
    n = name.lower()
    return any(h == n or n.endswith("_" + h) or n.startswith(h + "_") or h in n for h in hints)


def _classify(name: str, series: pd.Series, distinct: int, n_rows: int) -> str:
    # 1) Already a real datetime dtype?
    if ptypes.is_datetime64_any_dtype(series):
        return "datetime"

    is_num = ptypes.is_numeric_dtype(series) and not ptypes.is_bool_dtype(series)

    # 2) A date-named, non-numeric column whose text actually parses as dates.
    if not is_num and _looks_like(name, DATE_HINTS):
        try:
            parsed = pd.to_datetime(series.dropna().head(50), errors="coerce")
            if len(parsed) and parsed.notna().mean() > 0.8:
                return "datetime"
        except Exception:
            pass

    # 3) Numbers: an id if the name says so AND values are mostly unique; else a measure.
    if is_num:
        nearly_unique = n_rows > 0 and distinct / n_rows > 0.9
        if _looks_like(name, ID_HINTS) and nearly_unique:
            return "id"
        return "measure"

    # 4) Everything else (text, boolean) is a category to group by.
    if _looks_like(name, ID_HINTS) and n_rows > 0 and distinct / n_rows > 0.9:
        return "id"
    return "dimension"


def _samples(series: pd.Series, k: int = 5):
    vals = series.dropna().unique()[:k]
    out = []
    for v in vals:
        # make everything JSON-friendly (dates/numpy types -> plain python)
        if hasattr(v, "item"):
            v = v.item()
        out.append(str(v) if not isinstance(v, (int, float, bool, str)) else v)
    return out


def profile_dataframe(df: pd.DataFrame) -> dict:
    """Return {'columns': [...], 'suggested_questions': [...]}"""
    n = len(df)
    columns = []
    for col in df.columns:
        s = df[col]
        distinct = int(s.nunique(dropna=True))
        role = _classify(col, s, distinct, n)
        is_kpi = role == "measure" and _looks_like(col, KPI_HINTS)
        columns.append({
            "column_name": col,
            "data_type": str(s.dtype),
            "semantic_role": role,
            "null_pct": round(float(s.isna().mean() * 100), 2) if n else 0.0,
            "distinct_count": distinct,
            "is_kpi": is_kpi,
            "sample_values": _samples(s),
        })

    questions = _suggest_questions(columns)
    return {"columns": columns, "suggested_questions": questions}


def _suggest_questions(columns: list[dict]) -> list[str]:
    measures = [c["column_name"] for c in columns if c["semantic_role"] == "measure"]
    dims = [c["column_name"] for c in columns if c["semantic_role"] == "dimension"]
    dates = [c["column_name"] for c in columns if c["semantic_role"] == "datetime"]
    kpis = [c["column_name"] for c in columns if c["is_kpi"]] or measures

    q = []
    m = kpis[0] if kpis else None
    d = dims[0] if dims else None
    dt = dates[0] if dates else None

    if m and d:
        q.append(f"What is the total {m} by {d}?")
        q.append(f"Which {d} has the highest {m}?")
    if m and dt:
        q.append(f"Show the trend of {m} over {dt}.")
    if m and d:
        q.append(f"What are the top 5 {d} by {m}?")
    if m:
        q.append(f"What is the average {m}?")
    if len(dims) >= 2 and m:
        q.append(f"Compare {m} across {dims[0]} and {dims[1]}.")

    # de-duplicate, keep order, cap at 5
    seen, out = set(), []
    for item in q:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out[:5]
