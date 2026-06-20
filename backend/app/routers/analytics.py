from __future__ import annotations

from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from backend.app.core import store
from backend.app.models.schemas import ForecastResponse, PoiStatsResponse, StatsResponse, TemporalResponse, PatrolResponse, RepeatOffendersResponse, EnforcementQualityResponse
from backend.app.services import forecast as forecast_service
from backend.app.services import patrol_optimizer

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
    dates_raw  = vdf[dt_col].dropna()
    dates = pd.to_datetime(dates_raw, format="mixed", errors="coerce").dropna()
    
    blind_spot_pct = 0.0
    if len(dates):
        mask = (dates.dt.hour >= 13) & (dates.dt.hour <= 16)
        blind_spot_pct = round(float(mask.sum()) / len(dates) * 100, 1)

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
        blind_spot_pct=blind_spot_pct,
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


@router.get("/forecast", response_model=ForecastResponse)
def get_forecast(
    top_n: int = Query(20, ge=1, le=100, description="Top-N hotspots to return ranked by predicted count"),
):
    """
    Predictive hotspot forecast — next ISO week.

    Returns the top_n hotspots with the highest predicted violation count
    for the coming week, powered by an XGBoost count:poisson model trained
    on lag / rolling-mean / seasonality features.

    The model trains once at first request and is cached for the server lifetime.
    Also surfaces `change_pct` (% change vs last week) to flag rising hotspots.
    """
    if store.violations.empty or store.hotspots.empty:
        raise HTTPException(503, "Artifacts not loaded yet")
    try:
        result = forecast_service.get_forecast(top_n=top_n)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"Forecast model error: {exc}") from exc
    return result


@router.get("/patrol", response_model=PatrolResponse)
def get_patrol(
    units: int = Query(10, ge=1, le=100, description="Number of patrol units to deploy"),
):
    """
    Patrol Deployment Optimizer.
    Assign N patrol units to maximize high-priority coverage using greedy
    spatial de-bunching.
    """
    if store.hotspots.empty:
        raise HTTPException(503, "Artifacts not loaded yet")
    return patrol_optimizer.optimize_patrol(units=units)


@router.get("/poi-stats", response_model=PoiStatsResponse)
def get_poi_stats():
    """
    POI / spillover category breakdown across all hotspots.

    Returns per-category counts, total violations, and avg risk score.
    Surfaces the story: "X% of hotspots are within metro / commercial zones."
    Requires hotspots.parquet to have been precomputed with the poi_tagging step.
    """
    hdf = store.hotspots
    if hdf.empty:
        raise HTTPException(503, "Artifacts not loaded yet")
    if "poi_category" not in hdf.columns:
        raise HTTPException(501, "POI tags not present — re-run: "
                            "python -m backend.pipeline.precompute --steps hotspots")

    total = len(hdf)
    tagged_mask = hdf["poi_category"].notna()
    tagged = int(tagged_mask.sum())

    rows: list[dict] = []
    for cat in ("sensitive", "metro", "commercial", "transit"):
        sub = hdf[hdf["poi_category"] == cat]
        if sub.empty:
            continue

        # join violations to get total violation count per category
        hs_ids = set(sub["hotspot_id"])
        vdf = store.violations
        viol_count = 0
        if not vdf.empty and "hex_id" in hdf.columns:
            # cheap: sum violation_count from hotspot rows (already aggregated)
            viol_count = int(sub["violation_count"].sum())
        else:
            viol_count = int(sub["violation_count"].sum())

        rows.append({
            "poi_category":    cat,
            "hotspot_count":   int(len(sub)),
            "total_violations": viol_count,
            "avg_risk_score":  round(float(sub["risk_score"].mean()), 1),
            "pct_of_hotspots": round(len(sub) / total * 100, 1),
        })

    # Sort by hotspot_count desc
    rows.sort(key=lambda r: r["hotspot_count"], reverse=True)

    return PoiStatsResponse(
        tagged_hotspots=tagged,
        untagged_hotspots=total - tagged,
        by_category=rows,
    )


@router.get("/repeat-offenders", response_model=RepeatOffendersResponse)
def get_repeat_offenders(limit: int = Query(20, ge=1, le=100)):
    """
    Top repeat offenders by violation count.
    Vehicle numbers are PII-masked (e.g. FKN00G****63) for public display.
    """
    rdf = store.repeat_offenders
    if rdf.empty:
        raise HTTPException(503, "Repeat-offender artifacts not loaded yet")

    total_violations = len(store.violations)
    total_repeat_vehicles = len(rdf)
    repeat_violation_sum = int(rdf["violation_count"].sum())

    top = rdf.head(limit).copy()
    # Use masked vehicle numbers for the API response
    plate_col = "vehicle_number_masked" if "vehicle_number_masked" in top.columns else "vehicle_number"

    offenders = []
    for _, row in top.iterrows():
        offenders.append({
            "vehicle_number": row[plate_col],
            "violation_count": int(row["violation_count"]),
            "top_location": row.get("top_location", "Unknown"),
            "distinct_locations": int(row.get("distinct_locations", 1)),
            "top_hotspot": row.get("top_hotspot"),
            "distinct_hotspots": int(row["distinct_hotspots"]) if pd.notna(row.get("distinct_hotspots")) else None,
        })

    return RepeatOffendersResponse(
        total_repeat_vehicles=total_repeat_vehicles,
        pct_of_total_violations=round(repeat_violation_sum / total_violations * 100, 2) if total_violations else 0.0,
        offenders=offenders,
    )


@router.get("/enforcement-quality", response_model=EnforcementQualityResponse)
def get_enforcement_quality():
    vdf = store.violations
    if vdf.empty:
        raise HTTPException(503, "Artifacts not loaded yet")
    grp = vdf.groupby("police_station")
    rows = []
    for station, g in grp:
        total = len(g)
        rejected = (g["validation_status"] == "rejected").sum()
        rows.append({
            "police_station": station,
            "rejection_rate": round(float(rejected) / total, 4) if total else 0.0,
            "total": total,
        })
    rows.sort(key=lambda x: x["rejection_rate"], reverse=True)
    return EnforcementQualityResponse(by_area=rows)
