"""
Gridlock Parking Intelligence — Streamlit dashboard.

Run from the repo root:
    streamlit run frontend/app.py

Requires backend:
    uvicorn backend.app.main:app --port 8000
"""
import sys
from pathlib import Path

# Make `services.*` importable regardless of working directory.
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import streamlit as st

from components import filters as filter_component
from components import map_view, priority_table
from services import api_client

st.set_page_config(
    page_title="Gridlock — Bengaluru Parking Intelligence",
    page_icon="🚦",
    layout="wide",
)


@st.fragment
def render_temporal_heatmap(police_station: str | None, vehicle_type: str | None = None) -> None:
    hotspots_data = api_client.get_hotspots(
        police_station=police_station,
        vehicle_type=vehicle_type,
        limit=200,
    )
    hotspots = hotspots_data.get("hotspots", [])
    hs_ids = [hs["hotspot_id"] for hs in hotspots]
    if not hs_ids:
        st.info("No hotspots match the current filters.")
        return

    selected_id = st.selectbox("Select Hotspot", hs_ids, key="temporal_hs")
    temporal = api_client.get_temporal(selected_id)
    matrix = temporal.get("matrix", [])
    if not matrix:
        return

    df_t = pd.DataFrame(matrix)
    pivot = (
        df_t.pivot(index="hour", columns="day_of_week", values="count")
        .reindex(index=range(24), columns=range(7), fill_value=0)
    )
    pivot.columns = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    pivot.index.name = "Hour"
    st.write(f"Violation count by hour × weekday for **{selected_id}**")
    st.dataframe(
        pivot.style.background_gradient(cmap="OrRd"),
        use_container_width=True,
    )

    hs_row = next((h for h in hotspots if h["hotspot_id"] == selected_id), None)
    if hs_row:
        pm_pct = hs_row["afternoon_log_pct"]
        am_pct = hs_row["morning_log_pct"]
        st.info(
            f"**{selected_id}** — morning logging: {am_pct:.0f}% | "
            f"afternoon logging: {pm_pct:.0f}%"
            + (" ⚠️ Afternoon blind spot" if pm_pct < 5 else "")
        )

# ── Backend health check ───────────────────────────────────────────────────────
if not api_client.health():
    st.error(
        "Backend not reachable at http://localhost:8000. "
        "Start it with: `uvicorn backend.app.main:app --port 8000`"
    )
    st.stop()

# ── Sidebar filters ────────────────────────────────────────────────────────────
active_filters = filter_component.render()

# ── Header metrics ─────────────────────────────────────────────────────────────
stats = api_client.get_stats()
if stats:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Violations", f"{stats.get('total_violations', 0):,}")
    c2.metric("Hotspot Zones", f"{stats.get('total_hotspots', 0):,}")

    by_station = stats.get("by_police_station", {})
    top_station = max(by_station, key=by_station.get) if by_station else "—"
    c3.metric("Busiest Station", top_station)

    by_vehicle = stats.get("by_vehicle_type", {})
    top_vehicle = max(by_vehicle, key=by_vehicle.get) if by_vehicle else "—"
    c4.metric("Top Vehicle Type", top_vehicle)

    # Blind-spot story: fraction of hotspots with <5% afternoon logging.
    stations_data = api_client.get_stations()
    stations_rows = stations_data.get("stations", [])
    if stations_rows:
        blind_avg = sum(s["blind_spot_pct"] for s in stations_rows) / len(stations_rows)
        c5.metric(
            "Afternoon Blind Spot",
            f"{blind_avg:.0f}%",
            help="% of hotspot zones with <5% of logs after 3 PM — city has near-zero PM enforcement coverage.",
        )

    dr = stats.get("date_range", {})
    st.caption(f"Dataset: {dr.get('start', '?')} → {dr.get('end', '?')}")

st.markdown("---")

# ── Map + Priority side by side ────────────────────────────────────────────────
col_map, col_table = st.columns([3, 2])

with col_map:
    map_view.render(active_filters)

with col_table:
    priority_table.render(active_filters)

st.markdown("---")

# ── Tabs: Forecast | Patrol Deployment | POI Spillover | Temporal | Stations | Junctions ──────────
tab_forecast, tab_patrol, tab_poi, tab_temporal, tab_stations, tab_junctions = st.tabs(
    ["🔮 Tomorrow's Hotspots", "🚓 Patrol Deployment", "🏙️ POI Spillover", "Temporal Heatmap", "By Police Station", "By Junction"]
)

