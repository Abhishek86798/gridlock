"""
Gridlock Parking Intelligence — Streamlit dashboard.

Run from the repo root:
    streamlit run frontend/app.py

Requires backend:
    uvicorn backend.app.main:app --port 8000
"""
import sys
from pathlib import Path

# Make `services.*` importable regardless of working directory.
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import streamlit as st

from components import filters as filter_component
from components import map_view, priority_table
from services import api_client

st.set_page_config(
    page_title="Gridlock — Bengaluru Parking Intelligence",
    page_icon="🚦",
    layout="wide",
)

# ── Backend health check ───────────────────────────────────────────────────────
if not api_client.health():
    st.error(
        "Backend not reachable at http://localhost:8000. "
        "Start it with: `uvicorn backend.app.main:app --port 8000`"
    )
    st.stop()

# ── Sidebar filters ────────────────────────────────────────────────────────────
active_filters = filter_component.render()

# ── Header metrics ─────────────────────────────────────────────────────────────
stats = api_client.get_stats()
if stats:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Violations", f"{stats.get('total_violations', 0):,}")
    c2.metric("Total Hotspots", f"{stats.get('total_hotspots', 0):,}")

    by_station = stats.get("by_police_station", {})
    top_station = max(by_station, key=by_station.get) if by_station else "—"
    c3.metric("Busiest Station", top_station)

    by_vehicle = stats.get("by_vehicle_type", {})
    top_vehicle = max(by_vehicle, key=by_vehicle.get) if by_vehicle else "—"
    c4.metric("Top Vehicle Type", top_vehicle)

    dr = stats.get("date_range", {})
    st.caption(f"Dataset: {dr.get('start', '?')} → {dr.get('end', '?')}")

st.markdown("---")

# ── Map + Priority side by side ────────────────────────────────────────────────
col_map, col_table = st.columns([3, 2])

with col_map:
    map_view.render(active_filters)

with col_table:
    priority_table.render(active_filters)

st.markdown("---")

# ── Tabs: Temporal | Stations | Junctions ─────────────────────────────────────
tab_temporal, tab_stations, tab_junctions = st.tabs(
    ["Temporal Heatmap", "By Police Station", "By Junction"]
)

with tab_temporal:
    hotspots_data = api_client.get_hotspots(
        police_station=active_filters.get("police_station"),
        limit=200,
    )
    hs_ids = [hs["hotspot_id"] for hs in hotspots_data.get("hotspots", [])]
    if hs_ids:
        selected_id = st.selectbox("Select Hotspot", hs_ids, key="temporal_hs")
        temporal = api_client.get_temporal(selected_id)
        matrix   = temporal.get("matrix", [])
        if matrix:
            df_t = pd.DataFrame(matrix)
            # Fill zeros for missing hour/day combinations.
            pivot = (
                df_t.pivot(index="hour", columns="day_of_week", values="count")
                .reindex(index=range(24), columns=range(7), fill_value=0)
            )
            pivot.columns = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            pivot.index.name = "Hour"
            st.write(f"Violation count by hour × weekday for **{selected_id}**")
            st.dataframe(
                pivot.style.background_gradient(cmap="OrRd"),
                use_container_width=True,
            )
            # Blind-spot callout.
            hs_row = next(
                (h for h in hotspots_data["hotspots"] if h["hotspot_id"] == selected_id),
                None,
            )
            if hs_row:
                pm_pct = hs_row["afternoon_log_pct"]
                am_pct = hs_row["morning_log_pct"]
                st.info(
                    f"**{selected_id}** — morning logging: {am_pct:.0f}% | "
                    f"afternoon logging: {pm_pct:.0f}%"
                    + (" ⚠️ Afternoon blind spot" if pm_pct < 5 else "")
                )
    else:
        st.info("No hotspots match the current filters.")

with tab_stations:
    stations = api_client.get_stations()
    rows = stations.get("stations", [])
    if rows:
        df_st = pd.DataFrame(rows)[[
            "police_station", "hotspot_count", "total_violations",
            "avg_risk_score", "max_risk_score", "blind_spot_pct",
            "dominant_violation", "top_hotspot_id",
        ]]
        df_st.columns = [
            "Station", "Hotspots", "Violations",
            "Avg Risk", "Max Risk", "Blind Spot %",
            "Top Violation", "Top Hotspot",
        ]
        st.caption(
            f"{len(df_st)} stations · city-wide afternoon blind-spot avg: "
            f"{df_st['Blind Spot %'].mean():.0f}%"
        )
        st.dataframe(
            df_st.style.background_gradient(subset=["Avg Risk", "Blind Spot %"], cmap="YlOrRd"),
            use_container_width=True,
            hide_index=True,
        )

with tab_junctions:
    junctions = api_client.get_junctions(min_violations=50)
    rows = junctions.get("junctions", [])
    if rows:
        df_jn = pd.DataFrame(rows)[[
            "junction_name", "total_violations", "hotspot_count",
            "avg_risk_score", "police_station", "top_hotspot_id",
        ]]
        df_jn.columns = [
            "Junction", "Violations", "Hotspots",
            "Avg Risk", "Station", "Top Hotspot",
        ]
        st.caption(f"{len(df_jn)} named junctions with ≥ 50 violations")
        st.dataframe(
            df_jn.style.background_gradient(subset=["Avg Risk"], cmap="YlOrRd"),
            use_container_width=True,
            hide_index=True,
        )
