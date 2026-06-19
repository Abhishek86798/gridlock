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
    return df.where(pd.notna(df), other=None).to_dict(orient="records")


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
    return HotspotsResponse(count=len(df), hotspots=_to_records(df))


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
    points = [
        {"lat": row["lat"], "lng": row["lng"], "weight": row["risk_score"] / max_score}
        for _, row in df.iterrows()
    ]
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

    items = [
        {
            "rank": i + 1,
            "hotspot_id": row["hotspot_id"],
            "risk_score": row["risk_score"],
            "logging_window": row["logging_window"],
            "police_station": row["police_station"],
            "recommended_units": max(1, int(row["risk_score"] // 30)),
        }
        for i, (_, row) in enumerate(df.iterrows())
    ]
    return PriorityResponse(priority=items)
