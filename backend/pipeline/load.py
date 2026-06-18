"""
Step 1.1 — Load raw violations CSV into a DataFrame with correct dtypes.

`created_datetime` is stored as UTC in the source; it is parsed as a
timezone-aware Series (dtype datetime64[ns, UTC]) so all downstream
IST conversions are unambiguous.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from backend.app.core.config import settings

# Columns whose values are JSON arrays in the CSV (e.g. '["WRONG PARKING"]').
# They are kept as raw strings here; parsing happens in clean.py.
_ARRAY_COLS = ("violation_type", "offence_code")

# Datetime columns other than the primary `created_datetime`.
# Parsed with errors="coerce" so missing / malformed values become NaT.
_EXTRA_DT_COLS = (
    "closed_datetime",
    "modified_datetime",
    "action_taken_timestamp",
    "validation_timestamp",
    "data_sent_to_scita_timestamp",
)

# Explicit dtype map keeps pandas from guessing and avoids silent downcasting.
_DTYPE: dict[str, str] = {
    "id":                     "string",
    "vehicle_number":         "string",
    "updated_vehicle_number": "string",
    "vehicle_type":           "string",
    "updated_vehicle_type":   "string",
    "description":            "string",
    "location":               "string",
    "junction_name":          "string",
    "police_station":         "string",
    "validation_status":      "string",
    "violation_type":         "string",
    "offence_code":           "string",
    "device_id":              "string",
    "created_by_id":          "string",
    "data_sent_to_scita":     "string",   # "TRUE"/"FALSE" / NULL — cast later
}


def load_violations(path: Path | None = None) -> pd.DataFrame:
    """Return the raw violations CSV as a DataFrame.

    Parameters
    ----------
    path:
        Override the CSV path from ``settings.raw_csv``.  Useful in tests.

    Returns
    -------
    pd.DataFrame
        All original columns present.  ``created_datetime`` is
        ``datetime64[ns, UTC]``; other datetime columns are
        ``datetime64[ns, UTC]`` where parseable, else ``NaT``.
        ``latitude`` / ``longitude`` / ``center_code`` use their natural
        numeric dtypes.
    """
    src = Path(path) if path is not None else settings.raw_csv

    df = pd.read_csv(
        src,
        dtype=_DTYPE,
        parse_dates=False,        # we handle datetimes explicitly
        na_values=["NULL", ""],
        keep_default_na=True,
    )

    # Primary timestamp — must be UTC-aware for IST conversion downstream.
    df["created_datetime"] = pd.to_datetime(
        df["created_datetime"], utc=True, errors="coerce"
    )

    # Secondary timestamps — coerce bad values to NaT; attach UTC tz.
    for col in _EXTRA_DT_COLS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")

    # Numeric columns — coerce so bad coordinates become NaN not crashes.
    df["latitude"]  = pd.to_numeric(df["latitude"],  errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["center_code"] = pd.to_numeric(df["center_code"], errors="coerce").astype(
        "Int64"
    )

    return df


if __name__ == "__main__":
    df = load_violations()
    print(f"Loaded {len(df):,} rows × {len(df.columns)} columns")
    print(f"created_datetime dtype : {df['created_datetime'].dtype}")
    print(f"Null created_datetime  : {df['created_datetime'].isna().sum():,}")
    print(df.dtypes)
