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


# ── Add-on: Forecast ──────────────────────────────────────────────────────────

class ForecastItem(BaseModel):
    hotspot_id: str
    predict_window: str
    predicted_intensity: float
    confidence: float


class ForecastResponse(BaseModel):
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
