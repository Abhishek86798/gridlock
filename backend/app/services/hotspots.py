"""
Step 2.1 — Hotspot detection: H3 hexbin clustering.

Risk scoring is delegated to risk_score.py (see that module for the
formula documentation).

Why H3 instead of DBSCAN:
  DBSCAN on the raw violations table creates mega-clusters because fixed
  enforcement cameras stack thousands of violations at identical coordinates.
  At any useful eps (~100-200 m) one cluster absorbs 50-60% of all rows.
  H3 hexbins partition the city into a fixed equal-area grid (res=9 ~174 m
  edge), which gives consistent, comparable zones regardless of camera density.

Logging-window vs enforcement-peak note:
  created_datetime reflects when officers *logged* a violation, not when
  the vehicle was parked. BTP logs are morning-concentrated (06-12 IST);
  afternoon/evening coverage is sparse across the city. This module
  therefore computes logging coverage metrics rather than claiming to
  identify peak parking hours:
    morning_log_pct    % of logs in 06:00-11:59 IST
    afternoon_log_pct  % of logs in 15:00-20:59 IST (blind-spot indicator)
    logging_window     dominant logging band label
"""

from __future__ import annotations

from pathlib import Path

import h3
import pandas as pd

from backend.app.core.config import settings
from backend.app.services.poi_tagging import tag_hotspots as _tag_hotspots
from backend.app.services.risk_score import compute_risk_scores


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mode_str(series: pd.Series) -> str:
    """Modal string value; returns '' when series is empty or all-null."""
    clean = series.dropna()
    return str(clean.mode().iloc[0]) if len(clean) else ""


def _top_junction(grp: pd.DataFrame) -> str | None:
    """Most common named junction in cluster, or None."""
    named = grp.loc[grp["has_junction"].astype(bool), "junction_name"].dropna()
    if named.empty:
        return None
    return str(named.mode().iloc[0])


_MORNING_HOURS   = set(range(6, 12))    # 06:00-11:59 — main patrol window
_AFTERNOON_HOURS = set(range(15, 21))   # 15:00-20:59 — typical blind spot


def _log_coverage(grp: pd.DataFrame) -> tuple[float, float, str]:
    """Compute logging-coverage metrics for one hotspot cluster.

    Returns
    -------
    morning_log_pct : float
        Percentage of violations logged 06:00-11:59 IST.
    afternoon_log_pct : float
        Percentage of violations logged 15:00-20:59 IST.
    logging_window : str
        Dominant logging band: 'morning', 'overnight', 'split', or 'afternoon'.
    """
    hours = grp["hour"].dropna().astype(int)
    n = len(hours)
    if n == 0:
        return 0.0, 0.0, "unknown"

    morning_pct   = hours.isin(_MORNING_HOURS).sum()   / n * 100
    afternoon_pct = hours.isin(_AFTERNOON_HOURS).sum() / n * 100

    if morning_pct >= 50:
        label = "morning"
    elif morning_pct + afternoon_pct >= 60:
        label = "split"
    elif afternoon_pct >= 30:
        label = "afternoon"
    else:
        label = "overnight"

    return round(morning_pct, 1), round(afternoon_pct, 1), label


# ── Core computation ──────────────────────────────────────────────────────────

