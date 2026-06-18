import json
from pathlib import Path
from fastapi import APIRouter
from app.models.schemas import HotspotResponse, PriorityResponse, HeatmapResponse

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
MOCKS_DIR = BASE_DIR / "mocks"

def load_mock(filename: str):
    try:
        with open(MOCKS_DIR / filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {}

@router.get("/hotspots", response_model=HotspotResponse)
def get_hotspots(start_date: str = None, end_date: str = None, police_station: str = None, vehicle_type: str = None, violation_type: str = None):
    # Currently ignoring filters and returning mock data
    data = load_mock("hotspots.sample.json")
    return data

@router.get("/priority", response_model=PriorityResponse)
def get_priority():
    data = load_mock("hotspots.sample.json")
    # Transform hotspots to priority queue
    hotspots = data.get("hotspots", [])
    # Sort by risk score descending
    hotspots.sort(key=lambda x: x["risk_score"], reverse=True)
    
    priority_items = []
    for idx, hs in enumerate(hotspots):
        priority_items.append({
            "rank": idx + 1,
            "hotspot_id": hs["hotspot_id"],
            "risk_score": hs["risk_score"],
            "peak_window": hs["peak_window"],
            "police_station": hs["police_station"],
            "recommended_units": max(1, int(hs["risk_score"] // 30))
        })
    return {"priority": priority_items}

@router.get("/heatmap", response_model=HeatmapResponse)
def get_heatmap():
    data = load_mock("hotspots.sample.json")
    hotspots = data.get("hotspots", [])
    
    points = []
    for hs in hotspots:
        points.append({
            "lat": hs["lat"],
            "lng": hs["lng"],
            "weight": hs["risk_score"] / 100.0
        })
    return {"points": points}
