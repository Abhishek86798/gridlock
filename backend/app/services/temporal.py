"""
Step 2.2 - Temporal analysis: hour x day-of-week violation matrices per hotspot.

Output schema (temporal.parquet, §2.2 of CONTRACTS.md):
  hotspot_id   string   FK -> hotspots.parquet
  hour         int      0-23
  day_of_week  int      0 (Mon) - 6 (Sun)
  count        int      violations in that slot

The matrix is sparse: only non-zero (hour, day_of_week) pairs are stored.
The API's get_temporal() endpoint returns this as-is; missing slots are
implicitly zero and the frontend fills them in the heatmap grid.

Peak-window derivation (also written back to hotspots):
  Top-3 hours by total count define the peak window string
  e.g. "Mon-Fri 08:00-11:00". Written to hotspots.parquet as
  peak_window_detail so the simpler peak_window column stays unchanged.
"""

from __future__ import annotations

from pathlib import Path

import h3
import numpy as np
import pandas as pd

from backend.app.core.config import settings

_DAY_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


# ---- helpers -----------------------------------------------------------------

def _format_peak_window(grp: pd.DataFrame) -> str:
    """Return a human-readable peak window from a per-hotspot temporal group.

    Finds the contiguous hour block that holds the most violations and
    formats it as 'DayRange HH:00-HH:00', e.g. 'Mon-Fri 08:00-11:00'.
    Falls back to the single peak hour if no block is obvious.
    """
    # Aggregate across days to find peak hours
    by_hour = grp.groupby("hour")["count"].sum().sort_values(ascending=False)
    if by_hour.empty:
        return "Unknown"

    peak_hour = int(by_hour.index[0])

    # Find the 3 busiest hours and the days they belong to
    top_hours = sorted(by_hour.head(3).index.tolist())
    hour_start = min(top_hours)
    hour_end   = max(top_hours) + 1   # exclusive end

    # Find which days carry the bulk of that window's load
    window_mask = grp["hour"].between(hour_start, max(top_hours))
    by_day = grp.loc[window_mask].groupby("day_of_week")["count"].sum()
    if by_day.empty:
        return f"{_DAY_ABBR[0]} {peak_hour:02d}:00"

    # Are we weekday-heavy, weekend-heavy, or spread?
    weekday_share = by_day[by_day.index < 5].sum() / by_day.sum()
    if weekday_share >= 0.75:
        day_str = "Mon-Fri"
    elif weekday_share <= 0.25:
        day_str = "Sat-Sun"
    else:
        peak_day = int(by_day.idxmax())
        day_str  = _DAY_ABBR[peak_day]

    return f"{day_str} {hour_start:02d}:00-{hour_end:02d}:00"


# ---- core computation --------------------------------------------------------

def compute_temporal(
    violations: pd.DataFrame,
    hotspots: pd.DataFrame,
    *,
    resolution: int | None = None,
) -> pd.DataFrame:
    """Build the hour x day_of_week count matrix for every hotspot.

    Parameters
    ----------
    violations:
        Processed violations DataFrame (from violations.parquet).
        Must have columns: latitude, longitude, hour, day_of_week.
    hotspots:
        Hotspots DataFrame (from hotspots.parquet).
        Must have columns: hotspot_id, hex_id.
    resolution:
        H3 resolution used during hotspot clustering (default: settings.h3_resolution).

    Returns
    -------
    pd.DataFrame
        Columns: hotspot_id, hour, day_of_week, count.
        Sorted by hotspot_id, day_of_week, hour.
    """
    res = resolution if resolution is not None else settings.h3_resolution

    # Build hex_id -> hotspot_id lookup from the precomputed hotspots.
    hex_to_hs = hotspots.set_index("hex_id")["hotspot_id"].to_dict()

    # Assign each violation to a hotspot via its H3 cell.
    viol = violations.copy()
    viol["hex_id"] = [
        h3.latlng_to_cell(lat, lng, res)
        for lat, lng in zip(viol["latitude"], viol["longitude"])
    ]
    viol["hotspot_id"] = viol["hex_id"].map(hex_to_hs)

    # Keep only violations that map to a known hotspot and have valid temporal data.
    viol = viol.dropna(subset=["hotspot_id", "hour", "day_of_week"])

    # Convert nullable Int8 to plain int so groupby is clean.
    viol["hour"]        = viol["hour"].astype(int)
    viol["day_of_week"] = viol["day_of_week"].astype(int)

    # Sparse matrix: count per (hotspot, hour, day_of_week).
    temporal = (
        viol
        .groupby(["hotspot_id", "hour", "day_of_week"], as_index=False)
        .size()
        .rename(columns={"size": "count"})
    )
    temporal["count"] = temporal["count"].astype(int)

    return temporal.sort_values(
        ["hotspot_id", "day_of_week", "hour"]
    ).reset_index(drop=True)


