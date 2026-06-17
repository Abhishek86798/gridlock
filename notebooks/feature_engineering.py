"""
feature_engineering.py  — PS1 Bengaluru Illegal Parking Intelligence
--------------------------------------------------------------------
Reads the raw violations CSV, cleans it, and engineers the features that
feed hotspot detection, the congestion-risk score, temporal analysis,
and forecasting. Output aligns with CONTRACTS.md (§2.3 violations.parquet).

Usage:
    python feature_engineering.py --in data/raw/violations.csv --out data/processed/violations.parquet

Place under: backend/pipeline/feature_engineering.py
"""

import argparse
import ast
import numpy as np
import pandas as pd

# Bengaluru bounding box (drop coordinates outside this)
BLR_BOUNDS = {"lat_min": 12.7, "lat_max": 13.25, "lng_min": 77.35, "lng_max": 77.85}

# Columns that are 100% null in this dataset — drop on load
DROP_COLS = ["description", "action_taken_timestamp", "closed_datetime"]

# --- Severity weights (traffic-flow impact). Higher = worse for flow. ---
# Tuned from the actual violation_type frequencies in the data.
SEVERITY_WEIGHTS = {
    "PARKING IN A MAIN ROAD": 1.00,
    "DOUBLE PARKING": 0.95,
    "PARKING NEAR ROAD CROSSING": 0.90,
    "PARKING NEAR TRAFFIC LIGHT OR ZEBRA CROSS": 0.90,
    "PARKING OPPOSITE TO ANOTHER PARKED VEHICLE": 0.85,
    "PARKING NEAR BUSTOP/SCHOOL/HOSPITAL ETC": 0.80,
    "PARKING ON FOOTPATH": 0.70,
    "WRONG PARKING": 0.60,
    "PARKING OTHER THAN BUS STOP": 0.50,
    "NO PARKING": 0.40,
}
# Anything not in SEVERITY_WEIGHTS is treated as non-parking (weight 0, is_parking=False)
PARKING_TYPES = set(SEVERITY_WEIGHTS.keys())

# --- Vehicle size weights (bigger vehicle blocks more carriageway). ---
VEHICLE_SIZE_WEIGHTS = {
    "HTV": 1.00, "TANKER": 1.00, "TRUCK": 1.00, "LORRY": 1.00, "BUS": 1.00,
    "MAXI-CAB": 0.75, "CAR": 0.70,
    "PASSENGER AUTO": 0.50, "AUTO": 0.50,
    "SCOOTER": 0.30, "MOTORCYCLE": 0.30, "BIKE": 0.30,
}
DEFAULT_VEHICLE_WEIGHT = 0.5


def parse_list(x):
    """Parse a JSON-style array string like '[\"NO PARKING\"]' into a Python list."""
    if pd.isna(x):
        return []
    if isinstance(x, list):
        return x
    try:
        return ast.literal_eval(x)
    except (ValueError, SyntaxError):
        return []


def load_and_drop(path):
    df = pd.read_csv(path, low_memory=False)
    df = df.drop(columns=[c for c in DROP_COLS if c in df.columns])
    print(f"Loaded {len(df):,} rows.")
    return df


def clean(df):
    # --- drop corrupt rows (missing core fields) ---
    before = len(df)
    df = df.dropna(subset=["created_datetime", "police_station", "created_by_id"])
    # --- coordinate sanity ---
    df = df[
        df["latitude"].between(BLR_BOUNDS["lat_min"], BLR_BOUNDS["lat_max"])
        & df["longitude"].between(BLR_BOUNDS["lng_min"], BLR_BOUNDS["lng_max"])
    ]
    print(f"Dropped {before - len(df):,} corrupt/out-of-bounds rows -> {len(df):,} remain.")

    # --- junction sentinel -> real missing ---
    df["junction_name"] = df["junction_name"].replace("No Junction", np.nan)
    df["has_junction"] = df["junction_name"].notna()

    # --- canonical vehicle type: prefer the validated value ---
    df["vehicle_type_clean"] = df["updated_vehicle_type"].fillna(df["vehicle_type"])

    # --- validation flags ---
    df["is_validated"] = df["validation_status"].notna()
    df["is_approved"] = (df["validation_status"] == "approved")
    return df


