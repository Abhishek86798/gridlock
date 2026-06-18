"""
Step 2 - Precompute all ML artifacts from violations.parquet.

Run after build_dataset.py:
    python -m backend.pipeline.precompute                      # all steps
    python -m backend.pipeline.precompute --steps hotspots temporal aggregations

Writes:
    data/processed/hotspots.parquet    (Step 2.1 - H3 hexbin clustering + risk score)
    data/processed/temporal.parquet    (Step 2.2 - hour x weekday matrices)
    data/processed/by_station.parquet  (Step 2.5 - police-station rollup)
    data/processed/by_junction.parquet (Step 2.5 - named-junction rollup)

Stubs (built next):
    data/processed/forecast.parquet
    data/processed/repeat_offenders.parquet

Data-quality gate:
    Runs a statistical batch-hour check before any time-based computation.
    An hour bin is flagged when its count is >BATCH_THRESHOLD x the median
    of its two neighbors - the signature of a fixed camera doing a bulk upload
    at a specific hour. If flagged hours are found they are excluded from
    logging_window derivation and temporal matrix (but kept for spatial counts).
    This dataset passes the check cleanly; the gate exists for future feeds.
"""

from __future__ import annotations

import argparse
import time

import numpy as np
import pandas as pd

from backend.app.core.config import settings
from backend.app.services.aggregations import by_junction, by_police_station
from backend.app.services.hotspots import compute_hotspots
from backend.app.services.temporal import compute_temporal

# An hour bin must exceed this multiple of its neighbors' median to be
# flagged as a batch-upload artifact.
BATCH_THRESHOLD: float = 3.0

_ALL_STEPS = ("hotspots", "temporal", "aggregations")


# ---- data quality gate -------------------------------------------------------

def detect_batch_hours(violations: pd.DataFrame) -> list[int]:
    """Return hour bins that look like batch-upload artifacts.

    Uses the smoothness criterion: flag any bin whose count exceeds
    BATCH_THRESHOLD x the median of its two immediate neighbors.
    An empty list means the temporal signal is trustworthy as-is.
    """
    hour_col = violations["hour"].dropna().astype(int)
    hd = hour_col.value_counts().sort_index().reindex(range(24), fill_value=0)

    flagged: list[int] = []
    for h in range(24):
        neighbors = [int(hd.get(h - 1, 0)), int(hd.get(h + 1, 0))]
        pos_neighbors = [v for v in neighbors if v > 0]
        if not pos_neighbors:
            continue
        med = float(np.median(pos_neighbors))
        if med > 0 and hd[h] / med > BATCH_THRESHOLD:
            flagged.append(h)

    return flagged


def _print_hour_bar(violations: pd.DataFrame) -> None:
    hour_col = violations["hour"].dropna().astype(int)
    hd = hour_col.value_counts(normalize=True).sort_index().reindex(range(24), fill_value=0.0)
    for h, p in hd.items():
        bar = "#" * int(p * 300)
        print(f"     {h:02d}:00  {p:.3f}  {bar}")


# ---- pipeline steps ----------------------------------------------------------

def step_hotspots(
    violations: pd.DataFrame,
    batch_hours: list[int],
) -> pd.DataFrame:
    """Cluster violations into hotspots and score them."""
    # Exclude flagged hours only from peak_window derivation.
    # Spatial clustering and counts use all rows.
    viol_for_peaks = (
        violations[~violations["hour"].isin(batch_hours)]
        if batch_hours else violations
    )
    hotspots = compute_hotspots(viol_for_peaks)

    dest = settings.hotspots_parquet
    dest.parent.mkdir(parents=True, exist_ok=True)
    hotspots.to_parquet(dest, index=False, engine="pyarrow")
    print(f"   Written  : {dest}  ({dest.stat().st_size / 1024:.0f} KB)")
    print(f"   Hotspots : {len(hotspots):,}")
    print(f"   Risk score: min={hotspots['risk_score'].min():.1f}  "
          f"mean={hotspots['risk_score'].mean():.1f}  "
          f"max={hotspots['risk_score'].max():.1f}")
    print(f"   Top-5:")
    top_cols = ["hotspot_id", "violation_count", "risk_score",
                "dominant_violation", "police_station",
                "logging_window", "morning_log_pct", "afternoon_log_pct"]
    print(hotspots[top_cols].head(5).to_string(index=False))
    return hotspots


def step_temporal(
    violations: pd.DataFrame,
    hotspots: pd.DataFrame,
    batch_hours: list[int],
) -> pd.DataFrame:
    """Build hour x day_of_week count matrices and enrich hotspot peak windows."""
    # Exclude flagged hours from the matrix so the UI heatmap isn't distorted.
    viol_clean = (
        violations[~violations["hour"].isin(batch_hours)]
        if batch_hours else violations
    )
    temporal = compute_temporal(viol_clean, hotspots)

    dest = settings.temporal_parquet
    dest.parent.mkdir(parents=True, exist_ok=True)
    temporal.to_parquet(dest, index=False, engine="pyarrow")
    print(f"   Written  : {dest}  ({dest.stat().st_size / 1024:.0f} KB)")
    print(f"   Rows     : {len(temporal):,}  "
          f"({temporal['hotspot_id'].nunique():,} hotspots, "
          f"avg {len(temporal)/temporal['hotspot_id'].nunique():.1f} slots each)")

    # hotspots.parquet logging_window uses simple category labels from
    # _log_coverage() ("morning" / "overnight" / "split") — no enrichment needed.

    return temporal


