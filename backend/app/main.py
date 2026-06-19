"""
FastAPI application entry point.

Run from the repo root:
    uvicorn backend.app.main:app --reload --port 8000

Startup loads all precomputed parquets into memory once so every
endpoint is an in-process DataFrame query — no disk I/O at request time.
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager

import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core import store
from backend.app.core.config import settings
from backend.app.routers import analytics, hotspots


def _load_parquet(path, label: str) -> pd.DataFrame:
    t0 = time.perf_counter()
    df = pd.read_parquet(path)
    ms = (time.perf_counter() - t0) * 1000
    print(f"  [{ms:5.0f} ms]  {label:<20} {len(df):>7,} rows  ({path.stat().st_size // 1024} KB)")
    return df


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("-- Gridlock API: loading artifacts --")
    missing = [
        p for p in (
            settings.violations_parquet,
            settings.hotspots_parquet,
            settings.temporal_parquet,
            settings.by_station_parquet,
            settings.by_junction_parquet,
        )
        if not p.exists()
    ]
    if missing:
        names = ", ".join(p.name for p in missing)
        raise RuntimeError(
            f"Missing parquets: {names}. "
            "Run: python -m backend.pipeline.build_dataset && "
            "python -m backend.pipeline.precompute"
        )

    store.violations  = _load_parquet(settings.violations_parquet,  "violations")
    store.hotspots    = _load_parquet(settings.hotspots_parquet,    "hotspots")
    store.temporal    = _load_parquet(settings.temporal_parquet,    "temporal")
    store.by_station  = _load_parquet(settings.by_station_parquet,  "by_station")
    store.by_junction = _load_parquet(settings.by_junction_parquet, "by_junction")
    print("-- Ready --")
    yield
    # Nothing to clean up — DataFrames are GC'd automatically.


app = FastAPI(
    title="Gridlock Parking Intelligence API",
    description="Bengaluru illegal-parking analytics — Flipkart x BTP hackathon",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(hotspots.router)
app.include_router(analytics.router)


@app.get("/", tags=["health"])
def health():
    return {
        "status": "ok",
        "hotspots": len(store.hotspots),
        "violations": len(store.violations),
    }
