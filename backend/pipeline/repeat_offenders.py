"""
Step 2.6 — Repeat-offender intelligence from violations.parquet.

Signals computed per vehicle (groupby vehicle_number):
    total_violations      total rows
    active_days           days between first and last violation
    frequency             violations per active day (0 if single day)
    avg_days_between      mean interval between consecutive violations (vectorized)
    violation_diversity   distinct primary_violation_type values
    distinct_hotspots     distinct hotspot_id values (via H3 join)
    distinct_locations    distinct police_station values
    top_location          most frequent police_station
    top_hotspot           most frequent hotspot_id
    first_seen / last_seen

Writes: data/processed/repeat_offenders.parquet
Only vehicles with >= MIN_VIOLATIONS are included.
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

from backend.app.core.config import settings

MIN_VIOLATIONS = 3
# A repeat offender must offend across more than a single day — this filters
# out one-day enforcement-drive bursts (3 tickets in <1 day) whose
# frequency = violations/active_days explodes and pollutes the clusters.
MIN_ACTIVE_DAYS = 7


def _attach_hotspot_id(vdf: pd.DataFrame, hdf: pd.DataFrame) -> pd.DataFrame:
    """
    Map each violation row to a hotspot_id via H3 hex lookup.
    Rows that don't fall in any known hotspot cell are left with hotspot_id=NaN.
    Uses the same logic as forecast._assign_hotspot_ids.
    """
    import h3
    res = settings.h3_resolution
    # Map lat/lng → H3 cell → hotspot_id as a column (no index join — an
    # index-aligned join would silently fan-out rows if vdf's index is
    # non-unique, inflating total_violations). Mirrors forecast._assign_hotspot_ids
    # but keeps rows outside any hotspot (hotspot_id stays NaN) so we don't
    # drop those vehicles' other signals.
    out = vdf.copy()
    # object dtype: hotspot_id values are strings ("HS-0267"); a float64 init
    # would raise the incompatible-dtype FutureWarning on assignment.
    out["hotspot_id"] = pd.Series(pd.NA, index=out.index, dtype="object")
    mask = out["latitude"].notna() & out["longitude"].notna()
    hexes = [
        h3.latlng_to_cell(lat, lng, res)
        for lat, lng in zip(out.loc[mask, "latitude"], out.loc[mask, "longitude"])
    ]
    hex_to_hs = hdf.set_index("hex_id")["hotspot_id"]
    out.loc[mask, "hotspot_id"] = pd.Series(hexes, index=out.loc[mask].index).map(hex_to_hs)
    return out


def _vectorized_avg_gap(df: pd.DataFrame) -> pd.Series:
    """
    Compute mean days between consecutive violations per vehicle — fully vectorized.

    Sort all rows by (vehicle_number, created_ist), compute diff within each
    vehicle group using shift, then groupby-mean. No apply(), no Python loop.
    """
    df_s = df[["vehicle_number", "created_ist"]].sort_values(
        ["vehicle_number", "created_ist"]
    )
    # Days since previous row; first row per vehicle becomes NaT after diff.
    # Use total_seconds()/86400 to preserve sub-day intervals — .dt.days would
    # truncate a 9h gap to 0 and make intra-day repeaters look more habitual.
    gap = df_s.groupby("vehicle_number")["created_ist"].diff()
    df_s["_gap"] = gap.dt.total_seconds() / 86400
    # mean per vehicle (NaN for single-violation vehicles stays NaN)
    return df_s.groupby("vehicle_number")["_gap"].mean().round(2).rename("avg_days_between")


# ── Step 2: K-Means tiering ───────────────────────────────────────────────────

# Signals fed to the clustering model — the three BEHAVIOURAL axes that carry
# real separation: how much, how often, how recently. violation_diversity and
# distinct_hotspots are deliberately EXCLUDED: at k=3/4 they outvoted cadence
# 2-to-1 and produced a spurious "spatial" cluster (two tiers identical on
# volume/frequency/gap, split only by diversity). They remain descriptive
# columns on each offender, just not cluster drivers.
CLUSTER_FEATURES = [
    "total_violations",
    "frequency",
    "avg_days_between",
]
# Ordered tiers, least → most concerning. k=3 chosen over k=4 because at k=4
# two clusters were near-duplicates on every strong signal (total_violations,
# frequency, gap), split only by the weakest feature (diversity/hotspots) —
# they read as copy-paste rows. Three tiers are each visibly distinct.
TIER_LABELS = ["Occasional", "Frequent", "Habitual"]
RANDOM_STATE = 42


def assign_tiers(out: pd.DataFrame, k: int = 3) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Cluster offenders on standardized behavioural signals, then rank the k
    clusters into ordered tiers (Occasional → Habitual).

    Returns (out_with_tier, centroids) where centroids is the cluster centres
    in real units (inverse-transformed) — the judge-facing "what is a Habitual
    offender" table.

    Design notes:
      - StandardScaler is mandatory: total_violations spans 0..hundreds while
        frequency is 0..~0.4. Without scaling, Euclidean K-Means just bins on
        total_violations and the multi-signal story collapses to a threshold.
      - avg_days_between is NaN for vehicles whose violations all share one
        timestamp. We impute with the cohort max gap — "longest possible
        interval" = least habitual — rather than dropping the vehicle.
      - K-Means returns unordered clusters; we rank centroids by a habituality
        score (high frequency + diversity + hotspots, low gap) to map them onto
        the ordered tier labels. Never assume cluster 0 == Low.
    """
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler

    feats = out[CLUSTER_FEATURES].copy()
    # Impute avg_days_between NaNs with the cohort max (least habitual).
    max_gap = feats["avg_days_between"].max()
    feats["avg_days_between"] = feats["avg_days_between"].fillna(max_gap)
    # Any other accidental NaN (e.g. distinct_hotspots) → 0.
    feats = feats.fillna(0.0)

    scaler = StandardScaler()
    X = scaler.fit_transform(feats)

    km = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10)
    labels = km.fit_predict(X)

    # Centroids back in real units for ranking + display.
    centers = pd.DataFrame(
        scaler.inverse_transform(km.cluster_centers_),
        columns=CLUSTER_FEATURES,
    )
    # Habituality score: more violations + higher frequency + SHORTER gaps ==
    # more habitual. Normalize each column 0..1 within the centroid set so no
    # single feature dominates the ranking. Only the three clustering axes feed
    # the score (diversity/hotspots are descriptive, not severity drivers).
    norm = (centers - centers.min()) / (centers.max() - centers.min()).replace(0, 1)
    habituality = (
        norm["total_violations"]
        + norm["frequency"]
        + (1.0 - norm["avg_days_between"])   # shorter gap = more habitual
    )
    # Rank clusters ascending → tier label; lowest score = Low, highest = Habitual.
    order = habituality.sort_values().index.tolist()
    cluster_to_tier = {cluster: TIER_LABELS[rank] for rank, cluster in enumerate(order)}

    out = out.copy()
    out["risk_tier"] = pd.Series(labels, index=out.index).map(cluster_to_tier)

    centers["risk_tier"] = [cluster_to_tier[i] for i in range(k)]
    centers["habituality_score"] = habituality.round(3).values
    centers = centers.sort_values("habituality_score").reset_index(drop=True)
    return out, centers


