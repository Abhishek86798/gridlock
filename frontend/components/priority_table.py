import streamlit as st
import pandas as pd

from frontend.services import api_client


def render(filters: dict):
    st.subheader("Enforcement Priority Queue")
    data = api_client.priority(filters)
    rows = data.get("priority", [])
    if not rows:
        st.info("No data — run the ML pipeline first.")
        return

    df = pd.DataFrame(rows)[
        ["rank", "hotspot_id", "risk_score", "peak_window", "police_station", "recommended_units"]
    ]
    df.columns = ["Rank", "Zone", "Risk Score", "Peak Window", "Station", "Units"]

    st.dataframe(
        df.style.background_gradient(subset=["Risk Score"], cmap="RdYlGn_r"),
        use_container_width=True,
        hide_index=True,
    )
