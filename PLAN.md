# Backend and Frontend Implementation Plan

This plan details the step-by-step implementation of the Backend (FastAPI) and Frontend (Streamlit) for the Parking Intelligence Dashboard, bypassing the data pipeline/ML work for now. We will strictly adhere to the API contract defined in `CONTRACTS.md` and use mock data to unblock development.

## Phase 1: Backend Setup & Mock Data
We will set up the FastAPI server and define the Pydantic models to strictly match the API contract, along with sample mock data.
- **Goal:** Set up the backend project structure and mock responses.
- **Steps:**
  1. Create `backend/requirements.txt` with `fastapi`, `uvicorn`, `pydantic`.
  2. Implement `backend/app/models/schemas.py` creating Pydantic models for `Hotspot`, `PriorityItem`, `HeatmapPoint`, `TemporalMatrix`, and `Stats`.
  3. Create `mocks/hotspots.sample.json` and `mocks/stats.sample.json` to hold static sample data matching the contract.
- **Outcome:** Backend project scaffolding is ready with data schemas perfectly mirroring `CONTRACTS.md`.

## Phase 2: Backend API Endpoints
We will implement the FastAPI routers that serve the mock data.
- **Goal:** Expose the data via HTTP endpoints.
- **Steps:**
  1. Create `backend/app/main.py` to initialize FastAPI and configure CORS for the frontend.
  2. Implement endpoints in `backend/app/routers/hotspots.py`: `GET /hotspots`, `GET /priority`, and `GET /heatmap`.
  3. Implement endpoints in `backend/app/routers/analytics.py`: `GET /stats` and `GET /temporal/{hotspot_id}`.
- **Outcome:** A fully functional backend server running at `http://localhost:8000` with interactive Swagger docs, returning the agreed-upon JSON structures.

## Phase 3: Frontend Scaffolding & API Client
We will set up the Streamlit application and the client that communicates with the Backend.
- **Goal:** Establish connection from the frontend UI to the backend API.
- **Steps:**
  1. Create `frontend/requirements.txt` with `streamlit`, `requests`, `pandas`, `folium`, `streamlit-folium`.
  2. Implement `frontend/services/api_client.py` as a robust client to fetch data from `http://localhost:8000` for all endpoints, passing query filters appropriately.
- **Outcome:** A Streamlit environment ready to consume live (or mocked) data from the backend.

## Phase 4: Frontend UI Implementation
We will build the actual interactive dashboard for the end user.
- **Goal:** Build the UI components based on the fetched data.
- **Steps:**
  1. Implement `frontend/app.py` for the main Streamlit layout.
  2. Add a sidebar for filters (Date Range, Police Station, Vehicle Type, Violation Type).
  3. Add a top row for header summary cards (Total Violations, Total Hotspots, etc.) via `/stats`.
  4. Create a main map view (using Folium) rendering hotspots and the heatmap via `/hotspots` and `/heatmap`.
  5. Build a ranked Priority Enforcement table via `/priority`.
- **Outcome:** A working, interactive dashboard prototype ready for demonstration.

---
Let me know if you approve of this plan so we can start executing Phase 1 immediately!
