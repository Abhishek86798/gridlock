"""
Central configuration — paths, risk-score weights, clustering params, constants.

Risk score formula (documented for explainability):
    raw = (severity_score  * WEIGHT_SEVERITY)
        + (density_score   * WEIGHT_DENSITY)
        + (vehicle_score   * WEIGHT_VEHICLE_SIZE)
        + (junction_bonus  * WEIGHT_JUNCTION)
    risk_score = min(raw, 100)          # clamp to 0–100

All weights are exposed here so they can be tuned without touching analysis code.
"""

from __future__ import annotations
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# ── Repo layout ──────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parents[3]   # d:/gridlockb


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # ── Paths ─────────────────────────────────────────────────────────────────
    raw_csv: Path = BASE_DIR / "data" / "raw" / "violations.csv"
    processed_dir: Path = BASE_DIR / "data" / "processed"

    # Derived parquet paths (properties, not env-overridable)
    @property
    def violations_parquet(self) -> Path:
        return self.processed_dir / "violations.parquet"

    @property
    def hotspots_parquet(self) -> Path:
        return self.processed_dir / "hotspots.parquet"

    @property
    def temporal_parquet(self) -> Path:
        return self.processed_dir / "temporal.parquet"

    @property
    def forecast_parquet(self) -> Path:
        return self.processed_dir / "forecast.parquet"

    @property
    def repeat_offenders_parquet(self) -> Path:
        return self.processed_dir / "repeat_offenders.parquet"

    # ── Coordinate validation (Bengaluru bounding box) ────────────────────────
    lat_min: float = 12.834
    lat_max: float = 13.143
    lng_min: float = 77.461
    lng_max: float = 77.784

    # ── Spatial clustering (DBSCAN) ───────────────────────────────────────────
    # eps in degrees (~200 m at Bengaluru's latitude: 200m / 111_320 ≈ 0.0018)
    dbscan_eps: float = 0.0018
    dbscan_min_samples: int = 5

    # H3 resolution (alternative to DBSCAN): res 9 ≈ 174 m hex edge
    h3_resolution: int = 9

    # ── Risk-score component weights (must sum to 1.0) ────────────────────────
    weight_severity: float = 0.40
    weight_density: float = 0.25
    weight_vehicle_size: float = 0.20
    weight_junction: float = 0.15

    # ── Junction bonus (added when junction_name is not null) ─────────────────
    junction_bonus_value: float = 25.0

    # ── POI proximity radius (metres) ─────────────────────────────────────────
    poi_radius_m: float = 200.0

    # ── Forecasting ───────────────────────────────────────────────────────────
    forecast_horizon_hours: int = 24    # how far ahead to predict
    forecast_n_estimators: int = 200
    forecast_max_depth: int = 5

    # ── Patrol optimizer ──────────────────────────────────────────────────────
    default_patrol_units: int = 10
    max_patrol_units: int = 100


settings = Settings()


# ── Lookup tables (constants, not env-overridable) ───────────────────────────
# These live here — not inside Settings — because pydantic-settings doesn't
# cleanly round-trip nested dicts through env vars.

# Relative severity of each violation type (higher = worse traffic impact).
# Source: domain knowledge / REQUIREMENTS.md FR-4.
SEVERITY_WEIGHTS: dict[str, float] = {
    "PARKING IN A MAIN ROAD":       3.0,
    "PARKING NEAR ROAD CROSSING":   2.5,
    "PARKING ON FOOTPATH":          2.0,
    "WRONG PARKING":                1.5,
    "NO PARKING":                   1.0,
}
DEFAULT_SEVERITY: float = 1.0   # fallback for unknown violation types

# Carriageway-blocking multiplier per vehicle class (larger = more obstruction).
VEHICLE_WEIGHTS: dict[str, float] = {
    "TANKER":       3.0,
    "TRUCK":        2.5,
    "BUS":          2.5,
    "CAR":          1.5,
    "AUTO":         1.2,
    "SCOOTER":      1.0,
    "MOTORCYCLE":   1.0,
    "TWO WHEELER":  1.0,
}
DEFAULT_VEHICLE_WEIGHT: float = 1.0   # fallback for unknown vehicle types
