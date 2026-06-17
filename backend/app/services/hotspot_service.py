"""
Hotspot service — loads processed parquets and serves map/heatmap/temporal data.
Stub: replace NotImplementedError bodies once ML pipeline writes the parquets.
"""
from __future__ import annotations
from typing import Optional

from app.core.config import settings
from app.models.schemas import HotspotsResponse, HeatmapResponse, TemporalResponse


def _load_hotspots_df():
    import pandas as pd
    path = settings.processed_dir / "hotspots.parquet"
    return pd.read_parquet(path)


def _load_temporal_df():
    import pandas as pd
    path = settings.processed_dir / "temporal.parquet"
    return pd.read_parquet(path)


def get_hotspots(
    start_date=None, end_date=None,
    police_station=None, vehicle_type=None, violation_type=None,
) -> HotspotsResponse:
    df = _load_hotspots_df()
    if police_station:
        df = df[df["police_station"] == police_station]
    hotspots = df.to_dict(orient="records")
    return HotspotsResponse(count=len(hotspots), hotspots=hotspots)


def get_heatmap(
    start_date=None, end_date=None,
    police_station=None, vehicle_type=None, violation_type=None,
) -> HeatmapResponse:
    df = _load_hotspots_df()
    if police_station:
        df = df[df["police_station"] == police_station]
    max_score = df["risk_score"].max() or 1.0
    points = [
        {"lat": row["lat"], "lng": row["lng"], "weight": row["risk_score"] / max_score}
        for _, row in df.iterrows()
    ]
    return HeatmapResponse(points=points)


def get_temporal(hotspot_id: str) -> TemporalResponse:
    df = _load_temporal_df()
    subset = df[df["hotspot_id"] == hotspot_id]
    matrix = subset[["hour", "day_of_week", "count"]].to_dict(orient="records")
    return TemporalResponse(hotspot_id=hotspot_id, matrix=matrix)
