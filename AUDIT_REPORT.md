# Trinetra — Audit Report & Enhancement Plan

> **Date:** 2026-06-22 · **Window:** ~2 days before submission
> **Purpose:** honest technical audit, the real reason the app feels slow (measured, not guessed),
> a database recommendation, and a prioritised list of enhancements — weighted toward ML.

---

## 0. TL;DR — what to fix first

| Priority | Item | Status | Impact |
|---|---|---|---|
| 🔴 P0 | Patrol optimiser `iterrows()` → NumPy vectorised | ✅ Done | `/patrol` 15s → <0.5s |
| 🔴 P0 | Cap patrol curve to `units` requested (was hardcoded 100) | ✅ Done | no wasted work |
| 🔴 P0 | `/forecast` per-hotspot loop → single `groupby` | ✅ Done | 4.5s → <0.3s |
| 🟠 P1 | `/stats` startup cache — zero per-call computation | ✅ Done | ~1s → instant |
| 🟠 P1 | Forecast model warm at startup — no cold-start on first request | ✅ Done | 11s first-hit gone |
| 🟡 P2 | Predictive patrol allocation + escalation watch (forecast → optimiser) | ✅ Done | dashboard → decision system |
| 🟡 P2 | Repeat-offender K-Means tiering (Occasional/Frequent/Habitual) | ✅ Done | habitual-offender intelligence |
| 🟡 P2 | Station-level forecasting (coarse grain, low noise) | ✅ Done | `/forecast/stations` — P@10 0.80, CV 1.01 vs 2.00 |
| 🟡 P2 | Risk-score rewrite (shares + shrinkage + junction mult) | ✅ Done | score spreads 9.9–62.8 (was mean 42, std 7) |
| 🟡 P2 | Shift-level forecasting (when, not just how many) | ⬜ Todo | shift-level patrol scheduling |
| 🟡 P2 | Spatial-lag forecasting (neighbour features) | ❌ Rejected | A/B: −0.07 MAE but **0** ranking gain — see CHANGES_2026-06-22.md §3 |
| 🟡 P2 | SHAP "why" panel on forecast | ⬜ Todo | trust + wow factor |
| 🟢 P3 | README / correctness issues (§6) | ⬜ Todo | honesty before judging |

**The headline finding: the slowness is NOT the static dataset. It's algorithmic — triple-nested
`iterrows()` loops and recomputation on every request. All three root causes are now fixed.**

**Update (since first audit): two ML differentiators are now shipped — predictive patrol
allocation (§8.1) and repeat-offender intelligence (§8.4). The remaining roadmap is in §8.**

---

## 1. Why it's slow — MEASURED, not guessed

I loaded the real artifacts and timed the endpoints:

```
hotspots: 1,196 | violations: 112,771

/patrol units=10  : 3.23 s
/patrol units=50  : 5.39 s
/patrol units=100 : 14.85 s   ← worst offender
/forecast (1st, trains) : 11.34 s
/forecast (2nd, cached) : 4.47 s   ← still slow even when "cached"!
/stats : ~1 s every call
```

### Root cause #1 — Patrol optimiser is O(n³) — `backend/app/services/patrol_optimizer.py`
The function has **three nested `iterrows()` loops**:
- outer loop over units (lines ~63)
- inner candidate scan over all hotspots (line ~81)
- a second full hotspot scan to mark coverage (line ~130)

`iterrows()` is the slowest way to touch a DataFrame (it boxes every row into a Series).
Worse: it **always computes the coverage curve up to 100 units** (`max_units = max(units, 100)`),
so even `/patrol?units=10` does the full 100-unit work. That's why 100 units = 15 s.

**Fix:** pull `lat/lng/priority` into NumPy arrays once; compute the haversine candidate/coverage
masks with vectorised NumPy (or `scipy.spatial.cKDTree` for nearest-neighbour). Expected: **<0.5 s**.

### Root cause #2 — `/forecast` re-loops 1,196 hotspots every request — `forecast.py:411`
Even after the XGBoost model is cached, `get_forecast()` runs:
```python
for hs_id in panel["hotspot_id"].unique():      # 1,196 iterations
    hs_base = baseline_panel[baseline_panel["hotspot_id"] == hs_id]   # full scan
    hs_lag  = lag_panel[lag_panel["hotspot_id"] == hs_id]             # full scan
    hs_any  = panel[panel["hotspot_id"] == hs_id].iloc[-1]            # full scan
```
That's ~3,600 full-DataFrame boolean scans **per request** → the 4.5 s "cached" time.

