"""
Thin wrapper around the backend API.
Set USE_MOCK=True to load mocks/hotspots.sample.json instead of hitting the server.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

import httpx

BASE_URL = "http://localhost:8000"
USE_MOCK = False  # flip to True while backend is not yet running

_MOCK_FILE = Path(__file__).parents[2] / "mocks" / "hotspots.sample.json"


def _mock_hotspots() -> dict:
    return json.loads(_MOCK_FILE.read_text())


def get(endpoint: str, params: dict | None = None) -> Any:
    if USE_MOCK and endpoint == "/hotspots":
        return _mock_hotspots()
    resp = httpx.get(f"{BASE_URL}{endpoint}", params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def hotspots(filters: dict | None = None) -> dict:
    return get("/hotspots", filters)


def priority(filters: dict | None = None) -> dict:
    return get("/priority", filters)


def heatmap(filters: dict | None = None) -> dict:
    return get("/heatmap", filters)


def temporal(hotspot_id: str) -> dict:
    return get(f"/temporal/{hotspot_id}")


def stats(filters: dict | None = None) -> dict:
    return get("/stats", filters)


def forecast() -> dict:
    return get("/forecast")


def patrol(units: int = 10) -> dict:
    return get("/patrol", {"units": units})


def repeat_offenders(limit: int = 20) -> dict:
    return get("/repeat-offenders", {"limit": limit})


def enforcement_quality() -> dict:
    return get("/enforcement-quality")
