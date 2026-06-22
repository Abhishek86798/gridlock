from __future__ import annotations

from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from backend.app.core import store
from backend.app.models.schemas import ForecastResponse, PoiStatsResponse, StatsResponse, TemporalResponse, PatrolResponse, RepeatOffendersResponse, EnforcementQualityResponse, StationForecastResponse
from backend.app.services import forecast as forecast_service
from backend.app.services import patrol_optimizer

router = APIRouter(tags=["analytics"])


def _to_records(df: pd.DataFrame) -> list[dict]:
    return df.where(pd.notna(df), other=None).to_dict(orient="records")


@router.get("/stats", response_model=StatsResponse)
def get_stats():
    if not store.stats_cache:
        raise HTTPException(503, "Artifacts not loaded yet")
    c = store.stats_cache
    return StatsResponse(
        total_violations=c["total_violations"],
        total_hotspots=c["total_hotspots"],
        date_range={"start": c["date_start"], "end": c["date_end"]},
        by_vehicle_type=c["by_vehicle_type"],
        by_violation_type=c["by_violation_type"],
        by_police_station=c["by_police_station"],
        blind_spot_pct=c["blind_spot_pct"],
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
    top_n: int = Query(20, ge=1, le=2000, description="Top-N hotspots to return ranked by predicted count"),
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


@router.get("/forecast/stations", response_model=StationForecastResponse)
def get_station_forecast():
    """
    Station-grain forecast for the next ISO week.

    Coarser than the per-hotspot forecast (53 stations vs ~1,200 hotspots), so
    the law of large numbers makes station-week counts far more predictable —
    roughly half the week-to-week noise (median CV ~1.0 vs ~2.0 per-hotspot).
    We surface it alongside the per-hotspot view to justify forecasting trend +
    flagging escalation rather than chasing exact per-hotspot counts.

    Trains once at first request and is cached for the server lifetime.
    """
    if store.violations.empty:
        raise HTTPException(503, "Artifacts not loaded yet")
    try:
        result = forecast_service.get_station_forecast()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"Station forecast error: {exc}") from exc
    return result


@router.get("/patrol", response_model=PatrolResponse)
def get_patrol(
    units: int = Query(10, ge=1, le=100, description="Number of patrol units to deploy"),
    mode: str = Query("predictive", pattern="^(predictive|historical)$",
                      description="predictive = allocate against forecast; historical = against past counts"),
):
    """
    Predictive Patrol Deployment Optimizer.

    Allocates N patrol units across hotspots using greedy spatial de-bunching.
    mode=predictive (default) ranks by next-week predicted load (with historical
    fallback) and returns predicted-violations-covered plus an escalation watch
    list of rising hotspots. mode=historical ranks by past counts as a baseline.
    """
    if store.hotspots.empty:
        raise HTTPException(503, "Artifacts not loaded yet")
    return patrol_optimizer.optimize_patrol(units=units, mode=mode)


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

    # The pipeline writes total_violations (not violation_count) — keep this
    # tolerant so a stale artifact doesn't 500 the endpoint.
    count_col = "total_violations" if "total_violations" in rdf.columns else "violation_count"

    total_violations = len(store.violations)
    total_repeat_vehicles = len(rdf)
    repeat_violation_sum = int(rdf[count_col].sum())

    # Tier rollup + centroid explainer (the ML-credibility artifact). Centroids
    # are the per-tier mean of the three behavioural axes the model clusters on.
    tier_counts: dict[str, int] = {}
    centroids = []
    if "risk_tier" in rdf.columns:
        tier_counts = {str(k): int(v) for k, v in rdf["risk_tier"].value_counts().items()}
        _TIER_ORDER = {"Occasional": 0, "Frequent": 1, "Habitual": 2}
        grp = rdf.groupby("risk_tier")
        rows = []
        for tier, g in grp:
            rows.append({
                "risk_tier": str(tier),
                "total_violations": round(float(g[count_col].mean()), 2),
                "frequency": round(float(g["frequency"].mean()), 3),
                "avg_days_between": round(float(g["avg_days_between"].mean()), 2),
                "vehicle_count": int(len(g)),
            })
        rows.sort(key=lambda r: _TIER_ORDER.get(r["risk_tier"], 99))
        centroids = rows

    top = rdf.head(limit).copy()
    # Use masked vehicle numbers for the API response
    plate_col = "vehicle_number_masked" if "vehicle_number_masked" in top.columns else "vehicle_number"

    offenders = []
    for _, row in top.iterrows():
        offenders.append({
            "vehicle_number": row[plate_col],
            "violation_count": int(row[count_col]),
            "top_location": row.get("top_location", "Unknown"),
            "distinct_locations": int(row.get("distinct_locations", 1)),
            "top_hotspot": row.get("top_hotspot"),
            "distinct_hotspots": int(row["distinct_hotspots"]) if pd.notna(row.get("distinct_hotspots")) else None,
            "risk_tier": row.get("risk_tier"),
            "frequency": round(float(row["frequency"]), 3) if pd.notna(row.get("frequency")) else None,
            "avg_days_between": round(float(row["avg_days_between"]), 2) if pd.notna(row.get("avg_days_between")) else None,
        })

    return RepeatOffendersResponse(
        total_repeat_vehicles=total_repeat_vehicles,
        pct_of_total_violations=round(repeat_violation_sum / total_violations * 100, 2) if total_violations else 0.0,
        tier_counts=tier_counts,
        centroids=centroids,
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