**Fix:** replace the loop with a single `groupby("hotspot_id").agg(...)`. The whole per-hotspot
baseline/prediction frame can be built once and **cached alongside the model** in `_cache`.
Expected: **<0.3 s** after first train.

### Root cause #3 — `/stats` re-parses datetimes every call — `analytics.py:29`
```python
dates = pd.to_datetime(dates_raw, format="mixed", errors="coerce")   # 112,771 rows, every call
```
`format="mixed"` is especially slow (it infers format per element). The value_counts on
vehicle/violation/station also recompute each call.

**Fix:** precompute these once at startup (store as a cached dict), or store `created_ist` already
as a datetime in the parquet so no re-parse is needed.

### What is NOT the problem
- **Not the parquet size** — loading all artifacts takes ~470 ms total at startup (one time).
- **Not "static dataset"** — in-memory pandas is fine at this scale; the algorithms are the issue.
- **Not the model** — XGBoost trains in ~7 s once; that's acceptable as a one-time cost.

---

## 2. Do you need a database?

**Short answer: not to fix the speed — but yes, it's a worthwhile upgrade for scalability and
clean filtering, and it makes a strong "production-ready" story for judges.**

### Why the current setup feels DB-like but isn't
Right now every request filters in-memory pandas (`df[df["police_station"] == x]`). That works,
but: filters re-scan full frames, there's no indexing, and concurrent requests share one mutable
global. It's fine for a demo, not for many users or a growing dataset.

### Recommended: **DuckDB** (best fit, already a dependency you removed — re-add it)
- **Embedded** (no server to run), reads your existing **`.parquet` files directly** — zero schema migration.
- Columnar + vectorised: filter/group/aggregate queries are *faster* than pandas at this size,
  and scale to millions of rows without loading everything into RAM.
- Drop-in: `duckdb.sql("SELECT * FROM 'hotspots.parquet' WHERE police_station = ?")`.
- Lets you push `/hotspots`, `/stations`, `/junctions`, `/enforcement-quality` filtering into SQL.

```python
import duckdb
con = duckdb.connect()  # in-memory, queries parquet on disk
con.sql("SELECT police_station, AVG(risk_score) FROM 'data/processed/hotspots.parquet' GROUP BY 1")
```

### Alternative: **SQLite** if you want a familiar relational store
- Load the parquets into SQLite tables once at build time; index `police_station`, `hotspot_id`,
  `vehicle_number`. Good for the repeat-offender and enforcement-quality lookups.
- Slightly more setup than DuckDB; less analytical performance.

### For a "real deployment" pitch: **Postgres + PostGIS**
- Only if you want to claim production-grade geospatial. PostGIS gives true spatial indexes
  (`ST_DWithin`) which would make the patrol coverage query trivial and fast.
- More infra (a running DB server) — probably overkill for a 2-day window, but worth *mentioning*
  in the deck as "the production path."

**My recommendation for the 2 days:** add **DuckDB** for the filter-heavy endpoints + precompute
the patrol/forecast artifacts. You get the speed win AND the "we use a database" credibility without
standing up a server.

---

## 3. Quick wins (do these first — high impact, low effort)

1. **Vectorise the patrol optimiser** (P0) — biggest single speedup.
2. **Cache the forecast per-hotspot frame** in `_cache` (P0) — build it inside `_fit`, not per request.
3. **Precompute `/stats` aggregates at startup** (P1) — no per-call datetime parsing.
4. **Precompute `forecast.parquet` at build time** so the first `/forecast` is instant (model
   training moves to the offline pipeline, not the first user click).
5. **Don't always compute the 100-unit curve** — cap the curve at `units` (or precompute it once).
6. **Add response caching** — `functools.lru_cache` keyed on query params for `/hotspots`,
   `/stations`, `/forecast` (the inputs rarely change between requests).

---

## 4. ML enhancements (the differentiation — judges weight this heavily)

Ordered by impact-vs-effort for a 2-day window.

### 4.1 Replace the "rolling mean as displayed prediction" with a genuinely better model (HIGH)
Right now you *ship the rolling-mean* because XGBoost ties it (MAE 5.26 vs 5.25). That's honest but
underwhelming. Improvements that could actually beat the baseline:
- **More clean weeks via data augmentation:** you excluded the backlog weeks. Instead, model the
  *approval rate* and reweight, recovering signal from W06–W13 instead of dropping them.
- **Hierarchical/pooled model:** predict at station level (more data per series) then allocate to
  hotspots — reduces the small-sample noise that flattens per-hotspot XGBoost.
