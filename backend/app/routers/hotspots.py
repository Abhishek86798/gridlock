from __future__ import annotations

from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from backend.app.core import store
from backend.app.models.schemas import (
    HeatmapResponse,
    HotspotsResponse,
    PriorityResponse,
)

router = APIRouter(tags=["hotspots"])


def _to_records(df: pd.DataFrame) -> list[dict]:
    """Convert DataFrame to records, replacing NaN with None for JSON safety."""
    import math
    records = df.to_dict(orient="records")
    for rec in records:
        for k, v in list(rec.items()):
            try:
                if v is pd.NA or (isinstance(v, (float, int)) and math.isnan(v)):
                    rec[k] = None
            except (TypeError, ValueError):
                pass
    return records


def _apply_hotspot_filters(
    df: pd.DataFrame,
    police_station: Optional[str],
    violation_type: Optional[str],
    vehicle_type: Optional[str],
    min_risk: float,
    poi_category: Optional[str] = None,
) -> pd.DataFrame:
    if police_station:
        df = df[df["police_station"] == police_station]
    if violation_type:
        df = df[df["dominant_violation"].str.contains(violation_type, case=False, na=False)]
    if vehicle_type:
        df = df[df["dominant_vehicle"].str.contains(vehicle_type, case=False, na=False)]
    if min_risk > 0:
        df = df[df["risk_score"] >= min_risk]
    if poi_category and "poi_category" in df.columns:
        df = df[df["poi_category"] == poi_category]
    return df


# Columns to select for the Hotspot schema response (avoid leaking internal columns)
_HOTSPOT_COLS = [
    "hotspot_id", "lat", "lng", "risk_score", "violation_count",
    "dominant_violation", "dominant_vehicle", "logging_window",
    "morning_log_pct", "afternoon_log_pct", "police_station",
    "junction_name", "near_poi", "poi_category",
]


@router.get("/hotspots", response_model=HotspotsResponse)
def get_hotspots(
    police_station: Optional[str] = Query(None, description="Filter by police station name"),
    violation_type: Optional[str] = Query(None, description="Filter by dominant violation type (partial match)"),
    vehicle_type: Optional[str] = Query(None, description="Filter by dominant vehicle type (partial match)"),
    min_risk: float = Query(0.0, ge=0, le=100, description="Minimum risk score threshold"),
    poi_category: Optional[str] = Query(None, description="Filter by POI category: sensitive|metro|commercial|transit"),
    limit: int = Query(500, ge=1, le=1200, description="Maximum hotspots to return"),
):
    df = _apply_hotspot_filters(store.hotspots, police_station, violation_type, vehicle_type, min_risk, poi_category)
    df = df.head(limit)
    # Select only schema-relevant columns
    use_cols = [c for c in _HOTSPOT_COLS if c in df.columns]
    return HotspotsResponse(count=len(df), hotspots=_to_records(df[use_cols]))


@router.get("/heatmap", response_model=HeatmapResponse)
def get_heatmap(
    police_station: Optional[str] = Query(None),
    violation_type: Optional[str] = Query(None),
    vehicle_type: Optional[str] = Query(None),
    min_risk: float = Query(0.0, ge=0, le=100),
    poi_category: Optional[str] = Query(None, description="Filter by POI category: sensitive|metro|commercial|transit"),
):
    df = _apply_hotspot_filters(store.hotspots, police_station, violation_type, vehicle_type, min_risk, poi_category)
    max_score = float(df["risk_score"].max()) if len(df) else 1.0
    points = (
        df[["lat", "lng"]]
        .assign(weight=df["risk_score"] / max_score)
        .to_dict(orient="records")
    )
    return HeatmapResponse(points=points)


@router.get("/priority", response_model=PriorityResponse)
def get_priority(
    police_station: Optional[str] = Query(None),
    vehicle_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
):
    df = store.hotspots.copy()
    if police_station:
        df = df[df["police_station"] == police_station]
    if vehicle_type:
        df = df[df["dominant_vehicle"].str.contains(vehicle_type, case=False, na=False)]
    df = df.sort_values("risk_score", ascending=False).head(limit).reset_index(drop=True)

    # Recommend priority tier based on the hotspot's percentile rank in the full dataset.
    # P90 = ~50.65, P95 = ~54.64, max = 69.27.
    # Top ~1% (risk >= P99) get Critical; top ~10% (risk >= P90) get Elevated; rest get Standard.
    all_scores = store.hotspots["risk_score"]
    p90 = float(all_scores.quantile(0.90))
    p99 = float(all_scores.quantile(0.99))

    df["_tier"] = pd.cut(
        df["risk_score"],
        bins=[-float("inf"), p90, p99, float("inf")],
        labels=["Standard", "Elevated", "Critical"],
    ).astype(str)
    df["_rank"] = range(1, len(df) + 1)
    items = (
        df[["_rank", "hotspot_id", "risk_score", "logging_window", "police_station", "_tier"]]
        .rename(columns={"_rank": "rank", "_tier": "priority_tier"})
        .to_dict(orient="records")
    )
    return PriorityResponse(priority=items)

