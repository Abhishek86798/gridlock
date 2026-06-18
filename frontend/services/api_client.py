import requests
from typing import Dict, Any

BASE_URL = "http://localhost:8000"

def get_hotspots(filters: Dict[str, Any] = None) -> Dict[str, Any]:
    url = f"{BASE_URL}/hotspots"
    response = requests.get(url, params=filters)
    if response.status_code == 200:
        return response.json()
    return {"count": 0, "hotspots": []}

def get_priority() -> Dict[str, Any]:
    url = f"{BASE_URL}/priority"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return {"priority": []}

def get_heatmap() -> Dict[str, Any]:
    url = f"{BASE_URL}/heatmap"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return {"points": []}

def get_stats(filters: Dict[str, Any] = None) -> Dict[str, Any]:
    url = f"{BASE_URL}/stats"
    response = requests.get(url, params=filters)
    if response.status_code == 200:
        return response.json()
    return {}

def get_temporal(hotspot_id: str) -> Dict[str, Any]:
    url = f"{BASE_URL}/temporal/{hotspot_id}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return {"hotspot_id": hotspot_id, "matrix": []}
