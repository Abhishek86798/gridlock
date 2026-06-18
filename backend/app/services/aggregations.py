"""
Step 2.4 - Aggregations: police-station and junction rollups.

All public functions return plain DataFrames so they can be:
  - serialised to JSON by FastAPI endpoints
  - exported to CSV / Excel by the reporting feature
  - merged with other frames for further analysis

Two primary views:
  by_police_station()  - 53-row admin table, one row per station
  by_junction()        - named-junction summary, sorted by risk

Helper:
  violation_stats()    - summary counts that feed the /stats header cards
  export_csv()         - write any aggregation frame to a CSV file

Blind-spot metric:
  afternoon_log_pct < 5%  means the zone has almost no logging after 3 PM.
  96% of hotspots fall into this bucket. The station/junction rollups
  expose this as `blind_spot_pct` so the dashboard can surface which
  *stations* are most affected, not just individual hexes.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from backend.app.core.config import settings

# Threshold below which a hotspot counts as an afternoon blind spot.
BLIND_SPOT_THRESHOLD: float = 5.0


# ── loaders ──────────────────────────────────────────────────────────────────

def _load_hotspots() -> pd.DataFrame:
    return pd.read_parquet(settings.hotspots_parquet)


def _load_violations() -> pd.DataFrame:
    return pd.read_parquet(settings.violations_parquet)


# ── internal helpers ──────────────────────────────────────────────────────────

def _mode(series: pd.Series) -> str:
    """Modal non-null value, or '' if empty."""
    clean = series.dropna()
    return str(clean.mode().iloc[0]) if len(clean) else ""


def _top_hotspot(grp: pd.DataFrame) -> str:
    """hotspot_id with the highest risk_score in the group."""
    idx = grp["risk_score"].idxmax()
    return str(grp.loc[idx, "hotspot_id"])


# ── public rollups ────────────────────────────────────────────────────────────

def by_police_station(
    hotspots: pd.DataFrame | None = None,
    violations: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """One row per police station with hotspot and violation metrics.

    Parameters
    ----------
    hotspots:
        hotspots.parquet DataFrame (loaded automatically if None).
    violations:
        violations.parquet DataFrame (loaded automatically if None).
        Used for raw violation counts and dominant type/vehicle tallies.
        Pass an empty DataFrame to skip violation-level columns.

    Returns
    -------
    pd.DataFrame sorted descending by avg_risk_score.

    Columns
    -------
    police_station       string
    hotspot_count        int    number of H3 hex clusters
    total_violations     int    sum of violation_count across hotspots
    avg_risk_score       float  mean risk score across station hotspots
    max_risk_score       float  peak risk score in station
    top_hotspot_id       string hotspot_id with highest risk in station
    dominant_violation   string most common primary_violation_type (from violations)
    dominant_vehicle     string most common vehicle_type (from violations)
    blind_spot_pct       float  % hotspots with afternoon_log_pct < BLIND_SPOT_THRESHOLD
    junction_hotspot_pct float  % hotspots that have a named junction
    """
    hs  = hotspots  if hotspots  is not None else _load_hotspots()
    vdf = violations if violations is not None else _load_violations()

    # Hotspot-level rollup.
    station_hs = (
        hs.groupby("police_station", as_index=False)
        .apply(
            lambda g: pd.Series({
                "hotspot_count":        len(g),
                "total_violations":     int(g["violation_count"].sum()),
                "avg_risk_score":       round(float(g["risk_score"].mean()), 2),
                "max_risk_score":       round(float(g["risk_score"].max()), 2),
                "top_hotspot_id":       _top_hotspot(g),
                "blind_spot_pct":       round(
                    float((g["afternoon_log_pct"] < BLIND_SPOT_THRESHOLD).mean() * 100), 1
                ),
                "junction_hotspot_pct": round(
                    float(g["junction_name"].notna().mean() * 100), 1
                ),
            }),
            include_groups=False,
        )
        .reset_index(drop=True)
    )

    # Violation-level dominant type/vehicle (richer than hotspot-level mode).
    if len(vdf):
        viol_agg = (
            vdf.groupby("police_station")
            .apply(
                lambda g: pd.Series({
                    "dominant_violation": _mode(g["primary_violation_type"]),
                    "dominant_vehicle":   _mode(g["vehicle_type"]),
                }),
                include_groups=False,
            )
            .reset_index()
        )
        station_hs = station_hs.merge(viol_agg, on="police_station", how="left")
    else:
        station_hs["dominant_violation"] = ""
        station_hs["dominant_vehicle"]   = ""

    return station_hs.sort_values("avg_risk_score", ascending=False).reset_index(drop=True)


def by_junction(
    hotspots: pd.DataFrame | None = None,
    violations: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """One row per named junction, ordered by total violations descending.

    Only junctions that appear in hotspots.parquet are included (i.e. zones
    with at least ``settings.dbscan_min_samples`` violations).

    Columns
    -------
    junction_name        string
    hotspot_count        int
    total_violations     int    summed from hotspots
    avg_risk_score       float
    max_risk_score       float
    top_hotspot_id       string
    dominant_violation   string (from violations if provided)
    police_station       string modal station for this junction
    """
    hs  = hotspots  if hotspots  is not None else _load_hotspots()
    vdf = violations if violations is not None else _load_violations()

    named = hs[hs["junction_name"].notna()].copy()
    if named.empty:
        return pd.DataFrame()

    junc_hs = (
        named.groupby("junction_name", as_index=False)
        .apply(
            lambda g: pd.Series({
                "hotspot_count":    len(g),
                "total_violations": int(g["violation_count"].sum()),
                "avg_risk_score":   round(float(g["risk_score"].mean()), 2),
                "max_risk_score":   round(float(g["risk_score"].max()), 2),
                "top_hotspot_id":   _top_hotspot(g),
                "police_station":   _mode(g["police_station"]),
            }),
            include_groups=False,
        )
        .reset_index(drop=True)
    )

    # Dominant violation from raw violations (richer signal than hotspot modal).
    if len(vdf):
        viol_junc = (
            vdf[vdf["junction_name"].notna()]
            .groupby("junction_name")
            .apply(
                lambda g: pd.Series({
                    "dominant_violation": _mode(g["primary_violation_type"]),
                }),
                include_groups=False,
            )
            .reset_index()
        )
        junc_hs = junc_hs.merge(viol_junc, on="junction_name", how="left")
    else:
        junc_hs["dominant_violation"] = ""

    return junc_hs.sort_values("total_violations", ascending=False).reset_index(drop=True)


def violation_stats(
    violations: pd.DataFrame | None = None,
    hotspots: pd.DataFrame | None = None,
    top_n: int = 20,
) -> dict:
    """Summary counts for the /stats API endpoint and dashboard header cards.

    Returns a plain dict (compatible with StatsResponse Pydantic model).

    Keys
    ----
    total_violations     int
    total_hotspots       int
    date_range           dict  {start: str, end: str}
    by_vehicle_type      dict  vehicle -> count  (top_n)
    by_violation_type    dict  type -> count      (top_n)
    by_police_station    dict  station -> count   (top_n)
    """
    vdf = violations if violations is not None else _load_violations()
    hs  = hotspots   if hotspots  is not None else _load_hotspots()

    # Date range from IST-converted datetime.
    dt_col = "created_ist" if "created_ist" in vdf.columns else "created_datetime"
    dates  = vdf[dt_col].dropna()
    date_range = {
        "start": str(dates.min().date()) if len(dates) else "unknown",
        "end":   str(dates.max().date()) if len(dates) else "unknown",
    }

    # violation_type is stored as a JSON string (list); use primary_violation_type.
    vt_counts = (
        vdf["primary_violation_type"]
        .dropna()
        .value_counts()
        .head(top_n)
        .to_dict()
    )

    return {
        "total_violations":   int(len(vdf)),
        "total_hotspots":     int(len(hs)),
        "date_range":         date_range,
        "by_vehicle_type":    vdf["vehicle_type"].value_counts().head(top_n).to_dict(),
        "by_violation_type":  vt_counts,
        "by_police_station":  vdf["police_station"].value_counts().head(top_n).to_dict(),
    }


# ── export helper ─────────────────────────────────────────────────────────────

def export_csv(df: pd.DataFrame, filename: str, dest_dir: Path | None = None) -> Path:
    """Write an aggregation DataFrame to a CSV file.

    Parameters
    ----------
    df:
        Any aggregation result from this module.
    filename:
        Base filename without extension (e.g. 'by_station').
    dest_dir:
        Directory to write into (defaults to settings.processed_dir).

    Returns
    -------
    Path to the written file.
    """
    out_dir  = dest_dir or settings.processed_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{filename}.csv"
    df.to_csv(out_path, index=False)
    return out_path


# ── smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Loading parquets ...")
    hs   = _load_hotspots()
    viol = _load_violations()

    print()
    print("=== by_police_station (top 10 by avg_risk) ===")
    st = by_police_station(hs, viol)
    print(st.head(10).to_string(index=False))
    print(f"\n  Stations: {len(st)}")
    print(f"  Blind-spot pct (city avg): {st['blind_spot_pct'].mean():.1f}%")
    worst_blind = st.nlargest(3, "blind_spot_pct")[["police_station", "blind_spot_pct", "hotspot_count"]]
    print(f"  Worst blind-spot stations:\n{worst_blind.to_string(index=False)}")

    print()
    print("=== by_junction (top 15 by total_violations) ===")
    jn = by_junction(hs, viol)
    print(jn.head(15).to_string(index=False))
    print(f"\n  Named junctions: {len(jn)}")

    print()
    print("=== violation_stats ===")
    stats = violation_stats(viol, hs)
    print(f"  total_violations  : {stats['total_violations']:,}")
    print(f"  total_hotspots    : {stats['total_hotspots']:,}")
    print(f"  date_range        : {stats['date_range']}")
    print(f"  top vehicle types : {dict(list(stats['by_vehicle_type'].items())[:5])}")
    print(f"  top violation types: {dict(list(stats['by_violation_type'].items())[:5])}")

    print()
    print("=== Exporting CSVs ===")
    p1 = export_csv(st, "by_station", settings.processed_dir / "exports")
    p2 = export_csv(jn, "by_junction", settings.processed_dir / "exports")
    print(f"  {p1}")
    print(f"  {p2}")
