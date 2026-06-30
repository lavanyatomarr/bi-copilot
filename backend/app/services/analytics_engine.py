"""Statistical analytics on a dataset's data -- no LLM, pure math.

  - anomalies : z-score (small data) or IsolationForest (richer data)
  - forecast  : Holt-Winters exponential smoothing (level + trend + seasonality)
  - trend     : linear-regression slope + significance test
"""
import numpy as np
import pandas as pd
from sqlalchemy import text

from ..db import engine


def _load_column(schema: str, table: str, column: str) -> pd.Series:
    fq = f'"{schema}"."{table}"'
    with engine.connect() as conn:
        rows = conn.execute(text(f'SELECT "{column}" FROM {fq}')).fetchall()
    return pd.Series([r[0] for r in rows], name=column)


def _load_series(schema: str, table: str, date_col: str, value_col: str) -> pd.Series:
    fq = f'"{schema}"."{table}"'
    with engine.connect() as conn:
        rows = conn.execute(
            text(f'SELECT "{date_col}", "{value_col}" FROM {fq}')
        ).fetchall()
    df = pd.DataFrame(rows, columns=["d", "v"])
    df["d"] = pd.to_datetime(df["d"], errors="coerce")
    df["v"] = pd.to_numeric(df["v"], errors="coerce")
    df = df.dropna().sort_values("d")
    return df.set_index("d")["v"]


def detect_anomalies(schema: str, table: str, column: str) -> dict:
    s = pd.to_numeric(_load_column(schema, table, column), errors="coerce").dropna()
    if len(s) < 5:
        return {"method": None, "anomalies": [], "message": "Not enough numeric data."}

    s = s.reset_index(drop=True)
    if len(s) < 20:
        # Z-SCORE: |value - mean| / std  > 3
        mean, std = s.mean(), s.std() or 1.0
        z = (s - mean) / std
        idx = s.index[z.abs() > 3]
        method = "z-score"
    else:
        # ISOLATION FOREST: outliers isolate in fewer random splits
        from sklearn.ensemble import IsolationForest
        model = IsolationForest(contamination=0.05, random_state=42)
        preds = model.fit_predict(s.values.reshape(-1, 1))
        idx = s.index[preds == -1]
        method = "IsolationForest"

    anomalies = [{"row": int(i), "value": float(s.loc[i])} for i in idx]
    return {
        "method": method,
        "count": len(anomalies),
        "anomalies": anomalies[:50],
        "column_mean": round(float(s.mean()), 2),
        "column_std": round(float(s.std()), 2),
    }


def forecast(schema: str, table: str, date_col: str, value_col: str, periods: int = 6) -> dict:
    s = _load_series(schema, table, date_col, value_col)
    if len(s) < 6:
        return {"message": "Not enough time-series data to forecast.", "forecast": []}

    # aggregate to monthly so the model has a regular frequency
    monthly = s.resample("MS").sum()
    monthly = monthly[monthly.index.notna()]
    if len(monthly) < 4:
        monthly = s.resample("W").sum()

    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    seasonal = len(monthly) >= 24
    try:
        model = ExponentialSmoothing(
            monthly, trend="add",
            seasonal="add" if seasonal else None,
            seasonal_periods=12 if seasonal else None,
        ).fit()
        fc = model.forecast(periods)
    except Exception as e:
        return {"message": f"Could not fit forecast model: {e}", "forecast": []}

    return {
        "method": "Holt-Winters" + (" (seasonal)" if seasonal else " (trend)"),
        "history": [{"date": str(d.date()), "value": float(v)} for d, v in monthly.items()],
        "forecast": [{"date": str(d.date()), "value": round(float(v), 2)} for d, v in fc.items()],
    }


def trend(schema: str, table: str, value_col: str) -> dict:
    from scipy.stats import linregress
    s = pd.to_numeric(_load_column(schema, table, value_col), errors="coerce").dropna().reset_index(drop=True)
    if len(s) < 3:
        return {"message": "Not enough data for a trend."}
    x = np.arange(len(s))
    lr = linregress(x, s.values)
    return {
        "direction": "increasing" if lr.slope > 0 else "decreasing",
        "slope": round(float(lr.slope), 4),
        "r_squared": round(float(lr.rvalue ** 2), 4),
        "significant": bool(lr.pvalue < 0.05),
        "p_value": round(float(lr.pvalue), 5),
    }