def compute_hotspots(
    df: pd.DataFrame,
    *,
    resolution: int | None = None,
    min_violations: int | None = None,
) -> pd.DataFrame:
    """Cluster violations into hotspots using H3 hexbins and score each one.

    Parameters
    ----------
    df:
        Output of ``build_features(clean_violations(load_violations()))``, or
        the processed violations parquet loaded into a DataFrame.
    resolution:
        H3 resolution (default: ``settings.h3_resolution`` = 9, ~174 m edge).
    min_violations:
        Drop cells below this count (default: ``settings.dbscan_min_samples``).

    Returns
    -------
    pd.DataFrame
        One row per hotspot, columns matching the ``Hotspot`` Pydantic schema
        plus diagnostic columns (``hex_id``, ``rank``, score components).
        Sorted descending by ``risk_score``.
    """
    res = resolution if resolution is not None else settings.h3_resolution
    min_v = min_violations if min_violations is not None else settings.dbscan_min_samples

    # Assign each violation to an H3 cell.
    df = df.copy()
    df["hex_id"] = [
        h3.geo_to_h3(lat, lng, res)
        for lat, lng in zip(df["latitude"], df["longitude"])
    ]

    rows: list[dict] = []
    for hex_id, grp in df.groupby("hex_id"):
        if len(grp) < min_v:
            continue

        # Centroid from H3 (not arithmetic mean — avoids camera-stack bias).
        clat, clng = h3.h3_to_geo(hex_id)

        # Risk score inputs (density + final score applied after the loop).
        sev_agg  = float(grp["severity_score"].mean())
        veh_agg  = float(grp["vehicle_score"].mean())
        junc_pct = float(grp["has_junction"].astype(float).mean())
        j_input  = settings.junction_bonus_value if junc_pct >= 0.5 else 0.0

        # Logging coverage (replaces misleading "peak_window").
        morning_pct, afternoon_pct, log_window = _log_coverage(grp)

        rows.append({
            "hex_id":              hex_id,
            "lat":                 clat,
            "lng":                 clng,
            "violation_count":     len(grp),
            "severity_score_agg":  sev_agg,
            "vehicle_score_agg":   veh_agg,
            "junction_pct":        junc_pct,
            "junction_input":      j_input,
            "morning_log_pct":     morning_pct,
            "afternoon_log_pct":   afternoon_pct,
            "logging_window":      log_window,
            "dominant_violation":  _mode_str(grp["primary_violation_type"]),
            "dominant_vehicle":    _mode_str(grp["vehicle_type"]),
            "police_station":      _mode_str(grp["police_station"]),
            "junction_name":       _top_junction(grp),
            "near_poi":            None,   # filled by tag_hotspots() below
        })

    hotspots = pd.DataFrame(rows)

    # Density + risk score via the documented formula in risk_score.py.
    hotspots = compute_risk_scores(hotspots)

    # POI / spillover tagging — keyword-match location text per hexcell.
    # `df` still carries the hex_id column assigned earlier in this function.
    hotspots = _tag_hotspots(df, hotspots)

    # Rank descending by risk_score, assign stable string IDs.
    hotspots = (
        hotspots
        .sort_values("risk_score", ascending=False)
        .reset_index(drop=True)
    )
    hotspots.insert(0, "hotspot_id", [f"HS-{i+1:04d}" for i in range(len(hotspots))])
    hotspots["rank"] = range(1, len(hotspots) + 1)

    return hotspots


# ── Precompute entry point ────────────────────────────────────────────────────

def build_hotspots_parquet(out_path: Path | None = None) -> pd.DataFrame:
    """Load violations.parquet, cluster, write hotspots.parquet."""
    viol_path = settings.violations_parquet
    if not viol_path.exists():
        raise FileNotFoundError(
            f"violations.parquet not found at {viol_path}. "
            "Run `python -m backend.pipeline.build_dataset` first."
        )

    print(f"Loading {viol_path} ...")
    df = pd.read_parquet(viol_path)
    print(f"  {len(df):,} rows loaded")

    print(f"Clustering at H3 resolution {settings.h3_resolution} ...")
    hotspots = compute_hotspots(df)
    print(f"  {len(hotspots):,} hotspots  "
          f"(noise / sub-threshold rows excluded)")

    dest = out_path or settings.hotspots_parquet
    dest.parent.mkdir(parents=True, exist_ok=True)
    hotspots.to_parquet(dest, index=False, engine="pyarrow")
    size_mb = dest.stat().st_size / 1_048_576
    print(f"Written: {dest}  ({size_mb:.2f} MB)")

    return hotspots


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    hs = build_hotspots_parquet()

    print()
    print(f"Total hotspots : {len(hs):,}")
    print(f"risk_score     : min={hs['risk_score'].min():.1f}  "
          f"mean={hs['risk_score'].mean():.1f}  "
          f"max={hs['risk_score'].max():.1f}")
    print()
    print("Top 15 hotspots:")
    cols = ["hotspot_id", "violation_count", "risk_score",
            "dominant_violation", "police_station",
            "logging_window", "morning_log_pct", "afternoon_log_pct"]
    print(hs[cols].head(15).to_string(index=False))
    print()
    print("Score component means:")
    for c in ["severity_score_agg", "density_score", "vehicle_score_agg", "junction_pct"]:
        print(f"  {c:<24} {hs[c].mean():.2f}")
    print()
    print("Logging coverage:")
    print(f"  morning_log_pct mean    : {hs['morning_log_pct'].mean():.1f}%")
    print(f"  afternoon_log_pct mean  : {hs['afternoon_log_pct'].mean():.1f}%")
    print(f"  logging_window counts:")
    print(hs["logging_window"].value_counts().to_string())
    print()
    print("Hotspots per police station (top 8):")
    print(hs["police_station"].value_counts().head(8).to_string())
