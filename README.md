# Trinetra: Bengaluru Illegal Parking Intelligence

Converting raw parking-violation logs into a prioritised, deployable enforcement plan for Bengaluru Traffic Police.

## Overview

Trinetra processes a raw violations CSV (112,000+ rows, Nov 2023 to Mar 2024) through a three-stage pipeline:

1. **Offline ETL pipeline** — cleans, clusters, and scores violations into spatial hotspots, temporal matrices, and repeat-offender records. Outputs are written as Parquet files.
2. **FastAPI backend** — loads the Parquet artifacts into memory at startup and serves REST endpoints. On-demand logic (patrol optimisation, forecasting) runs in-process with no disk I/O at request time.
3. **Next.js frontend (Trinetra)** — consumes the REST API and renders nine views: Overview, Live Map, Forecasts, Patrol Deployment, POI Spillover, Temporal Distribution, Stations, Junctions, and Repeat Offenders.

## Key Capabilities

- **H3 hexbin hotspot detection.** Partitions the city into resolution-9 cells (~174 m edge) rather than DBSCAN. DBSCAN was discarded because fixed enforcement cameras stack thousands of violations at identical coordinates, causing a single epsilon-radius cluster to absorb 50-60 percent of all rows.
- **Composite risk scoring.** Each hotspot receives a 0-100 risk score from four weighted components: violation severity (0.40), log-normalised density (0.25), vehicle blocking weight (0.20), and a junction-proximity bonus (0.15).
- **Predictive weekly forecasting.** An XGBoost count:poisson model is trained on lag features, a 4-week rolling mean, and static hotspot attributes. On the clean holdout (W03-W04, before a validation-status backlog corrupted W06 onward), the model MAE is 5.26 violations per hotspot, matching the 4-week rolling mean baseline (5.25). The rolling mean is used as the primary displayed prediction because it is equally accurate and interpretable for a non-technical police audience.
- **Greedy patrol optimiser.** Assigns N patrol units to maximise priority-weighted coverage. Each unit is anchored to the highest-priority uncovered hotspot, then extended to up to four nearby stops within 2 km using a nearest-neighbour route. Hotspots within 1 km of any route point are marked covered.
- **Afternoon enforcement blind spot.** The `GET /stats` endpoint computes the fraction of violations logged between 13:00 and 16:00 IST. Across this dataset it is near zero, confirming almost no afternoon enforcement. The value is surfaced as a KPI tile on the Overview page.
- **POI spillover tagging.** Keyword-matches location text from the violations table to assign each hotspot to one of four categories: sensitive (schools, hospitals), metro, commercial, or transit. No external geofencing database is used.
- **PII-masked repeat offenders.** Vehicle plate numbers are partially masked (e.g., `KA01AB****23`) before being returned by the API.

## Architecture

```
data/raw/violations.csv
        |
        v
backend/pipeline/build_dataset.py      (load -> clean -> feature engineering -> violations.parquet)
        |
        v
backend/pipeline/precompute.py         (hotspot clustering -> risk scoring -> temporal matrices -> station/junction rollups)
        |
        v
data/processed/
    violations.parquet
    hotspots.parquet
    temporal.parquet
    by_station.parquet
    by_junction.parquet
    repeat_offenders.parquet           (optional)
        |
        v
backend/app/main.py                    (FastAPI, loads parquets into memory at startup)
    /hotspots  /heatmap  /priority
    /forecast  /patrol   /stats
    /temporal/{id}       /stations
    /junctions           /repeat-offenders
    /poi-stats           /enforcement-quality
        |
        v
frontend_v2/                           (Next.js 16 + React 19 + React Leaflet + Recharts)
```

## Tech Stack