with tab_forecast:
    _fc = api_client.get_forecast(top_n=25)
    fc_items = _fc.get("forecast", [])
    if not fc_items:
        st.warning(
            "Forecast not available. Ensure the backend is running and "
            "parquet artifacts exist (`python -m backend.pipeline.precompute`)."
        )
    else:
        pw  = _fc.get("predict_week", "?")
        mae = _fc.get("model_mae", 0.0)

        # ── headline metrics row ─────────────────────────────────────────────────
        fm1, fm2, fm3, fm4 = st.columns(4)
        fm1.metric("📅 Forecast Week", pw)
        fm2.metric("📊 Model MAE", f"{mae:.1f} violations/hotspot")

        df_fc = pd.DataFrame(fc_items)
        rising = (df_fc["change_pct"] > 10).sum()
        falling = (df_fc["change_pct"] < -10).sum()
        fm3.metric("🔺 Rising Hotspots  (≥10%)", int(rising))
        fm4.metric("🔻 Falling Hotspots (≤10%)", int(falling))

        st.caption(
            f"**Methodology**: XGBoost (count:poisson) trained on lag×4, "
            f"4-week rolling mean, ISO week seasonality, risk score, junction & POI flags. "
            f"2-week time-based hold-out. Prediction grain: ISO week **{pw}**."
        )

        # ── badge column + styled table ───────────────────────────────────────
        def _trend_badge(pct: float) -> str:
            if pct > 20:
                return "🔥 Spiking"
            if pct > 5:
                return "⬆️ Rising"
            if pct < -20:
                return "✅ Dropping fast"
            if pct < -5:
                return "⬇️ Easing"
            return "➡️ Stable"

        df_fc["Trend"] = df_fc["change_pct"].apply(_trend_badge)
        df_display = df_fc[[
            "hotspot_id", "police_station",
            "predicted_count", "prev_week_count", "change_pct",
            "risk_score", "Trend",
        ]].copy()
        df_display.columns = [
            "Hotspot", "Police Station",
            "Predicted Count", "Last Week", "Change %",
            "Risk Score", "Trend",
        ]
        df_display = df_display.sort_values("Predicted Count", ascending=False).reset_index(drop=True)
        df_display.index += 1  # rank starts at 1

        st.dataframe(
            df_display.style
                .background_gradient(subset=["Predicted Count", "Risk Score"], cmap="YlOrRd")
                .background_gradient(subset=["Change %"], cmap="RdYlGn_r")
                .format({"Predicted Count": "{:.1f}", "Last Week": "{:.0f}",
                         "Change %": "{:+.1f}%", "Risk Score": "{:.1f}"}),
            use_container_width=True,
        )

        # ── bar chart: top 10 by predicted count ──────────────────────────────────
        st.write("**Top 10 hotspots — next-week predicted violations**")
        top10 = df_display.head(10).reset_index(drop=True)
        st.bar_chart(
            top10.set_index("Hotspot")[["Predicted Count", "Last Week"]],
            use_container_width=True,
        )

with tab_patrol:
    st.write("### 🚓 Patrol Deployment Optimizer")
    st.write(
        "Assign N patrol units to maximize high-priority coverage. "
        "Uses greedy spatial de-bunching to prevent units from overlapping "
        "within 1km of each other."
    )
    
    units_to_deploy = active_filters.get("patrol_units", 0)
    if units_to_deploy == 0:
        st.info("👈 Use the **Patrol Deployment** slider in the sidebar to assign units and view the coverage curve.")
    else:
        patrol_data = api_client.get_patrol(units=units_to_deploy)
        if not patrol_data or not patrol_data.get("assignments"):
            st.warning("Patrol data not available. Ensure backend is running.")
        else:
            p_units = patrol_data.get("units", units_to_deploy)
        cov_pct = patrol_data.get("coverage_pct", 0.0)
        assignments = patrol_data.get("assignments", [])
        coverage_curve = patrol_data.get("coverage_curve", [])
        
        c1, c2 = st.columns(2)
        c1.metric("Units Assigned", len(assignments))
        c2.metric("Priority Coverage", f"{cov_pct:.1f}%")
        
        if coverage_curve:
            df_curve = pd.DataFrame(coverage_curve)
            st.write("**Coverage vs. Units Deployed**")
            st.line_chart(df_curve.set_index("units")["coverage_pct"], use_container_width=True)

        df_patrol = pd.DataFrame(assignments)
        if not df_patrol.empty:
            df_patrol = df_patrol.rename(columns={
                "unit_id": "Unit ID",
                "hotspot_id": "Hotspot ID",
                "time_window": "Time Window"
            })
            st.write("**Deployment Roster**")
            st.dataframe(df_patrol, use_container_width=True, hide_index=True)

