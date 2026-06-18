"""
Step 1.4 — Build the processed violations dataset.

Orchestrates: load → clean → features → parquet.

Usage
-----
    python -m backend.pipeline.build_dataset          # approved-only (default)
    python -m backend.pipeline.build_dataset --broad  # include unvalidated rows

Output
------
    data/processed/violations.parquet
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd

from backend.app.core.config import settings
from backend.pipeline.clean import clean_violations
from backend.pipeline.features import build_features
from backend.pipeline.load import load_violations

# List columns can't round-trip through parquet as Python objects; serialise
# them as JSON strings so any reader (DuckDB, pandas, Spark) can parse them.
_LIST_COLS = ("violation_type", "offence_code")


def _serialise_lists(df: pd.DataFrame) -> pd.DataFrame:
    """Convert list-valued columns to JSON strings for parquet compatibility."""
    import json
    df = df.copy()
    for col in _LIST_COLS:
        if col in df.columns:
            df[col] = df[col].apply(json.dumps)
    return df


def build(*, include_unvalidated: bool = False) -> pd.DataFrame:
    """Run the full pipeline and return the processed DataFrame."""
    t0 = time.perf_counter()

    print("-- Step 1: Load -----------------------------------------")
    raw = load_violations()
    print(f"   Loaded   : {len(raw):>8,} rows  x  {len(raw.columns)} columns")

    print("-- Step 2: Clean ----------------------------------------")
    clean = clean_violations(raw, include_unvalidated=include_unvalidated)
    dropped = len(raw) - len(clean)
    mode = "approved + unvalidated" if include_unvalidated else "approved-only"
    print(f"   Cleaned  : {len(clean):>8,} rows  ({mode})")
    print(f"   Dropped  : {dropped:>8,} rows  "
          f"({dropped / len(raw) * 100:.1f}% of raw)")

    print("-- Step 3: Feature engineering --------------------------")
    featured = build_features(clean)
    new_cols = set(featured.columns) - set(clean.columns)
    print(f"   Features : {len(featured.columns)} columns  "
          f"(+{len(new_cols)} new: {sorted(new_cols)})")

    print("-- Step 4: Write parquet --------------------------------")
    out_path: Path = settings.violations_parquet
    out_path.parent.mkdir(parents=True, exist_ok=True)

    featured = _serialise_lists(featured)
    featured.to_parquet(out_path, index=False, engine="pyarrow")

    size_mb = out_path.stat().st_size / 1_048_576
    elapsed = time.perf_counter() - t0
    print(f"   Written  : {out_path}")
    print(f"   File size: {size_mb:.1f} MB")
    print(f"   Elapsed  : {elapsed:.1f}s")

    return featured


def _summary(df: pd.DataFrame) -> None:
    """Print a quick sanity-check table after the build."""
    print()
    print("-- Summary ----------------------------------------------")
    print(f"   Final rows        : {len(df):,}")
    print(f"   Date range (IST)  : "
          f"{df['created_ist'].min().date()}  to  {df['created_ist'].max().date()}")
    print(f"   Null created_ist  : {df['created_ist'].isna().sum()}")
    print()

    print("   validation_status breakdown:")
    for status, cnt in df["validation_status"].value_counts(dropna=False).items():
        print(f"     {str(status):<20} {cnt:>8,}")

    print()
    print("   vehicle_score fall-through (OTHERS):")
    from backend.app.core.config import VEHICLE_NORMALIZE
    miss = ~df["vehicle_type"].isin(VEHICLE_NORMALIZE)
    print(f"     {miss.sum():,} rows  ({miss.mean()*100:.2f}%)")

    print()
    print("   Top 5 police stations by violation count:")
    print(df["police_station"].value_counts().head(5).to_string())

    print()
    print("   hour distribution (IST):")
    print(df["hour"].value_counts().sort_index().to_string())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build violations.parquet")
    parser.add_argument(
        "--broad",
        action="store_true",
        help="Include unvalidated rows (approved + <NA> + created1 + processing)",
    )
    args = parser.parse_args()

    df = build(include_unvalidated=args.broad)
    _summary(df)
