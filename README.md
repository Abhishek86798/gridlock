# Trinetra: Bengaluru Illegal Parking Intelligence

Trinetra is a parking-violation analytics and enforcement-support system built for the Flipkart x Bengaluru Traffic Police (BTP) hackathon (PS1: Poor Visibility on Parking-Induced Congestion). It processes raw violation logs from BTP into a prioritised, deployable enforcement plan. The system detects spatial hotspots, scores their congestion risk through a documented weighted index, forecasts next-week violation trends, and recommends optimal patrol assignments for a given number of units. It is intended for use by station chiefs and field commanders who need to move from reactive roaming patrols to targeted, data-driven deployments.

## Key Features

- **H3 hexbin hotspot detection.** Partitions Bengaluru into resolution-9 cells (approximately 174 m edge) and aggregates violations per cell, producing a ranked list of hotspot zones.
- **Composite congestion-risk score.** Assigns each hotspot a 0-100 impact index from four documented components: violation severity, log-normalised density, vehicle blocking weight, and junction-proximity bonus.
- **Temporal analysis.** Builds hour-of-day by day-of-week count matrices per hotspot and exposes them as heatmaps. Treats all timestamps as logging-activity signals, not as violation-occurrence times (see Limitations).
- **Afternoon enforcement blind-spot detection.** Computes the fraction of violations logged between 13:00 and 16:00 IST across each station. Near-zero values confirm a near-total absence of afternoon enforcement.
- **Weekly escalation forecasting.** An XGBoost count:poisson model trained on lag features, a 4-week rolling mean, and static hotspot attributes predicts next-week violation counts per hotspot. Escalating hotspots are flagged by percentage change and absolute volume tier.
- **Greedy spatial patrol optimiser.** Given N units, assigns each unit to the highest-priority uncovered hotspot and extends the route to up to four nearby stops within 2 km using a nearest-neighbour ordering. Hotspots within 1 km of any route point are marked covered.
- **POI spillover tagging.** Keyword-matches officer-logged location text to classify each hotspot into one of four categories: sensitive (schools, hospitals), metro, commercial, or transit. No external geofencing database is used.
- **Repeat-offender analytics.** Aggregates violation counts per vehicle identifier and surfaces chronic offenders and their preferred locations. All vehicle identifiers are PII-masked in API output.
- **Enforcement-quality reporting.** Computes per-station rejection rates from the `validation_status` field to surface where the reporting pipeline is weakest.
- **Station and junction rollups.** Aggregates hotspot and violation metrics by police station (53 stations) and by named junction for command-level views.

## Architecture

No database is used. All data is precomputed into Parquet files by the offline pipeline and loaded into memory at server startup. Every API request is an in-process DataFrame query with no disk I/O. This keeps the stack self-contained and reproducible from a single CSV.

```
data/raw/violations.csv
    |
    v
backend/pipeline/load.py          Parse CSV, attach UTC timezone, coerce numerics
    |
    v
backend/pipeline/clean.py         Filter to approved rows, drop null/OOB coordinates,
                                  parse violation_type JSON arrays, derive primary_violation_type
    |
    v
backend/pipeline/features.py      Convert timestamps to IST, derive hour/weekday/month/week,
                                  add has_junction flag, compute severity_score and vehicle_score
    |
    v
backend/pipeline/build_dataset.py  Write data/processed/violations.parquet
    |
    v
backend/pipeline/precompute.py
    |-- Step 2.1: compute_hotspots()     H3 hexbin clustering + risk scoring + POI tagging
    |                                    Write data/processed/hotspots.parquet
    |-- Step 2.2: compute_temporal()     Hour x weekday matrices per hotspot
    |                                    Write data/processed/temporal.parquet
    +-- Step 2.5: by_police_station()    Station rollup
                  by_junction()          Junction rollup
                                         Write data/processed/by_station.parquet
                                                data/processed/by_junction.parquet
    |
    v
backend/app/main.py               FastAPI lifespan loads all parquets into memory once.
                                  Raises RuntimeError if any required file is missing.
    |
    +-- /hotspots  /heatmap  /priority
    +-- /forecast  (XGBoost trains lazily on first request, then cached)
    +-- /patrol    (greedy optimiser runs per request)
    +-- /stats  /temporal/{id}  /stations  /junctions
    +-- /repeat-offenders  /poi-stats  /enforcement-quality
    |
    v
frontend_v2/  (Next.js 16, React 19)
    Overview, Live Map, Forecasts, Patrol Deployment, POI Spillover,
    Temporal Distribution, Stations, Junctions, Repeat Offenders
```

