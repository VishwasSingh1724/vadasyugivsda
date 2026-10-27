"""Thin async client for the Elexon BMRS dataset streams (no auth required)."""

import logging
from collections.abc import Iterator
from datetime import date, datetime, timedelta
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1/datasets"
CHUNK_DAYS = 7

log = logging.getLogger(__name__)
Rows = list[dict[str, Any]]


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return isinstance(exc, httpx.TransportError)


@retry(
    retry=retry_if_exception(_retryable),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=0.5, max=10),
    reraise=True,
)
async def _get(client: httpx.AsyncClient, path: str, params: dict[str, str]) -> Rows:
    resp = await client.get(f"{BASE_URL}/{path}", params=params)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        raise ValueError(f"unexpected payload from {path}: {type(data).__name__}")
    return data


def _chunks(start: date, end: date) -> Iterator[tuple[date, date]]:
    """Inclusive [start, end] split into windows of at most CHUNK_DAYS days."""
    cur = start
    while cur <= end:
        nxt = min(cur + timedelta(days=CHUNK_DAYS - 1), end)
        yield cur, nxt
        cur = nxt + timedelta(days=1)


async def fetch_actuals(client: httpx.AsyncClient, start: date, end: date) -> Rows:
    """FUELHH half-hourly WIND generation for settlement dates [start, end]."""
    rows: Rows = []
    for a, b in _chunks(start, end):
        params = {
            "settlementDateFrom": a.isoformat(),
            "settlementDateTo": b.isoformat(),
            "fuelType": "WIND",
        }
        chunk = await _get(client, "FUELHH/stream", params)
        log.info("fetched actuals", extra={"from": str(a), "to": str(b), "rows": len(chunk)})
        rows += chunk
    return rows


async def fetch_forecasts(client: httpx.AsyncClient, start: date, end: date) -> Rows:
    """WINDFOR forecasts published within [start, end] (UTC days, inclusive)."""
    rows: Rows = []
    for a, b in _chunks(start, end):
        params = {
            "publishDateTimeFrom": datetime.combine(a, datetime.min.time()).isoformat() + "Z",
            "publishDateTimeTo": datetime.combine(
                b + timedelta(days=1), datetime.min.time()
            ).isoformat()
            + "Z",
        }
        chunk = await _get(client, "WINDFOR/stream", params)
        log.info("fetched forecasts", extra={"from": str(a), "to": str(b), "rows": len(chunk)})
        rows += chunk
    return rows
