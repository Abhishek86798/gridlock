from typing import List, Optional, Dict
from pydantic import BaseModel

class Hotspot(BaseModel):
    hotspot_id: str
    lat: float
    lng: float
    risk_score: float
    violation_count: int
    dominant_violation: str
    dominant_vehicle: str
    peak_window: str
    police_station: str
    junction_name: Optional[str] = None
    near_poi: Optional[str] = None

class HotspotResponse(BaseModel):
    count: int
    hotspots: List[Hotspot]

class PriorityItem(BaseModel):
    rank: int
    hotspot_id: str
    risk_score: float
    peak_window: str
    police_station: str
    recommended_units: int

class PriorityResponse(BaseModel):
    priority: List[PriorityItem]

class HeatmapPoint(BaseModel):
    lat: float
    lng: float
    weight: float

class HeatmapResponse(BaseModel):
    points: List[HeatmapPoint]

class TemporalMatrixItem(BaseModel):
    hour: int
    day_of_week: int
    count: int

class TemporalResponse(BaseModel):
    hotspot_id: str
    matrix: List[TemporalMatrixItem]

class DateRange(BaseModel):
    start: str
    end: str

class StatsResponse(BaseModel):
    total_violations: int
    total_hotspots: int
    date_range: DateRange
    by_vehicle_type: Dict[str, int]
    by_violation_type: Dict[str, int]
    by_police_station: Dict[str, int]
