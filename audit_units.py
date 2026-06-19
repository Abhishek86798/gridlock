"""STEP 1: Audit recommended_units distribution from patrol optimizer."""
import sys
sys.path.insert(0, "D:/flipkart_Gridlock/gridlock")

import pandas as pd
from collections import Counter
from pathlib import Path
from backend.app.core.config import settings

# Load data into store manually
from backend.app.core import store
PROC = settings.processed_dir

store.hotspots = pd.read_parquet(PROC / "hotspots.parquet")
store.temporal = pd.read_parquet(PROC / "temporal.parquet")

from backend.app.services import patrol_optimizer

hs = store.hotspots
total_hotspots = len(hs)
all_hs_ids = set(hs["hotspot_id"].tolist())
print(f"Total hotspots: {total_hotspots}")

for units in [100, 200, 300, 500, 800]:
    result = patrol_optimizer.optimize_patrol(units=units)
    hs_to_units = {}
    for a in result.assignments:
        hs_to_units[a.hotspot_id] = hs_to_units.get(a.hotspot_id, 0) + 1

    real_assigned = all_hs_ids & set(hs_to_units.keys())
    fallback = all_hs_ids - real_assigned

    print(f"\n=== optimize_patrol(units={units}) ===")
    print(f"  Assignments returned: {len(result.assignments)}")
    print(f"  Unique hotspots assigned: {len(real_assigned)}")
    print(f"  Hotspots falling to default=1: {len(fallback)}")
    print(f"  Coverage: {len(real_assigned)}/{total_hotspots} = {len(real_assigned)/total_hotspots*100:.1f}%")

    dist = Counter(hs_to_units.values())
    print(f"  Units distribution (assigned only):")
    for k in sorted(dist.keys()):
        print(f"    {k} units: {dist[k]} hotspots")

    # Check top 20 + top 30
    top30 = hs.nlargest(30, "risk_score")
    top20_real = 0
    top20_fallback = 0
    top30_real = 0
    top30_fallback = 0
    for i, (_, row) in enumerate(top30.iterrows()):
        hid = row["hotspot_id"]
        is_real = hid in real_assigned
        u = hs_to_units.get(hid, 1)
        if i < 20:
            if is_real:
                top20_real += 1
            else:
                top20_fallback += 1
        if is_real:
            top30_real += 1
        else:
            top30_fallback += 1
        tag = "REAL" if is_real else "FALLBACK"
        print(f"  rank {i+1}: {hid} risk={row['risk_score']:.2f} units={u} [{tag}]")

    print(f"\n  TOP 20: {top20_real} real, {top20_fallback} fallback")
    print(f"  TOP 30: {top30_real} real, {top30_fallback} fallback")

    if top30_fallback == 0:
        print(f"\n  >>> ALL TOP 30 have real optimizer values at units={units}. DONE.")
        break
