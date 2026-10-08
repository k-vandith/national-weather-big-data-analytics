"""Weather platform: Parquet, DuckDB/Polars, climatology, FastAPI, benchmarks."""
from __future__ import annotations
import time
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd

def to_parquet(df: pd.DataFrame, path: Path) -> Path:
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_parquet(path, index=False); return path
    except Exception:
        alt = path.with_suffix(".csv"); df.to_csv(alt, index=False); return alt

def climatology_stats(df: pd.DataFrame, value_col: str = "temp_c") -> dict[str, Any]:
    if value_col not in df.columns:
        value_col = df.select_dtypes(include=[np.number]).columns[0]
    s = df[value_col]
    return {"mean": float(s.mean()), "std": float(s.std()), "min": float(s.min()), "max": float(s.max()), "p95": float(s.quantile(0.95))}

def trend_and_anomalies(df: pd.DataFrame, value_col: str = "temp_c") -> pd.DataFrame:
    df = df.copy()
    if value_col not in df.columns:
        value_col = df.select_dtypes(include=[np.number]).columns[0]
    x = np.arange(len(df), dtype=float); y = df[value_col].values.astype(float)
    coef = np.polyfit(x, y, 1) if len(x) > 1 else [0, float(y[0]) if len(y) else 0]
    trend = coef[0]*x + coef[1]; resid = y - trend
    mu, sigma = float(np.mean(resid)), float(np.std(resid)+1e-6)
    df["trend"] = trend; df["anomaly"] = resid; df["is_anomaly"] = np.abs(resid) > 2*sigma
    return df

def benchmark_engines(df: pd.DataFrame, path: Path) -> dict[str, float]:
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    csv_path = path.with_suffix(".csv"); df.to_csv(csv_path, index=False)
    results = {}
    t0 = time.perf_counter(); _ = pd.read_csv(csv_path).groupby(df.columns[0]).mean(numeric_only=True)
    results["pandas_s"] = round(time.perf_counter()-t0, 6)
    try:
        import polars as pl
        t0 = time.perf_counter(); _ = pl.read_csv(csv_path).group_by(df.columns[0]).mean()
        results["polars_s"] = round(time.perf_counter()-t0, 6)
    except Exception as exc:
        results["polars_s"] = -1.0; results["polars_error"] = str(exc)
    try:
        import duckdb
        t0 = time.perf_counter(); duckdb.execute(f"SELECT * FROM read_csv_auto('{csv_path}') LIMIT 100").df()
        results["duckdb_s"] = round(time.perf_counter()-t0, 6)
    except Exception as exc:
        results["duckdb_s"] = -1.0; results["duckdb_error"] = str(exc)
    return results

def create_fastapi_app():
    try:
        from fastapi import FastAPI
    except ImportError:
        class _Stub:
            title = "National Weather Analytics API (stub)"
            def get(self, path):
                def deco(fn): return fn
                return deco
        return _Stub()
    app = FastAPI(title="National Weather Analytics API", version="0.1.0")
    @app.get("/health")
    def health(): return {"status": "ok"}
    @app.get("/climatology/demo")
    def clim_demo():
        rng = np.random.default_rng(0)
        return climatology_stats(pd.DataFrame({"temp_c": rng.normal(25, 5, 365)}))
    return app
