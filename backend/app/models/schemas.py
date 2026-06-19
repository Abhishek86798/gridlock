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
    predicted_count: float   # 4-week rolling mean forecast for next ISO week
    prev_week_count: int     # actual count last observed week
    change_pct: Optional[float] = None   # % change vs last week (null if insufficient baseline)
    count_delta: Optional[int] = None    # raw predicted - prev_week_count
    trend_label: Optional[str] = None    # "emerging" / "rising" / "stable" / "declining"
    risk_score: float        # static risk score for display / sorting


class ForecastResponse(BaseModel):
    predict_week: str                        # ISO label e.g. "2024-W22"
    method: Optional[str] = None             # prediction method used
    model_mae: float                         # MAE of primary method on hold-out
    baseline_mae_last_week: float            # naive baseline: predict = last week's count
    baseline_mae_rolling_mean: float         # naive baseline: predict = 4-week rolling mean
    pct_beat_last_week: Optional[float] = None      # deprecated — use model_comparison
    pct_beat_rolling_mean: Optional[float] = None   # deprecated — use model_comparison
    precision_at: dict[int, float]           # {10: 0.7, 20: 0.65} — top-N overlap on hold-out
    weekly_totals: list[dict]                # [{week, total_violations}] for ramp diagnosis
    data_quality_note: str                   # plain-English enforcement-ramp / gap assessment
    model_comparison: Optional[dict] = None  # XGBoost vs rolling mean MAE comparison
    forecast: list[ForecastItem]


# ── Add-on: Patrol ────────────────────────────────────────────────────────────

class PatrolAssignment(BaseModel):
    unit_id: int
    hotspot_id: str
    time_window: str
    risk_score: Optional[float] = None


class CoverageCurvePoint(BaseModel):
    units: int
    coverage_pct: float


class PatrolResponse(BaseModel):
    units: int
    coverage_pct: float
    naive_coverage_pct: Optional[float] = None
    improvement_pct: Optional[float] = None
    assignments: list[PatrolAssignment]
    coverage_curve: list[CoverageCurvePoint] = []


# ── Add-on: Repeat offenders ──────────────────────────────────────────────────

class OffenderItem(BaseModel):
    vehicle_number: str              # PII-masked plate (e.g. FKN00G****63)
    violation_count: int
    top_location: str
    distinct_locations: int
    top_hotspot: Optional[str] = None
    distinct_hotspots: Optional[int] = None


class RepeatOffendersResponse(BaseModel):
    total_repeat_vehicles: int       # vehicles with >= 3 violations
    pct_of_total_violations: float   # what % of all violations they account for
    offenders: list[OffenderItem]


# ── Add-on: Enforcement quality ───────────────────────────────────────────────

class EnforcementQualityItem(BaseModel):
    police_station: str
    rejection_rate: float
    total: int


class EnforcementQualityResponse(BaseModel):
    by_area: list[EnforcementQualityItem]
