import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from services import api_client

st.set_page_config(page_title="Gridlock Parking Intelligence", layout="wide")

st.title("Bengaluru Illegal Parking Intelligence")

# Sidebar Filters
st.sidebar.header("Filters")
police_station = st.sidebar.text_input("Police Station", value="")
vehicle_type = st.sidebar.selectbox("Vehicle Type", ["All", "CAR", "SCOOTER", "AUTO", "TANKER"])
violation_type = st.sidebar.selectbox("Violation Type", ["All", "NO PARKING", "WRONG PARKING", "PARKING IN A MAIN ROAD"])

filters = {}
if police_station:
    filters["police_station"] = police_station
if vehicle_type != "All":
    filters["vehicle_type"] = vehicle_type
if violation_type != "All":
    filters["violation_type"] = violation_type

# Fetch Data
stats = api_client.get_stats(filters)
hotspots_data = api_client.get_hotspots(filters)
priority_data = api_client.get_priority()
heatmap_data = api_client.get_heatmap()

# Top Row Stats
if stats:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Violations", stats.get("total_violations", 0))
    col2.metric("Total Hotspots", stats.get("total_hotspots", 0))
    col3.metric("Top Station", max(stats.get("by_police_station", {"N/A": 0}).items(), key=lambda k: k[1])[0] if stats.get("by_police_station") else "N/A")
    col4.metric("Top Vehicle", max(stats.get("by_vehicle_type", {"N/A": 0}).items(), key=lambda k: k[1])[0] if stats.get("by_vehicle_type") else "N/A")

st.markdown("---")

col_map, col_table = st.columns([3, 2])

with col_map:
    st.subheader("Hotspots Map")
    
    # Base map centered around Bengaluru
    m = folium.Map(location=[12.9716, 77.5946], zoom_start=11)
    
    # Add hotspots as markers
    for hs in hotspots_data.get("hotspots", []):
        popup_text = f"<b>Risk Score:</b> {hs['risk_score']}<br><b>Violations:</b> {hs['violation_count']}<br><b>Peak:</b> {hs['peak_window']}"
        folium.CircleMarker(
            location=[hs["lat"], hs["lng"]],
            radius=hs["risk_score"] / 10,  # Scaled for visibility
            popup=folium.Popup(popup_text, max_width=300),
            tooltip=hs.get("junction_name") or hs["hotspot_id"],
            color="red" if hs["risk_score"] > 80 else "orange" if hs["risk_score"] > 60 else "blue",
            fill=True,
            fill_opacity=0.7
        ).add_to(m)

    st_folium(m, width=700, height=500)

with col_table:
    st.subheader("Priority Enforcement Queue")
    priority_items = priority_data.get("priority", [])
    if priority_items:
        df = pd.DataFrame(priority_items)
        # Reorder and format
        df = df[["rank", "police_station", "peak_window", "risk_score", "recommended_units"]]
        df.columns = ["Rank", "Station", "Peak Window", "Risk Score", "Units"]
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No priority data available.")

st.markdown("---")
st.subheader("Hotspot Temporal Analysis")
hotspot_id_to_check = st.selectbox("Select Hotspot ID", [hs["hotspot_id"] for hs in hotspots_data.get("hotspots", [])])

if hotspot_id_to_check:
    temporal_data = api_client.get_temporal(hotspot_id_to_check)
    matrix = temporal_data.get("matrix", [])
    if matrix:
        df_temp = pd.DataFrame(matrix)
        # Pivot table for heatmap display in Streamlit
        pivot_df = df_temp.pivot(index="hour", columns="day_of_week", values="count")
        pivot_df.columns = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        st.dataframe(pivot_df.style.background_gradient(cmap="OrRd"), use_container_width=True)
