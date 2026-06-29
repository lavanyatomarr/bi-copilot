from datetime import datetime

from pydantic import BaseModel


class DatasetOut(BaseModel):
    id: int
    name: str
    original_filename: str
    row_count: int
    status: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ColumnProfile(BaseModel):
    column_name: str
    data_type: str
    semantic_role: str
    null_pct: float
    distinct_count: int | None = None
    is_kpi: bool
    sample_values: list | None = None

    model_config = {"from_attributes": True}


class DatasetProfile(BaseModel):
    dataset: DatasetOut
    columns: list[ColumnProfile]
    suggested_questions: list[str]
