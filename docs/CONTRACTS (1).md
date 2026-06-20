# CONTRACTS.md — The Single Source of Truth

> **Everyone follows this file.** It defines the repo structure, the **ML → Backend** data handoff, and the **Backend → Frontend** API contract. If you need to change anything here, announce it at the daily sync first — silent changes to this file are the #1 cause of integration failures.
>
> **Owners:** ML/Data = produces the artifacts in §2. Backend = serves the API in §3. Frontend = consumes the API in §3.

---

## 0. Conventions (read once, apply everywhere)

- **Field naming:** `snake_case` everywhere — parquet columns *and* JSON keys match exactly.
- **Coordinates:** WGS84 decimal degrees. `lat` then `lng`. Floats.
- **Datetimes:** ISO 8601 UTC strings in JSON (e.g. `2023-11-20T00:28:46Z`). Timezone-aware in parquet.
- **IDs:** strings, zero-padded (`HS001`, not `1`).
- **Risk score:** float `0–100`, higher = wiiorse.
- **Time windows:** human-readable string, e.g. `"Mon–Fri 18:00–21:00"`.
- **Empty/unknown:** use `null` in JSON, not `""` or `"NULL"`.
- **API base URL:** `http://localhost:8000` (backend). CORS must allow the frontend origin.
- **Errors:** FastAPI default shape `{ "detail": "message" }` with the right HTTP status.

---

## 1. Repo Structure

```
parking-intel/
├── data/
│   ├── raw/
│   │   └── violations.csv            # provided dataset — never edited
│   └── processed/                    # ML writes here; Backend reads here
│       ├── violations.parquet
│       ├── hotspots.parquet
│       ├── temporal.parquet
│       ├── forecast.parquet          # add-on
│       ├── patrol_plan.parquet       # add-on (or computed live)
│       └── repeat_offenders.parquet  # add-on
├── backend/
│   ├── app/
│   │   ├── main.py                   # FastAPI entry, loads artifacts on startup
│   │   ├── core/config.py            # paths, risk-score weights
│   │   ├── models/schemas.py         # Pydantic = mirrors §3 responses
│   │   ├── routers/
│   │   │   ├── hotspots.py
│   │   │   └── analytics.py
│   │   └── services/                 # ML logic lives here (hotspots, risk_score, ...)
│   ├── pipeline/                     # build_dataset.py, precompute.py
│   ├── db/                           # SQLite/DuckDB file + loader
│   └── requirements.txt
├── frontend/
│   ├── app.py                        # streamlit run frontend/app.py
│   ├── services/api_client.py        # all calls to backend
│   └── components/                   # map_view, priority_table, filters
├── mocks/
│   ├── hotspots.sample.json          # frontend/backend build against this Day 1
│   └── make_sample_parquet.py        # generates fake processed/*.parquet
├── deck/                             # pitch + architecture diagram
├── CONTRACTS.md                      # this file
├── PROJECT_CONTEXT.md
├── REQUIREMENTS.md
├── ROADMAP.md
└── README.md
```

---

## 2. Data Handoff Schema (ML → Backend)

ML writes these files to `data/processed/`. Backend reads them (directly or loaded into DuckDB/SQLite). **Column names and types are fixed by this section.**

### 2.1 `hotspots.parquet` (core)
| column | type | description |
|---|---|---|
| `hotspot_id` | string | `HS001`, unique |
| `lat` | float | centroid latitude |
| `lng` | float | centroid longitude |
| `risk_score` | float | 0–100 congestion-risk index |
| `violation_count` | int | violations in this cluster |
| `dominant_violation` | string | most common violation type |
| `dominant_vehicle` | string | most common vehicle type |
| `peak_window` | string | e.g. `"Mon–Fri 18:00–21:00"` |
| `police_station` | string | associated station |
| `junction_name` | string \| null | named junction or null |
| `near_poi` | string \| null | add-on: nearest metro/commercial POI |

### 2.2 `temporal.parquet` (core)
One row per hotspot × hour × weekday.
| column | type | description |
|---|---|---|
| `hotspot_id` | string | FK to hotspots |
| `hour` | int | 0–23 |
| `day_of_week` | int | 0=Mon … 6=Sun |
| `count` | int | violations in that slot |

### 2.3 `violations.parquet` (cleaned base, optional for API)
Cleaned/feature-engineered rows. Backend uses for drill-down/stats.
| column | type | description |
|---|---|---|
| `id` | string | original record id |
| `lat`, `lng` | float | coordinates |
| `violation_type` | string | single primary type (exploded) |
| `vehicle_type` | string | normalized |
| `vehicle_number` | string | pre-anonymized vehicle ID (`FKN00GL*` format, not a real plate) |
| `police_station` | string | station |
| `junction_name` | string \| null | junction |
| `created_at` | datetime | ISO, tz-aware |
| `hour`, `day_of_week` | int | derived |
| `severity_weight` | float | from config weights |
| `validation_status` | string | approved/rejected |

