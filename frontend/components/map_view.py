"""
Map view — dark tiles, rich popups, legend matching screenshot.
"""
import folium
import streamlit as st
from folium import MacroElement
from jinja2 import Template
from streamlit_folium import st_folium

from services import api_client
from styles import COLORS, TIER_MARKER

class _MapExtras(MacroElement):
    _template = Template("""
        {% macro header(this, kwargs) %}
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
        {% raw %}
        <style>
        .leaflet-popup-content-wrapper {
            background: #1B1D24 !important;
            color: #D1D5DB !important;
            border-radius: 8px !important;
            font-family: 'Inter', sans-serif !important;
            font-size: 13px !important;
            border: 1px solid #2F333D !important;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3) !important;
        }
        .leaflet-popup-tip { background: #1B1D24 !important; }
        .leaflet-popup-content { margin: 12px 16px !important; line-height: 1.6; }
        .pop-id { font-size: 14px; font-weight: 600; color: #FFFFFF; }
        .pop-lbl { color: #9CA3AF; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; }
        .pop-val { color: #F9FAFB; font-weight: 500; }
        .pop-badge {
            display: inline-block; font-size: 10px; font-weight: 700;
            padding: 2px 6px; border-radius: 4px;
            letter-spacing: 0.05em; text-transform: uppercase;
        }
        </style>
        {% endraw %}
        {% endmacro %}

        {% macro html(this, kwargs) %}
        {% raw %}
        <div style="
            position:absolute; z-index:999; bottom:16px; right:12px;
            background:#1B1D24; border:1px solid #2F333D; border-radius:8px;
            padding:12px 16px; font-family:'Inter',sans-serif;
            font-size:11px; color:#D1D5DB; line-height:1.8; font-weight:500;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            pointer-events:auto;
        ">
            <div style="color:#FFFFFF;font-weight:600;font-size:11px;margin-bottom:6px;letter-spacing:0.05em;text-transform:uppercase;">RISK TIER</div>
            <div><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#EF4444;margin-right:8px;vertical-align:middle;"></span>CRITICAL</div>
            <div><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#F59E0B;margin-right:8px;vertical-align:middle;"></span>ELEVATED</div>
            <div><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#3B82F6;margin-right:8px;vertical-align:middle;"></span>STANDARD</div>
        </div>
        {% endraw %}
        {% endmacro %}
    """)

    def __init__(self):
        super().__init__()
        self._name = "MapExtras"

_TIER_STYLES = {
    "Critical": "background:#991B1B; color:#FECACA; border:1px solid #DC2626;",
    "Elevated": "background:#92400E; color:#FDE68A; border:1px solid #D97706;",
    "Standard": "background:#1E3A8A; color:#BFDBFE; border:1px solid #2563EB;",
}

def _get_tier(score: float, p90: float, p99: float) -> str:
    if score >= p99: return "Critical"
    if score >= p90: return "Elevated"
    return "Standard"

def _popup_html(hs: dict, tier: str, is_assigned: bool) -> str:
    badge = f'<span class="pop-badge" style="{_TIER_STYLES[tier]}">{tier}</span>'
    patrol = ""
    if is_assigned:
        patrol = '<div style="margin-top:8px;"><span class="pop-badge" style="background:#064E3B;color:#34D399;border:1px solid #059669;">Patrol Assigned</span></div>'

    return (
        f'<div class="pop-id">{hs["hotspot_id"]}</div>'
        f'<div style="margin:6px 0;">{badge}</div>'
        f'<table style="border:none;border-collapse:collapse;margin-top:8px;width:100%;">'
        f'<tr><td class="pop-lbl" style="padding:2px 0;">Risk</td><td class="pop-val" style="text-align:right;">{hs["risk_score"]:.1f}</td></tr>'
        f'<tr><td class="pop-lbl" style="padding:2px 0;">Vio</td><td class="pop-val" style="text-align:right;">{hs["violation_count"]:,}</td></tr>'
        f'<tr><td class="pop-lbl" style="padding:2px 0;">Win</td><td class="pop-val" style="text-align:right;">{hs["logging_window"]}</td></tr>'
        f'</table>'
        f'{patrol}'
    )

def render(filters: dict):
    data = api_client.get_hotspots(
        police_station=filters.get("police_station"),
        violation_type=filters.get("violation_type"),
        vehicle_type=filters.get("vehicle_type"),
        min_risk=float(filters.get("min_risk", 0)),
    )
    hotspots = data.get("hotspots", [])

    all_data = api_client.get_hotspots(limit=1200)
    all_scores = sorted(h["risk_score"] for h in all_data.get("hotspots", []) if h.get("risk_score"))
    if all_scores:
        n = len(all_scores)
        p90, p99 = all_scores[int(n * 0.90)], all_scores[int(n * 0.99)]
    else:
        p90, p99 = 50.0, 60.0

    m = folium.Map(location=[12.9716, 77.5946], zoom_start=12, tiles="CartoDB dark_matter")

    patrol_units = filters.get("patrol_units", 0)
    assigned_ids = {a["hotspot_id"] for a in api_client.get_patrol(units=patrol_units).get("assignments", [])} if patrol_units > 0 else set()

    for hs in hotspots:
        hs_id, score = hs["hotspot_id"], hs["risk_score"]
        tier = _get_tier(score, p90, p99)
        color = TIER_MARKER[tier]
        is_assigned = hs_id in assigned_ids
        radius = max(5, score / 8)

        popup = folium.Popup(_popup_html(hs, tier, is_assigned), max_width=220)

        folium.CircleMarker(
            location=[hs["lat"], hs["lng"]], radius=radius,
            color=color, fill=True, fill_color=color, fill_opacity=0.8, weight=1,
            popup=popup, tooltip=hs.get("junction_name") or hs_id,
        ).add_to(m)

        if is_assigned:
            folium.CircleMarker(
                location=[hs["lat"], hs["lng"]], radius=radius + 4,
                color="#10B981", fill=False, weight=2, dash_array="4 4"
            ).add_to(m)

    m.get_root().add_child(_MapExtras())
    st_folium(m, width="100%", height=480, returned_objects=[])
