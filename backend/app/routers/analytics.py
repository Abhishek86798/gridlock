from __future__ import annotations

from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from backend.app.core import store
from backend.app.models.schemas import StatsResponse, TemporalResponse

router = APIRouter(tags=["analytics"])


def _to_records(df: pd.DataFrame) -> list[dict]:
    return df.where(pd.notna(df), other=None).to_dict(orient="records")


@router.get("/stats", response_model=StatsResponse)
def get_stats():
    vdf = store.violations
    hdf = store.hotspots
    if vdf.empty:
        raise HTTPException(503, "Artifacts not loaded yet")

    dt_col = "created_ist" if "created_ist" in vdf.columns else "created_datetime"
    dates  = vdf[dt_col].dropna()

    return StatsResponse(
        total_violations=int(len(vdf)),
        total_hotspots=int(len(hdf)),
        date_range={
            "start": str(dates.min().date()) if len(dates) else "unknown",
            "end":   str(dates.max().date()) if len(dates) else "unknown",
        },
        by_vehicle_type=vdf["vehicle_type"].value_counts().head(20).to_dict(),
        by_violation_type=vdf["primary_violation_type"].value_counts().head(20).to_dict(),
        by_police_station=vdf["police_station"].value_counts().head(20).to_dict(),
    )


@router.get("/temporal/{hotspot_id}", response_model=TemporalResponse)
def get_temporal(hotspot_id: str):
    df = store.temporal
    subset = df[df["hotspot_id"] == hotspot_id]
    if subset.empty:
        raise HTTPException(404, f"No temporal data for hotspot {hotspot_id!r}")
    matrix = subset[["hour", "day_of_week", "count"]].to_dict(orient="records")
    return TemporalResponse(hotspot_id=hotspot_id, matrix=matrix)


@router.get("/stations")
def get_stations(
    min_hotspots: int = Query(1, ge=1, description="Minimum hotspot count"),
    limit: int = Query(53, ge=1, le=200),
):
    """Police-station rollup: hotspot counts, avg risk, blind-spot percentage."""
    df = store.by_station
    if min_hotspots > 1:
        df = df[df["hotspot_count"] >= min_hotspots]
    df = df.head(limit)
    return {"count": len(df), "stations": _to_records(df)}


@router.get("/junctions")
def get_junctions(
    min_violations: int = Query(1, ge=1, description="Minimum violation count"),
    limit: int = Query(100, ge=1, le=500),
):
    """Named-junction rollup: violation counts, avg risk, top hotspot."""
    df = store.by_junction
    if min_violations > 1:
        df = df[df["total_violations"] >= min_violations]
    df = df.head(limit)
    return {"count": len(df), "junctions": _to_records(df)}
