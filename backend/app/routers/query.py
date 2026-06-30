from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_current_user
from ..db import get_db
from ..models.dataset import UploadedDataset
from ..models.history import QueryHistory
from ..models.user import User
from ..schemas.query import QueryIn, QueryOut
from ..services import query_service, safety_engine

router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=QueryOut)
def run_query(body: QueryIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Ownership check (BOLA/IDOR defense): the dataset must belong to this user.
    ds = (
        db.query(UploadedDataset)
        .filter(UploadedDataset.id == body.dataset_id, UploadedDataset.user_id == user.id)
        .first()
    )
    if not ds:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")
    if ds.status != "ready":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Dataset is not ready")

    try:
        result = query_service.answer_question(db, ds, body.question)
    except safety_engine.SafetyError as e:
        # The query was generated but BLOCKED by the safety engine. This is a
        # successful defense, not a server error -- report it clearly (200).
        return QueryOut(sql=None, explanation=f"Query blocked by safety engine: {e}",
                        rows=[], row_count=0, blocked=True)
    except ValueError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e))

    # Save to history (best-effort; never fail the query if this errors).
    try:
        db.add(QueryHistory(
            user_id=user.id, dataset_id=ds.id, dataset_name=ds.name,
            question=body.question,
            chart_type=result.get("chart_type", "table"),
            row_count=result.get("row_count", 0),
            from_cache=result.get("from_cache", False),
        ))
        db.commit()
    except Exception:
        db.rollback()

    return result
