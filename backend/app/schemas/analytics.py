from pydantic import BaseModel


class AnomalyIn(BaseModel):
    dataset_id: int
    column: str


class ForecastIn(BaseModel):
    dataset_id: int
    date_column: str
    value_column: str
    periods: int = 6
