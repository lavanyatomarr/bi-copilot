"""Orchestrates a natural-language question into a safe answer.

Flow:  question + schema  ->  LLM writes SQL  ->  SafetyEngine validates  ->
       execute on a READ-ONLY transaction  ->  rows.
"""
import json

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import settings
from ..db import engine
from ..models.dataset import DatasetMetadata, UploadedDataset
from . import safety_engine
from . import chart_selector, insight_engine
from . import embeddings, rag_cache
from . import analytics_engine
from .llm_adapter import get_llm

SQL_SYSTEM = """You are a careful analytics SQL generator for PostgreSQL.
Generate SQL for exactly ONE read-only SELECT statement.

HARD RULES:
- SELECT only. Never INSERT/UPDATE/DELETE/DROP/ALTER/CREATE.
- Use ONLY the table and columns listed in SCHEMA. Never invent columns.
- Reference the table by its plain name exactly as given.
- If the question cannot be answered from the schema, set "sql" to null and
  explain why in "explanation".

ANSWER-QUALITY RULES (important for good charts and insights):
- For "which/what has the most/least/highest/lowest" questions, ALWAYS return BOTH
  the grouping column AND the aggregated value (e.g. SELECT region, SUM(revenue) AS total).
  Never return just the label by itself.
- For ranking/"top"/"by" questions, return ALL groups ordered appropriately (do NOT
  add LIMIT 1) so the result can be charted -- a safety layer caps the row count.
- Always alias aggregates with a clear name (AS total_revenue, AS customer_count, etc.).
- Count questions use COUNT(*); totals use SUM(); averages use AVG().

Return STRICT JSON only: {"sql": <string or null>, "explanation": <string>}"""


def _schema_description(db: Session, ds: UploadedDataset) -> tuple[str, set[str]]:
    cols = db.query(DatasetMetadata).filter(DatasetMetadata.dataset_id == ds.id).all()
    lines, names = [], set()
    for c in cols:
        names.add(c.column_name)
        lines.append(f"  {c.column_name} ({c.data_type}, {c.semantic_role})")
    desc = f"TABLE {ds.table_name}:\n" + "\n".join(lines)
    return desc, names


def _run_readonly(fq_table: str, sql: str) -> list[dict]:
    """Execute inside a READ ONLY transaction with a statement timeout.

    Even if something slipped past the safety engine, Postgres itself refuses
    any write/DDL in a read-only transaction. Defense in depth.
    """
    # The LLM/safety engine use the plain table name; point it at the real schema.
    runnable = sql.replace(f" {fq_table.split('.')[-1]}", f" {fq_table}")
    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        conn.execute(text(f"SET LOCAL statement_timeout = '{settings.query_timeout_seconds}s'"))
        result = conn.execute(text(runnable))
        rows = [dict(r._mapping) for r in result]
        conn.rollback()
    return rows


def _analytics_intent(question: str) -> str | None:
    q = question.lower()
    if any(w in q for w in ["anomaly", "anomalies", "outlier", "unusual", "abnormal"]):
        return "anomaly"
    if any(w in q for w in ["forecast", "predict", "projection", "next month", "future", "coming months"]):
        return "forecast"
    return None


def _pick_columns(db: Session, ds: UploadedDataset, question: str):
    """Find the measure/date columns a question refers to (by name, else first KPI/date)."""
    cols = db.query(DatasetMetadata).filter(DatasetMetadata.dataset_id == ds.id).all()
    q = question.lower()
    measures = [c.column_name for c in cols if c.semantic_role == "measure"]
    dates = [c.column_name for c in cols if c.semantic_role == "datetime"]
    kpis = [c.column_name for c in cols if c.is_kpi] or measures
    mentioned_measure = next((m for m in measures if m.lower() in q), None)
    value_col = mentioned_measure or (kpis[0] if kpis else None)
    date_col = next((d for d in dates if d.lower() in q), None) or (dates[0] if dates else None)
    return value_col, date_col


def _analytics_answer(db: Session, ds: UploadedDataset, question: str, intent: str) -> dict:
    value_col, date_col = _pick_columns(db, ds, question)
    base = {"sql": None, "explanation": "", "rows": [], "row_count": 0, "blocked": False,
            "chart_type": "table", "chart_spec": {"type": "table", "data": [], "layout": {}},
            "confidence": 0.0, "follow_ups": [], "from_cache": False, "cache_similarity": None}

    if intent == "anomaly":
        if not value_col:
            return {**base, "insight": "No numeric column found to check for anomalies."}
        res = analytics_engine.detect_anomalies(ds.schema_name, ds.table_name, value_col)
        rows = res.get("anomalies", [])
        return {**base, "rows": rows, "row_count": len(rows),
                "explanation": f"Anomaly detection on '{value_col}' using {res.get('method')}.",
                "insight": f"Found {res.get('count', 0)} anomalies in '{value_col}' "
                           f"(method: {res.get('method')}). Column mean ~{res.get('column_mean')}.",
                "confidence": 0.8}

    # forecast
    if not (value_col and date_col):
        return {**base, "insight": "Need a date column and a numeric column to forecast."}
    res = analytics_engine.forecast(ds.schema_name, ds.table_name, date_col, value_col)
    fc = res.get("forecast", [])
    spec = chart_selector.build_spec("line", res.get("history", []) + fc) if fc else base["chart_spec"]
    return {**base, "rows": fc, "row_count": len(fc), "chart_type": "line", "chart_spec": spec,
            "explanation": f"Forecast of '{value_col}' over '{date_col}' ({res.get('method', '')}).",
            "insight": res.get("message") or f"Forecasted the next {len(fc)} periods of '{value_col}'.",
            "confidence": 0.7}


