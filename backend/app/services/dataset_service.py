"""Handles an uploaded file end-to-end:
validate -> read -> sanitize -> store in an isolated schema -> profile.
"""
import io
import re

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import settings
from ..db import engine
from ..models.dataset import DatasetMetadata, UploadedDataset
from . import profiling_engine


class UploadError(Exception):
    """Raised for any bad-file situation; the router turns it into a 400."""


ALLOWED_EXT = {".csv", ".xlsx", ".xls"}


def _sanitize_identifier(name: str, fallback: str = "col") -> str:
    """Make a safe SQL identifier (prevents identifier injection in CREATE TABLE)."""
    s = str(name).strip().lower()
    s = re.sub(r"[^a-z0-9_]", "_", s)   # only letters/digits/underscore survive
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = fallback
    if s[0].isdigit():
        s = "c_" + s
    return s[:60]


def _read_file(file_bytes: bytes, filename: str) -> pd.DataFrame:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXT:
        raise UploadError(f"Unsupported file type '{ext}'. Use CSV or Excel.")

    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > settings.max_upload_mb:
        raise UploadError(f"File too large ({size_mb:.1f} MB). Max is {settings.max_upload_mb} MB.")

    try:
        if ext == ".csv":
            df = pd.read_csv(io.BytesIO(file_bytes))
        else:
            df = pd.read_excel(io.BytesIO(file_bytes))
    except Exception as e:
        raise UploadError(f"Could not parse the file: {e}")

    if df.empty or len(df.columns) == 0:
        raise UploadError("The file has no data.")
    if len(df) > settings.max_rows:
        raise UploadError(f"Too many rows ({len(df)}). Max is {settings.max_rows}.")
    return df


def _coerce_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Convert date-like text columns to real datetimes.

    CSV/Excel load every column as text, so a column like '2024-01-01' becomes a
    string. Postgres date functions (EXTRACT, DATE_TRUNC, ...) then fail because
    the column isn't a real date. Here we detect date-looking columns and convert
    them so they're stored as proper timestamps, and date queries work.
    """
    import re
    date_like = re.compile(r"^\s*\d{4}[-/]\d{1,2}[-/]\d{1,2}")  # 2024-01-01 / 2024/1/1 ...
    for col in df.columns:
        # pandas 2.2 may use a 'str'/'string' dtype instead of 'object' for text
        if not (pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col])):
            continue
        sample = df[col].dropna().astype(str).head(50)
        if sample.empty:
            continue
        # only attempt if most sampled values look like dates (avoids touching
        # numeric/category/id columns)
        if (sample.str.match(date_like).mean()) >= 0.8:
            converted = pd.to_datetime(df[col], errors="coerce")
            if converted.notna().mean() >= 0.8:   # conversion actually worked
                df[col] = converted
    return df


def _sanitize_columns(df: pd.DataFrame) -> pd.DataFrame:
    seen, new_cols = {}, []
    for col in df.columns:
        clean = _sanitize_identifier(col)
        if clean in seen:                 # handle duplicates after cleaning
            seen[clean] += 1
            clean = f"{clean}_{seen[clean]}"
        else:
            seen[clean] = 0
        new_cols.append(clean)
    df.columns = new_cols
    return df


def create_dataset(db: Session, user_id: int, file_bytes: bytes, filename: str) -> UploadedDataset:
    # 1) Read + validate, then clean column names and fix date columns.
    df = _read_file(file_bytes, filename)
    df = _sanitize_columns(df)
    df = _coerce_dates(df)          # store real dates so date functions work

    table_name = _sanitize_identifier(filename.rsplit(".", 1)[0], fallback="dataset")

    # 2) Insert the dataset row FIRST so we get an id to name the schema with.
    ds = UploadedDataset(
        user_id=user_id,
        name=filename,
        original_filename=filename,
        schema_name="pending",
        table_name=table_name,
        status="processing",
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)

    schema_name = f"data_{ds.id}"          # isolated, generated name (never user input)

    try:
        # 3) Create an isolated schema and load the data into it.
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
        df.to_sql(table_name, engine, schema=schema_name,
                  if_exists="replace", index=False, chunksize=5000, method="multi")

        # 4) Profile the data and save per-column metadata.
        profile = profiling_engine.profile_dataframe(df)
        for col in profile["columns"]:
            db.add(DatasetMetadata(dataset_id=ds.id, **col))

        # 5) Mark ready.
        ds.schema_name = schema_name
        ds.row_count = len(df)
        ds.suggested_questions = profile["suggested_questions"]
        ds.status = "ready"
        db.commit()
        db.refresh(ds)
        return ds
    except Exception:
        ds.status = "failed"
        db.commit()
        raise


def delete_dataset(db: Session, ds: UploadedDataset) -> None:
    """Drop the isolated schema, then delete the rows."""
    with engine.begin() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{ds.schema_name}" CASCADE'))
    db.delete(ds)        # cascades to dataset_metadata via FK ondelete
    db.commit()