| Layer | Library / Version | Role |
|---|---|---|
| Python runtime | Python 3.11+ | Pipeline and backend |
| Data processing | pandas 2.2.3, numpy 1.26.4 | ETL, feature engineering, in-process queries |
| Spatial clustering | h3 3.7.7 | H3 hexbin partitioning at resolution 9 |
| Machine learning | scikit-learn 1.5.2, xgboost 2.1.3 | Feature preprocessing, XGBoost forecasting |
| Geospatial utilities | geopandas 0.14.4, shapely 2.0.6 | Coordinate validation, geometry helpers |
| Serialisation | pyarrow 17.0.0 | Parquet read/write |
| API server | fastapi 0.115.5, uvicorn 0.32.1 | REST endpoints, lifespan-managed data loading |
| Schema validation | pydantic 2.10.3, pydantic-settings 2.14.1 | Request/response models, config from env |
| Frontend framework | next 16.2.9, react 19.2.4 | App Router, server components, page routing |
| Mapping | leaflet 1.9.4, react-leaflet 5.0.0 | Interactive hotspot map with patrol routes |
| Charts | recharts 3.8.1 | Temporal heatmaps, forecast charts |
| Styling | tailwindcss 4, tailwind-merge 3.6.0 | Utility-first CSS |

## Folder Structure

```
gridlockb/
  backend/
    app/
      core/           config.py (weights, paths, DBSCAN params), store.py (in-memory singletons)
      models/         schemas.py (Pydantic response models)
      routers/        hotspots.py, analytics.py
      services/       forecast.py, patrol_optimizer.py, hotspots.py, risk_score.py,
                      temporal.py, aggregations.py, poi_tagging.py, analytics_service.py
    pipeline/
      build_dataset.py   Step 1: load -> clean -> features -> violations.parquet
      precompute.py      Step 2: hotspots, temporal matrices, station/junction rollups
      load.py, clean.py, features.py
    tests/
      test_api.py
  data/
    raw/               violations.csv (not committed)
    processed/         *.parquet artifacts (not committed)
  frontend_v2/
    src/app/           Route pages: page.tsx, map/, forecast/, deploy/, offenders/,
                       poi/, temporal/, stations/, junctions/
    src/components/    LiveMap.tsx, MapWrapper.tsx, Sidebar.tsx
    src/lib/           api.ts (fetchApi + typed wrappers), hooks/useWatchlist.ts
  notebooks/
    01_eda.ipynb
  docs/
    RUN_INSTRUCTIONS.md
  run.sh
  requirements.txt
```

## Prerequisites

- Python 3.11 or later
- Node.js 18 or later and npm
- The raw dataset at `data/raw/violations.csv` (not included in the repository)

## Setup

### 1. Clone and create a virtual environment

```bash
git clone <repository-url>
cd gridlockb
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Install Node dependencies

```bash
cd frontend_v2
npm install
cd ..
```

### 4. Environment variables

The frontend reads one environment variable. Create `frontend_v2/.env.local`:

```
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

The backend reads its configuration from `pydantic-settings`. All defaults point to `data/raw/violations.csv` and `data/processed/`. Override via a `.env` file in the repo root if your paths differ.

## Running the Pipeline

Run these two commands once from the repo root before starting the servers. They are skipped automatically by `run.sh` if `data/processed/*.parquet` files already exist.

```bash
# Step 1: clean and feature-engineer the raw CSV
python -m backend.pipeline.build_dataset

# Step 2: cluster hotspots, build temporal matrices, station/junction rollups
python -m backend.pipeline.precompute
```

To force a rebuild:

```bash
python -m backend.pipeline.build_dataset --broad   # includes unvalidated rows
python -m backend.pipeline.precompute --steps hotspots temporal aggregations
```

## Running the Application

### Option A: single script (Linux / macOS / Git Bash)

```bash
./run.sh
# Pass --force to rebuild the pipeline even if processed data exists
./run.sh --force
```

The script checks for `data/raw/violations.csv`, runs the pipeline if needed, starts the FastAPI backend on port 8000, waits for it to become healthy, then builds and starts the Next.js frontend.

### Option B: two terminals

**Terminal 1 (backend):**

```bash
uvicorn backend.app.main:app --reload --port 8000
```

**Terminal 2 (frontend):**

```bash
cd frontend_v2
npm run dev
```

Access the application at `http://localhost:3000`.
The interactive API documentation is available at `http://localhost:8000/docs`.

## API Reference

All responses are JSON. The base URL defaults to `http://127.0.0.1:8000`.

