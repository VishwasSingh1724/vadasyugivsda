"""Validate, de-duplicate and normalise raw Elexon rows into the snapshot schema."""

import logging
from typing import Any

import pandas as pd

log = logging.getLogger(__name__)


def _clean(df: pd.DataFrame, time_cols: list[str], what: str) -> pd.DataFrame:
    """Parse timestamps and generation; drop (and log) malformed or negative rows."""
    before = len(df)
    for c in time_cols:
        df[c] = pd.to_datetime(df[c], utc=True, errors="coerce")
    df["generation"] = pd.to_numeric(df["generation"], errors="coerce")
    df = df.dropna(subset=[*time_cols, "generation"])
    df = df[df["generation"] >= 0]
    if (dropped := before - len(df)) > 0:
        log.warning("dropped malformed rows", extra={"dataset": what, "dropped": dropped})
    return df


def clean_forecasts(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Columns: start_time, publish_time, forecast_mw. One row per (start, publish)."""
    cols = ["start_time", "publish_time", "forecast_mw"]
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows).rename(
        columns={"startTime": "start_time", "publishTime": "publish_time"}
    )
    df = _clean(df, ["start_time", "publish_time"], "WINDFOR")
    df = df.rename(columns={"generation": "forecast_mw"})[cols]
    n = len(df)
    df = df.drop_duplicates(["start_time", "publish_time"], keep="last")
    if n - len(df):
        log.warning("dropped duplicate forecasts", extra={"dropped": n - len(df)})
    return df.sort_values(["start_time", "publish_time"]).reset_index(drop=True)


def hourly_actuals(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Half-hourly FUELHH -> hourly mean MW. Columns: start_time, actual_mw.

    Hours lacking both half-hours are dropped (a one-sided mean would bias the comparison).
    """
    cols = ["start_time", "actual_mw"]
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows).rename(columns={"startTime": "start_time"})
    df = _clean(df, ["start_time"], "FUELHH")
    # Same half-hour can be re-published; the latest publication wins.
    if "publishTime" in df:
        df = df.sort_values("publishTime")
    df = df.drop_duplicates("start_time", keep="last")
    df["hour"] = df["start_time"].dt.floor("h")
    agg = df.groupby("hour")["generation"].agg(actual_mw="mean", n="count").reset_index()
    partial = int((agg["n"] < 2).sum())
    if partial:
        log.warning("dropped partial hours", extra={"hours": partial})
    agg = agg[agg["n"] == 2].rename(columns={"hour": "start_time"})
    return agg[cols].sort_values("start_time").reset_index(drop=True)
