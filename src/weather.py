"""National weather observation ingestion and SQLite analytics helpers."""
from __future__ import annotations

from contextlib import closing
from io import BytesIO, StringIO
from pathlib import Path
import re
import sqlite3
from typing import Any

import numpy as np
import pandas as pd


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_UPLOAD_ROWS = 100_000

SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
  id INTEGER PRIMARY KEY,
  station TEXT NOT NULL,
  ts TEXT NOT NULL,
  temp_c REAL NOT NULL,
  humidity REAL,
  pressure_hpa REAL,
  wind_ms REAL,
  precip_mm REAL
);
"""

ALIASES = {
    "station": {"station", "station_id", "site_id", "station_code", "site"},
    "ts": {"ts", "timestamp", "date", "datetime", "time", "observation_time", "valid_time"},
    "temp_c": {"temp_c", "temperature_c", "temperature", "air_temp_c", "temperature_2m"},
    "humidity": {"humidity", "humidity_pct", "relative_humidity", "relative_humidity_pct"},
    "pressure_hpa": {"pressure_hpa", "pressure", "station_pressure_hpa", "sea_level_pressure_hpa"},
    "wind_ms": {"wind_ms", "wind_speed", "wind_speed_ms", "wind_speed_m_s"},
    "precip_mm": {"precip_mm", "precipitation_mm", "rainfall_mm", "precipitation", "rain_mm"},
}
ALIASES_TO_CANONICAL = {
    alias: canonical for canonical, names in ALIASES.items() for alias in names
}
CANONICAL_COLUMNS = ["station", "ts", "temp_c", "humidity", "pressure_hpa", "wind_ms", "precip_mm"]


def generate_sample(n: int = 500, seed: int = 42) -> pd.DataFrame:
    """Generate deterministic synthetic hourly observations for three stations."""
    if isinstance(n, bool) or not isinstance(n, (int, np.integer)) or not 1 <= int(n) <= 1_000_000:
        raise ValueError("n must be an integer between 1 and 1000000")

    rng = np.random.default_rng(seed)
    stations = ("STN-A", "STN-B", "STN-C")
    base = pd.Timestamp("2025-01-01T00:00:00Z")
    times = [base + pd.Timedelta(hours=i) for i in range(int(n))]
    idx = np.arange(int(n))
    frame = pd.DataFrame({
        "station": [stations[i % len(stations)] for i in idx],
        "ts": [ts.strftime("%Y-%m-%dT%H:%M:%SZ") for ts in times],
        "temp_c": np.round(15 + 10 * np.sin(idx / 24) + rng.normal(0, 1.5, size=int(n)), 2),
        "humidity": np.round(np.clip(60 + rng.normal(0, 10, size=int(n)), 10, 100), 1),
        "pressure_hpa": np.round(1013 + rng.normal(0, 5, size=int(n)), 1),
        "wind_ms": np.round(np.abs(rng.normal(3, 2, size=int(n))), 2),
        "precip_mm": np.round(np.where(rng.random(int(n)) > 0.7, rng.exponential(0.5, size=int(n)), 0), 2),
    })
    return frame


def load_weather_csv(upload: bytes | bytearray | Any) -> pd.DataFrame:
    """Read a CSV after enforcing byte and row limits for bytes and file-like inputs."""
    if isinstance(upload, (bytes, bytearray)):
        raw: bytes | str = bytes(upload)
    elif hasattr(upload, "read"):
        tell = getattr(upload, "tell", None)
        seek = getattr(upload, "seek", None)
        position = None
        if callable(tell) and callable(seek):
            try:
                position = tell()
            except (OSError, ValueError):
                position = None
        try:
            raw = upload.read(MAX_UPLOAD_BYTES + 1)
        finally:
            if position is not None:
                try:
                    seek(position)
                except (OSError, ValueError):
                    pass
        if not isinstance(raw, (str, bytes, bytearray)):
            raise TypeError("file-like upload must return CSV bytes or text")
    else:
        raise TypeError("upload must be CSV bytes or a file-like object")

    byte_count = len(raw.encode("utf-8")) if isinstance(raw, str) else len(raw)
    if byte_count > MAX_UPLOAD_BYTES:
        raise ValueError("CSV upload must be 10 MB or smaller")
    if not raw.strip():
        raise ValueError("CSV contains no observations")
    source = StringIO(raw) if isinstance(raw, str) else BytesIO(bytes(raw))
    try:
        frame = pd.read_csv(source, nrows=MAX_UPLOAD_ROWS + 1)
    except pd.errors.EmptyDataError as error:
        raise ValueError("CSV contains no observations") from error
    if frame.empty:
        raise ValueError("CSV contains no observations")
    if len(frame) > MAX_UPLOAD_ROWS:
        raise ValueError("CSV must contain 100000 rows or fewer")
    return frame


def normalize_observations(df: pd.DataFrame) -> pd.DataFrame:
    """Map common station-CSV aliases to the canonical schema and clean bad rows.

    Required values are station, timestamp, and plausible Celsius temperature.
    Invalid optional measurements become missing values instead of discarding an
    otherwise usable observation. Duplicate station/timestamp pairs keep the last row.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("observations must be a pandas DataFrame")
    if df.empty:
        return pd.DataFrame(columns=CANONICAL_COLUMNS)
    if len(df) > MAX_UPLOAD_ROWS:
        raise ValueError("Input must contain 100000 rows or fewer")

    df = df.reset_index(drop=True)
    mapped: dict[str, pd.Series] = {}
    for column in df.columns:
        key = re.sub(r"[^a-z0-9]+", "_", str(column).strip().casefold()).strip("_")
        canonical = ALIASES_TO_CANONICAL.get(key)
        if canonical is None:
            continue
        if canonical in mapped:
            raise ValueError(f"CSV contains multiple columns for {canonical}")
        mapped[canonical] = df[column]

    missing = [field for field in ("station", "ts", "temp_c") if field not in mapped]
    if missing:
        raise ValueError(f"Missing required weather fields: {', '.join(missing)}")

    clean = pd.DataFrame(index=df.index)
    clean["station"] = mapped["station"].astype("string").str.strip()
    clean["station"] = clean["station"].replace("", pd.NA)
    timestamps = pd.to_datetime(mapped["ts"], errors="coerce", utc=True, format="mixed")
    clean["ts"] = timestamps.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    clean["temp_c"] = pd.to_numeric(mapped["temp_c"], errors="coerce")

    valid = (
        clean["station"].notna()
        & clean["ts"].notna()
        & np.isfinite(clean["temp_c"].to_numpy(dtype=float, na_value=np.nan))
        & clean["temp_c"].between(-90, 60, inclusive="both")
    )
    clean = clean.loc[valid].copy()

    ranges = {
        "humidity": (0, 100),
        "pressure_hpa": (500, 1200),
        "wind_ms": (0, 150),
        "precip_mm": (0, 2000),
    }
    for column, (lower, upper) in ranges.items():
        if column not in mapped:
            clean[column] = np.nan
        else:
            values = pd.to_numeric(mapped[column], errors="coerce").reindex(clean.index)
            clean[column] = values.where(values.between(lower, upper, inclusive="both"))

    clean = clean[CANONICAL_COLUMNS]
    clean = clean.drop_duplicates(subset=["station", "ts"], keep="last")
    return clean.reset_index(drop=True)


