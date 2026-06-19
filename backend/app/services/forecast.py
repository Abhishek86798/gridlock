"""
Step 5.1 — Predictive forecasting service.

Grain   : next-week violation count per hotspot.
Model   : XGBoost with count:poisson objective.
Panel   : violations.parquet → weekly counts per hotspot (via H3 cell lookup),
          zero-filled for every week in the dataset range.
Features: lag1–lag4 weekly counts, 4-week rolling mean,
          ISO week-of-year + calendar month (seasonality),
          static hotspot attributes: risk_score, violation_severity,
          has_junction, has_poi.
Split   : time-based — train on all-but-last-2 weeks, hold out final 2 weeks.
Predict : one ISO week beyond the last observed week.
Cache   : model trained once per server process (lazy singleton, _cache).
"""
from __future__ import annotations

import datetime
from typing import Any

import h3
import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from backend.app.core import store
from backend.app.core.config import settings

# ── Constants ─────────────────────────────────────────────────────────────────

_LAG_WEEKS = 4

_SEVERITY_MAP: dict[str, float] = {
    "PARKING IN A MAIN ROAD":       5.0,
    "PARKING NEAR ROAD CROSSING":   4.0,
    "PARKING ON FOOTPATH":          3.0,
    "WRONG PARKING":                2.0,
    "NO PARKING":                   1.0,
}

_FEATURE_COLS: list[str] = [
    "lag1", "lag2", "lag3", "lag4",
    "rolling_mean_4w",
    "week_of_year", "month",
    "risk_score", "violation_severity",
    "has_junction", "has_poi",
]

# ── Module-level model cache (trains once per server process) ─────────────────

_cache: dict[str, Any] | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _iso_label(year: int, week: int) -> str:
    return f"{year}-W{week:02d}"


def _month_from_iso(year: int, week: int) -> int:
    """Calendar month of the Monday that opens the given ISO year+week."""
    return datetime.date.fromisocalendar(int(year), int(week), 1).month


def _assign_hotspot_ids(vdf: pd.DataFrame, hdf: pd.DataFrame) -> pd.DataFrame:
    """
    Map each violation row to a hotspot_id by converting its lat/lng to an
    H3 cell and looking it up in the hotspot hex index.
    Rows outside any known hotspot cell are dropped (~1.3% of the dataset).
    """
    res = settings.h3_resolution
    good = vdf.dropna(subset=["latitude", "longitude"]).copy()
    good["_hex"] = [
        h3.geo_to_h3(lat, lng, res)
        for lat, lng in zip(good["latitude"], good["longitude"])
    ]
    hex_to_hs = hdf.set_index("hex_id")["hotspot_id"]
    good["hotspot_id"] = good["_hex"].map(hex_to_hs)
    return good.dropna(subset=["hotspot_id"]).drop(columns=["_hex"])