def answer_question(db: Session, ds: UploadedDataset, question: str) -> dict:
    # If the question is asking for anomalies/forecast, route to the analytics engine.
    intent = _analytics_intent(question)
    if intent:
        return _analytics_answer(db, ds, question, intent)

    schema_desc, allowed_cols = _schema_description(db, ds)

    # 0) HYBRID RAG CACHE: embed the question and look for a near-duplicate past one.
    embedding = embeddings.embed(question)
    if embedding:
        hit = rag_cache.hybrid_lookup(db, ds.user_id, ds.id, question, embedding)
        if hit and hit["similarity"] >= settings.cache_similarity_threshold:
            # CACHE HIT: reuse the already-validated SQL. Skip the LLM entirely (fast path).
            # Still re-validate through the safety engine -- never trust stored SQL blindly.
            safe_sql = safety_engine.validate(
                hit["validated_sql"], ds.table_name, allowed_cols, settings.query_row_limit
            )
            fq_table = f'"{ds.schema_name}".{ds.table_name}'
            rows = _run_readonly(fq_table, safe_sql)
            chart_type = chart_selector.choose_chart(question, rows)
            rag_cache.record_hit(db, hit["id"])
            return {
                "sql": safe_sql,
                "explanation": "Reused validated SQL from a semantically similar earlier question.",
                "rows": rows, "row_count": len(rows), "blocked": False,
                "chart_type": chart_type, "chart_spec": chart_selector.build_spec(chart_type, rows),
                "insight": f"(cache hit) Answered from a similar earlier question.",
                "confidence": round(hit["similarity"], 3), "follow_ups": [],
                "from_cache": True, "cache_similarity": round(hit["similarity"], 3),
            }

    # 1) LLM writes candidate SQL.
    raw = get_llm().complete(
        SQL_SYSTEM,
        f"SCHEMA:\n{schema_desc}\n\nQUESTION: {question}\n\nGenerate SQL.",
    )
    try:
        parsed = json.loads(raw)
        candidate_sql = parsed.get("sql")
        explanation = parsed.get("explanation", "")
    except (json.JSONDecodeError, AttributeError):
        raise ValueError("The model did not return valid JSON.")

    # mock backend uses a {{TABLE}} placeholder
    if candidate_sql:
        candidate_sql = candidate_sql.replace("{{TABLE}}", ds.table_name)

    if not candidate_sql:
        return {"sql": None, "explanation": explanation or "Could not answer from this dataset.",
                "rows": [], "row_count": 0, "blocked": False,
                "chart_type": "table", "chart_spec": {"type": "table", "data": [], "layout": {}},
                "insight": "No query could be generated for this question.",
                "confidence": 0.0, "follow_ups": [],
                "from_cache": False, "cache_similarity": None}

    # 2) Safety engine validates (raises SafetyError if unsafe).
    safe_sql = safety_engine.validate(
        candidate_sql, ds.table_name, allowed_cols, settings.query_row_limit
    )

    # 3) Execute read-only against the dataset's real schema.
    fq_table = f'"{ds.schema_name}".{ds.table_name}'
    rows = _run_readonly(fq_table, safe_sql)

    # 3b) Store the validated SQL in the cache for future near-duplicate questions.
    if embedding:
        try:
            rag_cache.store(db, ds.user_id, ds.id, question, safe_sql, embedding)
        except Exception:
            pass   # caching is best-effort; never fail the query over it

    # 4) Pick a chart (rule-based) and build a Plotly spec.
    chart_type = chart_selector.choose_chart(question, rows)
    chart_spec = chart_selector.build_spec(chart_type, rows)

    # 5) Generate an AI insight + confidence + follow-up questions (one LLM call).
    ins = insight_engine.generate_insight(question, rows)

    return {
        "sql": safe_sql,
        "explanation": explanation,
        "rows": rows,
        "row_count": len(rows),
        "blocked": False,
        "chart_type": chart_type,
        "chart_spec": chart_spec,
        "insight": ins["insight"],
        "confidence": ins["confidence"],
        "follow_ups": ins["follow_ups"],
        "from_cache": False,
        "cache_similarity": None,
    }
