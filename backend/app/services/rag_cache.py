"""Semantic query cache with HYBRID retrieval.

To find a past question similar to the new one, we run TWO searches and fuse them:
  - dense  : vector similarity (meaning)        -> pgvector  embedding <=> query
  - sparse : full-text keyword match (exact)    -> tsvector  fts @@ query
Fused with Reciprocal Rank Fusion (RRF): rank-based, so the two different score
scales never need calibrating. Then we gate the winner on cosine similarity.

Security: we only ever store SQL that already passed the Safety Engine, scoped per
user+dataset, so a cache hit can never serve unvalidated SQL or another user's query.
"""
from sqlalchemy import text
from sqlalchemy.orm import Session

from .embeddings import to_pgvector


def hybrid_lookup(db: Session, user_id: int, dataset_id: int, question: str,
                  embedding: list[float], rrf_k: int = 60) -> dict | None:
    """Return the best matching cached row {id, validated_sql, similarity} or None."""
    vec = to_pgvector(embedding)
    scope = {"u": user_id, "d": dataset_id}

    # DENSE: nearest neighbours by cosine distance (<=>).
    dense = db.execute(text("""
        SELECT id FROM rag_query_cache
        WHERE user_id = :u AND dataset_id = :d AND embedding IS NOT NULL
        ORDER BY embedding <=> CAST(:v AS vector)
        LIMIT 10
    """), {**scope, "v": vec}).mappings().all()

    # SPARSE: full-text keyword matches, ranked.
    sparse = db.execute(text("""
        SELECT id FROM rag_query_cache
        WHERE user_id = :u AND dataset_id = :d
          AND fts @@ plainto_tsquery('english', :q)
        ORDER BY ts_rank(fts, plainto_tsquery('english', :q)) DESC
        LIMIT 10
    """), {**scope, "q": question}).mappings().all()

    # RECIPROCAL RANK FUSION: score = sum over lists of 1/(rrf_k + rank)
    scores: dict[int, float] = {}
    for rank, row in enumerate(dense):
        scores[row["id"]] = scores.get(row["id"], 0.0) + 1.0 / (rrf_k + rank)
    for rank, row in enumerate(sparse):
        scores[row["id"]] = scores.get(row["id"], 0.0) + 1.0 / (rrf_k + rank)

    if not scores:
        return None
    best_id = max(scores, key=scores.get)

    # Gate on actual cosine similarity (1 - cosine distance) before declaring a hit.
    row = db.execute(text("""
        SELECT validated_sql, 1 - (embedding <=> CAST(:v AS vector)) AS similarity
        FROM rag_query_cache WHERE id = :id
    """), {"v": vec, "id": best_id}).mappings().first()
    if not row:
        return None
    return {"id": best_id, "validated_sql": row["validated_sql"],
            "similarity": float(row["similarity"])}


def record_hit(db: Session, cache_id: int) -> None:
    db.execute(text("UPDATE rag_query_cache SET hit_count = hit_count + 1 WHERE id = :id"),
               {"id": cache_id})
    db.commit()


def store(db: Session, user_id: int, dataset_id: int, question: str,
          validated_sql: str, embedding: list[float]) -> None:
    """Store ONLY safety-validated SQL."""
    db.execute(text("""
        INSERT INTO rag_query_cache (user_id, dataset_id, question, validated_sql, embedding)
        VALUES (:u, :d, :q, :sql, CAST(:v AS vector))
    """), {"u": user_id, "d": dataset_id, "q": question,
           "sql": validated_sql, "v": to_pgvector(embedding)})
    db.commit()