def _build_weekly_panel(vdf: pd.DataFrame, hdf: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate violations → weekly counts per hotspot, zero-fill missing weeks,
    and attach static hotspot features.

    Returns a DataFrame with one row per (hotspot_id, week_ord) where
    week_ord = iso_year * 100 + iso_week (e.g. 202413 = 2024-W13).
    """
    v = _assign_hotspot_ids(vdf, hdf)

    # Derive ISO year+week from IST timestamp (violations don't have hotspot_id,
    # but do have created_ist with the IST-local time already computed).
    ts = pd.to_datetime(v["created_ist"])
    if ts.dt.tz is not None:
        from zoneinfo import ZoneInfo
        ts = ts.dt.tz_convert(ZoneInfo("Asia/Kolkata")).dt.tz_localize(None)
    iso = ts.dt.isocalendar()
    v = v.copy()
    v["week_ord"] = (iso["year"].astype(int) * 100 + iso["week"].astype(int)).values

    weekly = (
        v.groupby(["hotspot_id", "week_ord"])
        .size()
        .reset_index(name="count")
    )

    # Cross-join every hotspot with every observed week so lags are contiguous.
    all_weeks = sorted(weekly["week_ord"].unique())
    full = pd.DataFrame(
        pd.MultiIndex.from_product(
            [weekly["hotspot_id"].unique(), all_weeks],
            names=["hotspot_id", "week_ord"],
        ).tolist(),
        columns=["hotspot_id", "week_ord"],
    ).merge(weekly, on=["hotspot_id", "week_ord"], how="left")
    full["count"] = full["count"].fillna(0).astype(int)

    # Calendar features derived from week_ord
    full["iso_year"]      = full["week_ord"] // 100
    full["iso_week"]      = full["week_ord"] % 100
    full["week_of_year"]  = full["iso_week"]
    full["month"] = [
        _month_from_iso(y, w)
        for y, w in zip(full["iso_year"], full["iso_week"])
    ]

    # Static hotspot features
    static = hdf[[
        "hotspot_id", "risk_score", "dominant_violation",
        "police_station", "junction_name", "near_poi",
    ]].copy()
    static["has_junction"] = (
        static["junction_name"].notna()
        & (static["junction_name"] != "No Junction")
    ).astype(float)
    static["has_poi"]            = static["near_poi"].notna().astype(float)
    static["violation_severity"] = (
        static["dominant_violation"].map(_SEVERITY_MAP).fillna(1.0)
    )

    panel = full.merge(
        static[[
            "hotspot_id", "risk_score", "has_junction",
            "has_poi", "violation_severity", "police_station",
        ]],
        on="hotspot_id",
        how="left",
    )
    return panel.sort_values(["hotspot_id", "week_ord"]).reset_index(drop=True)


def _add_lag_features(panel: pd.DataFrame) -> pd.DataFrame:
    """
    Add lag1–lag4 shifted counts and a 4-week rolling mean per hotspot.
    Drops the first _LAG_WEEKS rows per hotspot (no complete lag history yet).
    """
    out = panel.copy()
    for lag in range(1, _LAG_WEEKS + 1):
        out[f"lag{lag}"] = out.groupby("hotspot_id")["count"].shift(lag)
    lag_cols = [f"lag{i}" for i in range(1, _LAG_WEEKS + 1)]
    out["rolling_mean_4w"] = out[lag_cols].mean(axis=1)
    return out.dropna(subset=lag_cols).reset_index(drop=True)


# ── Model training ────────────────────────────────────────────────────────────

def _fit(vdf: pd.DataFrame, hdf: pd.DataFrame) -> dict[str, Any]:
    """
    Build panel, split by time (hold out last 2 weeks), train XGBRegressor
    with Poisson objective, evaluate MAE on hold-out.

    Returns a dict with keys: model, panel, mae, predict_week, next_yr, next_wk.
    """
    panel = _build_weekly_panel(vdf, hdf)
    panel = _add_lag_features(panel)

    all_ords = sorted(panel["week_ord"].unique())
    if len(all_ords) < _LAG_WEEKS + 3:
        raise ValueError(
            f"Dataset has only {len(all_ords)} usable weeks after lag warmup; "
            f"need at least {_LAG_WEEKS + 3} to train."
        )

    # Hold out the final 2 weeks; everything else is training.
    cutoff  = all_ords[-3]
    train   = panel[panel["week_ord"] <= cutoff]
    holdout = panel[panel["week_ord"] >  cutoff]

    X_tr = train[_FEATURE_COLS].fillna(0)
    y_tr = train["count"].clip(lower=0).astype(float)
    X_ho = holdout[_FEATURE_COLS].fillna(0)
    y_ho = holdout["count"].clip(lower=0).astype(float)

    model = XGBRegressor(
        n_estimators=settings.forecast_n_estimators,
        max_depth=settings.forecast_max_depth,
        objective="count:poisson",
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
        verbosity=0,
    )
    model.fit(X_tr, y_tr)

    mae = (
        float(np.abs(model.predict(X_ho) - y_ho.values).mean())
        if len(y_ho) else 0.0
    )

    # Determine the ISO week immediately after the last observed week.
    last_yr, last_wk = all_ords[-1] // 100, all_ords[-1] % 100
    next_monday = (
        datetime.date.fromisocalendar(last_yr, last_wk, 1)
        + datetime.timedelta(weeks=1)
    )
    ni = next_monday.isocalendar()
    next_yr, next_wk = int(ni[0]), int(ni[1])

    return {
        "model":        model,
        "panel":        panel,
        "mae":          mae,
        "predict_week": _iso_label(next_yr, next_wk),
        "next_yr":      next_yr,
        "next_wk":      next_wk,
    }


def _ensure_trained() -> dict[str, Any]:
    global _cache
    if _cache is None:
        _cache = _fit(store.violations, store.hotspots)
    return _cache


# ── Public API ────────────────────────────────────────────────────────────────

def get_forecast(top_n: int = 30) -> dict[str, Any]:
    """
    Return the top_n hotspots predicted to have the highest violation count
    in the next ISO week, ranked by predicted_count descending.

    Returns a plain dict matching the ForecastResponse schema.
    """
    ctx     = _ensure_trained()
    model   = ctx["model"]
    panel   = ctx["panel"]
    next_yr = ctx["next_yr"]
    next_wk = ctx["next_wk"]

    # For each hotspot, build one inference row from its 4 most recent weeks.
    last4 = (
        panel
        .sort_values("week_ord")
        .groupby("hotspot_id", sort=False)
        .tail(_LAG_WEEKS)
    )

    def _inference_row(grp: pd.DataFrame) -> dict:
        grp    = grp.sort_values("week_ord")
        counts = grp["count"].values
        # Pad with zeros at the front if hotspot has < 4 observed weeks.
        counts = np.pad(counts, (max(0, _LAG_WEEKS - len(counts)), 0))[-_LAG_WEEKS:]
        # counts is oldest→newest; lag1 = most recent, lag4 = oldest.
        lag1, lag2, lag3, lag4 = counts[3], counts[2], counts[1], counts[0]
        latest = grp.iloc[-1]
        return {
            "hotspot_id":         latest["hotspot_id"],
            "police_station":     latest["police_station"],
            "risk_score":         float(latest["risk_score"]),
            "lag1":               float(lag1),
            "lag2":               float(lag2),
            "lag3":               float(lag3),
            "lag4":               float(lag4),
            "rolling_mean_4w":    float(counts.mean()),
            "week_of_year":       next_wk,
            "month":              _month_from_iso(next_yr, next_wk),
            "violation_severity": float(latest["violation_severity"]),
            "has_junction":       float(latest["has_junction"]),
            "has_poi":            float(latest["has_poi"]),
            "prev_week_count":    int(lag1),
        }

    inf = pd.DataFrame([
        _inference_row(g) for _, g in last4.groupby("hotspot_id", sort=False)
    ])

    inf["predicted_count"] = (
        model.predict(inf[_FEATURE_COLS].fillna(0)).clip(min=0)
    )
    inf["change_pct"] = (
        (inf["predicted_count"] - inf["prev_week_count"])
        / (inf["prev_week_count"] + 1e-9)
        * 100
    ).round(1)

    top = inf.nlargest(top_n, "predicted_count").reset_index(drop=True)

    return {
        "predict_week": ctx["predict_week"],
        "model_mae":    round(ctx["mae"], 2),
        "forecast": [
            {
                "hotspot_id":      row["hotspot_id"],
                "police_station":  row["police_station"],
                "predicted_count": round(float(row["predicted_count"]), 1),
                "prev_week_count": int(row["prev_week_count"]),
                "change_pct":      float(row["change_pct"]),
                "risk_score":      round(float(row["risk_score"]), 1),
            }
            for _, row in top.iterrows()
        ],
    }
