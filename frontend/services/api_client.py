"""
API client — single module for all backend calls.

BASE_URL is the only thing to change when deploying or switching frameworks.
All functions return plain dicts so Streamlit components can use them directly.
"""
from __future__ import annotations

from typing import Any

import requests
import streamlit as st

BASE_URL = "http://localhost:8000"
_TIMEOUT = 10  # seconds
_CACHE_TTL = 300  # API artifacts are static during a dashboard session.


def _get(path: str, params: dict | None = None) -> dict:
    try:
        r = requests.get(f"{BASE_URL}{path}", params=params or {}, timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.RequestException:
        return {}


# ── Core endpoints ────────────────────────────────────────────────────────────

@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def get_hotspots(
    police_station: str | None = None,
    violation_type: str | None = None,
    vehicle_type: str | None = None,
    min_risk: float = 0.0,
    limit: int = 500,
) -> dict:
    params: dict[str, Any] = {"limit": limit, "min_risk": min_risk}
    if police_station:
        params["police_station"] = police_station
    if violation_type:
        params["violation_type"] = violation_type
    if vehicle_type:
        params["vehicle_type"] = vehicle_type
    return _get("/hotspots", params) or {"count": 0, "hotspots": []}


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def get_heatmap(
    police_station: str | None = None,
    violation_type: str | None = None,
    vehicle_type: str | None = None,
    min_risk: float = 0.0,
) -> dict:
    params: dict[str, Any] = {"min_risk": min_risk}
    if police_station:
        params["police_station"] = police_station
    if violation_type:
        params["violation_type"] = violation_type
    if vehicle_type:
        params["vehicle_type"] = vehicle_type
    return _get("/heatmap", params) or {"points": []}


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def get_priority(
    police_station: str | None = None,
    vehicle_type: str | None = None,
    limit: int = 50,
) -> dict:
    params: dict[str, Any] = {"limit": limit}
    if police_station:
        params["police_station"] = police_station
    if vehicle_type:
        params["vehicle_type"] = vehicle_type
    return _get("/priority", params) or {"priority": []}


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def get_temporal(hotspot_id: str) -> dict:
    return _get(f"/temporal/{hotspot_id}") or {"hotspot_id": hotspot_id, "matrix": []}


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def get_stats() -> dict:
    return _get("/stats") or {}


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def get_stations(min_hotspots: int = 1) -> dict:
    return _get("/stations", {"min_hotspots": min_hotspots}) or {"count": 0, "stations": []}


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def get_junctions(min_violations: int = 100) -> dict:
    return _get("/junctions", {"min_violations": min_violations, "limit": 153}) or {"count": 0, "junctions": []}


@st.cache_data(ttl=600, show_spinner=False)
def get_forecast(top_n: int = 20) -> dict:
    """
    Fetch next-week violation forecast from the XGBoost Poisson model.
    Returns {predict_week, model_mae, forecast: [...]} or {} on failure.
    """
    return _get("/forecast", {"top_n": top_n}) or {"predict_week": "?", "model_mae": 0.0, "forecast": []}


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def get_poi_stats() -> dict:
    """
    Fetch POI / spillover category breakdown.
    Returns {tagged_hotspots, untagged_hotspots, by_category: [...]} or {} on failure.
    """
    return _get("/poi-stats") or {"tagged_hotspots": 0, "untagged_hotspots": 0, "by_category": []}


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def get_patrol(units: int = 10) -> dict:
    """
    Fetch Patrol Deployment Optimizer results.
    Returns {units, coverage_pct, assignments: [...], coverage_curve: [...]} or {} on failure.
    """
    return _get("/patrol", {"units": units}) or {"units": units, "coverage_pct": 0.0, "assignments": [], "coverage_curve": []}


@st.cache_data(ttl=5, show_spinner=False)
def health() -> bool:
    try:
        r = requests.get(f"{BASE_URL}/", timeout=3)
        return r.status_code == 200
    except requests.RequestException:
        return False
