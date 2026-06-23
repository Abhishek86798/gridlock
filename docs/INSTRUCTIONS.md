# Running Trinetra Locally

Two terminals required — backend first, then frontend.

---

## Prerequisites

- Python 3.10+, Node.js 18+
- A built parquet dataset in `backend/data/` (run the pipeline once if absent)

---

## Terminal 1 — Backend (FastAPI)

```powershell
cd backend
python -m venv venv              # first time only
venv\Scripts\activate
pip install -r requirements.txt  # first time only
uvicorn app.main:app --reload
```

Backend runs at **http://localhost:8000**
API docs at **http://localhost:8000/docs**

> On first start the model trains automatically (~10–15 seconds). Subsequent starts use the cache.

---

## Terminal 2 — Frontend (Next.js)

```powershell
cd frontend_v2
npm install                      # first time only
npm run dev
```

Dashboard runs at **http://localhost:3000**

---

## If data parquet files are missing

Run the pipeline to build them from the raw CSV:

```powershell
cd backend
python -m pipeline.precompute
```

This generates `hotspots.parquet`, `temporal.parquet`, and aggregation files under `backend/data/`.

---

## Environment variable

The frontend expects the backend at `http://127.0.0.1:8000` by default.
To override, set in `frontend_v2/.env.local`:

```
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

---

## Quick sanity check

| URL | Expected |
|-----|----------|
| `localhost:8000/health` | `{"status":"ok"}` |
| `localhost:8000/hotspots?limit=5` | JSON array of 5 hotspots |
| `localhost:3000` | Overview dashboard loads |
