import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(Settings(auth_enabled=False)))  # real January snapshot in data/


def test_health_and_ready(client):
    assert client.get("/api/v1/health").json() == {"status": "ok"}
    r = client.get("/api/v1/ready").json()
    assert r["rows"]["actuals"] == 744


def test_delivery_days_cover_decision_month(client):
    d = client.get("/api/v1/delivery-days").json()
    assert d["days"][0]["date"] == "2026-01-02" and d["days"][-1]["date"] == "2026-02-01"
    assert d["cutoff_local"] == "09:00"


def test_forecast_day_shape_and_cutoff_rule(client):
    r = client.get("/api/v1/forecast", params={"delivery_date": "2026-01-15"}).json()
    assert len(r["points"]) == 24 and r["cutoff_time"] == "2026-01-14T09:00:00Z"
    for p in r["points"]:
        assert p["publish_time"] <= r["cutoff_time"]  # nothing newer than the cutoff leaks in
    assert r["risk"]["available"] and r["risk"]["suggested_buffer_mw"] >= 0


def test_early_day_has_no_band_with_reason(client):
    r = client.get("/api/v1/forecast", params={"delivery_date": "2026-01-03"}).json()
    assert r["risk"]["available"] is False and r["risk"]["reason"]
    assert all(p["band_lower_mw"] is None for p in r["points"])


def test_unknown_day_is_404_envelope(client):
    r = client.get("/api/v1/forecast", params={"delivery_date": "2030-01-01"})
    assert r.status_code == 404
    assert set(r.json()["error"]) == {"code", "message", "request_id"}


def test_bad_date_is_422_envelope(client):
    r = client.get("/api/v1/forecast", params={"delivery_date": "nope"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


def test_inverted_range_is_422(client):
    r = client.get("/api/v1/accuracy/summary", params={"from": "2026-01-10", "to": "2026-01-05"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_range"


def test_summary_metrics_sane(client):
    m = client.get("/api/v1/accuracy/summary").json()["metrics"]
    assert m["n"] > 600 and m["rmse_mw"] >= m["mae_mw"] >= abs(m["bias_mw"])
    assert m["p50_abs_mw"] <= m["p90_abs_mw"] <= m["p99_abs_mw"]


def test_groups_endpoints(client):
    assert len(client.get("/api/v1/accuracy/daily").json()["groups"]) == 31
    assert len(client.get("/api/v1/accuracy/by-hour").json()["groups"]) == 24
    keys = [g["key"] for g in client.get("/api/v1/accuracy/by-horizon").json()["groups"]]
    assert keys[0] == "0-6h"  # ordered by bucket, not alphabetically


def test_vintages_flag_cutoff(client):
    r = client.get("/api/v1/forecast/vintages", params={"target": "2026-01-15T12:00:00Z"}).json()
    assert r["vintages"]
    for v in r["vintages"]:
        assert v["available_at_cutoff"] == (v["publish_time"] <= r["cutoff_time"])


def test_request_id_echo_and_etag_304(client):
    r = client.get("/api/v1/delivery-days", headers={"X-Request-ID": "abc"})
    assert r.headers["x-request-id"] == "abc"
    again = client.get("/api/v1/delivery-days", headers={"If-None-Match": r.headers["etag"]})
    assert again.status_code == 304


def test_coverage_counts_only_delivery_days(client):
    s = client.get("/api/v1/accuracy/summary").json()
    assert s["coverage_pct"] == pytest.approx(100 * s["metrics"]["n"] / (31 * 24), abs=0.5)