## Tech Stack

### Backend and Data Pipeline

| Library | Version | Role |
|---|---|---|
| Python | 3.11+ | Runtime |
| fastapi | 0.115.5 | REST API framework |
| uvicorn[standard] | 0.32.1 | ASGI server |
| pydantic | 2.10.3 | Request/response schema validation |
| pydantic-settings | 2.14.1 | Configuration from environment variables |
| python-dotenv | 1.0.1 | `.env` file loading |
| pandas | 2.2.3 | ETL, feature engineering, in-process queries |
| numpy | 1.26.4 | Numerical operations |
| scikit-learn | 1.5.2 | Feature preprocessing utilities |
| xgboost | 2.1.3 | Weekly violation count forecasting |
| scipy | 1.14.1 | Statistical utilities |
| h3 | 3.7.7 | H3 hexbin spatial partitioning at resolution 9 |
| geopandas | 0.14.4 | Coordinate validation and geometry helpers |
| shapely | 2.0.6 | Geometric operations |
| folium | 0.18.0 | Map rendering utility |
| pyarrow | 17.0.0 | Parquet serialisation |
| duckdb | 1.1.3 | Ad-hoc analytical queries |
| streamlit | 1.40.0 | Fallback dashboard |
| plotly | 5.24.1 | Charts in the Streamlit fallback |
| httpx | 0.27.2 | HTTP client for inter-service calls |

### Frontend

| Library | Version | Role |
|---|---|---|
| next | 16.2.9 | App Router, server components, page routing |
| react | 19.2.4 | UI framework |
| react-dom | 19.2.4 | DOM rendering |
| leaflet | 1.9.4 | Interactive map |
| react-leaflet | 5.0.0 | React bindings for Leaflet |
| recharts | 3.8.1 | Temporal heatmaps and forecast charts |
| tailwindcss | 4.x | Utility-first CSS |
| tailwind-merge | 3.6.0 | Class merging utility |
| clsx | 2.1.1 | Conditional class names |
| lucide-react | 1.21.0 | Icon set |
| typescript | 5.x | Type checking |

## Project Structure

```
gridlockb/
  backend/
    app/
      core/
        config.py           All tunable constants: risk weights, DBSCAN params,
                            H3 resolution, bounding box, severity/vehicle lookup tables.
        store.py            Module-level DataFrame singletons populated at startup.
      models/
        schemas.py          Pydantic response models for every endpoint.
      routers/
        hotspots.py         GET /hotspots, /heatmap, /priority
        analytics.py        GET /stats, /temporal/{id}, /forecast, /patrol,
                            /stations, /junctions, /repeat-offenders,
                            /poi-stats, /enforcement-quality
      services/
        forecast.py         XGBoost training, evaluation, and prediction logic.
        patrol_optimizer.py Greedy spatial unit-assignment algorithm.
        hotspots.py         H3 hexbin clustering and logging-window computation.
        risk_score.py       Documented composite risk-score formula.
        temporal.py         Hour x weekday matrix builder.
        aggregations.py     Station and junction rollups; violation_stats helper.
        poi_tagging.py      Keyword-match POI classification.
        analytics_service.py Shared analytics helpers.
      main.py               FastAPI app, CORS middleware, lifespan data loader.
    pipeline/
      load.py               Step 1.1: load CSV with typed columns, UTC datetimes.
      clean.py              Step 1.2: filter approved, parse arrays, drop OOB coords.
      features.py           Step 1.3: IST temporal features, junction flag, risk inputs.
      build_dataset.py      Step 1.4: orchestrates load + clean + features, writes violations.parquet.
      precompute.py         Step 2: hotspot clustering, temporal matrices, rollups.
    tests/
      test_api.py
  data/
    raw/
      violations.csv        Not committed. Place the HackerEarth-provided CSV here.
    processed/              Generated by the pipeline. Not committed.
      violations.parquet
      hotspots.parquet
      temporal.parquet
      by_station.parquet
      by_junction.parquet
      repeat_offenders.parquet
  frontend_v2/
    src/
      app/
        page.tsx            Overview (KPI cards + priority queue)
        map/page.tsx        Live Map with hotspot clusters and patrol routes
        forecast/page.tsx   Weekly escalation forecast and top-10 chart
        deploy/page.tsx     Patrol Deployment Optimizer
        poi/page.tsx        POI Spillover breakdown
        temporal/page.tsx   Temporal heatmap distribution
        stations/page.tsx   Per-station analytics
        junctions/page.tsx  Named-junction analytics
        offenders/page.tsx  Repeat-offender table
      components/
        LiveMap.tsx         React Leaflet map with hotspot markers and patrol routes
        MapWrapper.tsx      Client-side wrapper for SSR-safe map loading
        Sidebar.tsx         Navigation and global filter controls
      lib/
        api.ts              fetchApi wrapper and typed endpoint helpers
        hooks/
          useWatchlist.ts   Client-side hotspot watchlist state
  docs/
    PROJECT_CONTEXT.md      Hackathon brief, problem statement, and design goals
    RUN_INSTRUCTIONS.md     Legacy startup instructions (see Running section below)
  notebooks/
    01_eda.ipynb            Exploratory data analysis
  run.sh                    Bash startup script (pipeline + backend + frontend)
  requirements.txt          Python dependency lockfile
```

