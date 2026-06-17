import streamlit as st


def render() -> dict:
    """Render sidebar filters and return active filter dict."""
    with st.sidebar:
        st.header("Filters")

        start_date = st.date_input("Start date", value=None)
        end_date = st.date_input("End date", value=None)

        police_station = st.text_input("Police station", placeholder="e.g. Madiwala")

        vehicle_type = st.selectbox(
            "Vehicle type",
            ["", "CAR", "SCOOTER", "AUTO", "MOTORCYCLE", "TRUCK", "TANKER", "BUS"],
        )

        violation_type = st.selectbox(
            "Violation type",
            ["", "NO PARKING", "WRONG PARKING", "PARKING IN A MAIN ROAD",
             "PARKING NEAR ROAD CROSSING", "PARKING ON FOOTPATH"],
        )

    filters = {}
    if start_date:
        filters["start_date"] = str(start_date)
    if end_date:
        filters["end_date"] = str(end_date)
    if police_station:
        filters["police_station"] = police_station
    if vehicle_type:
        filters["vehicle_type"] = vehicle_type
    if violation_type:
        filters["violation_type"] = violation_type
    return filters
