# Requirements — Bengaluru Illegal Parking Intelligence (PS1)

> Companion to `PROJECT_CONTEXT.md`. This document lists the concrete functional, data, technical, and non-functional requirements, plus deliverables and how each maps to the judging criteria. An AI agent or developer should be able to build the prototype from this.

---

## 1. Functional Requirements

### FR-1 — Data Ingestion & Cleaning
- Load the provided violations CSV.
- Parse `violation_type` (JSON-style array of strings) into structured categories.
- Parse `offence_code` arrays.
- Derive temporal features from `created_datetime`: `hour`, `day_of_week`, `is_weekend`, `month`.
- Filter / flag records by `validation_status` (default analysis on `approved`).
- Validate and clean `latitude`/`longitude` (drop nulls, out-of-Bengaluru outliers).

### FR-2 — Hotspot Detection
- Cluster violations spatially (DBSCAN on lat/long **or** H3 hexbin aggregation).
- Output a ranked list of hotspots with: centroid coords, violation count, dominant violation types, dominant vehicle types, associated junction/police station.

### FR-3 — Temporal Pattern Analysis
- For each hotspot, compute an hour-of-day × day-of-week distribution.
- Identify peak windows (top time slots) per hotspot.

### FR-4 — Congestion-Risk (Impact) Score
- Compute an interpretable per-hotspot score combining:
  - violation **severity** (PARKING IN A MAIN ROAD / NEAR ROAD CROSSING weighted highest),
  - violation **density** (count and concentration),
  - **vehicle size** (tanker/car > auto > scooter),
  - **junction proximity** (named junction present → higher).
- The scoring formula must be **documented and explainable** (no black box).
- Output a normalized 0–100 risk score per hotspot.

### FR-5 — Predictive Forecasting (differentiator)
- Train a model (gradient boosting / Poisson regression) on location + temporal features.
- Predict expected violation intensity per zone per upcoming time window.
- Output: "next-window" hotspot forecast with confidence.

### FR-6 — Patrol Deployment Recommendation (differentiator)
- Input: number of available patrol units (configurable).
- Output: recommended hotspot/time-window assignments maximizing weighted coverage of high-risk zones (greedy set-cover or clustering into patrol beats).

### FR-7 — POI / Spillover Tagging (differentiator)
- Tag hotspots near metro stations / commercial areas using `location` text or POI proximity.
- Report share of high-severity violations near these POIs.

### FR-8 — Repeat-Offender Analytics (differentiator)
- Aggregate by `vehicle_number` to identify chronic offenders and chronic locations.
- Report concentration stats (e.g., top N vehicles' share of violations).

### FR-9 — Interactive Dashboard
- Map view: hotspots colored/sized by risk score, with heatmap layer.
- Priority queue: ranked enforcement table (zone, peak window, risk score, recommended units).
- Filters: time range, police station, vehicle type, violation type.
- Drill-down: click a hotspot → detail panel (violations, types, timing).

### FR-10 — Reporting
- Generate violation statistics and trends.
- Provide exportable summary (per zone / per station).

---

## 2. Data Requirements

- **Source:** HackerEarth-provided PS1 dataset only. No external datasets for core analysis (compliance rule).
- **Permitted enrichment:** map/road geometry or POI lookups (e.g., OpenStreetMap) used only as geographic context — must be documented and clearly separated from the provided data.
- **Known gaps to handle:** no traffic-flow column (use derived risk score), frequent NULL resolution timestamps, multi-value `violation_type`.
- **Privacy note:** `vehicle_number` is law-enforcement data; handle/display responsibly and note this in the writeup.

---

## 3. Non-Functional Requirements

- **Robustness:** pipeline must handle NULLs, malformed arrays, and bad coordinates without crashing.
- **Explainability:** the impact score and any model outputs must be interpretable to a non-technical (police) audience.
- **Scalability:** architecture should describe ingestion of live/streaming device feeds (`device_id` present), not only a static file.
- **Performance:** dashboard must load and respond interactively on a laptop during a live demo.
- **Reproducibility:** a documented, runnable pipeline (notebook + app entrypoint) that regenerates all outputs from the raw CSV.
- **Demo-readiness:** the prototype must actually run live (finale requirement), not exist only as slides.

---

## 4. Technical Stack (recommended)

- **Language:** Python 3.x
- **Data/ML:** pandas, numpy, scikit-learn, XGBoost/LightGBM (forecasting), h3 / scikit-learn DBSCAN (clustering)
- **Geospatial:** geopandas, folium / pydeck / kepler.gl
- **Dashboard:** Streamlit (recommended for speed) or React + map library
- **Packaging:** requirements.txt, README, single-command run

---

## 5. Deliverables (Round 2 submission)

1. Working prototype (runnable dashboard/app).
2. Source code + README with setup and run instructions.
3. Reproducible analysis notebook.
4. Pitch deck / solution writeup: problem, approach, scoring logic, results, impact, scalability.
5. (Optional but recommended) a fallback demo video in case of live-demo failure.
6. All files < 50 MB each.

---

## 6. Requirements → Judging Criteria Map

| Judging criterion | Addressed by |
|---|---|
| **Solution robustness** | FR-1 cleaning, NFR robustness, reproducible pipeline |
| **Innovation** | FR-5 forecasting, FR-6 patrol optimizer, FR-7 spillover tagging |
| **Prototype clarity** | FR-9 dashboard, FR-4 explainable score, README + deck |
| **Scalability** | NFR scalability, real-time ingestion architecture (device feeds) |
| **Real-world viability** | FR-6 patrol recommendations, FR-3 peak windows, FR-7 POI relevance, BTP-aligned outputs |

---

## 7. Build Priority (3-day reality check)

- **P0 (must ship):** FR-1, FR-2, FR-3, FR-4, FR-9 (core dashboard).
- **P1 (differentiators — ship at least 1–2):** FR-5, FR-6, FR-7.
- **P2 (polish if time):** FR-8, FR-10, scenario simulator, scalability slide.
