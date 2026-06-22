from __future__ import annotations

import math

import numpy as np
import pandas as pd

from backend.app.core import store
from backend.app.models.schemas import PatrolAssignment, PatrolResponse, CoverageCurvePoint, EscalationItem
from backend.app.services.temporal import _format_peak_window
from backend.app.services import forecast as forecast_service

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


def _haversine_vec(lat1: float, lon1: float, lats: np.ndarray, lngs: np.ndarray) -> np.ndarray:
    """Vectorized haversine: distance from one point to an array of points, in meters."""
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = np.radians(lats)
    dphi = np.radians(lats - lat1)
    dlam = np.radians(lngs - lon1)
    a = np.sin(dphi / 2.0) ** 2 + math.cos(phi1) * np.cos(phi2) * np.sin(dlam / 2.0) ** 2
    return R * 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))


def optimize_patrol(units: int, mode: str = "predictive") -> PatrolResponse:
    """
    Allocate ``units`` patrol units across hotspots.

    mode="predictive" (default): rank hotspots by FUTURE predicted load —
        priority = risk_score * predicted_count, falling back to historical
        violation_count where the forecast has no clean-week signal (so no
        historically-dangerous hotspot goes unstaffed). This closes the loop:
        forecast → allocation, deploying resources against next week's problem.
    mode="historical": rank by past load — priority = risk_score *
        violation_count. Kept as a baseline so the dashboard can show the
        predictive-vs-historical delta (the quantified value of forecasting).
    """
    df = store.hotspots
    tdf = store.temporal
    if df.empty or tdf.empty:
        return PatrolResponse(units=units, coverage_pct=0.0, assignments=[])

    df = df.copy()
    valid_mask = df["violation_count"] >= _MIN_VIOLATION_COUNT

    # Attach per-hotspot predicted_count (next week) from the forecast model.
    # Same quantity get_forecast surfaces, so the two views stay consistent.
    try:
        pred = forecast_service.get_predicted_counts()
        df["predicted_count"] = df["hotspot_id"].map(pred).fillna(0.0)
    except Exception:  # noqa: BLE001 — forecast unavailable: degrade to historical
        df["predicted_count"] = 0.0

    # 1. Compute dispatch score (priority) per mode.
    if mode == "historical":
        df["priority"] = df["risk_score"] * df["violation_count"]
    else:
        # Predictive with historical fallback where predicted_count == 0.
        effective_count = df["predicted_count"].where(
            df["predicted_count"] > 0, df["violation_count"]
        )
        df["priority"] = df["risk_score"] * effective_count

    work_df = df[valid_mask].copy()

    total_priority = work_df["priority"].sum()
    if total_priority == 0:
        return PatrolResponse(units=units, coverage_pct=0.0, assignments=[])

    # Sort descending by priority
    work_df = work_df.sort_values("priority", ascending=False).reset_index(drop=True)

    # Pull arrays once — avoids repeated pandas row access inside the loop
    lats = work_df["lat"].to_numpy()
    lngs = work_df["lng"].to_numpy()
    priorities = work_df["priority"].to_numpy()
    hotspot_ids = work_df["hotspot_id"].to_numpy()
    risk_scores = work_df["risk_score"].to_numpy()
    pred_counts = work_df["predicted_count"].to_numpy()

    # Total predicted load across all eligible hotspots — the denominator for
    # "X of Y predicted violations covered".
    total_predicted_load = float(pred_counts.sum())

    assignments: list[PatrolAssignment] = []
    coverage_curve: list[CoverageCurvePoint] = []
    covered_priority = 0.0
    covered_predicted = 0.0   # sum of predicted_count over covered hotspots
    covered_mask = np.zeros(len(work_df), dtype=bool)

    # 2. Greedy spatial assignment with dynamic temporal window
    unit_id = 1
    for idx in range(len(work_df)):
        if unit_id > units:
            break

        if covered_mask[idx]:
            continue

        # Get dynamic temporal peak window
        hid = hotspot_ids[idx]
        grp = tdf[tdf["hotspot_id"] == hid]
        time_window = _format_peak_window(grp) if not grp.empty else work_df.iloc[idx].get("logging_window", "all_day")

        lat1, lng1 = lats[idx], lngs[idx]
        route = [hid]
        route_geometry = [[lat1, lng1]]

        # 2a. Find up to 4 other high-priority uncovered hotspots within 2km
        dists_to_anchor = _haversine_vec(lat1, lng1, lats, lngs)
        nearby_mask = (dists_to_anchor <= 2000.0) & ~covered_mask
        nearby_mask[idx] = False
        nearby_indices = np.where(nearby_mask)[0]

        # already sorted by priority (work_df is sorted), take top 4
        top_candidates = nearby_indices[:4]

        # 2b. Order the route using greedy Nearest Neighbor
        stops = list(top_candidates)
        current_lat, current_lng = lat1, lng1

        while stops:
            stop_lats = lats[stops]
            stop_lngs = lngs[stops]
            dists = _haversine_vec(current_lat, current_lng, stop_lats, stop_lngs)
            best = int(np.argmin(dists))
            best_idx = stops[best]
            route.append(hotspot_ids[best_idx])
            route_geometry.append([lats[best_idx], lngs[best_idx]])
            current_lat, current_lng = lats[best_idx], lngs[best_idx]
            stops.pop(best)

        # Assign unit to this route
        assignments.append(
            PatrolAssignment(
                unit_id=unit_id,
                hotspot_id=hid,
                time_window=time_window,
                risk_score=float(risk_scores[idx]),
                route=route,
                route_geometry=route_geometry
            )
        )

        # 2c. Mark everything within _COVERAGE_RADIUS_M of ANY route point as covered
        for pt_lat, pt_lng in route_geometry:
            dists_from_pt = _haversine_vec(pt_lat, pt_lng, lats, lngs)
            newly_covered = (dists_from_pt <= _COVERAGE_RADIUS_M) & ~covered_mask
            covered_priority += priorities[newly_covered].sum()
            covered_predicted += pred_counts[newly_covered].sum()
            covered_mask |= newly_covered

        current_cov_pct = round(covered_priority / total_priority * 100, 1)
        coverage_curve.append(CoverageCurvePoint(units=unit_id, coverage_pct=current_cov_pct))

        unit_id += 1

    final_assignments = assignments  # all assignments are already <= units

    if not coverage_curve:
        final_coverage_pct = 0.0
    else:
        final_coverage_pct = coverage_curve[-1].coverage_pct

    # 3. Naive baseline comparison (count-based, top-N, no spatial checks)
    naive_df = df.sort_values("violation_count", ascending=False).head(units)
    naive_covered_priority = (naive_df["risk_score"] * naive_df["violation_count"]).sum()
    naive_coverage_pct = round((naive_covered_priority / total_priority * 100) if total_priority else 0.0, 1)
    
    improvement_pct = round(((final_coverage_pct - naive_coverage_pct) / naive_coverage_pct * 100) if naive_coverage_pct else 0.0, 1)

    # 4. Predictive impact metric — predicted violations covered vs total
    #    predicted load. This is COVERAGE of predicted load, NOT a causal
    #    "prevented" claim (we have no patrol-effectiveness data).
    pct_predicted_covered = round(
        (covered_predicted / total_predicted_load * 100) if total_predicted_load else 0.0, 1
    )

    # 5. Escalation watch — eligible hotspots whose FUTURE load is rising vs
    #    baseline. Dual view: the optimizer covers predicted load (mostly stable
    #    high-volume hotspots), while this list surfaces the few rising ones so
    #    units can pre-position for growth. Each is tagged covered/uncovered by
    #    the current allocation so the gap is actionable.
    covered_ids = set(hotspot_ids[covered_mask].tolist())
    escalation_watch = []
    try:
        esc = forecast_service.get_escalation_frame()
        eligible_ids = set(work_df["hotspot_id"])
        rising = esc[esc["is_escalating"] & esc.index.isin(eligible_ids)]
        rising = rising.sort_values("count_delta", ascending=False)
        station_by_id = work_df.set_index("hotspot_id")["police_station"].to_dict() \
            if "police_station" in work_df.columns else {}
        for hid, r in rising.iterrows():
            escalation_watch.append(EscalationItem(
                hotspot_id=str(hid),
                police_station=station_by_id.get(hid),
                baseline_count=int(r["baseline_count"]),
                predicted_count=float(r["predicted_count"]),
                count_delta=int(r["count_delta"]),
                change_pct=float(r["change_pct"]),
                covered=hid in covered_ids,
            ))
    except Exception:  # noqa: BLE001 — forecast unavailable: empty watch list
        escalation_watch = []

    return PatrolResponse(
        units=units,
        mode=mode,
        coverage_pct=final_coverage_pct,
        naive_coverage_pct=naive_coverage_pct,
        improvement_pct=improvement_pct,
        predicted_violations_covered=round(covered_predicted, 1),
        total_predicted_load=round(total_predicted_load, 1),
        pct_predicted_covered=pct_predicted_covered,
        escalation_watch=escalation_watch,
        assignments=final_assignments,
        coverage_curve=coverage_curve
    )
