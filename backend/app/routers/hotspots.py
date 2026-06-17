from fastapi import APIRouter, Query
from typing import Optional

from app.models.schemas import HotspotsResponse, HeatmapResponse, TemporalResponse
from app.services import hotspot_service

router = APIRouter()


@router.get("/hotspots", response_model=HotspotsResponse)
def get_hotspots(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    police_station: Optional[str] = Query(None),
    vehicle_type: Optional[str] = Query(None),
    violation_type: Optional[str] = Query(None),
):
    return hotspot_service.get_hotspots(
        start_date=start_date,
        end_date=end_date,
        police_station=police_station,
        vehicle_type=vehicle_type,
        violation_type=violation_type,
    )


@router.get("/heatmap", response_model=HeatmapResponse)
def get_heatmap(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    police_station: Optional[str] = Query(None),
    vehicle_type: Optional[str] = Query(None),
    violation_type: Optional[str] = Query(None),
):
    return hotspot_service.get_heatmap(
        start_date=start_date,
        end_date=end_date,
        police_station=police_station,
        vehicle_type=vehicle_type,
        violation_type=violation_type,
    )


@router.get("/temporal/{hotspot_id}", response_model=TemporalResponse)
def get_temporal(hotspot_id: str):
    return hotspot_service.get_temporal(hotspot_id)