def build_repeat_offenders(vdf: pd.DataFrame, hdf: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Compute per-vehicle behavioural signals.
    hdf (hotspots DataFrame) is used for the H3 hotspot_id join.
    Returns one row per repeat offender sorted by total_violations desc.
    """
    required = {"vehicle_number", "created_ist", "primary_violation_type"}
    missing = required - set(vdf.columns)
    if missing:
        raise ValueError(f"violations DataFrame missing columns: {missing}")

    df = vdf.dropna(subset=["vehicle_number", "created_ist"]).copy()
    df["created_ist"] = pd.to_datetime(df["created_ist"], utc=False, errors="coerce")
    df = df.dropna(subset=["created_ist"])

    # Attach hotspot_id via H3 if hotspots available and not already present
    if "hotspot_id" not in df.columns and hdf is not None and "hex_id" in hdf.columns:
        print("   Joining hotspot_id via H3 hex lookup...")
        df = _attach_hotspot_id(df, hdf)

    # ── Vectorized avg gap ────────────────────────────────────────────────────
    avg_gap = _vectorized_avg_gap(df)

    # ── All other signals — single groupby pass ───────────────────────────────
    grp = df.groupby("vehicle_number")

    agg = grp.agg(
        total_violations=("vehicle_number", "size"),
        first_seen=("created_ist", "min"),
        last_seen=("created_ist", "max"),
        violation_diversity=("primary_violation_type", "nunique"),
        distinct_locations=("police_station", "nunique") if "police_station" in df.columns else ("vehicle_number", "size"),
    )

    if "hotspot_id" in df.columns:
        agg["distinct_hotspots"] = grp["hotspot_id"].nunique()
        agg["top_hotspot"] = grp["hotspot_id"].agg(
            lambda x: x.value_counts().index[0] if x.notna().any() else None
        )
    else:
        agg["distinct_hotspots"] = 0
        agg["top_hotspot"] = None

    if "police_station" in df.columns:
        agg["top_location"] = grp["police_station"].agg(
            lambda x: x.value_counts().index[0]
        )
    else:
        agg["top_location"] = "Unknown"

    # active_days and frequency derived from first/last seen
    agg["active_days"] = (agg["last_seen"] - agg["first_seen"]).dt.days.clip(lower=0)
    agg["frequency"] = (
        (agg["total_violations"] / agg["active_days"].clip(lower=1))
        .where(agg["active_days"] > 0, other=0.0)
        .round(3)
    )

    out = agg.join(avg_gap).reset_index()

    # Filter to repeat offenders only: enough violations AND across enough days
    # to be a real recurring pattern rather than a single-day burst.
    out = out[
        (out["total_violations"] >= MIN_VIOLATIONS)
        & (out["active_days"] >= MIN_ACTIVE_DAYS)
    ].copy()

    # Privacy mask: keep first 6 chars + last 2, mask middle
    def _mask(plate: str) -> str:
        if not isinstance(plate, str) or len(plate) < 6:
            return plate
        return plate[:6] + "****" + plate[-2:]

    out["vehicle_number_masked"] = out["vehicle_number"].apply(_mask)
    out = out.sort_values("total_violations", ascending=False).reset_index(drop=True)
    return out


def run() -> None:
    t0 = time.perf_counter()

    viol_path = settings.violations_parquet
    hs_path   = settings.hotspots_parquet
    if not viol_path.exists():
        raise FileNotFoundError(
            f"{viol_path} not found. Run "
            "`python -m backend.pipeline.build_dataset` first."
        )

    print("-- Load artifacts -------------------------------------------")
    vdf = pd.read_parquet(viol_path)
    print(f"   violations : {len(vdf):,} rows")
    hdf = None
    if hs_path.exists():
        hdf = pd.read_parquet(hs_path)
        print(f"   hotspots   : {len(hdf):,} rows  (hex_id present: {'hex_id' in hdf.columns})")
    else:
        print("   hotspots   : not found — distinct_hotspots will be 0")

    print()
    print("-- Step 2.6: Repeat-offender signals ------------------------")
    out = build_repeat_offenders(vdf, hdf)

    print("-- Step 2.7: K-Means tiering (k=3) --------------------------")
    out, centroids = assign_tiers(out, k=3)
    print(f"   Tier counts: {out['risk_tier'].value_counts().to_dict()}")

    dest = settings.processed_dir / "repeat_offenders.parquet"
    dest.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(dest, index=False, engine="pyarrow")

    elapsed = time.perf_counter() - t0
    print(f"   Vehicles (>= {MIN_VIOLATIONS} violations) : {len(out):,}")
    print(f"   Written  : {dest}  ({dest.stat().st_size / 1024:.0f} KB)")
    print(f"   Elapsed  : {elapsed:.1f}s")
    print()

    # ── Signal summary ────────────────────────────────────────────────────────
    print("-- Signal distributions -------------------------------------")
    print(out[[
        "total_violations", "active_days", "frequency",
        "avg_days_between", "violation_diversity", "distinct_hotspots",
    ]].describe().round(2).to_string())

    print()
    print("-- Cluster centroids (real units) — judge-facing tier table -")
    print(centroids.round(2).to_string(index=False))

    print()
    print("-- Top 10 by total violations -------------------------------")
    display_cols = [
        "vehicle_number_masked", "total_violations", "active_days",
        "frequency", "avg_days_between", "violation_diversity",
        "distinct_hotspots", "top_location",
    ]
    print(out[display_cols].head(10).to_string(index=False))


if __name__ == "__main__":
    run()
