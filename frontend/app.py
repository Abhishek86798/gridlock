"""
Gridlock Parking Intelligence — Streamlit dashboard.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import altair as alt
import pandas as pd
import streamlit as st

from components import filters as filter_component
from components import map_view, priority_table
from services import api_client
from styles import (
    COLORS,
    dark_altair,
    inject_css,
    kpi_card,
    kpi_row,
    panel_header,
)

st.set_page_config(page_title="Gridlock", layout="wide")

inject_css()

# ── Temporal heatmap (fragment) ───────────────────────────────────────────────

@st.fragment
def render_temporal_heatmap(police_station, vehicle_type):
    hotspots_data = api_client.get_hotspots(
        police_station=police_station, vehicle_type=vehicle_type, limit=200
    )
    hotspots = hotspots_data.get("hotspots", [])
    hs_ids = [hs["hotspot_id"] for hs in hotspots]
    if not hs_ids:
        st.info("No hotspots match filters.")
        return

    selected_id = st.selectbox("Select Hotspot", hs_ids, key="temporal_hs")
    temporal = api_client.get_temporal(selected_id)
    matrix = temporal.get("matrix", [])
    if not matrix:
        return

    df_t = pd.DataFrame(matrix)
    pivot = (
        df_t.pivot(index="hour", columns="day_of_week", values="count")
        .reindex(index=range(24), columns=range(7), fill_value=0)
    )
    pivot.columns = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    pivot.index.name = "Hour"

    st.markdown(f'<div style="color:#D1D5DB; font-size:13px; margin-bottom:12px;">Violation count by hour × weekday for <b>{selected_id}</b></div>', unsafe_allow_html=True)
    st.dataframe(pivot.style.background_gradient(cmap="Blues"), use_container_width=True)

# ── Health check ─────────────────────────────────────────────────────────────
if not api_client.health():
    st.error("Backend not reachable at http://localhost:8000.")
    st.stop()

# ── Sidebar ──────────────────────────────────────────────────────────────────
active_filters = filter_component.render()

# ── KPIs ─────────────────────────────────────────────────────────────────────
stats = api_client.get_stats()
if stats:
    by_station = stats.get("by_police_station", {})
    top_station = max(by_station, key=by_station.get) if by_station else "—"

    by_vehicle = stats.get("by_vehicle_type", {})
    top_vehicle = max(by_vehicle, key=by_vehicle.get) if by_vehicle else "—"

    stations_data = api_client.get_stations()
    stations_rows = stations_data.get("stations", [])
    blind_avg = (
        sum(s["blind_spot_pct"] for s in stations_rows) / len(stations_rows)
        if stations_rows else 0
    )

    sparkline = '<svg width="60" height="20" viewBox="0 0 60 20" fill="none" stroke="#60A5FA" stroke-width="1.5"><path d="M0 15 L10 10 L20 18 L30 8 L40 12 L50 4 L60 8"/></svg>'
    circle = f'<svg width="40" height="40" viewBox="0 0 36 36"><path stroke-dasharray="{blind_avg}, 100" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="#60A5FA" stroke-width="3"/><text x="18" y="20.35" font-family="Inter" font-size="9" fill="#FFF" font-weight="bold" text-anchor="middle">{blind_avg:.0f}%</text></svg>'

    kpi_row(
        kpi_card("Total Violations", f"{stats.get('total_violations', 0):,}", "shield", sparkline),
        kpi_card("Hotspot Zones", f"{stats.get('total_hotspots', 0):,}", "map_pin"),
        kpi_card("Busiest Station", top_station, "building"),
        kpi_card("Afternoon Blind Spot", f"{blind_avg:.0f}%", "eye", circle),
    )

# ── Map + Priority ───────────────────────────────────────────────────────────
c1, c2 = st.columns([6, 4], gap="medium")

with c1:
    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
    st.markdown(panel_header("Hotspot Map"), unsafe_allow_html=True)
    map_view.render(active_filters)
    st.markdown('</div>', unsafe_allow_html=True)

with c2:
    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
    st.markdown(panel_header("Enforcement Priority Queue"), unsafe_allow_html=True)
    priority_table.render(active_filters)
    st.markdown('</div>', unsafe_allow_html=True)

# ── Tabs ─────────────────────────────────────────────────────────────────────
(
    tab_forecast, tab_patrol, tab_poi, tab_temporal, tab_stations, tab_junctions
) = st.tabs([
    "Forecast", "Patrol Deployment", "POI Spillover", "Temporal", "By Station", "By Junction"
])

with tab_forecast:
    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
    st.markdown(panel_header("Forecast"), unsafe_allow_html=True)
    _fc = api_client.get_forecast(top_n=25)
    if _fc and _fc.get("forecast"):
        df_fc = pd.DataFrame(_fc["forecast"])
        df_display = df_fc[["hotspot_id", "police_station", "predicted_count", "baseline_count", "risk_score"]].copy()
        st.dataframe(df_display.style.set_properties(**{'text-align': 'center'}).set_table_styles([dict(selector='th', props=[('text-align', 'center')])]), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with tab_patrol:
    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
    st.markdown(panel_header("Patrol Deployment"), unsafe_allow_html=True)
    units_to_deploy = active_filters.get("patrol_units", 0)
    if units_to_deploy > 0:
        patrol_data = api_client.get_patrol(units=units_to_deploy)
        if patrol_data and patrol_data.get("assignments"):
            st.dataframe(pd.DataFrame(patrol_data["assignments"]).style.set_properties(**{'text-align': 'center'}).set_table_styles([dict(selector='th', props=[('text-align', 'center')])]), use_container_width=True, hide_index=True)
    else:
        st.info("Assign units using the Deployment slider in the control panel.")
    st.markdown('</div>', unsafe_allow_html=True)

with tab_poi:
    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
    st.markdown(panel_header("POI Spillover"), unsafe_allow_html=True)
    _poi = api_client.get_poi_stats()
    by_cat = _poi.get("by_category", [])
    if by_cat:
        st.dataframe(pd.DataFrame(by_cat).style.set_properties(**{'text-align': 'center'}).set_table_styles([dict(selector='th', props=[('text-align', 'center')])]), use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)

with tab_temporal:
    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
    st.markdown(panel_header("Temporal Distribution"), unsafe_allow_html=True)
    render_temporal_heatmap(active_filters.get("police_station"), active_filters.get("vehicle_type"))
    st.markdown('</div>', unsafe_allow_html=True)

with tab_stations:
    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
    st.markdown(panel_header("Stations"), unsafe_allow_html=True)
    stations = api_client.get_stations()
    rows = stations.get("stations", [])
    if rows:
        st.dataframe(pd.DataFrame(rows).style.set_properties(**{'text-align': 'center'}).set_table_styles([dict(selector='th', props=[('text-align', 'center')])]), use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)

with tab_junctions:
    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
    st.markdown(panel_header("Junctions"), unsafe_allow_html=True)
    junctions = api_client.get_junctions(min_violations=50)
    rows = junctions.get("junctions", [])
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)
