"""
Step 1.3 — Feature engineering on the cleaned violations DataFrame.

Adds three groups of derived columns:

Temporal (IST)
  created_ist   datetime64[ns, Asia/Kolkata]  — timezone-converted source
  hour          int8   0–23
  day_of_week   int8   0 (Mon) – 6 (Sun)
  month         int8   1–12
  week_of_year  int16  ISO week number
  date          datetime64[ns, UTC]  floor to midnight UTC (grouper-friendly)

Spatial / categorical
  has_junction  bool   True when junction_name is a real named junction

Risk-score inputs (unit-normalised 0–100)
  severity_score  float32  weighted by SEVERITY_WEIGHTS,   scaled to 0–100
  vehicle_score   float32  weighted by VEHICLE_NORMALIZE,  scaled to 0–100

These columns feed the hotspot risk scorer, temporal heatmaps, and the
gradient-boosting forecast model.
"""

from __future__ import annotations

from zoneinfo import ZoneInfo

import pandas as pd

from backend.app.core.config import (
    DEFAULT_SEVERITY,
    DEFAULT_VEHICLE_WEIGHT,
    SEVERITY_WEIGHTS,
    VEHICLE_NORMALIZE,
)

_IST = ZoneInfo("Asia/Kolkata")

# "No Junction" sentinel used in the raw data
_NO_JUNCTION = "No Junction"

# Max severity weight for 0–100 normalisation (stable across batches).
_MAX_SEVERITY = max(SEVERITY_WEIGHTS.values())   # 3.0
# VEHICLE_NORMALIZE is already on a 0–1 scale; multiply by 100 directly.


# ── Temporal features ─────────────────────────────────────────────────────────

def add_temporal_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add IST-based temporal columns derived from ``created_datetime``."""
    ist = df["created_datetime"].dt.tz_convert(_IST)
    df = df.copy()
    df["created_ist"]  = ist
    df["hour"]         = ist.dt.hour.astype("Int8")         # nullable: NaT rows → NA
    df["day_of_week"]  = ist.dt.dayofweek.astype("Int8")    # 0=Mon
    df["month"]        = ist.dt.month.astype("Int8")
    df["week_of_year"] = ist.dt.isocalendar().week.astype("Int16")
    # Floor to UTC midnight so downstream groupers work without tz math.
    df["date"] = df["created_datetime"].dt.floor("D").dt.tz_localize(None)
    return df


# ── Spatial / categorical features ───────────────────────────────────────────

def add_junction_flag(df: pd.DataFrame) -> pd.DataFrame:
    """Add ``has_junction`` bool: True when a real named junction is present."""
    df = df.copy()
    df["has_junction"] = (
        df["junction_name"].notna()
        & (df["junction_name"] != _NO_JUNCTION)
    )
    return df


# ── Risk-score input features ─────────────────────────────────────────────────

def add_risk_inputs(df: pd.DataFrame) -> pd.DataFrame:
    """Add ``severity_score`` and ``vehicle_score`` (both 0–100 floats).

    ``primary_violation_type`` is mapped through SEVERITY_WEIGHTS;
    ``vehicle_type`` is mapped through VEHICLE_NORMALIZE (keyed to exact
    uppercased strings in the dataset).  Unknown values fall back to their
    respective defaults.  Fall-through rate is printed as a data-quality check.
    """
    df = df.copy()

    raw_sev = df["primary_violation_type"].map(
        lambda vt: SEVERITY_WEIGHTS.get(vt, DEFAULT_SEVERITY)
    )
    df["severity_score"] = (raw_sev / _MAX_SEVERITY * 100).astype("float32")

    miss_mask = ~df["vehicle_type"].isin(VEHICLE_NORMALIZE)
    miss_pct = miss_mask.mean() * 100
    if miss_pct > 5:
        import warnings
        missing = df.loc[miss_mask, "vehicle_type"].value_counts().head(5).to_dict()
        warnings.warn(
            f"vehicle_score: {miss_pct:.1f}% of rows fell through to default "
            f"({DEFAULT_VEHICLE_WEIGHT}).  Top missing: {missing}",
            stacklevel=2,
        )

    df["vehicle_score"] = (
        df["vehicle_type"]
        .map(lambda vt: VEHICLE_NORMALIZE.get(vt, DEFAULT_VEHICLE_WEIGHT))
        .mul(100)
        .astype("float32")
    )

    return df


# ── Public entry point ────────────────────────────────────────────────────────

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Apply all feature-engineering steps and return the augmented DataFrame.

    Parameters
    ----------
    df:
        Output of :func:`backend.pipeline.clean.clean_violations`.

    Returns
    -------
    pd.DataFrame
        Original columns plus all derived feature columns listed in the
        module docstring.
    """
    df = add_temporal_features(df)
    df = add_junction_flag(df)
    df = add_risk_inputs(df)
    return df


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from backend.pipeline.clean import clean_violations
    from backend.pipeline.load import load_violations

    df = build_features(clean_violations(load_violations()))

    print(f"Rows: {len(df):,}  |  Columns: {len(df.columns)}")
    print()

    print("=== Temporal dtypes ===")
    for col in ("created_ist", "hour", "day_of_week", "month", "week_of_year", "date"):
        print(f"  {col:<16} {df[col].dtype}")

    print()
    print("=== Peak hour (IST) ===")
    peak = df["hour"].value_counts().sort_index()
    print(peak.to_string())

    print()
    print("=== Day-of-week distribution (0=Mon) ===")
    print(df["day_of_week"].value_counts().sort_index().to_string())

    print()
    print("=== has_junction ===")
    vc = df["has_junction"].value_counts()
    print(vc.to_string())
    pct = vc[True] / len(df) * 100
    print(f"  named junction: {pct:.1f}%")

    print()
    print("=== Risk score inputs ===")
    print(df[["severity_score", "vehicle_score"]].describe().round(2).to_string())

    print()
    miss_mask = ~df["vehicle_type"].isin(VEHICLE_NORMALIZE)
    miss_pct = miss_mask.mean() * 100
    print(f"=== vehicle_score fall-through rate: {miss_pct:.2f}% ===")
    if miss_mask.any():
        print(df.loc[miss_mask, "vehicle_type"].value_counts().to_string())
    else:
        print("  All vehicle types mapped — no fall-through.")

    print()
    print("=== vehicle_score by vehicle_type ===")
    print(
        df.groupby("vehicle_type")["vehicle_score"]
        .agg(["mean", "count"])
        .sort_values("count", ascending=False)
        .round(2)
        .to_string()
    )

    print()
    print("=== severity_score by primary_violation_type ===")
    print(
        df.groupby("primary_violation_type")["severity_score"]
        .agg(["mean", "count"])
        .sort_values("mean", ascending=False)
        .round(2)
        .to_string()
    )
