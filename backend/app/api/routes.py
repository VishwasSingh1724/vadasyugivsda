from datetime import date, datetime
from typing import Annotated, Any

import pandas as pd
from fastapi import APIRouter, Depends, Query, Request

from app.api import schemas as s
from app.api.auth import require_user
from app.domain import metrics as m
from app.services.analytics import AnalyticsService

router = APIRouter(prefix="/api/v1")  # public: liveness only
data = APIRouter(prefix="/api/v1", dependencies=[Depends(require_user)])  # requires a session

ERRORS: dict[int | str, dict[str, Any]] = {
    404: {"model": s.ErrorResponse},
    422: {"model": s.ErrorResponse},
}
Start = Annotated[date | None, Query(alias="from", description="First delivery date (inclusive)")]
End = Annotated[date | None, Query(alias="to", description="Last delivery date (inclusive)")]


def get_service(request: Request) -> AnalyticsService:
    return request.app.state.service  # type: ignore[no-any-return]


Svc = Annotated[AnalyticsService, Depends(get_service)]


def _metrics(x: m.Metrics) -> s.Metrics:
    return s.Metrics.model_validate(x, from_attributes=True)


def _groups(items: list[tuple[str, m.Metrics]]) -> s.AccuracyGroups:
    return s.AccuracyGroups(groups=[s.GroupMetrics(key=k, metrics=_metrics(v)) for k, v in items])


# ---- health --------------------------------------------------------------------------------
@router.get("/health", response_model=s.Health, tags=["ops"])
async def health() -> s.Health:
    return s.Health(status="ok")


@data.get("/ready", response_model=s.Ready, tags=["ops"])
async def ready(svc: Svc) -> s.Ready:
    return s.Ready(status="ready", data_version=svc.version, rows=svc.manifest["rows"])


# ---- decision view -------------------------------------------------------------------------
@data.get("/delivery-days", response_model=s.DeliveryDays, tags=["forecast"])
async def delivery_days(svc: Svc) -> s.DeliveryDays:
    """Delivery days with data, for the date picker."""
    return s.DeliveryDays(
        timezone=svc.settings.timezone,
        cutoff_local=svc.settings.decision_cutoff_local.strftime("%H:%M"),
        days=[
            s.DeliveryDay(
                date=d, cutoff_time=c.to_pydatetime(), hours_with_forecast=f, hours_with_actual=a
            )
            for d, c, f, a in svc.delivery_days()
        ],
    )


@data.get("/forecast", response_model=s.ForecastDay, responses=ERRORS, tags=["forecast"])
async def forecast(svc: Svc, delivery_date: date) -> s.ForecastDay:
    """Latest forecast available at the D-1 cutoff, with risk band and suggested buffer."""
    day = svc.day_forecast(delivery_date)
    f = day.frame
    fc = f["forecast_mw"]
    points = [s.ForecastPoint.model_validate(r) for r in f.to_dict("records")]
    risk = (
        s.Risk(available=False, reason=day.band_reason)
        if day.band is None
        else s.Risk(
            available=True,
            confidence=day.band.confidence,
            history_days=day.band.history_days,
            suggested_buffer_mw=day.band.buffer_mw,
        )
    )
    return s.ForecastDay(
        delivery_date=delivery_date,
        cutoff_time=day.cutoff_time.to_pydatetime(),
        timezone=svc.settings.timezone,
        points=points,
        summary=s.DaySummary(
            mean_mw=fc.mean(),
            peak_mw=fc.max(),
            trough_mw=fc.min(),
            energy_mwh=fc.sum(),
            hours_missing=int(fc.isna().sum()),
        ),
        risk=risk,
    )


@data.get("/forecast/vintages", response_model=s.Vintages, responses=ERRORS, tags=["forecast"])
async def vintages(svc: Svc, target: datetime) -> s.Vintages:
    """Every revision of the forecast for one target hour, and which predate the cutoff."""
    ts = pd.Timestamp(target)
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
    rows, cutoff, actual = svc.vintages(ts)
    return s.Vintages(
        target=ts.to_pydatetime(),
        cutoff_time=cutoff.to_pydatetime(),
        actual_mw=actual,
        vintages=[s.Vintage.model_validate(r) for r in rows.to_dict("records")],
    )


# ---- accuracy view -------------------------------------------------------------------------
@data.get(
    "/accuracy/summary", response_model=s.AccuracySummary, responses=ERRORS, tags=["accuracy"]
)
async def accuracy_summary(svc: Svc, start: Start = None, end: End = None) -> s.AccuracySummary:
    """Headline metrics of the decision-time forecast over a range of delivery days."""
    return s.AccuracySummary(
        date_from=start,
        date_to=end,
        coverage_pct=svc.coverage_pct(start, end),
        metrics=_metrics(m.summarize(svc.decision_errors(start, end))),
    )


@data.get("/accuracy/daily", response_model=s.AccuracyGroups, responses=ERRORS, tags=["accuracy"])
async def accuracy_daily(svc: Svc, start: Start = None, end: End = None) -> s.AccuracyGroups:
    df = svc.decision_errors(start, end)
    return _groups(m.grouped(df, df["delivery_date"]))


@data.get(
    "/accuracy/by-horizon", response_model=s.AccuracyGroups, responses=ERRORS, tags=["accuracy"]
)
async def accuracy_by_horizon(svc: Svc, start: Start = None, end: End = None) -> s.AccuracyGroups:
    """Error of every published revision, bucketed by how far ahead it was made."""
    df = svc.vintage_errors(start, end)
    return _groups(m.grouped(df, m.horizon_bucket(df["horizon_h"])))


@data.get("/accuracy/by-hour", response_model=s.AccuracyGroups, responses=ERRORS, tags=["accuracy"])
async def accuracy_by_hour(svc: Svc, start: Start = None, end: End = None) -> s.AccuracyGroups:
    df = svc.decision_errors(start, end)
    return _groups(m.grouped(df, m.hour_of_day(df["start_time"], svc.tz)))


@data.get(
    "/accuracy/by-wind-level", response_model=s.AccuracyGroups, responses=ERRORS, tags=["accuracy"]
)
async def accuracy_by_wind(svc: Svc, start: Start = None, end: End = None) -> s.AccuracyGroups:
    df = svc.decision_errors(start, end)
    return _groups(m.grouped(df, m.wind_bucket(df["actual_mw"])))


@data.get("/accuracy/errors", response_model=s.ErrorHistogram, responses=ERRORS, tags=["accuracy"])
async def accuracy_errors(svc: Svc, start: Start = None, end: End = None) -> s.ErrorHistogram:
    """Distribution of signed decision-time errors (forecast - actual)."""
    width = 500
    bins = m.error_histogram(svc.decision_errors(start, end)["error_mw"], width)
    return s.ErrorHistogram(
        bin_width_mw=width,
        bins=[s.HistogramBin(start_mw=a, end_mw=b, count=c) for a, b, c in bins],
    )