| Method | Path | Key query params | Description |
|---|---|---|---|
| GET | `/` | | Health check. Returns hotspot and violation counts. |
| GET | `/stats` | | Total violations, hotspot count, date range, vehicle/violation/station breakdowns, afternoon blind-spot percentage. |
| GET | `/hotspots` | `police_station`, `violation_type`, `vehicle_type`, `min_risk` (float), `poi_category`, `limit` (default 500, max 1200) | Filtered hotspot list with coordinates, risk scores, and logging window. |
| GET | `/heatmap` | same filters as `/hotspots` | Lat/lng/weight tuples for a Leaflet heatmap layer. |
| GET | `/priority` | `police_station`, `vehicle_type`, `limit` (default 50) | Hotspots ranked by risk score with Critical / Elevated / Standard tier labels. |
| GET | `/forecast` | `top_n` (default 20, max 2000) | Next-week predicted violation counts per hotspot. Includes MAE, baseline comparisons, precision-at-N, and a citywide summary. |
| GET | `/patrol` | `units` (default 10, max 100) | Greedy patrol assignments for N units. Returns coverage percentage, naive baseline comparison, and a coverage curve. |
| GET | `/temporal/{hotspot_id}` | | Hour x day-of-week count matrix for one hotspot. |
| GET | `/stations` | `min_hotspots`, `limit` | Police-station rollup: hotspot count, average risk, blind-spot percentage. |
| GET | `/junctions` | `min_violations`, `limit` | Named-junction rollup: violation count, average risk, top hotspot. |
| GET | `/repeat-offenders` | `limit` (default 20) | Top repeat vehicles with PII-masked plate numbers and violation counts. |
| GET | `/poi-stats` | | Per-category counts, violation totals, and average risk for the four POI categories. |
| GET | `/enforcement-quality` | | Per-station rejection rates from the `validation_status` field. |

## Risk Score Formula

```
risk_score = (severity_score_agg  x 0.40)
           + (density_score        x 0.25)
           + (vehicle_score_agg   x 0.20)
           + (junction_input      x 0.15)

Clamped to [0, 100].
```

- `severity_score_agg`: mean per-violation severity normalised to 0-100. "PARKING IN A MAIN ROAD" = 100; "NO PARKING" = 33.
- `density_score`: log1p-normalised violation count. `log1p(count) / log1p(max_count) x 100`.
- `vehicle_score_agg`: mean carriageway-blocking weight normalised to 0-100. Tanker/HGV = 100; scooter = 30.
- `junction_input`: flat bonus of 25 when at least 50 percent of the hotspot's violations carry a named junction, otherwise 0.

Weights are in `backend/app/core/config.py` and can be adjusted without touching the scoring code.

## Forecasting Notes

- **Training data.** The dataset covers approximately 20 ISO weeks (Nov 2023 to Mar 2024). Weeks W06-W10 and W12-W13 have over 80 percent null `validation_status` values due to an approval-system backlog, making them unreliable for lag training. The model is trained on clean weeks only; W01-W05 are used as the baseline and W02-W05 as the lag window.
- **Model.** XGBoost with `count:poisson` objective. 200 estimators, max depth 5, learning rate 0.05, subsample 0.8.
- **Evaluation.** Holdout is W03-W04 (two clean weeks before the gap). XGBoost MAE: 5.26. Rolling-mean baseline MAE: 5.25. The two methods are near-tied on this dataset because only four clean weeks of lag history are available. The rolling mean is used for the displayed prediction.
- **Precision-at-N.** On the most recent holdout week: Precision@10 = 0.60, Precision@20 = 0.60 (fraction of actual top-N hotspots that appear in the predicted top-N).

## Results

| Metric | Value |
|---|---|
| Total violations processed | 112,000+ rows |
| Forecast MAE (XGBoost, clean holdout) | 5.26 violations per hotspot |
| Forecast MAE (4-week rolling mean) | 5.25 violations per hotspot |
| Precision@10 (top-10 hotspot ranking) | 0.60 |
| Precision@20 (top-20 hotspot ranking) | 0.60 |
| Afternoon blind-spot enforcement share | ~0% of violations logged 13:00-16:00 IST |

Coverage percentage for the patrol optimiser is runtime-computed and depends on the number of units requested and the current hotspot dataset.

## Roadmap

- Replace the static Parquet pipeline with a real-time ingestion feed (Kafka or equivalent).
- Add per-station authentication so station chiefs see only their jurisdiction.
- Expand POI tagging with dynamic bounds from the OpenStreetMap Overpass API.

## License

<!-- TODO: choose a license -->

## Contact

<!-- TODO: add author contact information -->