def add_temporal_features(df):
    # Parse as UTC then CONVERT TO IST before deriving hour/weekday (critical!)
    ts = pd.to_datetime(df["created_datetime"], utc=True, errors="coerce")
    ist = ts.dt.tz_convert("Asia/Kolkata")
    df["created_at"] = ist
    df["date"] = ist.dt.date
    df["hour"] = ist.dt.hour
    df["day_of_week"] = ist.dt.dayofweek      # 0=Mon ... 6=Sun
    df["is_weekend"] = df["day_of_week"] >= 5
    df["month"] = ist.dt.month
    # Coarse time-of-day bucket
    bins = [-1, 5, 11, 16, 20, 23]
    labels = ["night", "morning", "afternoon", "evening", "late_evening"]
    df["time_bucket"] = pd.cut(df["hour"], bins=bins, labels=labels)
    return df


def add_violation_features(df):
    df["_vtypes"] = df["violation_type"].apply(parse_list)
    df["n_violations"] = df["_vtypes"].apply(len)

    # is_parking: at least one parking-related tag
    df["is_parking"] = df["_vtypes"].apply(lambda lst: any(v in PARKING_TYPES for v in lst))

    # severity_weight: the MAX severity among this record's tags (the worst offence drives impact)
    def max_sev(lst):
        weights = [SEVERITY_WEIGHTS.get(v, 0.0) for v in lst]
        return max(weights) if weights else 0.0
    df["severity_weight"] = df["_vtypes"].apply(max_sev)

    # primary_violation: the single most-severe tag (used as the canonical type)
    def primary(lst):
        if not lst:
            return None
        return max(lst, key=lambda v: SEVERITY_WEIGHTS.get(v, 0.0))
    df["primary_violation"] = df["_vtypes"].apply(primary)
    return df


def add_vehicle_features(df):
    def size_weight(vt):
        if pd.isna(vt):
            return DEFAULT_VEHICLE_WEIGHT
        return VEHICLE_SIZE_WEIGHTS.get(str(vt).upper(), DEFAULT_VEHICLE_WEIGHT)
    df["vehicle_size_weight"] = df["vehicle_type_clean"].apply(size_weight)
    return df


def add_impact_feature(df):
    # Per-record impact = severity x vehicle size. Aggregated later into hotspot risk_score.
    df["record_impact"] = df["severity_weight"] * df["vehicle_size_weight"]
    return df


def finalize(df):
    keep = [
        "id", "latitude", "longitude", "location", "police_station",
        "junction_name", "has_junction",
        "vehicle_number", "vehicle_type_clean",
        "primary_violation", "n_violations", "is_parking",
        "severity_weight", "vehicle_size_weight", "record_impact",
        "created_at", "date", "hour", "day_of_week", "is_weekend", "month", "time_bucket",
        "device_id", "created_by_id", "center_code",
        "validation_status", "is_validated", "is_approved",
    ]
    out = df[[c for c in keep if c in df.columns]].copy()
    out = out.rename(columns={"latitude": "lat", "longitude": "lng"})
    return out


def quick_report(df):
    print("\n--- QUICK CHECKS ---")
    print(f"Rows: {len(df):,}")
    print(f"Parking records: {df['is_parking'].mean():.1%}")
    print(f"Validated: {df['is_validated'].mean():.1%} | "
          f"Approved (of validated): {df.loc[df['is_validated'],'is_approved'].mean():.1%}")
    print(f"Unique vehicle plates: {df['vehicle_number'].nunique():,} "
          f"({df['vehicle_number'].nunique()/len(df):.1%} of rows) "
          f"-> repeat-offender add-on {'VIABLE' if df['vehicle_number'].nunique()/len(df) < 0.9 else 'NOT viable (plates ~unique)'}")
    print(f"Date span: {df['date'].min()} -> {df['date'].max()}")
    print("Top primary violations:\n", df["primary_violation"].value_counts().head(8))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="data/raw/violations.csv")
    ap.add_argument("--out", dest="out", default="data/processed/violations.parquet")
    ap.add_argument("--parking-only", action="store_true", help="keep only parking violations")
    args = ap.parse_args()

    df = load_and_drop(args.inp)
    df = clean(df)
    df = add_temporal_features(df)
    df = add_violation_features(df)
    df = add_vehicle_features(df)
    df = add_impact_feature(df)
    out = finalize(df)

    if args.parking_only:
        before = len(out)
        out = out[out["is_parking"]]
        print(f"Filtered to parking only: {before:,} -> {len(out):,}")

    quick_report(out)
    out.to_parquet(args.out, index=False)
    print(f"\nWrote {len(out):,} rows -> {args.out}")


if __name__ == "__main__":
    main()