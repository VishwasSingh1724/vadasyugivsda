"""Empirical risk band from historical decision-time forecast errors.

No look-ahead: at the cutoff for day D (D-1 09:00 local) day D-1 is still in progress, so only
delivery days <= D-2 have complete actuals and may inform the band.
"""

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd


@dataclass(frozen=True)
class RiskBand:
    confidence: float
    history_days: int
    lower_offset_mw: float  # low quantile of (forecast - actual); negative = under-forecast
    upper_offset_mw: float  # high quantile of (forecast - actual); positive = over-forecast
    buffer_mw: float  # upper_offset floored at 0: extra MW to cover over-forecast risk

    def bounds(self, forecast_mw: pd.Series) -> tuple[pd.Series, pd.Series]:
        """Plausible actual range: forecast minus the high/low error quantiles, floored at 0."""
        return (
            (forecast_mw - self.upper_offset_mw).clip(lower=0),
            (forecast_mw - self.lower_offset_mw).clip(lower=0),
        )


def usable_history(errors: pd.DataFrame, delivery_date: date) -> pd.DataFrame:
    """Errors from delivery days complete before the cutoff of `delivery_date`."""
    return errors[errors["delivery_date"] <= delivery_date - timedelta(days=2)]


def risk_band(
    errors: pd.DataFrame, delivery_date: date, confidence: float, min_history_days: int
) -> RiskBand | None:
    """Band for `delivery_date`, or None when there are too few prior complete days."""
    hist = usable_history(errors, delivery_date)
    days = hist["delivery_date"].nunique()
    if days < min_history_days:
        return None
    tail = (1 - confidence) / 2
    lo, hi = (float(hist["error_mw"].quantile(q)) for q in (tail, 1 - tail))
    return RiskBand(confidence, days, lo, hi, buffer_mw=max(hi, 0.0))
