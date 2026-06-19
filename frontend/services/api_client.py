"""
API client — single module for all backend calls.

BASE_URL is the only thing to change when deploying or switching frameworks.
All functions return plain dicts so Streamlit components can use them directly.
"""
from __future__ import annotations

from typing import Any

import requests

BASE_URL = "http://localhost:8000"
_TIMEOUT = 10  # seconds


def _get(path: str, params: dict | None = None) -> dict:
    try:
        r = requests.get(f"{BASE_URL}{path}", params=params or {}, timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.RequestException:
        return {}


# ── Core endpoints ────────────────────────────────────────────────────────────

def get_hotspots(
    police_station: str | None = None,
    violation_type: str | None = None,
    min_risk: float = 0.0,
    limit: int = 500,
) -> dict:
    params: dict[str, Any] = {"limit": limit, "min_risk": min_risk}
    if police_station:
        params["police_station"] = police_station
    if violation_type:
        params["violation_type"] = violation_type
    return _get("/hotspots", params) or {"count": 0, "hotspots": []}


def get_heatmap(
    police_station: str | None = None,
    violation_type: str | None = None,
    min_risk: float = 0.0,
) -> dict:
    params: dict[str, Any] = {"min_risk": min_risk}
    if police_station:
        params["police_station"] = police_station
    if violation_type:
        params["violation_type"] = violation_type
    return _get("/heatmap", params) or {"points": []}


def get_priority(
    police_station: str | None = None,
    limit: int = 50,
) -> dict:
    params: dict[str, Any] = {"limit": limit}
    if police_station:
        params["police_station"] = police_station
    return _get("/priority", params) or {"priority": []}


def get_temporal(hotspot_id: str) -> dict:
    return _get(f"/temporal/{hotspot_id}") or {"hotspot_id": hotspot_id, "matrix": []}


def get_stats() -> dict:
    return _get("/stats") or {}


def get_stations(min_hotspots: int = 1) -> dict:
    return _get("/stations", {"min_hotspots": min_hotspots}) or {"count": 0, "stations": []}


def get_junctions(min_violations: int = 100) -> dict:
    return _get("/junctions", {"min_violations": min_violations, "limit": 153}) or {"count": 0, "junctions": []}


def health() -> bool:
    try:
        r = requests.get(f"{BASE_URL}/", timeout=3)
        return r.status_code == 200
    except requests.RequestException:
        return False
