"""
Generate fake processed/*.parquet files that match the CONTRACTS.md §2 schema.
Run once so backend can start before the real ML pipeline delivers data.

Usage:
    python mocks/make_sample_parquet.py
"""
from __future__ import annotations
import random
import json
from pathlib import Path

import pandas as pd
import numpy as np

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

OUT = Path(__file__).parents[1] / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

STATIONS = ["Madiwala", "Shivajinagar", "Koramangala", "Jayanagar", "Yeshwanthpur", "Whitefield"]
VIOLATION_TYPES = [
    "PARKING IN A MAIN ROAD", "WRONG PARKING", "NO PARKING",
    "PARKING NEAR ROAD CROSSING", "PARKING ON FOOTPATH",
]
VEHICLE_TYPES = ["CAR", "SCOOTER", "AUTO", "MOTORCYCLE", "TRUCK", "TANKER"]
PEAK_WINDOWS = ["Mon–Fri 18:00–21:00", "Mon–Sat 09:00–11:00", "Sat–Sun 11:00–14:00"]

N_HOTSPOTS = 20
N_VIOLATIONS = 2000

# ── hotspots.parquet ─────────────────────────────────────────────────────────
hotspots = pd.DataFrame({
    "hotspot_id": [f"HS{i:03d}" for i in range(1, N_HOTSPOTS + 1)],
    "lat": np.random.uniform(12.85, 13.05, N_HOTSPOTS),
    "lng": np.random.uniform(77.50, 77.75, N_HOTSPOTS),
    "risk_score": np.random.uniform(10, 100, N_HOTSPOTS).round(1),
    "violation_count": np.random.randint(20, 200, N_HOTSPOTS),
    "dominant_violation": np.random.choice(VIOLATION_TYPES, N_HOTSPOTS),
    "dominant_vehicle": np.random.choice(VEHICLE_TYPES, N_HOTSPOTS),
    "peak_window": np.random.choice(PEAK_WINDOWS, N_HOTSPOTS),
    "police_station": np.random.choice(STATIONS, N_HOTSPOTS),
    "junction_name": [random.choice([None, "Some Junction"]) for _ in range(N_HOTSPOTS)],
    "near_poi": [random.choice([None, "Metro Station", "Commercial Area"]) for _ in range(N_HOTSPOTS)],
})
hotspots.to_parquet(OUT / "hotspots.parquet", index=False)
print(f"hotspots.parquet  → {len(hotspots)} rows")

# ── temporal.parquet ─────────────────────────────────────────────────────────
temporal_rows = []
for hid in hotspots["hotspot_id"]:
    for hour in range(24):
        for dow in range(7):
            temporal_rows.append({
                "hotspot_id": hid,
                "hour": hour,
                "day_of_week": dow,
                "count": max(0, int(np.random.poisson(3))),
            })
temporal = pd.DataFrame(temporal_rows)
temporal.to_parquet(OUT / "temporal.parquet", index=False)
print(f"temporal.parquet  → {len(temporal)} rows")

# ── violations.parquet ───────────────────────────────────────────────────────
hotspot_ids = hotspots["hotspot_id"].tolist()
violations = pd.DataFrame({
    "id": [f"V{i:05d}" for i in range(N_VIOLATIONS)],
    "lat": np.random.uniform(12.85, 13.05, N_VIOLATIONS),
    "lng": np.random.uniform(77.50, 77.75, N_VIOLATIONS),
    "violation_type": np.random.choice(VIOLATION_TYPES, N_VIOLATIONS),
    "vehicle_type": np.random.choice(VEHICLE_TYPES, N_VIOLATIONS),
    "vehicle_number": [f"KA{random.randint(1,99):02d}AB{random.randint(1000,9999)}" for _ in range(N_VIOLATIONS)],
    "police_station": np.random.choice(STATIONS, N_VIOLATIONS),
    "junction_name": [random.choice([None, "Some Junction"]) for _ in range(N_VIOLATIONS)],
    "created_at": pd.date_range("2023-11-01", periods=N_VIOLATIONS, freq="1h", tz="UTC"),
    "hour": np.random.randint(0, 24, N_VIOLATIONS),
    "day_of_week": np.random.randint(0, 7, N_VIOLATIONS),
    "severity_weight": np.random.uniform(1.0, 3.0, N_VIOLATIONS).round(2),
    "validation_status": np.random.choice(["approved", "rejected"], N_VIOLATIONS, p=[0.88, 0.12]),
})
violations.to_parquet(OUT / "violations.parquet", index=False)
print(f"violations.parquet → {len(violations)} rows")

# ── forecast.parquet ─────────────────────────────────────────────────────────
forecast = pd.DataFrame({
    "hotspot_id": np.random.choice(hotspot_ids, 30),
    "predict_window": ["Tomorrow 18:00–21:00"] * 30,
    "predicted_intensity": np.random.uniform(10, 60, 30).round(1),
    "confidence": np.random.uniform(0.5, 0.95, 30).round(2),
})
forecast.to_parquet(OUT / "forecast.parquet", index=False)
print(f"forecast.parquet  → {len(forecast)} rows")

# ── repeat_offenders.parquet ─────────────────────────────────────────────────
plates = [f"KA{random.randint(1,99):02d}AB{random.randint(1000,9999)}" for _ in range(50)]
offenders = pd.DataFrame({
    "vehicle_number": plates,
    "violation_count": np.random.randint(2, 25, 50),
    "top_location": np.random.choice(STATIONS, 50),
    "distinct_locations": np.random.randint(1, 6, 50),
}).sort_values("violation_count", ascending=False).reset_index(drop=True)
offenders.to_parquet(OUT / "repeat_offenders.parquet", index=False)
print(f"repeat_offenders.parquet → {len(offenders)} rows")

print("\nAll mock parquets written to", OUT)