### 2.4 Add-on artifacts (only if built)
- `forecast.parquet`: `hotspot_id, predict_window, predicted_intensity (float), confidence (float 0–1)`
- `repeat_offenders.parquet`: `vehicle_number, violation_count, top_location, distinct_locations (int)`
- patrol plan: usually computed **live** from `units` param (see §3.6), no file needed.

---

## 3. API Contract (Backend → Frontend)

Base: `http://localhost:8000`. All responses JSON. All list endpoints accept the **common filters** below.

**Common query filters (optional on all list endpoints):**
`start_date`, `end_date` (ISO date), `police_station` (string), `vehicle_type` (string), `violation_type` (string).

### 3.1 `GET /hotspots`
Returns hotspots for the map.
```json
{
  "count": 2,
  "hotspots": [
    {
      "hotspot_id": "HS001",
      "lat": 12.9255567, "lng": 77.618665,
      "risk_score": 62.5,
      "violation_count": 142,
      "dominant_violation": "PARKING IN A MAIN ROAD",
      "dominant_vehicle": "CAR",
      "peak_window": "Mon–Fri 18:00–21:00",
      "police_station": "Madiwala",
      "junction_name": null,
      "near_poi": "Koramangala Commercial"
    }
  ]
}
```

### 3.2 `GET /priority`
Ranked enforcement queue (hotspots sorted by risk_score, with a unit suggestion).
```json
{
  "priority": [
    {
      "rank": 1,
      "hotspot_id": "HS001",
      "risk_score": 62.5,
      "peak_window": "Mon–Fri 08:00–11:00",
      "police_station": "Madiwala",
      "recommended_units": 1
    }
  ]
}
```

### 3.3 `GET /heatmap`
Lightweight points for the heatmap layer.
```json
{
  "points": [
    { "lat": 12.9255, "lng": 77.6186, "weight": 0.87 }
  ]
}
```

### 3.4 `GET /temporal/{hotspot_id}`
Hour × weekday matrix for one hotspot.
```json
{
  "hotspot_id": "HS001",
  "matrix": [
    { "hour": 18, "day_of_week": 0, "count": 12 },
    { "hour": 19, "day_of_week": 0, "count": 9 }
  ]
}
```

### 3.5 `GET /stats`
Summary numbers for header cards / reporting.
```json
{
  "total_violations": 10532,
  "total_hotspots": 64,
  "date_range": { "start": "2023-11-11", "end": "2023-12-26" },
  "by_vehicle_type": { "CAR": 4210, "SCOOTER": 3980 },
  "by_violation_type": { "NO PARKING": 6100, "WRONG PARKING": 3200 },
  "by_police_station": { "Madiwala": 980, "Shivajinagar": 870 }
}
```

### 3.6 Add-on endpoints (only if built; frontend feature-flags them)
- `GET /forecast` →
  ```json
  { "forecast": [ { "hotspot_id": "HS001", "predict_window": "Tomorrow 18:00–21:00", "predicted_intensity": 38.0, "confidence": 0.81 } ] }
  ```
- `GET /patrol?units=10` →
  ```json
  { "units": 10, "coverage_pct": 76.5,
    "assignments": [ { "unit_id": 1, "hotspot_id": "HS001", "time_window": "18:00–21:00" } ] }
  ```
- `GET /repeat-offenders?limit=20` →
  ```json
  { "offenders": [ { "vehicle_number": "FKN00GL0000", "violation_count": 19, "top_location": "Koramangala", "distinct_locations": 6 } ] }
  ```
- `GET /enforcement-quality` →
  ```json
  { "by_area": [ { "police_station": "Madiwala", "rejection_rate": 0.12, "total": 980 } ] }
  ```

---

## 4. Day-1 Unblock: Mock Data

So Backend and Frontend don't wait for real ML output:

1. **`mocks/hotspots.sample.json`** — a hand-written file matching §3.1 exactly (5–10 fake hotspots). Frontend's `api_client.py` reads this until the API is live.
2. **`mocks/make_sample_parquet.py`** — generates fake `processed/*.parquet` files matching §2 (random Bengaluru coords + plausible values). Backend serves these until ML delivers the real ones.

**Switch-over:** once ML drops real files in `data/processed/`, Backend points to them and Frontend points `api_client` at `http://localhost:8000`. Nothing else changes because the shapes match this contract.

---

## 5. Change Control

- Any change to §1–§3 → raise it at the **start-of-day or end-of-day sync** before coding against it.
- Keep `models/schemas.py` (Pydantic) as the literal mirror of §3 — if they drift, this file wins.
- When in doubt: match the field names and types here **exactly**. Consistency beats cleverness.
