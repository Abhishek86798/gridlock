"""
API smoke tests — every public endpoint, contract-level assertions.

Requires the server to be running:
    uvicorn backend.app.main:app --port 8000

Run from the repo root:
    pytest backend/tests/test_api.py -v

Uses httpx against the live server so tests never load parquets themselves.
"""
from __future__ import annotations

import pytest
import httpx

BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="session")
def client():
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as c:
        # Verify server is reachable before running any tests.
        try:
            c.get("/")
        except httpx.ConnectError:
            pytest.skip("Live server not running on port 8000 — start with: "
                        "uvicorn backend.app.main:app --port 8000")
        yield c


# ── Health ────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_root_ok(self, client):
        r = client.get("/")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["hotspots"] == 1196
        assert body["violations"] == 112771


# ── /hotspots ─────────────────────────────────────────────────────────────────

class TestHotspots:
    def test_default_returns_up_to_500(self, client):
        r = client.get("/hotspots")
        assert r.status_code == 200
        body = r.json()
        assert "count" in body and "hotspots" in body
        assert body["count"] <= 500
        assert len(body["hotspots"]) == body["count"]

    def test_limit_param(self, client):
        r = client.get("/hotspots?limit=10")
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 10
        assert len(body["hotspots"]) == 10

    def test_hotspot_schema(self, client):
        r = client.get("/hotspots?limit=1")
        hs = r.json()["hotspots"][0]
        required = {
            "hotspot_id", "lat", "lng", "risk_score", "violation_count",
            "dominant_violation", "dominant_vehicle", "logging_window",
            "morning_log_pct", "afternoon_log_pct", "police_station",
        }
        assert required.issubset(hs.keys()), f"Missing fields: {required - hs.keys()}"

    def test_hotspot_id_format(self, client):
        r = client.get("/hotspots?limit=5")
        for hs in r.json()["hotspots"]:
            assert hs["hotspot_id"].startswith("HS-"), hs["hotspot_id"]

    def test_risk_score_range(self, client):
        r = client.get("/hotspots?limit=200")
        for hs in r.json()["hotspots"]:
            assert 0 <= hs["risk_score"] <= 100, hs["hotspot_id"]

    def test_filter_by_police_station(self, client):
        r = client.get("/hotspots?police_station=Upparpet")
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 14
        for hs in body["hotspots"]:
            assert hs["police_station"] == "Upparpet"

    def test_filter_unknown_station_returns_empty(self, client):
        r = client.get("/hotspots?police_station=DOES_NOT_EXIST")
        assert r.status_code == 200
        assert r.json()["count"] == 0

    def test_filter_min_risk(self, client):
        r = client.get("/hotspots?min_risk=60")
        assert r.status_code == 200
        for hs in r.json()["hotspots"]:
            assert hs["risk_score"] >= 60

    def test_logging_window_valid_values(self, client):
        r = client.get("/hotspots?limit=200")
        valid = {"morning", "overnight", "split", "afternoon", "unknown"}
        for hs in r.json()["hotspots"]:
            assert hs["logging_window"] in valid, (
                f"{hs['hotspot_id']} has logging_window={hs['logging_window']!r}"
            )

    def test_no_peak_window_field(self, client):
        r = client.get("/hotspots?limit=1")
        assert "peak_window" not in r.json()["hotspots"][0]

    def test_sorted_by_risk_descending(self, client):
        r = client.get("/hotspots?limit=50")
        scores = [hs["risk_score"] for hs in r.json()["hotspots"]]
        assert scores == sorted(scores, reverse=True), "Hotspots not sorted by risk_score desc"

    def test_top_hotspot_is_hs0001(self, client):
        r = client.get("/hotspots?limit=1")
        assert r.json()["hotspots"][0]["hotspot_id"] == "HS-0001"


# ── /heatmap ──────────────────────────────────────────────────────────────────

