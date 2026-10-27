"""Data access seam. Swap `CsvRepository` for a DB-backed class without touching services."""

import json
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

FORECASTS_FILE = "forecasts.csv"
ACTUALS_FILE = "actuals.csv"
MANIFEST_FILE = "manifest.json"


class DataRepository(Protocol):
    def forecasts(self) -> pd.DataFrame:
        """Columns: start_time, publish_time (UTC), forecast_mw."""

    def actuals(self) -> pd.DataFrame:
        """Columns: start_time (UTC, hourly), actual_mw."""

    def manifest(self) -> dict[str, Any]: ...


class CsvRepository:
    def __init__(self, data_dir: Path) -> None:
        self._dir = data_dir

    def forecasts(self) -> pd.DataFrame:
        return pd.read_csv(
            self._dir / FORECASTS_FILE,
            parse_dates=["start_time", "publish_time"],
            date_format="ISO8601",
        ).astype({"forecast_mw": "float64"})

    def actuals(self) -> pd.DataFrame:
        return pd.read_csv(
            self._dir / ACTUALS_FILE, parse_dates=["start_time"], date_format="ISO8601"
        ).astype({"actual_mw": "float64"})

    def manifest(self) -> dict[str, Any]:
        manifest: dict[str, Any] = json.loads((self._dir / MANIFEST_FILE).read_text())
        return manifest
