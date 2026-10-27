from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.domain import metrics as m
from app.domain.risk import risk_band
from tests.conftest import actuals, forecasts


def joined(fc, act):
    return m.join_with_actuals(forecasts(fc), actuals(act))


def test_perfect_forecast_is_all_zero():
    s = m.summarize(
        joined(
            [("2026-01-02T00:00:00Z", "2026-01-01T00:00:00Z", 100)], [("2026-01-02T00:00:00Z", 100)]
        )
    )
    assert (s.mae_mw, s.rmse_mw, s.bias_mw) == (0, 0, 0)


def test_constant_over_forecast():
    hrs = [f"2026-01-02T0{i}:00:00Z" for i in range(4)]
    df = joined([(h, "2026-01-01T00:00:00Z", 110) for h in hrs], [(h, 100) for h in hrs])
    s = m.summarize(df)
    assert (s.bias_mw, s.mae_mw, s.rmse_mw, s.n) == (10, 10, 10, 4)
    assert s.nmae_pct == pytest.approx(10.0)


def test_bias_and_mae_differ_when_errors_cancel():
    hrs = ["2026-01-02T00:00:00Z", "2026-01-02T01:00:00Z"]
    df = joined(
        [(hrs[0], "2026-01-01T00:00:00Z", 110), (hrs[1], "2026-01-01T00:00:00Z", 90)],
        [(h, 100) for h in hrs],
    )
    s = m.summarize(df)
    assert s.bias_mw == 0 and s.mae_mw == 10


def test_hour_without_actual_is_not_scored():
    df = joined(
        [
            ("2026-01-02T00:00:00Z", "2026-01-01T00:00:00Z", 1),
            ("2026-01-02T01:00:00Z", "2026-01-01T00:00:00Z", 1),
        ],
        [("2026-01-02T00:00:00Z", 1)],
    )
    assert len(df) == 1


def test_empty_summary_is_nan_not_crash():
    s = m.summarize(pd.DataFrame(columns=["error_mw", "abs_error_mw", "actual_mw"]))
    assert s.n == 0 and np.isnan(s.mae_mw)


def test_horizon_bucket_edges():
    b = m.horizon_bucket(pd.Series([0, 5.9, 6, 47.9, 48, 70]))
    assert b.astype(str).tolist() == ["0-6h", "0-6h", "6-12h", "36-48h", "48h+", "48h+"]


def test_histogram_counts_everything():
    e = pd.Series([-600, -10, 0, 10, 499, 1200.0])
    bins = m.error_histogram(e, 500)
    assert sum(c for _, _, c in bins) == len(e)


# ---- risk band ----
def history(days: int, err=100.0):
    start = date(2026, 1, 2)
    rows = [(start + timedelta(days=i), err + k) for i in range(days) for k in range(4)]
    return pd.DataFrame(rows, columns=["delivery_date", "error_mw"])


def test_band_hidden_with_too_little_history():
    # delivery day 5 Jan -> usable days <= 3 Jan -> 2 days (2,3 Jan) < 3
    assert risk_band(history(10), date(2026, 1, 5), 0.8, 3) is None


def test_band_available_with_enough_history():
    band = risk_band(history(10), date(2026, 1, 6), 0.8, 3)  # usable: 2,3,4 Jan
    assert band is not None and band.history_days == 3 and band.buffer_mw > 0


def test_band_never_uses_cutoff_day_or_later_errors():
    """Leakage guard: poisoning errors on D-1, D and later must not move the band."""
    d = date(2026, 1, 10)
    clean = history(8)  # 2..9 Jan
    poisoned = clean.copy()
    poisoned.loc[poisoned["delivery_date"] >= date(2026, 1, 9), "error_mw"] = 1e9
    a = risk_band(clean, d, 0.8, 3)
    b = risk_band(poisoned, d, 0.8, 3)
    assert a == b


def test_buffer_floored_at_zero_when_always_under_forecast():
    band = risk_band(history(10, err=-500.0), date(2026, 1, 12), 0.8, 3)
    assert band is not None and band.buffer_mw == 0


def test_bounds_floor_at_zero():
    band = risk_band(history(10, err=5000.0), date(2026, 1, 12), 0.8, 3)
    lo, hi = band.bounds(pd.Series([100.0]))
    assert lo.iloc[0] == 0 and hi.iloc[0] == 0
