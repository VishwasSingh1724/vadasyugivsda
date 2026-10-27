import os

# Importing app.main builds the app; tests exercise auth explicitly via create_app(Settings(...)).
os.environ.setdefault("AUTH_ENABLED", "false")

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

LONDON = ZoneInfo("Europe/London")


def ts(s: str) -> pd.Timestamp:
    return pd.Timestamp(s, tz="UTC")


def forecasts(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    """rows: (start, publish, mw)"""
    return pd.DataFrame(
        {
            "start_time": [ts(a) for a, _, _ in rows],
            "publish_time": [ts(b) for _, b, _ in rows],
            "forecast_mw": [float(c) for _, _, c in rows],
        }
    )


def actuals(rows: list[tuple[str, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        {"start_time": [ts(a) for a, _ in rows], "actual_mw": [float(b) for _, b in rows]}
    )


@pytest.fixture
def utc_now() -> datetime:
    return datetime.now(UTC)
