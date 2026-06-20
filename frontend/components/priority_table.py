"""
Priority table — Custom HTML table mimicking the dark SaaS aesthetic.
"""
import pandas as pd
import streamlit as st

from services import api_client
from styles import status_badge

def render(filters: dict):
    data = api_client.get_priority(
        police_station=filters.get("police_station"),
        vehicle_type=filters.get("vehicle_type"),
    )
    rows = data.get("priority", [])
    if not rows:
        st.info("No data.")
        return

    df = pd.DataFrame(rows)

    c1, c2 = st.columns([2, 1])
    with c1:
        sort_by = st.selectbox(
            "Sort by", ["Risk Score", "Hotspot ID", "Station", "Priority Tier"],
            index=0, key="pq_sort_field", label_visibility="collapsed"
        )
    with c2:
        sort_dir = st.radio(
            "Dir", ["Desc", "Asc"],
            horizontal=True, index=0, key="pq_sort_dir", label_visibility="collapsed"
        )

    _COL = {
        "Risk Score": "risk_score",
        "Hotspot ID": "hotspot_id",
        "Station": "police_station",
        "Priority Tier": "priority_tier",
    }
    df = df.sort_values(_COL[sort_by], ascending=(sort_dir == "Asc")).reset_index(drop=True)

    thead = (
        "<tr>"
        '<th style="width:32px;">#</th>'
        "<th>ZONE</th>"
        "<th>RISK</th>"
        "<th>PEAK BLOCK</th>"
        "<th>STATION</th>"
        "<th>TIER</th>"
        "</tr>"
    )

    rows_html: list[str] = []
    for i, (_, r) in enumerate(df.iterrows(), 1):
        badge = status_badge(r["priority_tier"])
        rows_html.append(
            f"<tr>"
            f'<td>{i}</td>'
            f'<td class="tbl-id">{r["hotspot_id"]}</td>'
            f'<td>{r["risk_score"]:.1f}</td>'
            f'<td>{r["logging_window"]}</td>'
            f'<td>{r["police_station"]}</td>'
            f"<td>{badge}</td>"
            f"</tr>"
        )

    st.markdown(
        f'<div class="ptbl-wrapper">'
        f'<div style="max-height:480px; overflow-y:auto;">'
        f'<table class="ptbl">'
        f"<thead>{thead}</thead>"
        f'<tbody>{"".join(rows_html)}</tbody>'
        f"</table></div></div>",
        unsafe_allow_html=True,
    )