def _open_db(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(path))


def init_db(db_path: str | Path) -> None:
    """Create the observations schema and a unique station/time index."""
    with closing(_open_db(db_path)) as conn:
        with conn:
            conn.executescript(SCHEMA)
            # Keep the latest copy if an older database already contains duplicates.
            conn.execute(
                """DELETE FROM observations
                   WHERE id NOT IN (
                     SELECT MAX(id) FROM observations GROUP BY station, ts
                   )"""
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_observations_station_ts "
                "ON observations(station, ts)"
            )


def ingest(df: pd.DataFrame, db_path: str | Path) -> int:
    """Clean and idempotently upsert station observations into SQLite."""
    clean = normalize_observations(df)
    init_db(db_path)
    if clean.empty:
        return 0

    values = list(clean[CANONICAL_COLUMNS].itertuples(index=False, name=None))
    statement = """
        INSERT INTO observations (station, ts, temp_c, humidity, pressure_hpa, wind_ms, precip_mm)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(station, ts) DO UPDATE SET
          temp_c=excluded.temp_c,
          humidity=excluded.humidity,
          pressure_hpa=excluded.pressure_hpa,
          wind_ms=excluded.wind_ms,
          precip_mm=excluded.precip_mm
    """
    with closing(_open_db(db_path)) as conn:
        with conn:
            conn.executemany(statement, values)
    return len(clean)


