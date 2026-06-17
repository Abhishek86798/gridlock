from fastapi import APIRouter, Query
from typing import Optional

from app.models.schemas import (
    PriorityResponse,
    StatsResponse,
    ForecastResponse,
    PatrolResponse,
    RepeatOffendersResponse,
    EnforcementQualityResponse,
)
from app.services import analytics_service

router = APIRouter()


@router.get("/priority", response_model=PriorityResponse)
def get_priority(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    police_station: Optional[str] = Query(None),
    vehicle_type: Optional[str] = Query(None),
    violation_type: Optional[str] = Query(None),
):
    return analytics_service.get_priority(
        start_date=start_date,
        end_date=end_date,
        police_station=police_station,
        vehicle_type=vehicle_type,
        violation_type=violation_type,
    )


@router.get("/stats", response_model=StatsResponse)
def get_stats(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    police_station: Optional[str] = Query(None),
    vehicle_type: Optional[str] = Query(None),
    violation_type: Optional[str] = Query(None),
):
    return analytics_service.get_stats(
        start_date=start_date,
        end_date=end_date,
        police_station=police_station,
        vehicle_type=vehicle_type,
        violation_type=violation_type,
    )


@router.get("/forecast", response_model=ForecastResponse)
def get_forecast():
    return analytics_service.get_forecast()


@router.get("/patrol", response_model=PatrolResponse)
def get_patrol(units: int = Query(10, ge=1, le=100)):
    return analytics_service.get_patrol(units=units)


@router.get("/repeat-offenders", response_model=RepeatOffendersResponse)
def get_repeat_offenders(limit: int = Query(20, ge=1, le=200)):
    return analytics_service.get_repeat_offenders(limit=limit)


@router.get("/enforcement-quality", response_model=EnforcementQualityResponse)
def get_enforcement_quality():
    return analytics_service.get_enforcement_quality()