## Dataset and Compliance

The dataset is the HackerEarth-provided BTP violations export. Each row represents one logged illegal-parking violation. Key columns used:

| Column | Use |
|---|---|
| `latitude`, `longitude` | H3 hex assignment, hotspot centroid |
| `location` | POI keyword tagging |
| `junction_name` | Junction flag, named-junction rollup |
| `police_station` | Administrative grouping |
| `violation_type` | JSON array, parsed to derive `primary_violation_type` |
| `vehicle_type` | Vehicle blocking-weight score |
| `vehicle_number` | Repeat-offender tracking (synthetic IDs, PII-masked in output) |
| `created_datetime` | IST temporal features (hour, weekday, month, ISO week) |
| `validation_status` | Approved-only filtering |

**Cleaning decisions applied by `clean.py`:**

1. Parse `violation_type` and `offence_code` from JSON-array strings to Python lists.
2. Derive `primary_violation_type` as the single highest-severity violation in each row's list.
3. Filter to `validation_status == "approved"` only. Rows with status `rejected` or `duplicate` are always excluded. Unvalidated rows are excluded by default (pass `--broad` to include them).
4. Drop rows with null `latitude` or `longitude`.
5. Drop rows whose coordinates fall outside the Bengaluru bounding box: lat [12.834, 13.143], lng [77.461, 77.784].
6. Normalise `vehicle_type` to uppercase-stripped form for consistent lookup against `VEHICLE_NORMALIZE`.

**Timezone handling:** `created_datetime` is stored as UTC in the source CSV. `features.py` converts it to `Asia/Kolkata` (IST) before deriving all temporal columns.

**Only the HackerEarth-provided dataset is used for analysis.** POI tagging uses keyword matching against the officer-logged `location` text field, which is part of the provided dataset. No external POI database or geofencing service is queried.

**Raw CSV size:** The raw CSV exceeds the 50 MB HackerEarth submission limit and is not committed. Place it at `data/raw/violations.csv` before running the pipeline.

## Methodology

### Risk Score Formula

Each hotspot receives a composite 0-100 risk score from four components. All weights are in `backend/app/core/config.py` and can be adjusted without modifying scoring logic.

```
risk_score = (severity_score_agg  x 0.40)
           + (density_score        x 0.25)
           + (vehicle_score_agg   x 0.20)
           + (junction_input      x 0.15)

Clamped to [0, 100].
```

| Component | Range | Description |
|---|---|---|
| `severity_score_agg` | 0-100 | Mean per-violation severity, normalised. PARKING IN A MAIN ROAD = 100. NO PARKING = 33. |
| `density_score` | 0-100 | Log-normalised violation count. `log1p(count) / log1p(max_count) x 100`. |
| `vehicle_score_agg` | 0-100 | Mean carriageway-blocking weight, normalised. Tanker/HGV = 100. Scooter = 30. |
| `junction_input` | 0 or 25 | Flat bonus of 25 when at least 50% of the hotspot's violations carry a named junction, otherwise 0. Max contribution: 3.75 points. |

### Escalation Forecasting

The forecast model trains once per server process on a weekly panel built from `violations.parquet`. To avoid data leakage, lag features use only weeks that precede the training cutoff. Weeks W06-W10 and W12-W13 are excluded from training because over 80% of their rows have null `validation_status` due to an approval-system backlog in the source data (raw data volume is normal; only the approval pipeline was lagged).

