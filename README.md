# Bengaluru Illegal-Parking Intelligence — PS1

> **Hackathon:** AI-driven traffic solutions · Flipkart × Bengaluru Traffic Police  
> **Problem statement:** PS1 — Poor Visibility on Parking-Induced Congestion  
> **Round 2 deadline:** 21 June 2026 · Onsite finale: 3 July 2026, Flipkart HQ

---

## What this solves

BTP today enforces illegal parking **reactively** — patrols roam and ticket whatever they find.
This system turns five months of violation logs into a **predictive enforcement layer**:

1. **Detect** where illegal parking clusters (spatial hotspot detection)
2. **Score** how badly each hotspot hurts traffic flow (interpretable risk index)
3. **Forecast** when the next spike will hit (gradient-boosting on temporal features)
4. **Deploy** tell N patrol units exactly *where* and *when* to go (greedy set-cover optimizer)

---

## Quick start

```bash
# 1. Clone and activate the virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # Windows PowerShell
# source .venv/bin/activate           # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Place the raw dataset
#    Copy the provided CSV to:
#    data/raw/violations.csv

## Running Locally

The easiest way to run the full stack is using the single run script:
```bash
./run.sh
```
This will:
1. Verify raw data exists.
2. Run the data pipeline (skips if data is already processed; use `./run.sh --force` to rebuild).
3. Start the FastAPI backend and wait for it to be healthy.
4. Start the Streamlit frontend.

### Manual Startup

If you prefer to start services manually:

**1. Process Data** (one-time or when raw data changes)
```bash
python backend/pipeline/build_dataset.py
python backend/pipeline/precompute.py
```

**2. Start Backend**
```bash
uvicorn backend.app.main:app --reload
```

**3. Start Frontend** (in a separate terminal)
```bash
streamlit run frontend/app.py
```

Open **http://localhost:8501** in a browser.

> **Demo fallback:** if the pipeline hasn't run yet, set `USE_MOCK = True` in
> `frontend/services/api_client.py` and run `python mocks/make_sample_parquet.py`
> to generate synthetic data. The dashboard loads instantly.

---

## Repo layout

```
parking-intel/
├── data/
│   ├── raw/violations.csv          # provided dataset — never edited
│   └── processed/                  # pipeline writes parquets here
├── backend/
│   ├── app/                        # FastAPI application
│   │   ├── main.py                 # server entry point
│   │   ├── core/config.py          # paths, risk-score weights (edit here to tune)
│   │   ├── models/schemas.py       # Pydantic — mirrors API contract exactly
│   │   ├── routers/                # hotspots.py + analytics.py
│   │   └── services/               # business logic (hotspot, analytics)
│   ├── pipeline/
│   │   ├── build_dataset.py        # Step 1: clean + feature-engineer → violations.parquet
│   │   └── precompute.py           # Step 2: cluster → hotspots + temporal + forecast + patrol
│   └── db/                         # DuckDB loader (optional)
├── frontend/
│   ├── app.py                      # streamlit run frontend/app.py
│   ├── services/api_client.py      # all backend calls (USE_MOCK flag here)
│   └── components/                 # map_view, priority_table, filters
├── mocks/
│   ├── hotspots.sample.json        # hand-written sample matching API contract
│   └── make_sample_parquet.py      # generates synthetic processed/*.parquet
├── notebooks/
│   └── 01_eda.ipynb                # exploratory analysis — run first
├── deck/                           # pitch deck + architecture diagram
├── CONTRACTS.md                    # ML↔Backend↔Frontend data contract
├── PROJECT_CONTEXT.md
└── REQUIREMENTS.md
```

---

## Pipeline steps

| Script | Input | Output | Notes |
|---|---|---|---|
| `build_dataset.py` | `data/raw/violations.csv` | `violations.parquet` | Clean, parse arrays, convert to IST, filter approved |
| `precompute.py` | `violations.parquet` | `hotspots.parquet`, `temporal.parquet`, `forecast.parquet`, `repeat_offenders.parquet` | Run after build_dataset |

---

## API endpoints

Base URL: `http://localhost:8000`

| Endpoint | Returns |
|---|---|
| `GET /hotspots` | Hotspots for the map, colored by risk score |
| `GET /priority` | Ranked enforcement queue with unit recommendations |
| `GET /heatmap` | Lightweight point weights for the heatmap layer |
| `GET /temporal/{id}` | Hour × weekday matrix for one hotspot |
| `GET /stats` | Summary counts for header cards |
| `GET /forecast` | Next-window predicted violation intensity |
| `GET /patrol?units=N` | Greedy patrol assignments for N units |
| `GET /repeat-offenders` | Chronic-offender frequency table |
| `GET /enforcement-quality` | Rejection rates by station / device |

All list endpoints accept `?start_date`, `end_date`, `police_station`, `vehicle_type`, `violation_type`.

---

## Risk score formula

```
risk_score = (severity_score  × 0.40)
           + (density_score   × 0.25)
           + (vehicle_score   × 0.20)
           + (junction_bonus  × 0.15)

Clamped to 0–100. Weights are tunable in backend/app/core/config.py.
```

| Component | Source | High-score signal |
|---|---|---|
| `severity_score` | violation_type → `SEVERITY_WEIGHTS` | PARKING IN A MAIN ROAD (3.0×) |
| `density_score` | violation count in cluster | Large cluster |
| `vehicle_score` | vehicle_type → `VEHICLE_WEIGHTS` | Tanker/truck (3.0×) |
| `junction_bonus` | `junction_name` not null | Named junction present |

---

## Dataset notes

- Source: HackerEarth PS1 dataset (Jan–Apr 2024, ~298k rows)
- `vehicle_number` is **anonymised** (`FKN00GL*` synthetic IDs) — frequency stats are valid, real-world identity is not claimed
- No direct traffic-flow measurement exists; `risk_score` is a **derived proxy index**, not a measured value
- `created_datetime` is **UTC** — all temporal features are converted to **IST (+5:30)** before analysis
- `validation_status` has three actionable values: `approved` (core analysis), `rejected` (enforcement-quality add-on), `null` (unvalidated, excluded)

---

## Judging criteria map

| Criterion | Where to look |
|---|---|
| **Robustness** | `build_dataset.py` — null handling, bbox filter, IST conversion, array parsing |
| **Innovation** | Forecast model (`/forecast`), patrol optimizer (`/patrol`), junction + POI tagging |
| **Prototype clarity** | Live dashboard, explainable risk score formula above, this README |
| **Scalability** | `device_id` column supports live device feeds; architecture diagram in `deck/` |
| **Real-world viability** | BTP-aligned outputs: patrol assignments, peak windows, station-level views |

---

## Development status

- [x] Repo scaffold + environment
- [x] Raw data in place
- [x] Central config (`core/config.py`)
- [x] EDA notebook (`notebooks/01_eda.ipynb`)
- [ ] `build_dataset.py` — cleaning pipeline
- [ ] `precompute.py` — hotspot detection + risk score
- [ ] Temporal analysis
- [ ] Forecast model
- [ ] Patrol optimizer
- [ ] Dashboard components
- [ ] Pitch deck

---

## Requirements

- Python 3.11+
- See `requirements.txt` for pinned versions
- No GPU required; all models run on CPU

---

*Built for the Flipkart × BTP AI Traffic Hackathon, Round 2.*
