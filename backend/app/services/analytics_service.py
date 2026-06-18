"""
Analytics service — priority queue, stats, forecast, patrol optimizer, repeat offenders.
Stubs: each function raises NotImplementedError until real data is available.
"""
from __future__ import annotations

from app.core.config import settings
from app.models.schemas import (
    PriorityResponse, StatsResponse, ForecastResponse,
    PatrolResponse, RepeatOffendersResponse, EnforcementQualityResponse,
)


def _load(name: str):
    import pandas as pd
    return pd.read_parquet(settings.processed_dir / f"{name}.parquet")


def get_priority(**filters) -> PriorityResponse:
    df = _load("hotspots").sort_values("risk_score", ascending=False).reset_index(drop=True)
    items = []
    for rank, (_, row) in enumerate(df.iterrows(), start=1):
        items.append({
            "rank": rank,
            "hotspot_id": row["hotspot_id"],
            "risk_score": row["risk_score"],
            "logging_window": row["logging_window"],
            "police_station": row["police_station"],
            "recommended_units": max(1, int(row["risk_score"] // 30)),
        })
    return PriorityResponse(priority=items)


def get_stats(**filters) -> StatsResponse:
    vdf = _load("violations")
    hdf = _load("hotspots")
    dt_col = "created_ist" if "created_ist" in vdf.columns else "created_datetime"
    dates  = vdf[dt_col].dropna()
    return StatsResponse(
        total_violations=len(vdf),
        total_hotspots=len(hdf),
        date_range={
            "start": str(dates.min().date()) if len(dates) else "unknown",
            "end":   str(dates.max().date()) if len(dates) else "unknown",
        },
        by_vehicle_type=vdf["vehicle_type"].value_counts().to_dict(),
        by_violation_type=vdf["primary_violation_type"].value_counts().to_dict(),
        by_police_station=vdf["police_station"].value_counts().to_dict(),
    )


def get_forecast() -> ForecastResponse:
    df = _load("forecast")
    return ForecastResponse(forecast=df.to_dict(orient="records"))


def get_patrol(units: int = 10) -> PatrolResponse:
    """Greedy set-cover: assign units to highest-risk hotspots."""
    df = _load("hotspots").sort_values("risk_score", ascending=False).head(units)
    total_score = _load("hotspots")["risk_score"].sum()
    covered = df["risk_score"].sum()
    assignments = [
        {"unit_id": i + 1, "hotspot_id": row["hotspot_id"], "time_window": row["logging_window"]}
        for i, (_, row) in enumerate(df.iterrows())
    ]
    coverage_pct = round(covered / total_score * 100, 1) if total_score else 0.0
    return PatrolResponse(units=units, coverage_pct=coverage_pct, assignments=assignments)


def get_repeat_offenders(limit: int = 20) -> RepeatOffendersResponse:
    df = _load("repeat_offenders").head(limit)
    return RepeatOffendersResponse(offenders=df.to_dict(orient="records"))


def get_enforcement_quality() -> EnforcementQualityResponse:
    vdf = _load("violations")
    grp = vdf.groupby("police_station")
    rows = []
    for station, g in grp:
        total = len(g)
        rejected = (g["validation_status"] == "rejected").sum()
        rows.append({
            "police_station": station,
            "rejection_rate": round(rejected / total, 4) if total else 0.0,
            "total": total,
        })
    rows.sort(key=lambda x: x["rejection_rate"], reverse=True)
    return EnforcementQualityResponse(by_area=rows)
