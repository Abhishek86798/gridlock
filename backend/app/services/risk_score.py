"""
Step 2.3 - Congestion-risk score: interpretable 0-100 impact index per hotspot.

Formula (documented for explainability to judges / BTP leadership)
------------------------------------------------------------------

  risk_score = (severity_score_agg  x weight_severity)    [0.40]
             + (density_score        x weight_density)     [0.25]
             + (vehicle_score_agg   x weight_vehicle_size) [0.20]
             + (junction_input      x weight_junction)     [0.15]

  Clamped to [0, 100]. All four components are on a 0-100 scale.

Component breakdown
-------------------
  severity_score_agg  (0-100)
      Mean per-violation severity weight, normalised to 0-100.
      PARKING IN A MAIN ROAD = 100 (3.0 / max 3.0)
      PARKING NEAR ROAD CROSSING = 83
      PARKING ON FOOTPATH = 67
      WRONG PARKING = 50
      NO PARKING / unknown = 33
      Source: SEVERITY_WEIGHTS in config.py, normalised in features.py.

  density_score  (0-100)
      Log-normalised violation count. log1p is used so that the
      difference between a 10-violation cell and a 50-violation cell
      is meaningful, but a single mega-cluster at 5,000+ doesn't
      compress everything else to near-zero.
      density_score = log1p(count) / log1p(ref_max) x 100
      ref_max defaults to the observed maximum across all hotspots,
      but can be fixed for reproducibility across incremental runs.

  vehicle_score_agg  (0-100)
      Mean per-violation carriageway-blocking score, normalised 0-100.
      Tanker / HGV / large bus = 100  (1.0 / max 1.0 x 100)
      LGV / tempo = 80-85
      Car / van = 70-75
      Scooter / motorcycle = 30
      Source: VEHICLE_NORMALIZE in config.py, applied in features.py.

  junction_input  (0 or 25)
      Flat bonus from config.junction_bonus_value when >= 50 % of the
      hotspot's violations carry a named junction. Represents the
      documented higher traffic impact at intersections.
      Max contribution: 25 x 0.15 = 3.75 points.

Tuning
------
  All weights and the junction bonus value are exposed in config.py so
  they can be adjusted without touching this file. The formula is
  documented above so any judge can audit it in under 60 seconds.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backend.app.core.config import settings


def compute_density_score(
    counts: pd.Series,
    ref_max: float | None = None,
) -> pd.Series:
    """Log-normalise violation counts to a 0-100 density score.

    Parameters
    ----------
    counts:
        Series of integer violation counts, one per hotspot.
    ref_max:
        Reference maximum for normalisation. Defaults to the series
        maximum. Pin this to a fixed value when running incremental
        updates so existing scores don't drift.

    Returns
    -------
    pd.Series
        Float series on [0, 100], same index as counts.
    """
    max_val = float(ref_max) if ref_max is not None else float(counts.max())
    if max_val == 0:
        return pd.Series(0.0, index=counts.index, dtype="float32")
    return (np.log1p(counts.astype(float)) / np.log1p(max_val) * 100).astype("float32")


def compute_risk_scores(hotspots: pd.DataFrame) -> pd.DataFrame:
    """Apply the documented risk-score formula to a hotspots DataFrame.

    Expects columns produced by compute_hotspots():
        severity_score_agg  float  mean per-violation severity (0-100)
        vehicle_score_agg   float  mean per-violation vehicle weight (0-100)
        junction_input      float  0 or junction_bonus_value (default 25)
        violation_count     int    total violations in cluster

    Adds columns:
        density_score  float32  log-normalised count (0-100)
        risk_score     float32  final composite score (0-100)

    Parameters
    ----------
    hotspots:
        DataFrame with one row per hotspot.

    Returns
    -------
    pd.DataFrame
        Same DataFrame with density_score and risk_score columns added.
    """
    df = hotspots.copy()

    df["density_score"] = compute_density_score(df["violation_count"]).round(2)

    raw = (
        df["severity_score_agg"] * settings.weight_severity
        + df["density_score"]    * settings.weight_density
        + df["vehicle_score_agg"] * settings.weight_vehicle_size
        + df["junction_input"]   * settings.weight_junction
    )
    df["risk_score"] = raw.clip(upper=100).round(2).astype("float32")

    return df


def score_breakdown(hotspot_row: pd.Series) -> dict[str, float]:
    """Return a labelled breakdown of how a single hotspot's score is built.

    Useful for the judge explainability moment: "walk me through the score."

    Example
    -------
    >>> breakdown = score_breakdown(hotspots.iloc[0])
    >>> for component, value in breakdown.items():
    ...     print(f"  {component}: {value:.1f}")
    """
    sev  = float(hotspot_row["severity_score_agg"])
    den  = float(hotspot_row["density_score"])
    veh  = float(hotspot_row["vehicle_score_agg"])
    junc = float(hotspot_row["junction_input"])

    sev_contrib  = sev  * settings.weight_severity
    den_contrib  = den  * settings.weight_density
    veh_contrib  = veh  * settings.weight_vehicle_size
    junc_contrib = junc * settings.weight_junction
    total        = min(sev_contrib + den_contrib + veh_contrib + junc_contrib, 100.0)

    return {
        "severity_component  (x0.40)": round(sev_contrib,  2),
        "density_component   (x0.25)": round(den_contrib,  2),
        "vehicle_component   (x0.20)": round(veh_contrib,  2),
        "junction_component  (x0.15)": round(junc_contrib, 2),
        "risk_score                  ": round(total,         2),
    }