- **Poisson/Negative-Binomial GLM** as a statistically-principled count baseline; report it
  alongside XGBoost. Counts are over-dispersed → NB often beats both.

### 4.2 Spatio-temporal forecasting (HIGH differentiation)
- **Add spatial lag features:** a hotspot's neighbours' last-week counts (via H3 `grid_disk`)
  often predict its next week. Cheap to compute, usually a real accuracy gain.
- This turns "each hotspot in isolation" into a true spatio-temporal model — a strong slide.
- → **Now tracked as §8.3 (Spatial-Lag Forecasting), planned.**

### 4.3 Anomaly / emerging-hotspot detection (MEDIUM, high "wow")
- Flag **newly emerging** hotspots (cells that were quiet, now spiking) using a simple
  z-score / Poisson-surprise on weekly counts. Different from "high volume" — catches *change*.
- Visual: a "🆕 Emerging" badge on the map. Judges love seeing the system catch something new.
- → **Partially shipped:** the predictive-patrol **escalation watch** (§8.1) already flags rising
  hotspots (predicted > baseline). A dedicated z-score/Poisson-surprise *map badge* is the
  remaining "wow" piece if pursued.

### 4.4 Clustering for enforcement "regimes" (MEDIUM)
- Cluster hotspots by their hour×day temporal signature (KMeans on the 168-dim vector) to label
  "morning-market type", "overnight-arterial type", etc. Drives smarter patrol shift assignment.

### 4.5 Explainability (MEDIUM, cheap, high trust)
- Add **SHAP values** to the forecast — show *why* a hotspot is predicted to rise (lag1 high,
  neighbour spiking, etc.). A per-hotspot "why" panel is a killer judge moment.
- You already have an interpretable risk score; SHAP extends that story to the ML model.

### 4.6 Patrol optimisation upgrade (MEDIUM)
- Current optimiser is greedy nearest-neighbour. Upgrade to a proper **capacitated vehicle-routing**
  formulation (OR-Tools) or at least **2-opt** route improvement. Report route distance saved vs
  greedy — a concrete, quantifiable "optimisation" claim.

---

## 5. Product / feature enhancements (non-ML)

- **Time-window filter** on the dashboard (date range slider) — currently global stats only.
- **Hotspot detail drill-down** — click a map hotspot → its temporal heatmap, top vehicles,
  forecast, and SHAP "why". Ties all screens together.
- **Export / report generation** — "download this station's deployment plan as PDF" for commanders.
- **Live re-ingestion endpoint** — `POST /violations` to add new records and incrementally update
  hotspots (pairs naturally with the DB upgrade — sets up the "not just a static demo" narrative).
- **Auth + per-station login** — each station commander sees their jurisdiction. Small, but reads
  as production-ready.
- **Comparison view** — week-over-week change per station, to *show* the forecast was right.

---

## 6. Correctness / honesty issues found (fix before judging)

- **README mermaid says `.feather`** but artifacts are `.parquet`. (Diagram error.)
- **Data-pipeline mermaid** shows "Retain Approved & Pending" but code is approved-only.
- **Privacy masking example** in README uses `KA01AB****23`; real plates are synthetic `FKN…`.
- **Afternoon blind-spot** stated as 13:00–16:00 but code is `hour <= 16` (= 13:00–16:59).
- **Model-performance table** still has `[PLACEHOLDER]` for naive baseline precision.
- **h3 pin** was `3.7.7` (v3) but code uses v4 API — already bumped to 4.x in requirements.

---

## 7. Remaining plan

**Performance — all done ✅**
- [x] Vectorise patrol optimiser (O(n³) → O(n) NumPy)
- [x] Cap patrol curve to `units` requested
- [x] Forecast per-hotspot loop → `groupby` (3,600 scans → 3 passes)
- [x] `/stats` startup cache (zero per-call datetime parsing)
- [x] Forecast model warmed at startup (cold-start eliminated)

**ML — shipped since first audit ✅**
- [x] **Predictive patrol allocation + escalation watch** (§8.1) — forecast → optimiser, dual view
- [x] **Repeat-offender intelligence** (§8.4) — K-Means tiering on behavioural signals

**Still to do:**
- [ ] Shift-level forecasting (§8.2) — *when*, not just *how many*
- [ ] Spatial-lag forecasting (§8.3) — neighbour features → true spatio-temporal model
- [ ] Add SHAP "why" to the forecast (4.5) — cheap, high judge impact
- [ ] Fix README correctness issues (§6) — feather→parquet, blind-spot hours, placeholder metrics
- [ ] Re-verify all endpoints end-to-end after the performance changes

