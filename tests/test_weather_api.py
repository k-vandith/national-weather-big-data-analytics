from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx
import pytest

from src import api as api_module
from src.api import app


def request(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    *,
    content: bytes | str | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, json=payload, content=content, headers=headers)

    return asyncio.run(send())


CSV_WITH_BAD_ROWS = (
    "station_id,datetime,temperature_c,rainfall_mm,humidity_pct\n"
    "STN-A,2025-01-01T00:00:00Z,20,1,50\n"
    "STN-A,2025-01-01T00:00:00Z,21,2,55\n"
    "STN-B,2025-01-01T01:00:00Z,18,0,70\n"
    "STN-C,not-a-date,22,0,60\n"
    "STN-D,2025-01-01T03:00:00Z,95,0,40\n"
).encode("utf-8")


def test_html_css_and_javascript_are_served_without_streamlit() -> None:
    html_response = request("GET", "/")
    css_response = request("GET", "/styles.css")
    js_response = request("GET", "/app.js")
    assert html_response.status_code == 200
    assert 'id="csv-file"' in html_response.text
    assert 'href="/styles.css"' in html_response.text
    assert css_response.status_code == 200
    assert "--accent: #79e3d3" in css_response.text
    assert js_response.status_code == 200
    assert "async function analyzeCSV()" in js_response.text
    assert "exportReport" in js_response.text


def test_health_sample_and_template_endpoints() -> None:
    health = request("GET", "/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    sample = request("GET", "/api/sample?rows=12")
    assert sample.status_code == 200
    assert sample.json()["count"] == 12
    assert sample.json()["summary"]["station_count"] == 3
    assert len(sample.json()["observations"]) == 12

    template = request("GET", "/api/template.csv?rows=8")
    assert template.status_code == 200
    assert "text/csv" in template.headers["content-type"]
    assert "station" in template.text and "temp_c" in template.text

    invalid = request("GET", "/api/sample?rows=0")
    assert invalid.status_code == 422


def test_csv_analysis_cleans_aliases_bad_rows_and_duplicate_timestamps() -> None:
    response = request(
        "POST",
        "/api/analyze/csv",
        content=CSV_WITH_BAD_ROWS,
        headers={"Content-Type": "text/csv"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "uploaded-csv"
    assert payload["rows_read"] == 5
    assert payload["rows_removed"] == 3
    assert payload["count"] == 2
    rows = payload["observations"]
    assert {row["station"] for row in rows} == {"STN-A", "STN-B"}
    station_a = next(row for row in rows if row["station"] == "STN-A")
    assert station_a["temp_c"] == 21
    assert station_a["precip_mm"] == 2


def test_csv_analysis_returns_clear_validation_errors() -> None:
    empty = request("POST", "/api/analyze/csv", content=b"", headers={"Content-Type": "text/csv"})
    assert empty.status_code == 422
    missing_fields = request(
        "POST",
        "/api/analyze/csv",
        content=b"station,humidity\nSTN-A,50\n",
        headers={"Content-Type": "text/csv"},
    )
    assert missing_fields.status_code == 422
    assert "Missing required" in missing_fields.json()["detail"]


def test_ingest_is_idempotent_and_stored_archive_is_exportable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(api_module, "DB_PATH", tmp_path / "weather.db")
    csv = (
        "station,ts,temp_c,precip_mm\n"
        "STN-A,2025-01-01T00:00:00Z,20,1.5\n"
        "STN-A,2025-01-01T01:00:00Z,21,0\n"
        "STN-B,2025-01-01T00:00:00Z,16,2\n"
    ).encode("utf-8")
    first = request("POST", "/api/ingest/csv", content=csv, headers={"Content-Type": "text/csv"})
    second = request("POST", "/api/ingest/csv", content=csv, headers={"Content-Type": "text/csv"})
    assert first.status_code == second.status_code == 200
    assert first.json()["rows_upserted"] == 3
    assert second.json()["database_rows"] == 3
    summary = request("GET", "/api/stored/summary")
    assert summary.status_code == 200
    assert summary.json()["row_count"] == 3
    assert summary.json()["station_count"] == 2
    exported = request("GET", "/api/stored.csv")
    assert exported.status_code == 200
    assert "text/csv" in exported.headers["content-type"]
    assert exported.text.count("STN-A") == 2


def test_compatibility_api_routes() -> None:
    health = request("GET", "/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    summary = request("GET", "/climatology/demo")
    assert summary.status_code == 200
    assert summary.json()["count"] == 365

    response = request(
        "POST",
        "/analytics/summary",
        {
            "observations": [
                {"station": "STN-A", "ts": "2025-01-01T00:00:00Z", "temp_c": 18.0, "precip_mm": 1.2},
                {"station": "STN-A", "ts": "2025-01-01T01:00:00Z", "temp_c": 20.0, "precip_mm": 0.0},
                {"station": "STN-B", "ts": "2025-01-01T00:00:00Z", "temp_c": 16.0, "precip_mm": 2.0},
            ]
        },
    )
    assert response.status_code == 200
    assert response.json()["observations"] == 3
    assert response.json()["station_count"] == 2

    assert request("POST", "/analytics/summary", {"observations": []}).status_code == 422
