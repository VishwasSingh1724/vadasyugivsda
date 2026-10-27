"""Application service: composes the pure domain functions over a loaded snapshot.

The snapshot is immutable for the life of the process, so everything expensive is computed once
in __init__ and requests only slice. Ceiling: whole-snapshot-in-memory; if data grows beyond a
few months of hourly rows, precompute at ingest time or move behind a database repository.
"""

from dataclasses import dataclass
from datetime import date
from zoneinfo import ZoneInfo

import pandas as pd

from app.core.config import Settings
from app.domain import metrics as m
from app.domain.risk import RiskBand, risk_band
from app.domain.selection import (
    decision_cutoff,
    decision_time_forecasts,
    delivery_hours,
    local_dates,
)
from app.repository import DataRepository


class NotFoundError(Exception):
    """Requested date/target is outside the data coverage."""


class InvalidRangeError(Exception):
    """from > to."""


@dataclass(frozen=True)
class DayForecast:
    delivery_date: date
    cutoff_time: pd.Timestamp
    frame: pd.DataFrame  # one row per hour: forecast_mw, publish_time, horizon_h, actual_mw, band
    band: RiskBand | None
    band_reason: str | None


class AnalyticsService:
    def __init__(self, repo: DataRepository, settings: Settings) -> None:
        self.settings = settings
        self.tz = ZoneInfo(settings.timezone)
        self.manifest = repo.manifest()
        self._forecasts = repo.forecasts()
        self._actuals = repo.actuals()

        self._decision = decision_time_forecasts(
            self._forecasts, settings.decision_cutoff_local, self.tz
        )
        self._decision_errors = m.join_with_actuals(self._decision, self._actuals)
        self._vintage_errors = m.with_all_vintages(self._forecasts, self._actuals, self.tz)
        self.days: list[date] = sorted(set(local_dates(self._actuals["start_time"], self.tz)))

    @property
    def version(self) -> str:
        return str(self.manifest["version"])

    # ---- coverage -------------------------------------------------------------------------
    def delivery_days(self) -> list[tuple[date, pd.Timestamp, int, int]]:
        """(date, cutoff, hours_with_forecast, hours_with_actual) per available delivery day."""
        fc = self._decision.groupby("delivery_date").size()
        ac = self._decision_errors.groupby("delivery_date").size()
        return [
            (
                d,
                pd.Timestamp(self.cutoff(d)),
                int(fc.get(d, 0)),
                int(ac.get(d, 0)),
            )
            for d in self.days
        ]

    def cutoff(self, d: date) -> pd.Timestamp:
        return pd.Timestamp(decision_cutoff(d, self.settings.decision_cutoff_local, self.tz))

    def _require_day(self, d: date) -> None:
        if d not in self.days:
            raise NotFoundError(
                f"No data for delivery date {d}; available {self.days[0]}..{self.days[-1]}"
            )

    # ---- decision view --------------------------------------------------------------------
    def day_forecast(self, d: date) -> DayForecast:
        self._require_day(d)
        hours = pd.DataFrame({"start_time": delivery_hours(d, self.tz)})
        day = self._decision[self._decision["delivery_date"] == d]
        frame = hours.merge(
            day[["start_time", "forecast_mw", "publish_time", "horizon_h"]], how="left"
        ).merge(self._actuals, how="left")

        band = risk_band(
            self._decision_errors,
            d,
            self.settings.band_confidence,
            self.settings.min_history_days,
        )
        reason = None
        if band is None:
            reason = (
                f"Needs {self.settings.min_history_days} complete prior days of forecast "
                "history; not enough yet."
            )
            frame["band_lower_mw"] = frame["band_upper_mw"] = float("nan")
        else:
            frame["band_lower_mw"], frame["band_upper_mw"] = band.bounds(frame["forecast_mw"])
        return DayForecast(d, self.cutoff(d), frame, band, reason)

    def vintages(self, target: pd.Timestamp) -> tuple[pd.DataFrame, pd.Timestamp, float | None]:
        """All revisions of one target hour, flagged by whether they predate the cutoff."""
        rows = self._forecasts[self._forecasts["start_time"] == target]
        if rows.empty:
            raise NotFoundError(f"No forecasts for target {target.isoformat()}")
        cutoff = self.cutoff(local_dates(pd.Series([target]), self.tz).iloc[0])
        rows = rows.sort_values("publish_time").assign(
            available_at_cutoff=lambda d: d["publish_time"] <= cutoff,
            horizon_h=lambda d: (d["start_time"] - d["publish_time"]).dt.total_seconds() / 3600,
        )
        actual = self._actuals.loc[self._actuals["start_time"] == target, "actual_mw"]
        return rows, cutoff, (float(actual.iloc[0]) if len(actual) else None)

    # ---- accuracy view --------------------------------------------------------------------
    def _range(self, df: pd.DataFrame, start: date | None, end: date | None) -> pd.DataFrame:
        if start and end and start > end:
            raise InvalidRangeError("'from' must not be after 'to'")
        if start:
            df = df[df["delivery_date"] >= start]
        if end:
            df = df[df["delivery_date"] <= end]
        return df

    def decision_errors(self, start: date | None, end: date | None) -> pd.DataFrame:
        return self._range(self._decision_errors, start, end)

    def vintage_errors(self, start: date | None, end: date | None) -> pd.DataFrame:
        return self._range(self._vintage_errors, start, end)

    def coverage_pct(self, start: date | None, end: date | None) -> float:
        """Share of in-scope delivery-day hours that have both a decision-time forecast and an actual."""
        scored = len(self.decision_errors(start, end))
        in_scope = self._decision[self._decision["delivery_date"].isin(self.days)]
        total = len(self._range(in_scope, start, end))
        return 100 * scored / total if total else float("nan")
