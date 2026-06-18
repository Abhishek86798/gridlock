"""
Step 1.2 — Clean the raw violations DataFrame.

Operations (in order):
  1. Parse `violation_type` / `offence_code` JSON-array strings → Python lists.
  2. Derive `primary_violation_type` — the single worst offense in the list
     (by SEVERITY_WEIGHTS), used for risk scoring downstream.
  3. Filter rows to `validation_status == "approved"`.
  4. Drop rows with null coordinates.
  5. Drop rows whose coordinates fall outside the Bengaluru bounding box.
  6. Normalise `vehicle_type` to uppercase-stripped form for reliable lookups
     against VEHICLE_WEIGHTS.

Why not explode?
  Exploding multi-type rows (up to 12 types per row) would inflate per-hotspot
  violation counts and distort density scores.  Instead we keep one row per
  physical observation and carry the full list alongside the primary type.
"""

from __future__ import annotations

import json

import pandas as pd

from backend.app.core.config import DEFAULT_SEVERITY, SEVERITY_WEIGHTS, settings

_APPROVED = "approved"
# Statuses that are definitively bad data — excluded under both filter modes.
_ALWAYS_EXCLUDE = {"rejected", "duplicate"}


# ── Array parsing ─────────────────────────────────────────────────────────────

def _parse_str_array(val: str | None) -> list[str]:
    """Parse a JSON-array string into a list of strings; return [] on failure."""
    if pd.isna(val):
        return []
    try:
        result = json.loads(val)
        return result if isinstance(result, list) else [result]
    except (json.JSONDecodeError, TypeError):
        return []


def _parse_int_array(val: str | None) -> list[int]:
    """Parse a JSON-array string into a list of ints; return [] on failure."""
    parsed = _parse_str_array(val)
    try:
        return [int(x) for x in parsed]
    except (ValueError, TypeError):
        return parsed   # return as-is if cast fails


# ── Severity helper ───────────────────────────────────────────────────────────

def _primary_violation(types: list[str]) -> str:
    """Return the violation type with the highest severity weight."""
    if not types:
        return ""
    return max(types, key=lambda t: SEVERITY_WEIGHTS.get(t, DEFAULT_SEVERITY))


# ── Public entry point ────────────────────────────────────────────────────────

def clean_violations(
    df: pd.DataFrame,
    *,
    include_unvalidated: bool = False,
) -> pd.DataFrame:
    """Return a cleaned copy of the raw violations DataFrame.

    Parameters
    ----------
    df:
        Output of :func:`backend.pipeline.load.load_violations`.
    include_unvalidated:
        ``False`` (default) — keep only ``approved`` rows.  Use for the
        headline analysis.

        ``True`` — keep all rows except ``rejected`` and ``duplicate``
        (i.e. approved + unvalidated + in-progress).  Use to run the
        validation-bias check: re-rank hotspots on this broader set and
        compare the top-20 against the approved-only ranking.

    Returns
    -------
    pd.DataFrame
        Filtered, parsed, normalised DataFrame.  Row index is reset.
        New / modified columns:

        ``violation_type``         — list[str]  (replaces raw JSON string)
        ``offence_code``           — list[int]  (replaces raw JSON string)
        ``primary_violation_type`` — str, highest-severity violation in list
        ``vehicle_type``           — str, uppercased + stripped
    """
    out = df.copy()

    # 1. Parse JSON-array columns in-place (replaces raw string columns).
    out["violation_type"] = out["violation_type"].apply(_parse_str_array)
    out["offence_code"]   = out["offence_code"].apply(_parse_int_array)

    # 2. Derive primary violation type before any row dropping.
    out["primary_violation_type"] = out["violation_type"].apply(_primary_violation)

    # 3. Filter by validation status.
    if include_unvalidated:
        keep = ~out["validation_status"].isin(_ALWAYS_EXCLUDE)
        out = out[keep].copy()
    else:
        out = out[out["validation_status"] == _APPROVED].copy()

    # 4. Drop rows with null coordinates (none in this dataset, kept for safety).
    out = out.dropna(subset=["latitude", "longitude"])

    # 5. Drop out-of-bounding-box coordinates.
    in_bbox = (
        out["latitude"].between(settings.lat_min, settings.lat_max)
        & out["longitude"].between(settings.lng_min, settings.lng_max)
    )
    out = out[in_bbox].copy()

    # 6. Normalise vehicle_type for VEHICLE_NORMALIZE lookups.
    out["vehicle_type"] = (
        out["vehicle_type"]
        .str.upper()
        .str.strip()
    )

    return out.reset_index(drop=True)


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from backend.pipeline.load import load_violations

    raw = load_violations()
    print(f"Raw rows : {len(raw):,}")

    clean = clean_violations(raw)
    print(f"Clean rows: {len(clean):,}  "
          f"(dropped {len(raw) - len(clean):,})")

    print(f"\nvalidation_status: {clean['validation_status'].unique().tolist()}")
    print(f"Null coords      : {clean['latitude'].isna().sum()}")
    print(f"Out-of-bbox      : 0  (already filtered)")
    print(f"\nviolation_type sample:")
    print(clean["violation_type"].head(4).tolist())
    print(f"\nprimary_violation_type sample:")
    print(clean["primary_violation_type"].head(4).tolist())
    print(f"\noffence_code sample:")
    print(clean["offence_code"].head(4).tolist())
    print(f"\nvehicle_type value counts (top 8):")
    print(clean["vehicle_type"].value_counts().head(8).to_string())
    print(f"\nDtypes:")
    print(clean.dtypes)
