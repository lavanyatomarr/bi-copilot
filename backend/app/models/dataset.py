from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from ..db import Base


class UploadedDataset(Base):
    __tablename__ = "uploaded_datasets"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    schema_name = Column(String, nullable=False)        # e.g. "data_1"
    table_name = Column(String, nullable=False)          # e.g. "sales"
    row_count = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False, default="processing")  # processing|ready|failed
    suggested_questions = Column(JSONB, nullable=True)   # ["What is ...", ...]
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DatasetMetadata(Base):
    __tablename__ = "dataset_metadata"

    id = Column(Integer, primary_key=True)
    dataset_id = Column(Integer, ForeignKey("uploaded_datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    column_name = Column(String, nullable=False)
    data_type = Column(String, nullable=False)           # e.g. "int64", "object", "datetime64[ns]"
    semantic_role = Column(String, nullable=False)        # dimension|measure|datetime|id
    null_pct = Column(Float, nullable=False, default=0.0)
    distinct_count = Column(Integer, nullable=True)
    is_kpi = Column(Boolean, nullable=False, default=False)
    sample_values = Column(JSONB, nullable=True)
