"""Forecast-accuracy metrics.

Units are MW. Sign convention: error = forecast - actual, so positive = over-forecast
(wind fell short of the plan -> shortfall to cover).
"""

from dataclasses import dataclass
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from app.domain.selection import horizon_hours, local_dates

HORIZON_EDGES = [0, 6, 12, 24, 36, 48, np.inf]
HORIZON_LABELS = ["0-6h", "6-12h", "12-24h", "24-36h", "36-48h", "48h+"]
WIND_EDGES = [0, 5_000, 10_000, 15_000, 20_000, np.inf]
WIND_LABELS = ["<5 GW", "5-10 GW", "10-15 GW", "15-20 GW", "20+ GW"]


@dataclass(frozen=True)
class Metrics:
    n: int
    mae_mw: float
    rmse_mw: float
    bias_mw: float
    nmae_pct: float
    p50_abs_mw: float
    p90_abs_mw: float
    p99_abs_mw: float


def join_with_actuals(forecasts: pd.DataFrame, actuals: pd.DataFrame) -> pd.DataFrame:
    """Inner-join forecast rows to actuals on target hour and add error columns."""
    df = forecasts.merge(actuals[["start_time", "actual_mw"]], on="start_time", how="inner")
    df["error_mw"] = df["forecast_mw"] - df["actual_mw"]
    df["abs_error_mw"] = df["error_mw"].abs()
    return df


def with_all_vintages(forecasts: pd.DataFrame, actuals: pd.DataFrame, tz: ZoneInfo) -> pd.DataFrame:
    """Every forecast revision (not just the decision-time one) joined to actuals.

    Rows published after their target hour (negative horizon) are dropped: not a forecast.
    """
    df = join_with_actuals(forecasts, actuals)
    df["horizon_h"] = horizon_hours(df)
    df = df[df["horizon_h"] >= 0].copy()
    df["delivery_date"] = local_dates(df["start_time"], tz)
    return df


def summarize(df: pd.DataFrame) -> Metrics:
    """Headline metrics for a frame with `error_mw`, `abs_error_mw`, `actual_mw`."""
    n = len(df)
    if n == 0:
        nan = float("nan")
        return Metrics(0, nan, nan, nan, nan, nan, nan, nan)
    err, abs_err = df["error_mw"], df["abs_error_mw"]
    mae = float(abs_err.mean())
    mean_actual = float(df["actual_mw"].mean())
    p50, p90, p99 = (float(abs_err.quantile(q)) for q in (0.5, 0.9, 0.99))
    return Metrics(
        n=n,
        mae_mw=mae,
        rmse_mw=float(np.sqrt((err**2).mean())),
        bias_mw=float(err.mean()),
        nmae_pct=100 * mae / mean_actual if mean_actual > 0 else float("nan"),
        p50_abs_mw=p50,
        p90_abs_mw=p90,
        p99_abs_mw=p99,
    )


def grouped(df: pd.DataFrame, keys: pd.Series) -> list[tuple[str, Metrics]]:
    """Metrics per distinct key, in key order (categorical order for buckets)."""
    return [(str(k), summarize(g)) for k, g in df.groupby(keys, observed=True, sort=True)]


def horizon_bucket(horizon_h: pd.Series) -> pd.Series:
    return pd.cut(horizon_h, HORIZON_EDGES, labels=HORIZON_LABELS, right=False)


def wind_bucket(actual_mw: pd.Series) -> pd.Series:
    return pd.cut(actual_mw, WIND_EDGES, labels=WIND_LABELS, right=False)


def hour_of_day(start_time: pd.Series, tz: ZoneInfo) -> pd.Series:
    return pd.Series(start_time.dt.tz_convert(tz).dt.hour, index=start_time.index)


def error_histogram(error_mw: pd.Series, bin_mw: int = 500) -> list[tuple[int, int, int]]:
    """(bin_start, bin_end, count) over a fixed-width grid containing all errors."""
    if error_mw.empty:
        return []
    lo = int(np.floor(error_mw.min() / bin_mw)) * bin_mw
    hi = int(np.ceil((error_mw.max() + 1e-9) / bin_mw)) * bin_mw
    edges = np.arange(lo, hi + bin_mw, bin_mw)
    counts, _ = np.histogram(error_mw, bins=edges)
    return [(int(a), int(a + bin_mw), int(c)) for a, c in zip(edges[:-1], counts, strict=True)]
