"""Decision-time forecast selection.

All timestamps are UTC. Europe/London is only used to decide which local day a target hour
belongs to and when the D-1 cutoff falls, so DST is handled by zoneinfo, not by us.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

FORECAST_COLUMNS = ["start_time", "publish_time", "forecast_mw"]


def decision_cutoff(delivery_date: date, local_time: time, tz: ZoneInfo) -> datetime:
    """UTC instant of `local_time` on the day before `delivery_date`."""
    day_before = delivery_date - timedelta(days=1)
    return datetime.combine(day_before, local_time, tzinfo=tz).astimezone(ZoneInfo("UTC"))


def delivery_hours(delivery_date: date, tz: ZoneInfo) -> pd.DatetimeIndex:
    """Hourly UTC start times covering the local calendar day (23/24/25 hours across DST)."""
    start = datetime.combine(delivery_date, time.min, tzinfo=tz).astimezone(ZoneInfo("UTC"))
    end = datetime.combine(delivery_date + timedelta(days=1), time.min, tzinfo=tz).astimezone(
        ZoneInfo("UTC")
    )
    return pd.date_range(start, end, freq="h", inclusive="left", tz="UTC")


def local_dates(timestamps: pd.Series, tz: ZoneInfo) -> pd.Series:
    """Local calendar date of each UTC timestamp."""
    return pd.Series(timestamps.dt.tz_convert(tz).dt.date, index=timestamps.index)


def decision_time_forecasts(
    forecasts: pd.DataFrame, local_time: time, tz: ZoneInfo
) -> pd.DataFrame:
    """For each target hour, the latest forecast published at or before its D-1 cutoff.

    Returns one row per usable target hour with columns:
    start_time, delivery_date, cutoff_time, publish_time, forecast_mw, horizon_h.
    Target hours with no forecast published before the cutoff are absent.
    """
    cols = [*FORECAST_COLUMNS, "delivery_date", "cutoff_time", "horizon_h"]
    if forecasts.empty:
        return pd.DataFrame(columns=cols)

    df = forecasts.copy()
    df["delivery_date"] = local_dates(df["start_time"], tz)
    cutoffs = {d: decision_cutoff(d, local_time, tz) for d in df["delivery_date"].unique()}
    df["cutoff_time"] = pd.to_datetime(df["delivery_date"].map(cutoffs), utc=True)

    usable = df[df["publish_time"] <= df["cutoff_time"]]
    latest = usable.sort_values(["start_time", "publish_time"]).groupby("start_time").tail(1)
    latest = latest.assign(horizon_h=horizon_hours(latest))
    return latest[cols].sort_values("start_time").reset_index(drop=True)


def horizon_hours(df: pd.DataFrame) -> pd.Series:
    return (df["start_time"] - df["publish_time"]).dt.total_seconds() / 3600
