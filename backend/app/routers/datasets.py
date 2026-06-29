from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ..deps import get_current_user
from ..db import get_db
from ..models.dataset import DatasetMetadata, UploadedDataset
from ..models.user import User
from ..schemas.dataset import ColumnProfile, DatasetOut, DatasetProfile
from ..services import dataset_service

router = APIRouter(prefix="/datasets", tags=["datasets"])


def _get_owned_dataset(db: Session, user: User, dataset_id: int) -> UploadedDataset:
    """Load a dataset that belongs to THIS user, else 404.

    This is the BOLA/IDOR defense: we never trust the id alone; it must be
    scoped to the current user, so user A can't read user B's dataset by id.
    """
    ds = (
        db.query(UploadedDataset)
        .filter(UploadedDataset.id == dataset_id, UploadedDataset.user_id == user.id)
        .first()
    )
    if not ds:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")
    return ds


def _build_profile(db: Session, ds: UploadedDataset) -> DatasetProfile:
    cols = db.query(DatasetMetadata).filter(DatasetMetadata.dataset_id == ds.id).all()
    return DatasetProfile(
        dataset=DatasetOut.model_validate(ds),
        columns=[ColumnProfile.model_validate(c) for c in cols],
        suggested_questions=ds.suggested_questions or [],
    )


@router.post("/upload", response_model=DatasetProfile, status_code=status.HTTP_201_CREATED)
async def upload(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),     # <- reuses Milestone 2's auth guard
    db: Session = Depends(get_db),
):
    contents = await file.read()
    try:
        ds = dataset_service.create_dataset(db, user.id, contents, file.filename)
    except dataset_service.UploadError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return _build_profile(db, ds)


@router.get("", response_model=list[DatasetOut])
def list_datasets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(UploadedDataset)
        .filter(UploadedDataset.user_id == user.id)
        .order_by(UploadedDataset.created_at.desc())
        .all()
    )
    return rows


@router.get("/{dataset_id}/profile", response_model=DatasetProfile)
def get_profile(dataset_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ds = _get_owned_dataset(db, user, dataset_id)
    return _build_profile(db, ds)


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(dataset_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ds = _get_owned_dataset(db, user, dataset_id)
    dataset_service.delete_dataset(db, ds)