def enrich_hotspot_logging_windows(
    hotspots: pd.DataFrame,
    temporal: pd.DataFrame,
) -> pd.DataFrame:
    """Enrich logging_window with a richer temporal range derived from the matrix.

    Replaces the simple cluster-level logging_window label (e.g. 'overnight')
    with the top-activity hour block from the full temporal matrix
    (e.g. 'Mon-Fri 08:00-11:00').

    Parameters
    ----------
    hotspots:
        Output of compute_hotspots(); copy returned with logging_window updated.
    temporal:
        Output of compute_temporal().

    Returns
    -------
    pd.DataFrame
        Hotspots with logging_window enriched from the temporal matrix.
    """
    hotspots = hotspots.copy()
    enriched = (
        temporal
        .groupby("hotspot_id")
        .apply(_format_peak_window, include_groups=False)
        .reset_index()
        .rename(columns={0: "logging_window_enriched"})
    )
    hotspots = hotspots.merge(enriched, on="hotspot_id", how="left")
    mask = hotspots["logging_window_enriched"].notna()
    hotspots.loc[mask, "logging_window"] = hotspots.loc[mask, "logging_window_enriched"]
    hotspots = hotspots.drop(columns=["logging_window_enriched"])
    return hotspots


# ---- precompute entry point --------------------------------------------------

def build_temporal_parquet(out_path: Path | None = None) -> pd.DataFrame:
    """Load violations + hotspots, compute temporal matrix, write parquet."""
    viol_path = settings.violations_parquet
    hs_path   = settings.hotspots_parquet

    for p in (viol_path, hs_path):
        if not p.exists():
            raise FileNotFoundError(
                f"{p} not found. Run build_dataset.py then hotspots.py first."
            )

    print(f"Loading violations  : {viol_path}")
    violations = pd.read_parquet(viol_path)
    print(f"  {len(violations):,} rows")

    print(f"Loading hotspots    : {hs_path}")
    hotspots = pd.read_parquet(hs_path)
    print(f"  {len(hotspots):,} hotspots")

    print("Computing temporal matrix ...")
    temporal = compute_temporal(violations, hotspots)

    dest = out_path or settings.temporal_parquet
    dest.parent.mkdir(parents=True, exist_ok=True)
    temporal.to_parquet(dest, index=False, engine="pyarrow")
    size_kb = dest.stat().st_size / 1024
    print(f"Written: {dest}  ({size_kb:.0f} KB)")

    return temporal


# ---- smoke test --------------------------------------------------------------

if __name__ == "__main__":
    temporal = build_temporal_parquet()

    print()
    print(f"Total rows     : {len(temporal):,}")
    print(f"Hotspots cover : {temporal['hotspot_id'].nunique():,}")
    print(f"Avg rows/hs    : {len(temporal) / temporal['hotspot_id'].nunique():.1f}")
    print()
    print("Hour distribution across all hotspots:")
    print(
        temporal.groupby("hour")["count"]
        .sum()
        .sort_index()
        .to_string()
    )
    print()
    print("Day-of-week distribution (0=Mon):")
    print(
        temporal.groupby("day_of_week")["count"]
        .sum()
        .sort_index()
        .to_string()
    )
    print()

    # Show the full matrix for the top hotspot.
    top_hs = (
        temporal.groupby("hotspot_id")["count"]
        .sum()
        .idxmax()
    )
    print(f"Full matrix for busiest hotspot ({top_hs}):")
    subset = temporal[temporal["hotspot_id"] == top_hs].copy()
    pivot  = subset.pivot_table(
        index="hour", columns="day_of_week", values="count", fill_value=0
    )
    pivot.columns = [_DAY_ABBR[d] for d in pivot.columns]
    print(pivot.to_string())
    print()
    print(f"Peak window: {_format_peak_window(subset)}")
