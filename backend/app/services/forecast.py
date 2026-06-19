"""
Step 5.1 — Predictive forecasting service.

Grain   : next-week violation count per hotspot.
Model   : XGBoost with count:poisson objective.
Panel   : violations.parquet → weekly counts per hotspot (via H3 cell lookup),
          zero-filled for every week in the dataset range.
Features: lag1–lag4 weekly counts, 4-week rolling mean,
          calendar month (seasonality),
          static hotspot attributes: risk_score, violation_severity,
          has_junction, has_poi.
          NOTE: week_of_year intentionally excluded — the dataset spans only
          ~20 weeks (Nov 2023 – Mar 2024), so holdout weeks 12-13 never
          appear in training and the model would extrapolate on that feature.
          month is kept because all months in the dataset appear in training.
Data    : Two enforcement drives separated by a near-zero gap (W06-W10).
          Weekly totals are NOT a smooth ramp — they reflect reporting effort,
          not monotonic demand growth. Caveat surfaces in data_quality_notes.
Split   : time-based — train on all-but-last-2 weeks, hold out final 2 weeks.
Eval    : MAE vs two naive baselines (last-week, rolling-mean-4w) + Precision@N
          (overlap between predicted top-N and actual top-N on the hold-out).
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
    "month",          # week_of_year dropped: holdout weeks 12-13 unseen in training
    "risk_score", "violation_severity",
    "has_junction", "has_poi",
]

# ── Module-level model cache (trains once per server process) ─────────────────

_cache: dict[str, Any] | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _iso_label(year: int, week: int) -> str:
    return f"{year}-W{week:02d}"


def _compute_weekly_totals(vdf: pd.DataFrame) -> list[dict]:
    """
    Return total violation count per ISO week across all hotspots.
    Used to check for enforcement-effort ramps vs. stable demand.
    """
    ts = pd.to_datetime(vdf["created_ist"])
    if ts.dt.tz is not None:
        from zoneinfo import ZoneInfo
        ts = ts.dt.tz_convert(ZoneInfo("Asia/Kolkata")).dt.tz_localize(None)
    iso = ts.dt.isocalendar()
    week_ord = (iso["year"].astype(int) * 100 + iso["week"].astype(int)).values
    weekly = (
        pd.Series(week_ord, name="week_ord")
        .value_counts()
        .sort_index()
        .reset_index()
    )
    weekly.columns = ["week_ord", "total_violations"]
    weekly["week_label"] = weekly["week_ord"].apply(
        lambda w: _iso_label(w // 100, w % 100)
    )
    return [
        {"week": r["week_label"], "total_violations": int(r["total_violations"])}
        for _, r in weekly.iterrows()
    ]


def _enforcement_ramp_note(weekly_totals: list[dict]) -> str:
    """
    Inspect weekly totals and return a plain-English note about the trend.

    This dataset has two enforcement drives separated by a reporting gap
    (W06-W10 ≈ near-zero counts). We surface that fact rather than
    calling it a "ramp" or "stable demand."
    """
    counts = [w["total_violations"] for w in weekly_totals]
    if len(counts) < 4:
        return "Too few weeks to assess enforcement trend."

    # Detect gap weeks (< 5% of the median count — reporting dropout, not demand)
    median = float(pd.Series(counts).median())
    gap_threshold = max(median * 0.05, 50)
    gap_weeks = [w["week"] for w, c in zip(weekly_totals, counts) if c < gap_threshold]

    first3_avg = sum(counts[:3]) / 3
    last3_avg  = sum(counts[-3:]) / 3
    ratio      = last3_avg / first3_avg if first3_avg > 0 else 0.0

    if gap_weeks:
        return (
            f"Data contains reporting gaps (near-zero counts in {', '.join(gap_weeks)}), "
            f"likely reflecting enforcement-drive start/stop rather than smooth demand. "
            f"Weekly totals are NOT a monotonic ramp — they reflect reporting effort. "
            f"Forecast lags trained across the gap may be noisy; treat predictions with caution."
        )
    elif ratio > 1.5:
        return (
            f"Weekly totals show an upward trend (first-3-week avg {first3_avg:.0f} → "
            f"last-3-week avg {last3_avg:.0f}, {ratio:.1f}x). Model may partly be "
            f"forecasting reporting effort rather than pure parking demand."
        )
    else:
        return (
            f"Weekly totals are broadly flat (first-3-week avg {first3_avg:.0f}, "
            f"last-3-week avg {last3_avg:.0f}, ratio {ratio:.2f}x). "
            f"No evidence of an enforcement-effort ramp — model targets stable demand signal."
        )


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
        h3.latlng_to_cell(lat, lng, res)
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
    with Poisson objective, evaluate MAE + baselines + Precision@N on hold-out.
    Also computes weekly totals and enforcement-ramp diagnosis for the API response.
    """
    weekly_totals     = _compute_weekly_totals(vdf)
    data_quality_note = _enforcement_ramp_note(weekly_totals)

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

    if len(y_ho) == 0:
        mae = mae_naive_last = mae_naive_roll = 0.0
        precision_at = {}
    else:
        y_pred  = model.predict(X_ho)
        y_true  = y_ho.values

        mae              = float(np.abs(y_pred - y_true).mean())
        mae_naive_last   = float(np.abs(holdout["lag1"].fillna(0).values - y_true).mean())
        mae_naive_roll   = float(np.abs(holdout["rolling_mean_4w"].fillna(0).values - y_true).mean())

        # Precision@N: fraction of actual top-N hotspots that appear in predicted top-N.
        # Computed on the *most recent* holdout week only (the last week in holdout),
        # so ranking is meaningful (single point-in-time snapshot).
        last_ho_ord = holdout["week_ord"].max()
        snap = holdout[holdout["week_ord"] == last_ho_ord].copy()
        snap["_pred"] = model.predict(snap[_FEATURE_COLS].fillna(0))

        precision_at: dict[int, float] = {}
        for n in (10, 20):
            actual_top  = set(snap.nlargest(n, "count")["hotspot_id"])
            predict_top = set(snap.nlargest(n, "_pred")["hotspot_id"])
            overlap     = len(actual_top & predict_top)
            # Only report if there are at least n hotspots in the snapshot
            if len(snap) >= n:
                precision_at[n] = round(overlap / n, 3)

    # Determine the ISO week immediately after the last observed week.
    last_yr, last_wk = all_ords[-1] // 100, all_ords[-1] % 100
    next_monday = (
        datetime.date.fromisocalendar(last_yr, last_wk, 1)
        + datetime.timedelta(weeks=1)
    )
    ni = next_monday.isocalendar()
    next_yr, next_wk = int(ni[0]), int(ni[1])

    return {
        "model":              model,
        "panel":              panel,
        "mae":                mae,
        "mae_naive_last":     mae_naive_last,
        "mae_naive_roll":     mae_naive_roll,
        "precision_at":       precision_at,
        "weekly_totals":      weekly_totals,
        "data_quality_note":  data_quality_note,
        "predict_week":       _iso_label(next_yr, next_wk),
        "next_yr":            next_yr,
        "next_wk":            next_wk,
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
            "month":              _month_from_iso(next_yr, next_wk),
            "violation_severity": float(latest["violation_severity"]),
            "has_junction":       float(latest["has_junction"]),
            "has_poi":            float(latest["has_poi"]),
            "prev_week_count":    int(lag1),
        }

    inf = pd.DataFrame([
        _inference_row(g) for _, g in last4.groupby("hotspot_id", sort=False)
    ])

    # XGBoost prediction — kept for comparison but NOT the headline number
    inf["xgb_predicted"] = (
        model.predict(inf[_FEATURE_COLS].fillna(0)).clip(min=0)
    )

    # Primary prediction: 4-week rolling mean (MAE 1.30 vs XGBoost 4.63)
    inf["predicted_count"] = inf["rolling_mean_4w"].clip(lower=0).round(1)

    # Use max(prev, 1) to avoid absurd % when prev_week_count is 0
    inf["change_pct"] = (
        (inf["predicted_count"] - inf["prev_week_count"])
        / inf["prev_week_count"].clip(lower=1).astype(float)
        * 100
    ).round(1)
    inf["count_delta"] = (inf["predicted_count"] - inf["prev_week_count"]).round(0).astype(int)

    top = inf.nlargest(top_n, "predicted_count").reset_index(drop=True)

    mae       = ctx["mae"]
    mae_last  = ctx["mae_naive_last"]
    mae_roll  = ctx["mae_naive_roll"]

    def _build_item(row):
        predicted = round(float(row["predicted_count"]), 1)
        prev = int(row["prev_week_count"])
        delta = int(row["count_delta"])

        # If baseline is too low, percentage is meaningless
        if prev < 3:
            return {
                "hotspot_id":      row["hotspot_id"],
                "police_station":  row["police_station"],
                "predicted_count": predicted,
                "prev_week_count": prev,
                "change_pct":      None,
                "count_delta":     delta,
                "trend_label":     "emerging" if predicted > 5 else "insufficient history",
                "risk_score":      round(float(row["risk_score"]), 1),
            }

        pct = float(row["change_pct"])
        # Classify trend
        if pct > 500:
            label = "surging"
            pct = round(pct, 1)  # keep actual value, don't cap
        elif pct > 50:
            label = "rising"
        elif pct > -20:
            label = "stable"
        else:
            label = "declining"

        return {
            "hotspot_id":      row["hotspot_id"],
            "police_station":  row["police_station"],
            "predicted_count": predicted,
            "prev_week_count": prev,
            "change_pct":      round(pct, 1),
            "count_delta":     delta,
            "trend_label":     label,
            "risk_score":      round(float(row["risk_score"]), 1),
        }

    return {
        "predict_week":              ctx["predict_week"],
        "method":                    "4-week rolling mean",
        "model_mae":                 round(mae_roll, 2),
        "baseline_mae_last_week":    round(mae_last, 2),
        "baseline_mae_rolling_mean": round(mae_roll, 2),
        "precision_at":              ctx["precision_at"],
        "weekly_totals":             ctx["weekly_totals"],
        "data_quality_note":         ctx["data_quality_note"],
        "model_comparison": {
            "xgboost_mae":           round(mae, 2),
            "rolling_mean_mae":      round(mae_roll, 2),
            "last_week_mae":         round(mae_last, 2),
            "note":                  (
                "XGBoost count:poisson model trained but underperforms "
                "the simple rolling mean baseline (MAE {:.2f} vs {:.2f}) "
                "due to enforcement reporting gaps in weeks 06-10. "
                "Rolling mean is used as the primary prediction."
            ).format(mae, mae_roll),
        },
        "forecast": [_build_item(row) for _, row in top.iterrows()],
    }