> Speed is fixed. Two ML differentiators are now shipped (§8.1, §8.4). The remaining ROI is
> shift-level + spatial-lag forecasting (§8.2–8.3) + SHAP + clean README.

---

## 8. ML upgrade roadmap (owner-selected — the four moves)

The four upgrades being worked on, in priority order. §8.1 and §8.4 are **done**; §8.2 and §8.3
are next. Together they take the forecast from "per-hotspot weekly count" to a genuine
spatio-temporal, shift-aware decision system.

### 8.1 Predictive Patrol Allocation ✅ DONE
**What:** Use forecasted hotspot risk instead of historical risk in the patrol optimiser, so
patrol units are deployed where *future* violations are most likely. Converts the system from
prediction-only to actionable decision support.

**Status / how it shipped:**
- `optimize_patrol(units, mode)` — `mode="predictive"` ranks hotspots by next-week predicted load
  (`priority = risk_score * predicted_count`, with historical fallback where the forecast has no
  clean-week signal so no dangerous hotspot goes unstaffed). `mode="historical"` kept as baseline.
- Spatial de-bunching / routing unchanged — only the maximised objective changes.
- Reports **predicted violations covered / total predicted load (%)** — coverage of predicted
  load, *not* a causal "prevented" claim (no patrol-effectiveness data exists).
- **Escalation watch:** rising hotspots (predicted > baseline) tagged covered/uncovered by the
  current allocation — the "future problems your patrols miss" signal.

**Honest caveat (documented):** per-hotspot predicted_count is ~95% collinear with historical
count — the hotspots are stably dangerous — so predictive coverage is *not* higher than
historical. The differentiation lives in the escalation watch, not the coverage number. The UI
frames coverage as *validation*, not superiority.

### 8.2 Shift-Level Forecasting ⬜ TODO
**What:** Predict not just *how many* violations will occur, but *when* (e.g. Tue 8–10 AM at
MG Road). Enables patrol scheduling at the shift level and makes forecasts operationally useful.

**Implementation notes:**
- The temporal artifact (`temporal.parquet`, hour × day-of-week counts per hotspot) already holds
  the within-week distribution; the weekly forecast holds the volume. Combine: distribute the
  predicted weekly count across the hotspot's historical hour×day signature to get per-shift
  predicted load.
- Output: per-hotspot top predicted shift windows; feed into `PatrolAssignment.time_window`
  (currently derived from `_format_peak_window`) so the deployment roster becomes shift-aware.
- Differentiator slide: "Tue 08–10 at MG Road" beats "MG Road, sometime next week."

### 8.3 Spatial-Lag Forecasting ⬜ TODO
**What:** Incorporate activity from neighbouring hotspots as model features, so risk propagates
across nearby junctions. Turns per-hotspot-in-isolation into a true spatio-temporal model.

**Implementation notes:**
- For each hotspot's H3 cell, use `h3.grid_disk(cell, k=1)` to find neighbour cells; add
  neighbours' previous-week counts (sum / mean) as lag features alongside the existing lag1–lag4.
- Cheap to compute (the H3 → hotspot map already exists in the forecast panel build), usually a
  real accuracy gain, and it's the cleanest path to *beating* the rolling-mean baseline the
  forecast currently ties (MAE 5.26 vs 5.25).
- Pairs with §8.2: a neighbour spiking is exactly the kind of cross-junction signal a per-hotspot
  model misses.

### 8.4 Repeat Offender Intelligence ✅ DONE
**What:** Identify and cluster vehicles by violation frequency, reoffending interval, violation
diversity, and location spread to automatically detect habitual offenders and prioritise
enforcement.

**Status / how it shipped:**
- Pipeline `backend/pipeline/repeat_offenders.py` builds per-vehicle behavioural signals
  (total violations, frequency/active-day, mean reoffend interval, violation diversity,
  distinct hotspots/locations) over a cohort filtered to ≥3 violations across ≥7 active days
  (drops one-day enforcement-drive bursts).
- **K-Means (k=3) on standardised behavioural axes** → ranked tiers
  **Occasional / Frequent / Habitual** (centroids ranked, not thresholded). Diversity/hotspots
  kept descriptive — they distorted the clustering and were excluded from the model.
- `/repeat-offenders` exposes per-offender tier + the **centroid explainer table** (the
  ML-credibility artifact); dashboard shows tier badges, reoffend-gap, and the behavioural-tiers
  strip.
- Honest framing: "Frequent" = intense but short-lived; "Habitual" = sustained high volume —
  a two-axis (cadence vs volume) story, named explicitly.