class TestHeatmap:
    def test_returns_all_hotspots(self, client):
        r = client.get("/heatmap")
        assert r.status_code == 200
        body = r.json()
        assert "points" in body
        assert len(body["points"]) == 1196

    def test_point_schema(self, client):
        r = client.get("/heatmap")
        pt = r.json()["points"][0]
        assert {"lat", "lng", "weight"} == set(pt.keys())

    def test_weight_normalised_0_to_1(self, client):
        r = client.get("/heatmap")
        weights = [p["weight"] for p in r.json()["points"]]
        assert max(weights) == pytest.approx(1.0, abs=1e-6)
        assert min(weights) >= 0.0

    def test_coordinates_within_bengaluru_bbox(self, client):
        r = client.get("/heatmap")
        for pt in r.json()["points"]:
            assert 12.834 <= pt["lat"] <= 13.143, f"lat out of bbox: {pt['lat']}"
            assert 77.461 <= pt["lng"] <= 77.784, f"lng out of bbox: {pt['lng']}"

    def test_filter_station_reduces_points(self, client):
        r = client.get("/heatmap?police_station=Upparpet")
        assert r.status_code == 200
        assert len(r.json()["points"]) == 14


# ── /priority ─────────────────────────────────────────────────────────────────

class TestPriority:
    def test_default_returns_50(self, client):
        r = client.get("/priority")
        assert r.status_code == 200
        items = r.json()["priority"]
        assert len(items) == 50

    def test_rank_sequential(self, client):
        r = client.get("/priority?limit=10")
        ranks = [it["rank"] for it in r.json()["priority"]]
        assert ranks == list(range(1, 11))

    def test_priority_schema(self, client):
        r = client.get("/priority?limit=1")
        item = r.json()["priority"][0]
        required = {"rank", "hotspot_id", "risk_score", "logging_window",
                    "police_station", "priority_tier"}
        assert required.issubset(item.keys())
        assert "peak_window" not in item

    def test_descending_risk(self, client):
        r = client.get("/priority?limit=20")
        scores = [it["risk_score"] for it in r.json()["priority"]]
        assert scores == sorted(scores, reverse=True)

    def test_priority_tier_valid_values(self, client):
        r = client.get("/priority?limit=50")
        valid = {"Critical", "Elevated", "Standard"}
        for it in r.json()["priority"]:
            assert it["priority_tier"] in valid, it["priority_tier"]

    def test_filter_by_station(self, client):
        r = client.get("/priority?police_station=Upparpet")
        assert r.status_code == 200
        items = r.json()["priority"]
        assert len(items) == 14
        for it in items:
            # priority items don't expose police_station directly in all cases
            assert it["police_station"] == "Upparpet"


# ── /temporal/{hotspot_id} ────────────────────────────────────────────────────

class TestTemporal:
    def test_hs0001_returns_matrix(self, client):
        r = client.get("/temporal/HS-0001")
        assert r.status_code == 200
        body = r.json()
        assert body["hotspot_id"] == "HS-0001"
        assert len(body["matrix"]) > 0

    def test_cell_schema(self, client):
        r = client.get("/temporal/HS-0001")
        cell = r.json()["matrix"][0]
        assert {"hour", "day_of_week", "count"} == set(cell.keys())

    def test_hour_range(self, client):
        r = client.get("/temporal/HS-0001")
        for cell in r.json()["matrix"]:
            assert 0 <= cell["hour"] <= 23
            assert 0 <= cell["day_of_week"] <= 6
            assert cell["count"] > 0  # sparse — only non-zero stored

    def test_unknown_hotspot_404(self, client):
        r = client.get("/temporal/HS-9999")
        assert r.status_code == 404


# ── /stats ────────────────────────────────────────────────────────────────────

class TestStats:
    def test_stats_schema(self, client):
        r = client.get("/stats")
        assert r.status_code == 200
        body = r.json()
        assert body["total_violations"] == 112771
        assert body["total_hotspots"] == 1196
        assert body["date_range"]["start"] == "2023-11-10"
        assert body["date_range"]["end"] == "2024-03-29"
        assert isinstance(body["by_vehicle_type"], dict)
        assert isinstance(body["by_violation_type"], dict)
        assert isinstance(body["by_police_station"], dict)

    def test_top_vehicle_is_scooter_or_car(self, client):
        r = client.get("/stats")
        top = max(r.json()["by_vehicle_type"], key=r.json()["by_vehicle_type"].get)
        assert top in {"SCOOTER", "CAR"}

    def test_top_violation_types(self, client):
        r = client.get("/stats")
        types = set(r.json()["by_violation_type"].keys())
        assert "WRONG PARKING" in types
        assert "NO PARKING" in types


# ── /stations ─────────────────────────────────────────────────────────────────