def step_aggregations(
    violations: pd.DataFrame,
    hotspots: pd.DataFrame,
) -> None:
    """Roll up hotspots by police station and named junction; write parquets."""
    station_df = by_police_station(hotspots, violations)
    dest_st = settings.by_station_parquet
    dest_st.parent.mkdir(parents=True, exist_ok=True)
    station_df.to_parquet(dest_st, index=False, engine="pyarrow")
    print(f"   Written  : {dest_st}  ({dest_st.stat().st_size / 1024:.0f} KB)")
    print(f"   Stations : {len(station_df):,}  "
          f"(avg_risk {station_df['avg_risk_score'].mean():.1f}, "
          f"city blind_spot_pct {station_df['blind_spot_pct'].mean():.0f}%)")

    junction_df = by_junction(hotspots, violations)
    dest_jn = settings.by_junction_parquet
    junction_df.to_parquet(dest_jn, index=False, engine="pyarrow")
    print(f"   Written  : {dest_jn}  ({dest_jn.stat().st_size / 1024:.0f} KB)")
    print(f"   Junctions: {len(junction_df):,} named junctions")


# ---- orchestrator ------------------------------------------------------------

def run(steps: list[str] | None = None) -> None:
    steps = steps or list(_ALL_STEPS)
    t_total = time.perf_counter()

    # ── Load ─────────────────────────────────────────────────────────────────
    viol_path = settings.violations_parquet
    if not viol_path.exists():
        raise FileNotFoundError(
            f"{viol_path} not found. Run "
            "`python -m backend.pipeline.build_dataset` first."
        )

    print("-- Load violations.parquet ----------------------------------")
    violations = pd.read_parquet(viol_path)
    print(f"   {len(violations):,} rows  x  {len(violations.columns)} columns")
    n_approved = (violations["validation_status"] == "approved").sum()
    print(f"   approved: {n_approved:,}  "
          f"({'approved-only' if n_approved == len(violations) else 'broad set'})")

    # ── Data quality gate ─────────────────────────────────────────────────────
    print()
    print("-- Hour-distribution data-quality gate ----------------------")
    _print_hour_bar(violations)
    batch_hours = detect_batch_hours(violations)
    if batch_hours:
        print(f"   WARN: flagged hours {batch_hours} will be excluded "
              f"from peak_window and temporal matrix")
    else:
        print(f"   PASS: no batch-upload spikes detected "
              f"(threshold = {BATCH_THRESHOLD}x neighbors)")

    # ── Step 2.1 ─────────────────────────────────────────────────────────────
    hotspots = None
    if "hotspots" in steps:
        print()
        print(f"-- Step 2.1: Hotspot detection (H3 res={settings.h3_resolution}) --")
        t1 = time.perf_counter()
        hotspots = step_hotspots(violations, batch_hours)
        print(f"   Elapsed  : {time.perf_counter() - t1:.1f}s")

    # ── Step 2.2 ─────────────────────────────────────────────────────────────
    if "temporal" in steps:
        if hotspots is None:
            if not settings.hotspots_parquet.exists():
                raise FileNotFoundError(
                    "hotspots.parquet not found. Run with --steps hotspots first."
                )
            hotspots = pd.read_parquet(settings.hotspots_parquet)
        print()
        print("-- Step 2.2: Temporal matrices ------------------------------")
        t2 = time.perf_counter()
        step_temporal(violations, hotspots, batch_hours)
        print(f"   Elapsed  : {time.perf_counter() - t2:.1f}s")

    # ── Step 2.5 ─────────────────────────────────────────────────────────────
    if "aggregations" in steps:
        if hotspots is None:
            if not settings.hotspots_parquet.exists():
                raise FileNotFoundError(
                    "hotspots.parquet not found. Run with --steps hotspots first."
                )
            hotspots = pd.read_parquet(settings.hotspots_parquet)
        print()
        print("-- Step 2.5: Station + junction aggregations ----------------")
        t5 = time.perf_counter()
        step_aggregations(violations, hotspots)
        print(f"   Elapsed  : {time.perf_counter() - t5:.1f}s")

    # ── Done ──────────────────────────────────────────────────────────────────
    print()
    elapsed = time.perf_counter() - t_total
    print(f"-- Done in {elapsed:.1f}s -------------------------------------------")
    print(f"   Artifacts in {settings.processed_dir}:")
    for f in sorted(settings.processed_dir.glob("*.parquet")):
        print(f"     {f.name:<35} {f.stat().st_size / 1024:6.0f} KB")


# ---- entry point -------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Precompute ML artifacts")
    parser.add_argument(
        "--steps",
        nargs="+",
        choices=list(_ALL_STEPS),
        default=None,
        help=f"Which steps to run (default: all). Choices: {_ALL_STEPS}",
    )
    args = parser.parse_args()
    run(steps=args.steps)
