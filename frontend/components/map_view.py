import streamlit as st
import folium
from streamlit_folium import st_folium

from frontend.services import api_client


def render(filters: dict):
    st.subheader("Hotspot Map")
    data = api_client.hotspots(filters)
    hotspots = data.get("hotspots", [])

    m = folium.Map(location=[12.9716, 77.5946], zoom_start=12, tiles="CartoDB positron")

    for hs in hotspots:
        radius = 8 + hs["risk_score"] / 10
        color = _risk_color(hs["risk_score"])
        folium.CircleMarker(
            location=[hs["lat"], hs["lng"]],
            radius=radius,
            color=color,
            fill=True,
            fill_opacity=0.7,
            popup=folium.Popup(
                f"<b>{hs['hotspot_id']}</b><br>"
                f"Risk: {hs['risk_score']:.1f}<br>"
                f"Violations: {hs['violation_count']}<br>"
                f"Peak: {hs['peak_window']}<br>"
                f"Station: {hs['police_station']}",
                max_width=220,
            ),
        ).add_to(m)

    st_folium(m, width="100%", height=520)


def _risk_color(score: float) -> str:
    if score >= 75:
        return "#d73027"
    if score >= 50:
        return "#fc8d59"
    if score >= 25:
        return "#fee090"
    return "#91bfdb"
