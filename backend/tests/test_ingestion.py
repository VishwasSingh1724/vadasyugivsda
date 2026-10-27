import json

import httpx
import pytest
import respx

from app.ingestion import elexon
from app.ingestion.pipeline import write_snapshot
from app.ingestion.transform import clean_forecasts, hourly_actuals


def fh(start, mw, pub="2026-01-02T00:00:00Z"):
    return {"startTime": start, "generation": mw, "publishTime": pub, "fuelType": "WIND"}


def test_hourly_actuals_means_two_half_hours():
    df = hourly_actuals([fh("2026-01-02T00:00:00Z", 100), fh("2026-01-02T00:30:00Z", 200)])
    assert df["actual_mw"].tolist() == [150]


def test_partial_hour_dropped():
    assert hourly_actuals([fh("2026-01-02T00:00:00Z", 100)]).empty


def test_duplicate_half_hour_latest_publication_wins():
    df = hourly_actuals(
        [
            fh("2026-01-02T00:00:00Z", 100, "2026-01-02T00:30:00Z"),
            fh("2026-01-02T00:00:00Z", 300, "2026-01-02T01:00:00Z"),
            fh("2026-01-02T00:30:00Z", 100),
        ]
    )
    assert df["actual_mw"].tolist() == [200]


def test_malformed_rows_dropped():
    df = hourly_actuals(
        [fh("2026-01-02T00:00:00Z", "n/a"), fh("bad", 1), fh("2026-01-02T00:00:00Z", -5)]
    )
    assert df.empty


def test_forecast_dedup_and_negative_horizon_preserved():
    rows = [
        {
            "startTime": "2026-01-02T00:00:00Z",
            "publishTime": "2026-01-02T05:00:00Z",
            "generation": 1,
        },
        {
            "startTime": "2026-01-02T00:00:00Z",
            "publishTime": "2026-01-02T05:00:00Z",
            "generation": 2,
        },
    ]
    df = clean_forecasts(rows)
    assert (
        len(df) == 1 and df["forecast_mw"].iloc[0] == 2
    )  # last wins; row kept despite horizon < 0


def test_empty_inputs():
    assert clean_forecasts([]).empty and hourly_actuals([]).empty


def test_snapshot_is_idempotent_and_atomic(tmp_path):
    f = clean_forecasts(
        [
            {
                "startTime": "2026-01-02T00:00:00Z",
                "publishTime": "2026-01-01T00:00:00Z",
                "generation": 1,
            }
        ]
    )
    a = hourly_actuals([fh("2026-01-02T00:00:00Z", 1), fh("2026-01-02T00:30:00Z", 1)])
    m1 = write_snapshot(tmp_path, f, a)
    m2 = write_snapshot(tmp_path, f, a)
    assert (
        m1 == m2
        and json.loads((tmp_path / "manifest.json").read_text())["version"] == m1["version"]
    )
    assert not list(tmp_path.glob("*.tmp"))


@respx.mock
async def test_retries_on_503_then_succeeds(monkeypatch):
    monkeypatch.setattr(elexon._get.retry, "wait", lambda *_: 0)  # no sleeping in tests
    route = respx.get(url__startswith=elexon.BASE_URL).mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json=[{"a": 1}])]
    )
    async with httpx.AsyncClient() as c:
        rows = await elexon._get(c, "FUELHH/stream", {})
    assert rows == [{"a": 1}] and route.call_count == 2


@respx.mock
async def test_client_error_not_retried():
    route = respx.get(url__startswith=elexon.BASE_URL).mock(return_value=httpx.Response(400))
    async with httpx.AsyncClient() as c:
        with pytest.raises(httpx.HTTPStatusError):
            await elexon._get(c, "FUELHH/stream", {})
    assert route.call_count == 1


def test_chunks_cover_range_without_overlap():
    from datetime import date

    chunks = list(elexon._chunks(date(2026, 1, 1), date(2026, 1, 20)))
    assert chunks[0][0] == date(2026, 1, 1) and chunks[-1][1] == date(2026, 1, 20)
    assert all(b >= a for a, b in chunks) and len(chunks) == 3
