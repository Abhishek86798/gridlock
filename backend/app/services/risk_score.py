"""
Step 2.3 - Congestion-impact score: interpretable 0-100 index per hotspot.

This is a CARRIAGEWAY-OBSTRUCTION impact index, not a count-risk score. It is
built to vary widely so a tanker on a main road at a junction massively
outscores a scooter on a side lane — directly answering the problem statement's
"quantify impact on traffic flow" goal.

Formula (documented for explainability to judges / BTP leadership)
------------------------------------------------------------------

  core = (severity_share x SEV_W)    [0.45]   % high-impact parking
       + (density_score  x DEN_W)    [0.30]   log-normalised volume
       + (vehicle_share  x VEH_W)    [0.25]   % large vehicles

  risk_score = core x (1 + JUNC_MULT x junction_flag)   then clamp [0, 100]

  The junction term is MULTIPLICATIVE — a hotspot at an intersection is
  categorically worse, not "+3.75 points worse". (1 + x) form so it can only
  amplify, never annihilate.

Why SHARES, not means (the key design choice)
---------------------------------------------
  The previous score averaged per-violation severity/vehicle weights. Averaging
  hundreds of violations mean-reverts every hotspot toward the population centre
  (old score: mean 42, std 7 — nearly constant). A cell with many tankers but
  mostly scooters averaged to "medium" and the tanker signal vanished.

  Shares preserve the tail: "62% of this cell is main-road parking" /
  "34% are large vehicles" stays high regardless of the scooter background, and
  it is more interpretable than "mean severity 56".

Small-sample shrinkage (James-Stein toward the global prior)
------------------------------------------------------------
  A cell with 9 violations that happen to all be main-road parking shows 100%
  severity share — noise, not a hotspot. Each share is shrunk toward the global
  rate with strength SHRINK_K: a cell with n=SHRINK_K is pulled halfway to the
  prior; large cells are barely moved. This kept n<15 cells in the top-100 down
  from 31 (raw) to 2 (shrunk) in prototyping.

      shrunk_share = (k_hits + SHRINK_K * prior) / (n + SHRINK_K) * 100

Component scales
----------------
  severity_share  (0-100)  % of cell's violations that are high-impact types
                           (main road / near crossing / traffic-light-zebra).
  vehicle_share   (0-100)  % of cell's violations by large vehicles
                           (vehicle_score >= LARGE_VEHICLE_FLOOR, ~LGV and up).
  density_score   (0-100)  log1p(count) / log1p(ref_max) * 100.
  junction_flag   (0 or 1) 1 when >= 50% of the cell's violations are at a
                           named junction.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backend.app.core.config import settings

# ── Impact-index tuning (locked after offline prototype; see risk_score docs) ──
SEV_W = 0.45
DEN_W = 0.30
VEH_W = 0.25
JUNC_MULT = 0.35            # junction hotspot scores up to 35% higher
SHRINK_K = 20              # shrinkage strength: n=20 → halfway to the prior
LARGE_VEHICLE_FLOOR = 80.0  # vehicle_score >= this == "large vehicle" (LGV+)

# High-impact violation types — the ones that genuinely choke a carriageway.
HIGH_IMPACT_VIOLATIONS = {
    "PARKING IN A MAIN ROAD",
    "PARKING NEAR ROAD CROSSING",
    "PARKING NEAR TRAFFIC LIGHT OR ZEBRA CROSS",
}


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


def _shrunk_share(hits: pd.Series, n: pd.Series, prior: float) -> pd.Series:
    """James-Stein shrinkage of a 0-1 rate toward ``prior``, returned as 0-100.

    A cell with n == SHRINK_K is pulled halfway to the prior; large cells are
    barely moved. Kills small-sample share spikes (9/9 = 100%) without touching
    genuine high-volume hotspots.
    """
    return ((hits + SHRINK_K * prior) / (n + SHRINK_K) * 100).astype("float32")


def compute_risk_scores(hotspots: pd.DataFrame) -> pd.DataFrame:
    """Apply the congestion-impact formula to a hotspots DataFrame.

    Expects columns produced by compute_hotspots():
        high_impact_count  int    # high-impact-type violations in cluster
        large_vehicle_count int   # large-vehicle violations in cluster
        violation_count    int    total violations in cluster
        junction_flag      float  0 or 1 (>= 50% at a named junction)

    Adds columns:
        severity_share  float32  shrunk % high-impact (0-100)
        vehicle_share   float32  shrunk % large-vehicle (0-100)
        density_score   float32  log-normalised count (0-100)
        risk_score      float32  final composite impact index (0-100)

    Returns
    -------
    pd.DataFrame
        Same DataFrame with the four columns above added.
    """
    df = hotspots.copy()

    n = df["violation_count"].astype(float)
    # Global priors = citywide hit rates (weighted by volume).
    prior_sev = float(df["high_impact_count"].sum() / n.sum()) if n.sum() else 0.0
    prior_veh = float(df["large_vehicle_count"].sum() / n.sum()) if n.sum() else 0.0

    df["severity_share"] = _shrunk_share(df["high_impact_count"].astype(float), n, prior_sev)
    df["vehicle_share"]  = _shrunk_share(df["large_vehicle_count"].astype(float), n, prior_veh)
    df["density_score"]  = compute_density_score(df["violation_count"]).round(2)

    core = (
        df["severity_share"] * SEV_W
        + df["density_score"] * DEN_W
        + df["vehicle_share"] * VEH_W
    )
    raw = core * (1.0 + JUNC_MULT * df["junction_flag"].astype(float))
    df["risk_score"] = raw.clip(upper=100).round(2).astype("float32")

    return df


def score_breakdown(hotspot_row: pd.Series) -> dict[str, float]:
    """Return a labelled breakdown of how a single hotspot's score is built.

    The judge explainability moment: "walk me through the score." Shows the
    three additive components and the junction multiplier separately.
    """
    sev = float(hotspot_row["severity_share"])
    den = float(hotspot_row["density_score"])
    veh = float(hotspot_row["vehicle_share"])
    junc_flag = float(hotspot_row["junction_flag"])

    sev_contrib = sev * SEV_W
    den_contrib = den * DEN_W
    veh_contrib = veh * VEH_W
    core = sev_contrib + den_contrib + veh_contrib
    multiplier = 1.0 + JUNC_MULT * junc_flag
    total = min(core * multiplier, 100.0)

    return {
        "severity_component  (x0.45)": round(sev_contrib, 2),
        "density_component   (x0.30)": round(den_contrib, 2),
        "vehicle_component   (x0.25)": round(veh_contrib, 2),
        "core                       ": round(core, 2),
        "junction_multiplier        ": round(multiplier, 2),
        "risk_score                 ": round(total, 2),
    }
