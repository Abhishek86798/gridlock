from __future__ import annotations

import math

import pandas as pd

from backend.app.core import store
from backend.app.models.schemas import PatrolAssignment, PatrolResponse, CoverageCurvePoint
from backend.app.services.temporal import _format_peak_window

# Minimum violations needed to be considered for a patrol assignment
_MIN_VIOLATION_COUNT = 20

# Coverage radius in meters. Hotspots within this radius of an assigned unit
# are considered "covered", preventing units from bunching up.
_COVERAGE_RADIUS_M = 1000.0


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance between two points in meters."""
    R = 6371000  # radius of Earth in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def optimize_patrol(units: int) -> PatrolResponse:
    df = store.hotspots
    tdf = store.temporal
    if df.empty or tdf.empty:
        return PatrolResponse(units=units, coverage_pct=0.0, assignments=[])

    # 1. Compute dispatch score (priority)
    scores = df["risk_score"] * df["violation_count"]
    valid_mask = df["violation_count"] >= _MIN_VIOLATION_COUNT
    
    work_df = df[valid_mask].copy()
    work_df["priority"] = scores[valid_mask]
    
    total_priority = work_df["priority"].sum()
    if total_priority == 0:
        return PatrolResponse(units=units, coverage_pct=0.0, assignments=[])

    # Sort descending by priority
    work_df = work_df.sort_values("priority", ascending=False).reset_index(drop=True)
    
    assignments: list[PatrolAssignment] = []
    coverage_curve: list[CoverageCurvePoint] = []
    covered_priority = 0.0
    covered_indices = set()
    
    # 2. Greedy spatial assignment with dynamic temporal window
    unit_id = 1
    max_units = max(units, 100)  # compute curve
    for idx, row in work_df.iterrows():
        if unit_id > max_units:
            break
            
        if idx in covered_indices:
            continue
            
        # Get dynamic temporal peak window
        hid = row["hotspot_id"]
        grp = tdf[tdf["hotspot_id"] == hid]
        time_window = _format_peak_window(grp) if not grp.empty else row.get("logging_window", "all_day")
            
        # Assign unit to this hotspot
        assignments.append(
            PatrolAssignment(
                unit_id=unit_id,
                hotspot_id=hid,
                time_window=time_window,
                risk_score=row["risk_score"]
            )
        )
        
        # Mark this hotspot and nearby ones as covered
        lat1, lng1 = row["lat"], row["lng"]
        
        for check_idx, check_row in work_df.iterrows():
            if check_idx in covered_indices:
                continue
                
            lat2, lng2 = check_row["lat"], check_row["lng"]
            dist = _haversine(lat1, lng1, lat2, lng2)
            
            if dist <= _COVERAGE_RADIUS_M:
                covered_indices.add(check_idx)
                covered_priority += check_row["priority"]
        
        current_cov_pct = round(covered_priority / total_priority * 100, 1)
        coverage_curve.append(CoverageCurvePoint(units=unit_id, coverage_pct=current_cov_pct))
        
        unit_id += 1

    final_assignments = [a for a in assignments if a.unit_id <= units]
    
    if not coverage_curve:
        final_coverage_pct = 0.0
    else:
        exact_match = [c.coverage_pct for c in coverage_curve if c.units == units]
        final_coverage_pct = exact_match[0] if exact_match else coverage_curve[-1].coverage_pct

    # 3. Naive baseline comparison (count-based, top-N, no spatial checks)
    naive_df = df.sort_values("violation_count", ascending=False).head(units)
    naive_covered_priority = (naive_df["risk_score"] * naive_df["violation_count"]).sum()
    naive_coverage_pct = round((naive_covered_priority / total_priority * 100) if total_priority else 0.0, 1)
    
    improvement_pct = round(((final_coverage_pct - naive_coverage_pct) / naive_coverage_pct * 100) if naive_coverage_pct else 0.0, 1)

    return PatrolResponse(
        units=units,
        coverage_pct=final_coverage_pct,
        naive_coverage_pct=naive_coverage_pct,
        improvement_pct=improvement_pct,
        assignments=final_assignments,
        coverage_curve=coverage_curve
    )