- **Training features:** lag1-lag4 weekly counts per hotspot, 4-week rolling mean, calendar month, risk score, violation severity, junction flag, POI flag.
- **Model:** XGBoost with `count:poisson` objective. 200 estimators, max depth 5, learning rate 0.05, subsample 0.80, colsample_bytree 0.80.
- **Evaluation holdout:** W03-W04 (two clean weeks before the W06 gap).
- **Results on clean holdout:** XGBoost MAE 5.26 violations per hotspot. 4-week rolling mean baseline MAE 5.25. Last-week naive baseline MAE 6.17. Precision@10: 0.60. Precision@20: 0.60.
- **Displayed prediction:** The 4-week rolling mean (W02-W05) is used for the displayed prediction because it matches XGBoost accuracy on this dataset and is trivially interpretable for a non-technical police audience.

Hotspots are classified into tiers based on percentage change vs. baseline and absolute violation volume:
- Critical: more than 20% increase, baseline above 15 violations per week.
- Rising: more than 15% increase.
- Stable: between -15% and +15%.
- Declining: more than 15% decrease.

### Composite Priority Score (Patrol Ranking)

The patrol optimiser ranks hotspots by `priority = risk_score x violation_count`, selects each unit's anchor as the highest-priority uncovered hotspot, and builds a route of up to five stops (anchor plus up to four candidates within 2 km, ordered by nearest-neighbour). Hotspots within 1 km of any route point are marked covered and excluded from subsequent unit assignments.

### Timestamp Logging vs. Occurrence

A critical finding from the data: `created_datetime` records when the enforcement officer logged the violation, not when the vehicle was parked. The dataset shows near-zero afternoon logging (13:00-16:00 IST) city-wide. This does not mean parking violations stop in the afternoon; it means enforcement officers are not logging in that window (shift patterns, junction-management duties, etc.).

All temporal analysis in this system is therefore labelled as logging coverage, not demand signal. `morning_log_pct` and `afternoon_log_pct` are coverage metrics. The `logging_window` label (`morning`, `overnight`, `split`, `afternoon`) describes when officers log, not when violations occur. Forecasts use these features as enforcement-activity proxies, not as parking-demand estimates.

## Setup and Installation

### Prerequisites

- Python 3.11 or later
- Node.js 18 or later with npm
- The raw dataset at `data/raw/violations.csv`

### 1. Clone and create a virtual environment

**Windows (PowerShell):**
```powershell
git clone <repository-url>
cd gridlockb
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Unix / macOS:**
```bash
git clone <repository-url>
cd gridlockb
python -m venv .venv
source .venv/bin/activate
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Install frontend dependencies

```bash
cd frontend_v2
npm install
cd ..
```

### 4. Environment variables

Create `frontend_v2/.env.local` with:

```
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

The backend reads its paths and parameters from `pydantic-settings`. All defaults resolve correctly from the repo root. To override, create a `.env` file in the repo root. The only value typically needed is `raw_csv` if the violations CSV is not at `data/raw/violations.csv`.

### 5. Run the data pipeline

Run these once before starting the servers. They are skipped by `run.sh` if `data/processed/*.parquet` files already exist.

```bash
# Step 1: clean and feature-engineer the raw CSV
python -m backend.pipeline.build_dataset

# Step 2: cluster hotspots, build temporal matrices, station and junction rollups
python -m backend.pipeline.precompute
```

Optional flags:

```bash
# Include unvalidated rows (approved + unvalidated + in-progress; excludes rejected/duplicate)
python -m backend.pipeline.build_dataset --broad

# Run only specific precompute steps
python -m backend.pipeline.precompute --steps hotspots temporal aggregations
```

## Running the Application

### Option A: single script (Unix / macOS / Git Bash)

```bash
./run.sh
```

The script checks for `data/raw/violations.csv`, runs the pipeline if `data/processed/` is empty, starts the FastAPI backend on port 8000, waits for a healthy response, then builds and starts the Next.js frontend.

To force a pipeline rebuild even if processed data exists:

```bash
./run.sh --force
```

Note: `run.sh` uses `npm run build` followed by `npm start`, which serves the production build. For faster iteration during development, use Option B below.

### Option B: two terminals (recommended for development)

**Terminal 1 (backend):**

```bash
uvicorn backend.app.main:app --reload --port 8000
```

**Terminal 2 (frontend, development mode):**

```bash
cd frontend_v2
npm run dev
```

**Terminal 2 (frontend, production build):**

```bash
cd frontend_v2
npm run build
npm start
```

The Next.js frontend is available at `http://localhost:3000`.
The FastAPI interactive API documentation is at `http://localhost:8000/docs`.

### Option C: Streamlit fallback

A Streamlit dashboard is available for environments where the Next.js frontend cannot run.

```bash
# TODO: confirm Streamlit entrypoint path
streamlit run <entrypoint>
```

## API Reference

All endpoints return JSON. Base URL defaults to `http://127.0.0.1:8000`.

| Method | Path | Query parameters | Returns |
|---|---|---|---|
| GET | `/` | | Health check. Hotspot and violation row counts. |
| GET | `/stats` | | Total violations, total hotspots, date range, per-vehicle/violation/station breakdowns, afternoon blind-spot percentage. |
| GET | `/hotspots` | `police_station`, `violation_type`, `vehicle_type`, `min_risk` (float, default 0), `poi_category` (sensitive/metro/commercial/transit), `limit` (default 500, max 1200) | Filtered hotspot list with coordinates, risk scores, and logging window. |
| GET | `/heatmap` | Same filters as `/hotspots` | Lat/lng/weight tuples for a Leaflet heatmap layer. |
| GET | `/priority` | `police_station`, `vehicle_type`, `limit` (default 50, max 500) | Hotspots ranked by risk score with Critical/Elevated/Standard tier labels based on P99/P90 percentiles. |
| GET | `/temporal/{hotspot_id}` | | Hour x day-of-week count matrix for one hotspot. |
| GET | `/forecast` | `top_n` (default 20, max 2000) | Next-week predicted violation counts per hotspot. Includes model MAE, baseline comparisons, precision-at-N, escalation tiers, and citywide summary. |
| GET | `/patrol` | `units` (default 10, max 100) | Greedy patrol assignments for N units. Returns coverage percentage, naive baseline comparison, per-unit routes with geometry, and a coverage curve. |
| GET | `/stations` | `min_hotspots` (default 1), `limit` (default 53, max 200) | Per-station rollup: hotspot count, average risk, max risk, dominant violation, blind-spot percentage. |
| GET | `/junctions` | `min_violations` (default 1), `limit` (default 100, max 500) | Named-junction rollup: violation count, average risk, top hotspot. |
| GET | `/repeat-offenders` | `limit` (default 20, max 100) | Top repeat vehicles by violation count. Vehicle numbers are PII-masked. Includes dataset-wide repeat-offender share. |
| GET | `/poi-stats` | | Per-category counts, total violations, and average risk score for sensitive/metro/commercial/transit. |
| GET | `/enforcement-quality` | | Per-station rejection rates derived from `validation_status`. |

## Limitations and Honest Caveats

**Timestamp logging vs. occurrence.** `created_datetime` records when enforcement officers logged the violation, not when the vehicle was parked. Near-zero afternoon log counts reflect an enforcement absence, not an absence of parking violations. All temporal analysis is explicitly labelled as logging coverage.

**Approved-only filtering bias.** The core analysis uses only `validation_status == "approved"` rows. Weeks W06-W10 and W12-W13 have over 80% null validation status due to an approval-system backlog in the source pipeline, making them unreliable for training. The `--broad` flag in `build_dataset.py` includes unvalidated rows for sensitivity comparison.

**Congestion impact is a derived index, not a measured value.** The dataset contains no direct traffic-flow measurements (no speed, volume, queue length, or delay). The risk score is an interpretable proxy index combining severity, density, vehicle size, and junction proximity. It is presented as a prioritisation tool, not as a measured traffic-flow impact.

**Synthetic vehicle identifiers.** Vehicle numbers in the HackerEarth dataset follow a synthetic anonymised format (e.g. `FKN00GL*`). Repeat-offender frequency statistics are valid; the identifiers do not correspond to real vehicle registrations and no identity claim can be made.

**Small clean training window for forecasting.** Approximately four clean ISO weeks (W02-W05) are available for lag training after excluding degraded weeks. XGBoost and the 4-week rolling mean baseline are near-tied on this holdout, indicating the error is near the irreducible noise floor given the data volume. Accuracy will improve materially only with more clean weekly observations.

**Coverage percentage is runtime-computed.** The patrol optimiser's coverage figure depends on the number of units requested and the current hotspot dataset. It is not a fixed benchmark.

## Privacy and Data Handling

Vehicle numbers in the source dataset are synthetic anonymised identifiers provided by HackerEarth for the hackathon. They do not represent real vehicle registration plates. All API endpoints that return vehicle numbers apply an additional PII mask (e.g. `KA01AB****23`) before serving the response. No real personally identifiable information is stored, processed, or transmitted by this system.

## Team and Acknowledgements

- TODO: team member names and roles
- TODO: acknowledgements

Built for the Flipkart x Bengaluru Traffic Police AI-driven traffic solutions hackathon, Round 2 Prototype Phase.
