# Project Context — Bengaluru Illegal Parking Intelligence (PS1)

> **Purpose of this document:** Give any reader (a teammate, the author, or an AI coding agent) the *full* context of this project in one place — the problem, the data, what to build, the non-negotiables, and the differentiators. Read this first. Technical requirements live in `REQUIREMENTS.md`.

---

## 1. Hackathon Context

- **Event:** AI-driven traffic-solutions hackathon, Flipkart × Bengaluru Traffic Police (BTP).
- **Platform:** HackerEarth (Round 1 = ML Challenge, Round 2 = Prototype Phase).
- **Current stage:** Round 2 — Prototype Phase (virtual).
- **Round 2 deadline:** 21 June 2026, 11:59 PM IST.
- **Onsite finale:** 3 July 2026, Flipkart HQ, Bengaluru. Top 10 teams invited; **in-person attendance is mandatory to stay prize-eligible.**
- **Finale requirement:** A **working prototype** must be demonstrated live before a panel (BTP leadership + Flipkart subject-matter experts).
- **Prize pool:** ₹5,00,000.
- **Theme chosen:** Problem Statement 1 — *Poor Visibility on Parking-Induced Congestion*. (Only one theme may be chosen.)
- **Key rule:** Only the HackerEarth-provided dataset may be used for PS1/PS2. External datasets risk disqualification. (Map/POI geometry like OpenStreetMap is enrichment context, not a "dataset" — but treat any external data with caution and document it.)
- **Submission limit:** Each uploaded file < 50 MB. Desktop/laptop only.