class TestStations:
    def test_returns_53_stations(self, client):
        r = client.get("/stations")
        assert r.status_code == 200
        assert r.json()["count"] == 53

    def test_station_schema(self, client):
        r = client.get("/stations")
        st = r.json()["stations"][0]
        required = {
            "police_station", "hotspot_count", "total_violations",
            "avg_risk_score", "max_risk_score", "top_hotspot_id",
            "blind_spot_pct", "junction_hotspot_pct",
        }
        assert required.issubset(st.keys()), f"Missing: {required - st.keys()}"

    def test_blind_spot_pct_range(self, client):
        r = client.get("/stations")
        for st in r.json()["stations"]:
            assert 0 <= st["blind_spot_pct"] <= 100

    def test_city_avg_blind_spot_above_90(self, client):
        r = client.get("/stations")
        avg = sum(s["blind_spot_pct"] for s in r.json()["stations"]) / 53
        assert avg > 90, f"City avg blind_spot_pct = {avg:.1f}% (expected >90%)"

    def test_min_hotspots_filter(self, client):
        r = client.get("/stations?min_hotspots=10")
        assert r.status_code == 200
        for st in r.json()["stations"]:
            assert st["hotspot_count"] >= 10


# ── /junctions ────────────────────────────────────────────────────────────────

class TestJunctions:
    def test_returns_junctions(self, client):
        r = client.get("/junctions")
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 100   # default limit
        assert len(body["junctions"]) == 100

    def test_junction_schema(self, client):
        r = client.get("/junctions?limit=1")
        jn = r.json()["junctions"][0]
        required = {
            "junction_name", "hotspot_count", "total_violations",
            "avg_risk_score", "max_risk_score", "top_hotspot_id", "police_station",
        }
        assert required.issubset(jn.keys()), f"Missing: {required - jn.keys()}"

    def test_sorted_by_violations_desc(self, client):
        r = client.get("/junctions?limit=153")
        counts = [j["total_violations"] for j in r.json()["junctions"]]
        assert counts == sorted(counts, reverse=True)

    def test_top_junction_is_safina_plaza(self, client):
        r = client.get("/junctions?limit=1")
        name = r.json()["junctions"][0]["junction_name"]
        assert "Safina Plaza" in name

    def test_min_violations_filter(self, client):
        r = client.get("/junctions?min_violations=1000&limit=153")
        for jn in r.json()["junctions"]:
            assert jn["total_violations"] >= 1000


# ── /forecast/stations ──────────────────────────────────────────────────────────

class TestStationForecast:
    def test_returns_53_stations(self, client):
        r = client.get("/forecast/stations")
        assert r.status_code == 200
        body = r.json()
        assert body["n_stations"] == 53
        assert len(body["forecast"]) == 53

    def test_response_schema(self, client):
        r = client.get("/forecast/stations")
        body = r.json()
        required = {"predict_week", "model_mae", "precision_at",
                    "median_cv", "hotspot_median_cv", "n_stations", "forecast"}
        assert required.issubset(body.keys()), f"Missing: {required - body.keys()}"

    def test_item_schema(self, client):
        r = client.get("/forecast/stations")
        item = r.json()["forecast"][0]
        required = {"police_station", "predicted_count", "baseline_count",
                    "change_pct", "trend_label"}
        assert required.issubset(item.keys())

    def test_station_grain_less_noisy_than_hotspot(self, client):
        # The core design claim: aggregating to stations roughly halves the
        # week-to-week noise vs per-hotspot. Guard the narrative numerically.
        body = client.get("/forecast/stations").json()
        assert body["median_cv"] < body["hotspot_median_cv"]

    def test_predicted_counts_non_negative(self, client):
        r = client.get("/forecast/stations")
        for it in r.json()["forecast"]:
            assert it["predicted_count"] >= 0

    def test_sorted_by_predicted_desc(self, client):
        r = client.get("/forecast/stations")
        preds = [it["predicted_count"] for it in r.json()["forecast"]]
        assert preds == sorted(preds, reverse=True)

    def test_trend_label_valid_values(self, client):
        r = client.get("/forecast/stations")
        valid = {"rising", "declining", "stable", None}
        for it in r.json()["forecast"]:
            assert it["trend_label"] in valid, it["trend_label"]
