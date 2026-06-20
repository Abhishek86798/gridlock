"""
Design system — Rich Dark SaaS Dashboard.
"""
from __future__ import annotations

import streamlit as st

COLORS = {
    "bg_base":       "#13151A",
    "bg_surface":    "#1B1D24",
    "bg_elevated":   "#22252D",
    "border":        "#2F333D",
    "text_primary":  "#FFFFFF",
    "text_secondary":"#9CA3AF",
    "text_muted":    "#6B7280",
    "critical":      "#EF4444",
    "elevated":      "#F59E0B",
    "standard":      "#3B82F6",
    "patrol":        "#10B981",
    "accent":        "#6366F1",
}

TIER_MARKER = {
    "Critical": COLORS["critical"],
    "Elevated": COLORS["elevated"],
    "Standard": COLORS["standard"],
}

_A = ('xmlns="http://www.w3.org/2000/svg" width="18" height="18" '
      'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
      'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"')

ICONS: dict[str, str] = {
    "shield":      f'<svg {_A} stroke="#60A5FA"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
    "map_pin":     f'<svg {_A} stroke="#F472B6"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>',
    "building":    f'<svg {_A} stroke="#FCD34D"><rect x="4" y="2" width="16" height="20" rx="2" ry="2"/><path d="M9 22v-4h6v4"/><path d="M8 6h.01"/><path d="M16 6h.01"/><path d="M12 6h.01"/><path d="M12 10h.01"/><path d="M12 14h.01"/><path d="M16 10h.01"/><path d="M16 14h.01"/><path d="M8 10h.01"/><path d="M8 14h.01"/></svg>',
    "eye":         f'<svg {_A} stroke="#FBBF24"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>',
    "car":         f'<svg {_A} stroke="#9CA3AF"><path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2"/><circle cx="7" cy="17" r="2"/><path d="M9 17h6"/><circle cx="17" cy="17" r="2"/></svg>',
}

def icon(name: str) -> str:
    return ICONS.get(name, "")

_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
    background-color: #13151A !important;
}

/* Base Streamlit Overrides */
.stApp {
    background-color: #13151A;
}
section[data-testid="stSidebar"] {
    background-color: #1B1D24 !important;
    border-right: 1px solid #2F333D !important;
}

/* Header actions (Top right deploy button) */
.top-header-actions {
    position: absolute;
    top: 16px;
    right: 24px;
    display: flex;
    align-items: center;
    gap: 16px;
    z-index: 9999;
}
.btn-deploy {
    background: linear-gradient(180deg, #E2E8F0 0%, #94A3B8 100%);
    color: #0F172A;
    border: none;
    padding: 6px 20px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    box-shadow: 0 0 15px rgba(226, 232, 240, 0.3);
    cursor: pointer;
}
.sync-status {
    font-size: 11px;
    color: #9CA3AF;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* Section Containers (Cards for Map, Table) */
.panel-card {
    background: #1B1D24;
    border: 1px solid #2F333D;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 24px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
}
.panel-header {
    font-size: 13px;
    font-weight: 600;
    color: #E5E7EB;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
}

/* KPI Row */
.kpi-row {
    display: flex;
    gap: 16px;
    margin-bottom: 24px;
    margin-top: 48px; /* Room for absolute header */
}
.kpi-card {
    background: linear-gradient(180deg, #22252D 0%, #1B1D24 100%);
    border: 1px solid #2F333D;
    border-radius: 8px;
    padding: 16px 20px;
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    position: relative;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2);
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, rgba(255,255,255,0.1), rgba(255,255,255,0));
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}
.kpi-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    font-weight: 600;
    color: #9CA3AF;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 8px;
}
.kpi-body {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
}
.kpi-value {
    font-size: 28px;
    font-weight: 700;
    color: #F9FAFB;
    line-height: 1;
}

/* Badges */
.badge {
    display: inline-block;
    font-size: 10px;
    font-weight: 700;
    padding: 4px 8px;
    border-radius: 4px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.badge-critical { background: #991B1B; color: #FECACA; border: 1px solid #DC2626; }
.badge-elevated { background: #92400E; color: #FDE68A; border: 1px solid #D97706; }
.badge-standard { background: #1E3A8A; color: #BFDBFE; border: 1px solid #2563EB; }

/* Table */
.ptbl-wrapper {
    background: #1B1D24;
    border: 1px solid #2F333D;
    border-radius: 8px;
    overflow: hidden;
}
.ptbl {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
}
.ptbl thead th {
    background: #22252D;
    color: #9CA3AF;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 12px 16px;
    text-align: center;
    border-bottom: 1px solid #2F333D;
}
.ptbl tbody tr {
    border-bottom: 1px solid #2F333D;
}
.ptbl tbody tr:hover {
    background: #22252D;
}
.ptbl tbody td {
    padding: 12px 16px;
    color: #D1D5DB;
    text-align: center;
}
.ptbl .tbl-id {
    color: #F9FAFB;
    font-weight: 500;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    background: #1B1D24;
    padding: 6px;
    border-radius: 8px;
    border: 1px solid #2F333D;
}
.stTabs [data-baseweb="tab"] {
    font-family: 'Inter', sans-serif !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    color: #9CA3AF !important;
    padding: 8px 16px !important;
    border-radius: 6px !important;
    border: none !important;
    background: transparent !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.stTabs [aria-selected="true"] {
    color: #FFFFFF !important;
    background: #2F333D !important;
}

/* DataFrame */
[data-testid="stDataFrame"] {
    background: #1B1D24 !important;
    border: 1px solid #2F333D !important;
    border-radius: 8px !important;
}

/* Sidebar styles */
.sidebar-header {
    font-size: 14px;
    font-weight: 600;
    color: #E5E7EB;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 24px;
}
section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stSlider label {
    font-size: 11px !important;
    font-weight: 600 !important;
    color: #9CA3AF !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
}
"""

def inject_css() -> None:
    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)

def kpi_card(label: str, value: str, icon_name: str, extra_html: str = "") -> str:
    ico = icon(icon_name)
    return (
        f'<div class="kpi-card">'
        f'  <div class="kpi-header">{ico} {label}</div>'
        f'  <div class="kpi-body">'
        f'    <div class="kpi-value">{value}</div>'
        f'    {extra_html}'
        f'  </div>'
        f'</div>'
    )

def kpi_row(*cards: str) -> None:
    st.markdown(f'<div class="kpi-row">{"".join(cards)}</div>', unsafe_allow_html=True)

def panel_header(text: str) -> str:
    return f'<div class="panel-header">{text}</div>'

def status_badge(tier: str) -> str:
    return f'<span class="badge badge-{tier.lower()}">{tier}</span>'

def dark_altair(chart, height: int = 300):
    return (
        chart.properties(height=height)
        .configure_view(strokeWidth=0)
        .configure_axis(
            gridColor="#2F333D",
            domainColor="#2F333D",
            tickColor="#2F333D",
            labelColor="#9CA3AF",
            titleColor="#9CA3AF",
            labelFont="Inter",
            titleFont="Inter"
        )
        .configure_legend(
            labelColor="#9CA3AF",
            titleColor="#9CA3AF",
            labelFont="Inter",
            titleFont="Inter"
        )
        .configure(background="transparent")
    )