**Judging criteria (what we're optimizing for):** solution robustness, innovation, prototype clarity, scalability, and real-world viability for Bengaluru traffic.

---

## 2. The Problem Statement (short)

**Today:** BTP enforces illegal parking *reactively* — patrols roam and ticket whatever they happen to see. There is no systematic view of where violations cluster, when they peak, or which ones actually choke traffic. Enforcement is spread thin and blind, and zones can't be prioritized.

**Goal:** Build an **AI-driven parking intelligence layer** on top of violation logs that:
1. **Detects** illegal-parking hotspots (where).
2. **Quantifies** their impact on traffic flow (how much they hurt).
3. **Enables targeted enforcement** — tells patrols *where and when* to go.

The payoff judges care about most is #3: turning raw violation logs into **actionable, prioritized enforcement decisions.**

---

## 3. The Dataset (description)

One row = one logged illegal-parking violation. Key columns and what they unlock:

| Column | What it is | What we use it for |
|---|---|---|
| `latitude`, `longitude` | Geo-coordinates of the violation | Spatial clustering, hotspot maps, heatmaps |
| `location` | Full address text | Human-readable labels, POI/area inference |
| `junction_name` | Named junction or "No Junction" | Junction-level aggregation; high-impact flag |
| `police_station` | Reporting station | Administrative grouping, station dashboards |
| `violation_type` | List, e.g. `["WRONG PARKING","PARKING IN A MAIN ROAD"]` | **Severity signal** — main-road / near-crossing parking hurts flow most |
| `offence_code` | Numeric codes e.g. `[112,104]` | Structured violation category |
| `vehicle_type` | CAR, SCOOTER, AUTO, TANKER, etc. | Bigger vehicle = more carriageway blocked |
| `vehicle_number` | Pre-anonymized vehicle ID (format: `FKN00GL*`, not a real plate) | **Repeat-offender** tracking |
| `created_datetime` | When logged | Time-of-day / day-of-week patterns; forecasting |
| `validation_status` | approved / rejected | Data quality + ground truth on legitimacy |
| `closed_datetime`, `action_taken_timestamp` | Resolution timing | Response analysis (often NULL — use with care) |
| `device_id`, `created_by_id` | Source device / reporter | Pipeline/quality analysis; supports "real-time feed" story |
| `center_code` | Administrative center | Grouping |

**Important gap:** There is **no direct traffic-flow / congestion measurement** in the data (no speed, volume, delay, or queue length). So "quantify impact on traffic flow" must be a **proxy/derived score**, not a measured value. Be honest about this in the pitch — it's a strength, not a weakness, when framed as an interpretable risk index.

**Data quality notes:** Many resolution timestamps are NULL. `validation_status` lets us filter to `approved` violations for the core analysis. Violation_type is a JSON-style array that must be parsed.

---

## 4. What To Build (target solution)

A **Parking Intelligence Dashboard** backed by an analysis + ML pipeline. End-to-end flow:

```
Raw violations CSV
   → Clean & feature-engineer (parse violation arrays, extract hour/weekday, filter approved, geo-clean)
   → Hotspot detection (spatial clustering: DBSCAN / H3 hexbins)
   → Temporal pattern mining (hour × weekday heatmaps per hotspot)
   → Congestion-Risk / Impact score (interpretable weighted index)
   → Predictive layer (forecast next hotspots & peak windows)
   → Patrol deployment recommendation (which zones, which time windows)
   → Interactive dashboard (map + heatmap + priority queue + filters)
```

**The narrative we are selling:** *Reactive and blind → predictive and targeted.* Predict the hotspot, score its impact, and tell the patrol exactly where and when to go.

---

## 5. Necessary Things (must-have baseline)

These are non-negotiable for a credible submission. Without these there is no project.

1. **Data pipeline:** load CSV, parse `violation_type` arrays, derive `hour`/`weekday`/`month` from `created_datetime`, filter/flag `approved` vs `rejected`, drop or handle bad coordinates.
2. **Hotspot detection:** spatial clustering (DBSCAN on lat/long or H3 hexbin aggregation) producing a ranked list of hotspots by violation count.
3. **Temporal analysis:** per-hotspot heatmaps of violations across hour-of-day and day-of-week; identify peak windows.
4. **Congestion-Risk (impact) score:** an interpretable weighted index per hotspot combining violation severity (main-road / near-crossing weighted high), density, vehicle size, and junction proximity. Documented formula.
5. **Enforcement output:** a ranked, map-based "go here at this time" priority view.
6. **Interactive dashboard:** a clean UI showing the map, hotspots, the priority table, and basic filters (time, police station, vehicle type).
7. **A clear pitch deck / README** explaining the problem, approach, score logic, and impact.

---

## 6. Add-Ons (differentiators — ranked by impact per effort)

These separate a top-10 submission from a generic heatmap. Aim to ship #1–#3 as core differentiators, plus #4 and the polished dashboard.

1. **Predictive hotspot forecasting (headline).** Forecast *where and when* violations will spike next, not just where they were. Gradient-boosting or Poisson model on location + hour + weekday features. Directly kills the "enforcement is reactive" pain point.
2. **Patrol deployment optimizer.** Given N patrol units, recommend the hotspot/time assignments that maximize coverage of high-impact zones (weighted greedy set-cover or k-means beats). This is the tangible "targeted enforcement" payoff for police leadership.
3. **Metro / commercial spillover tagging.** The challenge explicitly names metro stations, commercial areas, and events as drivers. Tag hotspots near these and surface stats like "X% of high-severity violations are within 200m of a metro station." Proves domain understanding.
4. **Repeat-offender intelligence.** Use `vehicle_number` to find chronic offenders and chronic locations ("these vehicles account for X% of violations"). Striking, screenshot-worthy, trivial to compute.
5. **Enforcement-quality meta-analysis.** Use `validation_status` to show rejection rates by area/device — where the detection/reporting pipeline is weak. A second-order insight that engineering judges appreciate.
6. **Scalability / real-time story.** Data has `device_id` (camera/device-sourced). Show an ingestion-pipeline architecture so the system reads live feeds, not just a static CSV. Scores the "scalability" judging axis.
7. **What-if scenario simulator (stretch).** "Deploy 3 units to the top hotspots in this window → expected coverage = X%." Decision-support framing.

---

## 7. Constraints & Risks

- **Time:** ~3 days to Round 2 deadline. Prioritize ruthlessly: must-haves first, then add-ons 1–3.
- **Data rule:** PS1/PS2 must use only the HackerEarth dataset. Document any map/POI enrichment.
- **Impact framing:** Never claim "measured" traffic-flow impact — it's a derived risk index. Defend it as interpretable, not as ground truth.
- **Finale:** A working prototype must be demoable in person on 3 July. Build the dashboard to actually run, not just slides.
- **File size:** keep each submission file < 50 MB.

---

## 8. Suggested Tech Stack

- **Analysis/ML:** Python, pandas, scikit-learn, (XGBoost/LightGBM for forecasting), h3 or DBSCAN for clustering.
- **Geospatial/maps:** geopandas, folium / kepler.gl / pydeck for heatmaps.
- **Dashboard:** Streamlit (fastest for 3 days) or a lightweight React + map front-end.
- **Packaging:** clear README, reproducible notebook, and a runnable app entrypoint.
