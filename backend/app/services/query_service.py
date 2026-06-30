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
from .llm_adapter import get_llm

SQL_SYSTEM = """You are a careful analytics SQL generator for PostgreSQL.
Generate SQL for exactly ONE read-only SELECT statement.

HARD RULES:
- SELECT only. Never INSERT/UPDATE/DELETE/DROP/ALTER/CREATE.
- Use ONLY the table and columns listed in SCHEMA. Never invent columns.
- Reference the table by its plain name exactly as given.
- If the question cannot be answered from the schema, set "sql" to null and
  explain why in "explanation".

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


def answer_question(db: Session, ds: UploadedDataset, question: str) -> dict:
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
