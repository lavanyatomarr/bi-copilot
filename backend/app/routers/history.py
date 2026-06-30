from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_current_user
from ..db import get_db
from ..models.history import QueryHistory
from ..models.user import User

router = APIRouter(prefix="/history", tags=["history"])


@router.get("")
def list_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(QueryHistory)
        .filter(QueryHistory.user_id == user.id)
        .order_by(QueryHistory.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id": r.id,
            "dataset_id": r.dataset_id,
            "dataset_name": r.dataset_name,
            "question": r.question,
            "chart_type": r.chart_type,
            "row_count": r.row_count,
            "from_cache": r.from_cache,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.delete("")
def clear_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    deleted = db.query(QueryHistory).filter(QueryHistory.user_id == user.id).delete()
    db.commit()
    return {"deleted": deleted}
