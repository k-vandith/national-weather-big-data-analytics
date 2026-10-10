"""Local-first API and static frontend for national weather analytics."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import HTTPException, Query, Request
from fastapi.responses import FileResponse, Response

from src.weather import (
    MAX_UPLOAD_BYTES,
    aggregate,
    anomalies,
    generate_sample,
    ingest,
    load_weather_csv,
    normalize_observations,
    summarize_observations,
)
from src.weather_features import create_fastapi_app

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
DB_PATH = ROOT / "data" / "weather.db"

app = create_fastapi_app()


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert pandas/numpy values to strict JSON-safe Python values."""
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def _package_observations(
    frame: pd.DataFrame,
    *,
    source: str,
    rows_read: int | None = None,
) -> dict[str, Any]:
    clean = normalize_observations(frame)
    if clean.empty:
        raise HTTPException(status_code=422, detail="No valid observations remain after cleaning")
    read_count = int(len(clean) if rows_read is None else rows_read)
    return {
        "ok": True,
        "source": source,
        "rows_read": read_count,
        "rows_removed": max(0, read_count - len(clean)),
        "count": int(len(clean)),
        "summary": summarize_observations(clean),
        "observations": _records(clean),
    }


async def _read_csv_request(request: Request) -> tuple[pd.DataFrame, int]:
    """Read a raw CSV body while enforcing the upload limit before parsing."""
    size = 0
    chunks: list[bytes] = []
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="CSV upload must be 10 MB or smaller")
        chunks.append(chunk)
    body = b"".join(chunks)
    if not body.strip():
        raise HTTPException(status_code=422, detail="Upload a non-empty CSV file")
    try:
        raw = load_weather_csv(body)
        return normalize_observations(raw), int(len(raw))
    except (ValueError, TypeError, UnicodeDecodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB / "index.html", media_type="text/html")


@app.get("/styles.css", include_in_schema=False)
def styles() -> FileResponse:
    return FileResponse(WEB / "styles.css", media_type="text/css")


@app.get("/app.js", include_in_schema=False)
def javascript() -> FileResponse:
    return FileResponse(WEB / "app.js", media_type="text/javascript")


@app.get("/api/health")
def api_health() -> dict[str, str]:
    return {"status": "ok", "service": "national-weather-analytics"}


@app.get("/api/sample")
def api_sample(rows: int = Query(default=1200, ge=1, le=5000)) -> dict[str, Any]:
    frame = generate_sample(n=rows, seed=3)
    return _package_observations(frame, source="synthetic-network", rows_read=len(frame))


@app.post("/api/analyze/csv")
async def api_analyze_csv(request: Request) -> dict[str, Any]:
    frame, rows_read = await _read_csv_request(request)
    return _package_observations(frame, source="uploaded-csv", rows_read=rows_read)


@app.post("/api/ingest/csv")
async def api_ingest_csv(request: Request) -> dict[str, Any]:
    frame, rows_read = await _read_csv_request(request)
    # Use a deterministic project-local database path; client input never selects a filesystem path.
    processed = ingest(frame, DB_PATH)
    stored = aggregate(DB_PATH)
    return {
        "ok": True,
        "source": "uploaded-csv",
        "rows_read": rows_read,
        "rows_removed": max(0, rows_read - len(frame)),
        "rows_upserted": processed,
        "database_rows": int(stored["n"].sum()) if not stored.empty else 0,
        "database_stations": int(stored["station"].nunique()) if not stored.empty else 0,
    }


@app.get("/api/stored/summary")
def api_stored_summary() -> dict[str, Any]:
    station_rollup = aggregate(DB_PATH)
    anomaly_rows = anomalies(DB_PATH, z=3.0)
    with sqlite3.connect(DB_PATH) as connection:
        row_count = int(connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0])
    return {
        "ok": True,
        "row_count": row_count,
        "station_count": int(station_rollup["station"].nunique()) if not station_rollup.empty else 0,
        "anomaly_count": int(len(anomaly_rows)),
        "stations": _records(station_rollup),
    }


@app.get("/api/stored.csv")
def api_stored_csv() -> Response:
    # aggregate() ensures that an empty but valid database/schema exists.
    aggregate(DB_PATH)
    with sqlite3.connect(DB_PATH) as connection:
        frame = pd.read_sql_query(
            "SELECT station, ts, temp_c, humidity, pressure_hpa, wind_ms, precip_mm "
            "FROM observations ORDER BY ts, station",
            connection,
        )
    return Response(
        content=frame.to_csv(index=False),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="weather-database.csv"'},
    )


# Compatibility routes retained for scripts and API consumers from the previous release.
# The local browser frontend uses the /api/* routes above.
