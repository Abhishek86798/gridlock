"""
Sidebar filters — match dark SaaS aesthetic.
"""
import streamlit as st

from services import api_client
from styles import COLORS

def render() -> dict:
    with st.sidebar:
        st.markdown('<div class="sidebar-header">CONTROL PANEL</div>', unsafe_allow_html=True)

        stations_data = api_client.get_stations(min_hotspots=1)
        station_names = sorted(s["police_station"] for s in stations_data.get("stations", []))
        police_station_sel = st.selectbox("POLICE STATION", ["All stations"] + station_names)
        police_station = None if police_station_sel == "All stations" else police_station_sel

        st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)

        stats = api_client.get_stats()
        vehicle_types = sorted(stats.get("by_vehicle_type", {}).keys())
        vehicle_type_sel = st.selectbox("VEHICLE TYPE", ["All types"] + vehicle_types)
        vehicle_type = None if vehicle_type_sel == "All types" else vehicle_type_sel

        st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)

        violation_type_sel = st.selectbox("VIOLATION TYPE", [
            "All violations", "NO PARKING", "WRONG PARKING",
            "PARKING IN A MAIN ROAD", "PARKING NEAR ROAD CROSSING", "PARKING ON FOOTPATH"
        ])
        violation_type = None if violation_type_sel == "All violations" else violation_type_sel

        st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)

        min_risk = st.slider("MIN RISK SCORE", min_value=0, max_value=65, value=0, step=5)

        st.markdown(
            '<div style="height:1px; background:#2F333D; margin: 32px 0;"></div>',
            unsafe_allow_html=True
        )

        st.markdown('<div class="sidebar-header" style="font-size:11px;">PATROL UNITS TO DEPLOY</div>', unsafe_allow_html=True)
        patrol_units = st.slider("UNITS", min_value=0, max_value=100, value=0, step=1, label_visibility="collapsed")
        
        if patrol_units > 0:
            patrol_data = api_client.get_patrol(units=patrol_units)
            cov_pct = patrol_data.get("coverage_pct", 0.0)
            st.markdown(
                f'<div style="background:#1B2524; border:1px solid #065F46; padding:8px 12px; border-radius:6px; '
                f'color:#34D399; font-size:11px; font-weight:600; text-align:center; margin-top:8px;">'
                f'{patrol_units} units — {cov_pct:.1f}% priority coverage</div>',
                unsafe_allow_html=True,
            )

        st.markdown(
            '<div style="height:1px; background:#2F333D; margin: 32px 0;"></div>',
            unsafe_allow_html=True
        )
        
        dr = stats.get("date_range", {})
        if dr:
            st.markdown(
                f'<div style="border:1px solid #2F333D; border-radius:6px; padding:6px 12px; '
                f'font-size:11px; color:#9CA3AF; text-align:center; font-family:\'Inter\', monospace;">'
                f'{dr.get("start", "?")} → {dr.get("end", "?")}</div>',
                unsafe_allow_html=True,
            )

    filters = {}
    if police_station: filters["police_station"] = police_station
    if vehicle_type: filters["vehicle_type"] = vehicle_type
    if violation_type: filters["violation_type"] = violation_type
    if min_risk: filters["min_risk"] = float(min_risk)
    if patrol_units > 0: filters["patrol_units"] = patrol_units
    return filters
