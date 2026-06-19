import streamlit as st
import folium
from streamlit_folium import st_folium

from services import api_client


def render(filters: dict):
    st.subheader("Hotspot Map")
    data = api_client.get_hotspots(
        police_station=filters.get("police_station"),
        violation_type=filters.get("violation_type"),
        min_risk=float(filters.get("min_risk", 0)),
    )
    hotspots = data.get("hotspots", [])

    m = folium.Map(location=[12.9716, 77.5946], zoom_start=12, tiles="CartoDB positron")

    for hs in hotspots:
        radius = max(5, hs["risk_score"] / 8)
        color  = _risk_color(hs["risk_score"])
        popup  = (
            f"<b>{hs['hotspot_id']}</b><br>"
            f"Risk: {hs['risk_score']:.1f}<br>"
            f"Violations: {hs['violation_count']}<br>"
            f"Logging: {hs['logging_window']} "
            f"(AM {hs['morning_log_pct']:.0f}% / PM {hs['afternoon_log_pct']:.0f}%)<br>"
            f"Station: {hs['police_station']}"
        )
        folium.CircleMarker(
            location=[hs["lat"], hs["lng"]],
            radius=radius,
            color=color,
            fill=True,
            fill_opacity=0.7,
            popup=folium.Popup(popup, max_width=240),
            tooltip=hs.get("junction_name") or hs["hotspot_id"],
        ).add_to(m)

    st_folium(m, width="100%", height=520, returned_objects=[])


def _risk_color(score: float) -> str:
    # Scores in this dataset range 25–70.
    if score >= 60:
        return "#d73027"   # red
    if score >= 45:
        return "#fc8d59"   # orange
    return "#91bfdb"       # blue
