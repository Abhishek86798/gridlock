import streamlit as st

from services import api_client


def render() -> dict:
    """Render sidebar filters and return active filter dict."""
    with st.sidebar:
        st.header("Filters")

        stations_data = api_client.get_stations(min_hotspots=1)
        station_names = sorted(
            s["police_station"] for s in stations_data.get("stations", [])
        )
        police_station_sel = st.selectbox(
            "Police Station",
            ["All stations"] + station_names,
        )
        police_station = None if police_station_sel == "All stations" else police_station_sel

        stats = api_client.get_stats()
        vehicle_types = sorted(stats.get("by_vehicle_type", {}).keys())
        vehicle_type_sel = st.selectbox(
            "Vehicle Type",
            ["All types"] + vehicle_types,
        )
        vehicle_type = None if vehicle_type_sel == "All types" else vehicle_type_sel

        violation_type_sel = st.selectbox(
            "Violation Type",
            [
                "All violations",
                "NO PARKING",
                "WRONG PARKING",
                "PARKING IN A MAIN ROAD",
                "PARKING NEAR ROAD CROSSING",
                "PARKING ON FOOTPATH",
            ],
        )
        violation_type = None if violation_type_sel == "All violations" else violation_type_sel

        min_risk = st.slider(
            "Min Risk Score", min_value=0, max_value=65, value=0, step=5,
            help="Only show hotspots at or above this risk score (0–65 range in dataset).",
        )

        st.divider()
        dr = stats.get("date_range", {})
        if dr:
            st.caption(f"Dataset period: {dr.get('start', '?')} → {dr.get('end', '?')}")

    filters: dict = {}
    if police_station:
        filters["police_station"] = police_station
    if vehicle_type:
        filters["vehicle_type"] = vehicle_type
    if violation_type:
        filters["violation_type"] = violation_type
    if min_risk:
        filters["min_risk"] = float(min_risk)
    return filters
