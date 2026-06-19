import streamlit as st
import pandas as pd

from services import api_client


def render(filters: dict):
    st.subheader("Enforcement Priority Queue")
    data = api_client.get_priority(
        police_station=filters.get("police_station"),
    )
    rows = data.get("priority", [])
    if not rows:
        st.info("No data — is the backend running?")
        return

    df = pd.DataFrame(rows)[
        ["rank", "hotspot_id", "risk_score", "logging_window", "police_station", "recommended_units"]
    ]
    df.columns = ["Rank", "Zone", "Risk Score", "Logging Window", "Station", "Units"]

    st.dataframe(
        df.style.background_gradient(subset=["Risk Score"], cmap="RdYlGn_r"),
        use_container_width=True,
        hide_index=True,
    )
