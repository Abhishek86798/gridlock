# Trinetra — Traffic Enforcement Intelligence System

Trinetra is an AI-powered dashboard built for Bengaluru Traffic Police (BTP) to turn raw illegal-parking violation logs into actionable enforcement decisions. Built for the Flipkart × BTP AI Hackathon (Finale: 3 July 2026).

---

## The Problem

BTP enforces illegal parking reactively — patrols roam and ticket whatever they happen to see. There is no systematic view of where violations cluster, when they peak, or which hotspots genuinely choke traffic. Enforcement is spread thin and blind.

---

## What Trinetra Does

**Hotspot Detection**
Clusters 170,000+ violation records into geo-hotspots across Bengaluru using H3 hexagonal indexing. Each hotspot gets a risk score (0–100) combining violation density, frequency, and cluster size.

**Predictive Forecasting**
An XGBoost model forecasts next week's violation counts per hotspot and per police station. The dashboard flags hotspots predicted to spike >20% above their 5-week baseline — the "escalation watch" — so commanders know where violations are rising before they happen.

**Optimal Patrol Deployment**
Given N patrol units, a greedy spatial optimiser allocates units to maximise coverage of the highest-risk predicted load. Outputs a ready-to-action roster: unit number, patrol route, risk score, and time window.

**POI Spillover Analysis**
Tags hotspots by proximity to Points of Interest — metro stations, malls, hospitals, schools. Shows which POI categories drive the most violations and highlights them on an interactive map.

**Temporal Distribution**
Hour × weekday heatmap per hotspot showing when violations peak. Used to set patrol shift timings.

**Repeat Offender Profiling**
K-Means clustering identifies Occasional / Frequent / Habitual offenders from anonymised vehicle IDs. Commanders can pin offender hotspots directly to the Live Map.

**Live Map**
Interactive Leaflet map of all hotspots colour-coded by risk tier (Critical / Elevated / Standard) with patrol route overlays and a watchlist pin system.

---

## Stack

- **Backend:** FastAPI + Python, XGBoost, Pandas, H3
- **Frontend:** Next.js 15 (App Router), TypeScript, Tailwind CSS, Recharts, Leaflet
- **Data:** HackerEarth-provided BTP violation dataset (~170k records)
