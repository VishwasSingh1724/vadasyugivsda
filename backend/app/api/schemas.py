"""Public response contracts. Field names carry units; timestamps are ISO-8601 UTC."""

import math
from datetime import date, datetime
from typing import Annotated, Any

import pandas as pd
from pydantic import BaseModel, BeforeValidator, Field


def _nan_to_none(v: Any) -> Any:
    """NaN / NaT (pandas missing values) -> None so JSON carries null."""
    if v is pd.NaT or (isinstance(v, float) and math.isnan(v)):
        return None
    return v


OptFloat = Annotated[float | None, BeforeValidator(_nan_to_none)]
OptDatetime = Annotated[datetime | None, BeforeValidator(_nan_to_none)]


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class Metrics(BaseModel):
    n: int = Field(description="Number of scored hours")
    mae_mw: OptFloat
    rmse_mw: OptFloat
    bias_mw: OptFloat = Field(description="Mean of forecast - actual; positive = over-forecast")
    nmae_pct: OptFloat = Field(description="MAE as % of mean actual generation")
    p50_abs_mw: OptFloat
    p90_abs_mw: OptFloat
    p99_abs_mw: OptFloat


class GroupMetrics(BaseModel):
    key: str
    metrics: Metrics


class AccuracySummary(BaseModel):
    date_from: date | None
    date_to: date | None
    coverage_pct: OptFloat = Field(description="% of decision-time forecast hours with an actual")
    metrics: Metrics


class AccuracyGroups(BaseModel):
    groups: list[GroupMetrics]


class HistogramBin(BaseModel):
    start_mw: int
    end_mw: int
    count: int


class ErrorHistogram(BaseModel):
    bin_width_mw: int
    bins: list[HistogramBin]


class DeliveryDay(BaseModel):
    date: date
    cutoff_time: datetime
    hours_with_forecast: int
    hours_with_actual: int


class DeliveryDays(BaseModel):
    timezone: str
    cutoff_local: str
    days: list[DeliveryDay]


class ForecastPoint(BaseModel):
    start_time: datetime
    forecast_mw: OptFloat
    actual_mw: OptFloat
    publish_time: OptDatetime
    horizon_h: OptFloat
    band_lower_mw: OptFloat
    band_upper_mw: OptFloat


class Risk(BaseModel):
    available: bool
    reason: str | None = None
    confidence: float | None = None
    history_days: int | None = None
    suggested_buffer_mw: float | None = Field(
        default=None, description="Extra MW to hold so over-forecast shortfall is covered"
    )


class DaySummary(BaseModel):
    mean_mw: OptFloat
    peak_mw: OptFloat
    trough_mw: OptFloat
    energy_mwh: OptFloat = Field(description="Sum of hourly MW x 1h")
    hours_missing: int = Field(description="Hours with no forecast published before the cutoff")


class ForecastDay(BaseModel):
    delivery_date: date
    cutoff_time: datetime
    timezone: str
    points: list[ForecastPoint]
    summary: DaySummary
    risk: Risk


class Vintage(BaseModel):
    publish_time: datetime
    forecast_mw: float
    horizon_h: float
    available_at_cutoff: bool


class Vintages(BaseModel):
    target: datetime
    cutoff_time: datetime
    actual_mw: float | None
    vintages: list[Vintage]


class Health(BaseModel):
    status: str


class Ready(BaseModel):
    status: str
    data_version: str
    rows: dict[str, int]
