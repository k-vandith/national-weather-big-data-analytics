"""Weather analytics: storage, climatology, trends, engine benchmarks, and API factory."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def to_parquet(df: pd.DataFrame, path: str | Path) -> Path:
    """Write Parquet when an engine is installed, otherwise save a clearly named CSV."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_parquet(target, index=False)
        return target
    except (ImportError, ValueError, ModuleNotFoundError):
        fallback = target.with_suffix(".csv")
        df.to_csv(fallback, index=False)
        return fallback


def _numeric_series(df: pd.DataFrame, value_col: str) -> pd.Series:
    if not isinstance(df, pd.DataFrame) or df.empty:
        raise ValueError("df must contain at least one observation")
    if value_col not in df.columns:
        numeric = df.select_dtypes(include=[np.number]).columns
        if len(numeric) == 0:
            raise ValueError(f"{value_col!r} is missing and no numeric column is available")
        value_col = str(numeric[0])
    values = pd.to_numeric(df[value_col], errors="coerce")
    values = values[np.isfinite(values.to_numpy(dtype=float, na_value=np.nan))]
    if values.empty:
        raise ValueError(f"{value_col!r} has no finite numeric observations")
    return values.astype(float)


def climatology_stats(df: pd.DataFrame, value_col: str = "temp_c") -> dict[str, Any]:
    """Calculate descriptive statistics for a selected numeric observation column."""
    series = _numeric_series(df, value_col)
    standard_deviation = float(series.std(ddof=1)) if len(series) > 1 else 0.0
    if not np.isfinite(standard_deviation):
        standard_deviation = 0.0
    return {
        "count": int(len(series)),
        "mean": float(series.mean()),
        "std": standard_deviation,
        "min": float(series.min()),
        "max": float(series.max()),
        "p95": float(series.quantile(0.95)),
    }


def trend_and_anomalies(
    df: pd.DataFrame,
    value_col: str = "temp_c",
    anomaly_sigma: float = 2.0,
) -> pd.DataFrame:
    """Add a linear trend and flag unusually large deviations from that trend."""
    if not np.isfinite(float(anomaly_sigma)) or float(anomaly_sigma) <= 0:
        raise ValueError("anomaly_sigma must be a positive finite number")
    series = _numeric_series(df, value_col)
    result = df.loc[series.index].copy()
    x = np.arange(len(series), dtype=float)
    y = series.to_numpy(dtype=float)
    coef = np.polyfit(x, y, 1) if len(x) > 1 else np.array([0.0, float(y[0])])
    trend = coef[0] * x + coef[1]
    residual = y - trend
    center = float(np.mean(residual))
    sigma = float(np.std(residual))
    zscores = np.zeros(len(residual), dtype=float) if sigma <= 1e-12 else (residual - center) / sigma
    result["trend"] = trend
    result["anomaly"] = residual
    result["anomaly_zscore"] = zscores
    result["is_anomaly"] = np.abs(zscores) >= float(anomaly_sigma)
    return result


def benchmark_engines(df: pd.DataFrame, path: str | Path) -> dict[str, float | str]:
    """Time a small group-by/read benchmark for pandas and optional engines."""
    if not isinstance(df, pd.DataFrame) or df.empty or len(df.columns) == 0:
        raise ValueError("df must contain rows and columns for benchmarking")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    csv_path = path.with_suffix(".csv")
    df.to_csv(csv_path, index=False)
    group_column = str(df.columns[0])
    results: dict[str, float | str] = {}

    start = time.perf_counter()
    _ = pd.read_csv(csv_path).groupby(group_column).mean(numeric_only=True)
    results["pandas_s"] = round(time.perf_counter() - start, 6)

    try:
        import polars as pl

        start = time.perf_counter()
        _ = pl.read_csv(csv_path).group_by(group_column).mean()
        results["polars_s"] = round(time.perf_counter() - start, 6)
    except (ImportError, Exception) as exc:
        results["polars_s"] = -1.0
        results["polars_error"] = str(exc)[:240]

    try:
        import duckdb

        safe_path = str(csv_path.resolve()).replace("'", "''")
        start = time.perf_counter()
        duckdb.execute(f"SELECT * FROM read_csv_auto('{safe_path}') LIMIT 100").df()
        results["duckdb_s"] = round(time.perf_counter() - start, 6)
    except (ImportError, Exception) as exc:
        results["duckdb_s"] = -1.0
        results["duckdb_error"] = str(exc)[:240]
    return results


def create_fastapi_app():
    """Create the optional API; keep imports local so core analytics work without FastAPI."""
    try:
        from fastapi import FastAPI, HTTPException
    except ImportError:
        class _Stub:
            title = "National Weather Analytics API (FastAPI not installed)"

            def get(self, path):
                def decorator(function):
                    return function
                return decorator

            def post(self, path):
                def decorator(function):
                    return function
                return decorator

        return _Stub()

    app = FastAPI(
        title="National Weather Analytics API",
        description="Small JSON API for demonstration station-weather analytics.",
        version="0.2.0",
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/climatology/demo")
    def clim_demo() -> dict[str, Any]:
        rng = np.random.default_rng(0)
        values = pd.DataFrame({"temp_c": rng.normal(25, 5, 365)})
        return climatology_stats(values)

    @app.post("/analytics/summary")
    def analytics_summary(payload: dict[str, Any]) -> dict[str, Any]:
        rows = payload.get("observations")
        if not isinstance(rows, list) or not rows:
            raise HTTPException(status_code=422, detail="Body must contain a non-empty observations array")
        if len(rows) > 10_000:
            raise HTTPException(status_code=413, detail="At most 10000 observations are accepted per request")
        if not all(isinstance(row, dict) for row in rows):
            raise HTTPException(status_code=422, detail="Each observation must be a JSON object")
        try:
            from src.weather import summarize_observations

            return summarize_observations(pd.DataFrame(rows))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return app
