from pydantic import BaseModel, Field


class QueryIn(BaseModel):
    dataset_id: int
    question: str = Field(min_length=3, max_length=500)


class QueryOut(BaseModel):
    sql: str | None
    explanation: str
    rows: list[dict]
    row_count: int
    blocked: bool = False
