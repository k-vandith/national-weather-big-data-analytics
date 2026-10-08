"""Weather ingestion, validation, aggregation, anomaly detection, SQLite storage."""
from __future__ import annotations
from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
  id INTEGER PRIMARY KEY,
  station TEXT,
  ts TEXT,
  temp_c REAL,
  humidity REAL,
  pressure_hpa REAL,
  wind_ms REAL,
  precip_mm REAL
);
"""

def generate_sample(n: int = 500, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    stations = ["STN-A", "STN-B", "STN-C"]
    rows = []
    base = pd.Timestamp("2025-01-01")
    for i in range(n):
        st = stations[i % 3]
        rows.append({
            "station": st,
            "ts": (base + pd.Timedelta(hours=i)).isoformat(),
            "temp_c": round(float(15 + 10 * np.sin(i / 24) + rng.normal(0, 1.5)), 2),
            "humidity": round(float(np.clip(60 + rng.normal(0, 10), 10, 100)), 1),
            "pressure_hpa": round(float(1013 + rng.normal(0, 5)), 1),
            "wind_ms": round(float(abs(rng.normal(3, 2))), 2),
            "precip_mm": round(float(max(0, rng.exponential(0.5) if rng.random() > 0.7 else 0)), 2),
        })
    return pd.DataFrame(rows)

def init_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.close()

def ingest(df: pd.DataFrame, db_path: Path) -> int:
    init_db(db_path)
    df = df.dropna(subset=["station", "ts", "temp_c"])
    df = df[(df["temp_c"] > -80) & (df["temp_c"] < 60)]
    conn = sqlite3.connect(db_path)
    df.to_sql("observations", conn, if_exists="append", index=False)
    n = len(df)
    conn.close()
    return n

def aggregate(db_path: Path) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    df = pd.read_sql("SELECT station, AVG(temp_c) as avg_temp, SUM(precip_mm) as total_precip, COUNT(*) as n FROM observations GROUP BY station", conn)
    conn.close()
    return df

def anomalies(db_path: Path, z: float = 3.0) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    df = pd.read_sql("SELECT * FROM observations", conn)
    conn.close()
    if df.empty:
        return df
    mu, sigma = df["temp_c"].mean(), df["temp_c"].std() or 1
    df["zscore"] = (df["temp_c"] - mu) / sigma
    return df[df["zscore"].abs() >= z][["station", "ts", "temp_c", "zscore"]]
