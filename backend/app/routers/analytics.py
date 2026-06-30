from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_current_user
from ..db import get_db
from ..models.dataset import DatasetMetadata, UploadedDataset
from ..models.user import User
from ..schemas.analytics import AnomalyIn, ForecastIn
from ..services import analytics_engine

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _owned(db: Session, user: User, dataset_id: int) -> UploadedDataset:
    ds = (
        db.query(UploadedDataset)
        .filter(UploadedDataset.id == dataset_id, UploadedDataset.user_id == user.id)
        .first()
    )
    if not ds:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")
    return ds


def _has_column(db: Session, dataset_id: int, column: str) -> bool:
    return (
        db.query(DatasetMetadata)
        .filter(DatasetMetadata.dataset_id == dataset_id, DatasetMetadata.column_name == column)
        .first()
        is not None
    )


@router.post("/anomalies")
def anomalies(body: AnomalyIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ds = _owned(db, user, body.dataset_id)
    if not _has_column(db, ds.id, body.column):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown column '{body.column}'")
    return analytics_engine.detect_anomalies(ds.schema_name, ds.table_name, body.column)


@router.post("/forecast")
def forecast(body: ForecastIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ds = _owned(db, user, body.dataset_id)
    for col in (body.date_column, body.value_column):
        if not _has_column(db, ds.id, col):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown column '{col}'")
    return analytics_engine.forecast(ds.schema_name, ds.table_name,
                                     body.date_column, body.value_column, body.periods)


@router.get("/kpis/{dataset_id}")
def kpis(dataset_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ds = _owned(db, user, dataset_id)
    kpi_cols = (
        db.query(DatasetMetadata)
        .filter(DatasetMetadata.dataset_id == ds.id, DatasetMetadata.is_kpi == True)  # noqa: E712
        .all()
    )
    out = []
    for c in kpi_cols:
        t = analytics_engine.trend(ds.schema_name, ds.table_name, c.column_name)
        out.append({"column": c.column_name, "trend": t})
    return {"dataset_id": ds.id, "kpis": out}
