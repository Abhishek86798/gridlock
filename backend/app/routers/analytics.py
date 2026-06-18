import json
import random
from pathlib import Path
from fastapi import APIRouter
from app.models.schemas import StatsResponse, TemporalResponse

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
MOCKS_DIR = BASE_DIR / "mocks"

def load_mock(filename: str):
    try:
        with open(MOCKS_DIR / filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {}

@router.get("/stats", response_model=StatsResponse)
def get_stats(start_date: str = None, end_date: str = None, police_station: str = None, vehicle_type: str = None, violation_type: str = None):
    # Ignoring filters and returning mock data
    data = load_mock("stats.sample.json")
    return data

@router.get("/temporal/{hotspot_id}", response_model=TemporalResponse)
def get_temporal(hotspot_id: str):
    # We don't have a static mock file for temporal data, so we'll generate it dynamically
    # based on the contract
    matrix = []
    for hour in range(24):
        for day in range(7):
            # Generate random counts, maybe peaking at certain times to look realistic
            count = random.randint(0, 5)
            if 16 <= hour <= 20:  # Peak evening hours
                count += random.randint(5, 15)
            matrix.append({
                "hour": hour,
                "day_of_week": day,
                "count": count
            })
    return {
        "hotspot_id": hotspot_id,
        "matrix": matrix
    }
