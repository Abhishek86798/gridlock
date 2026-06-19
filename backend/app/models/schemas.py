from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


# ── Hotspot ───────────────────────────────────────────────────────────────────

class Hotspot(BaseModel):
    hotspot_id: str
    lat: float
    lng: float
    risk_score: float
    violation_count: int
    dominant_violation: str
    dominant_vehicle: str
    logging_window: str           # dominant logging band: morning/overnight/split
    morning_log_pct: float        # % logs in 06:00-11:59 (morning patrol coverage)
    afternoon_log_pct: float      # % logs in 15:00-20:59 (blind-spot indicator)
    police_station: str
    junction_name: Optional[str] = None
    near_poi: Optional[str] = None
    poi_category: Optional[str] = None   # sensitive | metro | commercial | transit


class HotspotsResponse(BaseModel):
    count: int
    hotspots: list[Hotspot]


# ── Priority queue ────────────────────────────────────────────────────────────

class PriorityItem(BaseModel):
    rank: int
    hotspot_id: str
    risk_score: float
    logging_window: str
    police_station: str
    recommended_units: int


class PriorityResponse(BaseModel):
    priority: list[PriorityItem]


# ── Heatmap ───────────────────────────────────────────────────────────────────

class HeatmapPoint(BaseModel):
    lat: float
    lng: float
    weight: float


class HeatmapResponse(BaseModel):
    points: list[HeatmapPoint]


# ── Temporal ──────────────────────────────────────────────────────────────────

class TemporalCell(BaseModel):
    hour: int
    day_of_week: int
    count: int


class TemporalResponse(BaseModel):
    hotspot_id: str
    matrix: list[TemporalCell]


# ── Stats ─────────────────────────────────────────────────────────────────────

class DateRange(BaseModel):
    start: str
    end: str


class StatsResponse(BaseModel):
    total_violations: int
    total_hotspots: int
    date_range: DateRange
    by_vehicle_type: dict[str, int]
    by_violation_type: dict[str, int]
    by_police_station: dict[str, int]


# ── Add-on: POI / Spillover stats ──────────────────────────────────────────────────

class PoiCategoryItem(BaseModel):
    poi_category: str
    hotspot_count: int
    total_violations: int
    avg_risk_score: float
    pct_of_hotspots: float     # % of all hotspots that fall in this category


class PoiStatsResponse(BaseModel):
    tagged_hotspots: int       # hotspots with any POI tag
    untagged_hotspots: int
    by_category: list[PoiCategoryItem]


# ── Add-on: Forecast ──────────────────────────────────────────────────────────

class ForecastItem(BaseModel):
    hotspot_id: str
    police_station: str
    predicted_count: float   # XGBoost Poisson forecast for next ISO week
    prev_week_count: int     # actual count last observed week
    change_pct: float        # % change vs last week (positive = rising)
    risk_score: float        # static risk score for display / sorting


class ForecastResponse(BaseModel):
    predict_week: str        # ISO label e.g. "2024-W22"
    model_mae: float         # mean-absolute-error on 2-week hold-out
    forecast: list[ForecastItem]


# ── Add-on: Patrol ────────────────────────────────────────────────────────────

class PatrolAssignment(BaseModel):
    unit_id: int
    hotspot_id: str
    time_window: str


class PatrolResponse(BaseModel):
    units: int
    coverage_pct: float
    assignments: list[PatrolAssignment]


# ── Add-on: Repeat offenders ──────────────────────────────────────────────────

class OffenderItem(BaseModel):
    vehicle_number: str
    violation_count: int
    top_location: str
    distinct_locations: int


class RepeatOffendersResponse(BaseModel):
    offenders: list[OffenderItem]


# ── Add-on: Enforcement quality ───────────────────────────────────────────────

class EnforcementQualityItem(BaseModel):
    police_station: str
    rejection_rate: float
    total: int


class EnforcementQualityResponse(BaseModel):
    by_area: list[EnforcementQualityItem]