def aggregate(db_path: str | Path) -> pd.DataFrame:
    """Return per-station temperature, precipitation, and record-count summaries."""
    init_db(db_path)
    query = """
        SELECT station,
               AVG(temp_c) AS avg_temp,
               COALESCE(SUM(precip_mm), 0.0) AS total_precip,
               COUNT(*) AS n
        FROM observations
        GROUP BY station
        ORDER BY station
    """
    with closing(_open_db(db_path)) as conn:
        return pd.read_sql_query(query, conn)


def _temperature_anomalies(df: pd.DataFrame, z: float = 3.0) -> pd.DataFrame:
    if not np.isfinite(float(z)) or float(z) <= 0:
        raise ValueError("z must be a positive finite number")
    columns = ["station", "ts", "temp_c", "zscore"]
    if df.empty:
        return pd.DataFrame(columns=columns)

    temp = pd.to_numeric(df["temp_c"], errors="coerce")
    temp = temp[np.isfinite(temp.to_numpy(dtype=float, na_value=np.nan))]
    if temp.empty:
        return pd.DataFrame(columns=columns)
    sigma = float(temp.std(ddof=0))
    if not np.isfinite(sigma) or sigma <= 1e-12:
        return pd.DataFrame(columns=columns)

    zscores = (pd.to_numeric(df["temp_c"], errors="coerce") - float(temp.mean())) / sigma
    mask = zscores.abs() >= float(z)
    result = df.loc[mask, ["station", "ts", "temp_c"]].copy()
    result["zscore"] = zscores.loc[mask].astype(float)
    return result[columns].reset_index(drop=True)


def anomalies(db_path: str | Path, z: float = 3.0) -> pd.DataFrame:
    """Find global temperature z-score outliers from the stored observations."""
    init_db(db_path)
    with closing(_open_db(db_path)) as conn:
        frame = pd.read_sql_query(
            "SELECT station, ts, temp_c FROM observations ORDER BY ts, station",
            conn,
        )
    return _temperature_anomalies(frame, z=z)


def summarize_observations(df: pd.DataFrame) -> dict[str, Any]:
    """Build JSON-safe climatology and per-station summaries for cleaned observations."""
    clean = normalize_observations(df)
    if clean.empty:
        raise ValueError("No valid weather observations remain after cleaning")

    temp = clean["temp_c"].astype(float)
    station_rollup = (
        clean.groupby("station", as_index=False)
        .agg(
            observations=("temp_c", "size"),
            mean_temp_c=("temp_c", "mean"),
            min_temp_c=("temp_c", "min"),
            max_temp_c=("temp_c", "max"),
            total_precip_mm=("precip_mm", "sum"),
        )
        .sort_values("station")
    )
    station_records: list[dict[str, Any]] = []
    for record in station_rollup.to_dict("records"):
        station_records.append({
            key: (None if pd.isna(value) else (float(value) if isinstance(value, (np.floating, float)) else int(value) if isinstance(value, (np.integer, int)) else value))
            for key, value in record.items()
        })

    sigma = float(temp.std(ddof=1)) if len(temp) > 1 else 0.0
    precip_total = clean["precip_mm"].sum(min_count=1)
    return {
        "observations": int(len(clean)),
        "station_count": int(clean["station"].nunique()),
        "period_start": str(clean["ts"].min()),
        "period_end": str(clean["ts"].max()),
        "temperature_c": {
            "mean": float(temp.mean()),
            "std": sigma if np.isfinite(sigma) else 0.0,
            "min": float(temp.min()),
            "max": float(temp.max()),
            "p95": float(temp.quantile(0.95)),
        },
        "total_precip_mm": None if pd.isna(precip_total) else float(precip_total),
        "anomaly_count": int(len(_temperature_anomalies(clean, z=3.0))),
        "by_station": station_records,
    }


def run_pipeline(csv_path: str | Path, db_path: str | Path | None = None) -> dict[str, Any]:
    """Read, clean, summarize, and optionally persist a station CSV batch."""
    source = Path(csv_path)
    if not source.is_file():
        raise FileNotFoundError(f"Weather CSV not found: {source}")
    raw = pd.read_csv(source)
    if len(raw) > MAX_UPLOAD_ROWS:
        raise ValueError("CSV must contain 100000 rows or fewer")
    clean = normalize_observations(raw)
    summary = summarize_observations(clean)
    summary["source_file"] = source.name
    summary["rows_read"] = int(len(raw))
    summary["rows_removed"] = int(len(raw) - len(clean))
    if db_path is not None:
        summary["rows_upserted"] = int(ingest(clean, db_path))
    return summary
