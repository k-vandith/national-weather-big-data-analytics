from __future__ import annotations

import asyncio
from typing import Any

import httpx

from src.api import app


def request(method: str, path: str, payload: dict[str, Any] | None = None) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, json=payload)

    return asyncio.run(send())


def test_health_and_climatology_api() -> None:
    health = request("GET", "/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    summary = request("GET", "/climatology/demo")
    assert summary.status_code == 200
    assert summary.json()["count"] == 365


def test_analytics_summary_accepts_station_json() -> None:
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
    payload = response.json()
    assert payload["observations"] == 3
    assert payload["station_count"] == 2
    assert payload["temperature_c"]["mean"] == 18
    assert payload["total_precip_mm"] == 3.2


def test_analytics_summary_rejects_empty_or_invalid_payloads() -> None:
    assert request("POST", "/analytics/summary", {"observations": []}).status_code == 422
    assert request("POST", "/analytics/summary", {"observations": [{"station": "A", "temp_c": 20}]}).status_code == 422
