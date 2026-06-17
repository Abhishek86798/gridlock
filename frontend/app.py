"""
Parking Intelligence Dashboard — entry point.
Run: streamlit run frontend/app.py
"""
import streamlit as st

st.set_page_config(
    page_title="Parking Intel · Bengaluru",
    page_icon="🚦",
    layout="wide",
)

from frontend.components import map_view, priority_table, filters as filter_bar

st.title("Bengaluru Illegal-Parking Intelligence")
st.caption("AI-driven enforcement prioritisation — PS1 prototype")

# Sidebar filters
active_filters = filter_bar.render()

col_map, col_priority = st.columns([3, 2])

with col_map:
    map_view.render(active_filters)

with col_priority:
    priority_table.render(active_filters)