with tab_poi:
    _poi = api_client.get_poi_stats()
    by_cat = _poi.get("by_category", [])
    tagged = _poi.get("tagged_hotspots", 0)
    untagged = _poi.get("untagged_hotspots", 0)
    total_hs = tagged + untagged

    if not by_cat:
        st.info(
            "POI tags not available yet. Re-run the pipeline:\n"
            "`python -m backend.pipeline.precompute --steps hotspots`"
        )
    else:
        # ── headline pitch line ──────────────────────────────────────────────────
        tagged_pct = tagged / total_hs * 100 if total_hs else 0
        top_cat_row = max(by_cat, key=lambda r: r["hotspot_count"])
        st.success(
            f"⚠️ **{tagged_pct:.0f}% of hotspot zones** are near a metro station, "
            f"commercial hub, bus stop, or sensitive facility. "
            f"The largest spillover category is **{top_cat_row['poi_category']}** "
            f"({top_cat_row['hotspot_count']} zones, "
            f"{top_cat_row['pct_of_hotspots']:.0f}% of all hotspots)."
        )

        # ── headline metrics ────────────────────────────────────────────────────────────────
        pm1, pm2, pm3 = st.columns(3)
        pm1.metric("📍 Tagged Hotspots", tagged, help="Hotspots with at least one POI keyword match")
        pm2.metric("❓ Untagged", untagged)
        pm3.metric("📊 Tag Coverage", f"{tagged_pct:.0f}%")

        # ── per-category breakdown table ────────────────────────────────────────────────
        _CAT_EMOJI = {
            "sensitive":  "🏫",
            "metro":      "🚇",
            "commercial": "🛍️",
            "transit":    "🚌",
        }
        df_poi = pd.DataFrame(by_cat)
        df_poi["Category"] = df_poi["poi_category"].map(
            lambda c: f"{_CAT_EMOJI.get(c, '')} {c.title()}"
        )
        df_poi = df_poi.rename(columns={
            "hotspot_count":    "Hotspots",
            "total_violations": "Violations",
            "avg_risk_score":   "Avg Risk",
            "pct_of_hotspots":  "% of All Hotspots",
        })[["Category", "Hotspots", "Violations", "Avg Risk", "% of All Hotspots"]]

        st.dataframe(
            df_poi.style
                .background_gradient(subset=["Hotspots", "Avg Risk"], cmap="YlOrRd")
                .format({"Avg Risk": "{:.1f}", "% of All Hotspots": "{:.1f}%",
                         "Violations": "{:,}"}),
            use_container_width=True,
            hide_index=True,
        )

        # ── bar chart ────────────────────────────────────────────────────────────────────
        st.write("**Violations per POI category**")
        st.bar_chart(
            df_poi.set_index("Category")[["Violations", "Hotspots"]],
            use_container_width=True,
        )

        st.caption(
            "**Method**: Keyword match on `location` + `junction_name` columns. "
            "Categories: `sensitive` (school/hospital), `metro`, `commercial` "
            "(mall/market/bazaar), `transit` (bus stop/stand). "
            "Priority order: sensitive → metro → commercial → transit. "
            "No external datasets used — PS1-compliant."
        )

with tab_temporal:
    render_temporal_heatmap(active_filters.get("police_station"), active_filters.get("vehicle_type"))

with tab_stations:
    stations = api_client.get_stations()
    rows = stations.get("stations", [])
    if rows:
        df_st = pd.DataFrame(rows)[[
            "police_station", "hotspot_count", "total_violations",
            "avg_risk_score", "max_risk_score", "blind_spot_pct",
            "dominant_violation", "top_hotspot_id",
        ]]
        df_st.columns = [
            "Station", "Hotspots", "Violations",
            "Avg Risk", "Max Risk", "Blind Spot %",
            "Top Violation", "Top Hotspot",
        ]
        st.caption(
            f"{len(df_st)} stations · city-wide afternoon blind-spot avg: "
            f"{df_st['Blind Spot %'].mean():.0f}%"
        )
        st.dataframe(
            df_st.style.background_gradient(subset=["Avg Risk", "Blind Spot %"], cmap="YlOrRd"),
            use_container_width=True,
            hide_index=True,
        )

with tab_junctions:
    junctions = api_client.get_junctions(min_violations=50)
    rows = junctions.get("junctions", [])
    if rows:
        df_jn = pd.DataFrame(rows)[[
            "junction_name", "total_violations", "hotspot_count",
            "avg_risk_score", "police_station", "top_hotspot_id",
        ]]
        df_jn.columns = [
            "Junction", "Violations", "Hotspots",
            "Avg Risk", "Station", "Top Hotspot",
        ]
        st.caption(f"{len(df_jn)} named junctions with ≥ 50 violations")
        st.dataframe(
            df_jn.style.background_gradient(subset=["Avg Risk"], cmap="YlOrRd"),
            use_container_width=True,
            hide_index=True,
        )
