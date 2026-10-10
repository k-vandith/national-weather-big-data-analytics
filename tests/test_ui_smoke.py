from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from src.api import app


def get(path: str) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(path)

    return asyncio.run(send())


def test_frontend_asset_routes_are_available() -> None:
    root = get("/")
    assert root.status_code == 200
    assert Path(__file__).resolve().parents[1].joinpath("web", "index.html").is_file()
    assert "Weather Atlas" in root.text
    assert get("/styles.css").status_code == 200
    assert get("/app.js").status_code == 200
