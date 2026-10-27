from datetime import date, time

from app.domain.selection import decision_cutoff, decision_time_forecasts, delivery_hours
from tests.conftest import LONDON, forecasts, ts

NINE = time(9, 0)
T = "2026-01-15T12:00:00Z"  # target hour on delivery day 15 Jan -> cutoff 14 Jan 09:00


def pick(rows):
    return decision_time_forecasts(forecasts(rows), NINE, LONDON)


def test_cutoff_is_day_before_local_time_in_utc():
    assert decision_cutoff(date(2026, 1, 15), NINE, LONDON) == ts("2026-01-14T09:00:00Z")


def test_cutoff_respects_bst():
    # 1 Jul: London is UTC+1, so 09:00 local = 08:00 UTC
    assert decision_cutoff(date(2026, 7, 2), NINE, LONDON) == ts("2026-07-01T08:00:00Z")


def test_delivery_hours_dst_lengths():
    assert len(delivery_hours(date(2026, 1, 15), LONDON)) == 24
    assert len(delivery_hours(date(2026, 3, 29), LONDON)) == 23  # spring forward
    assert len(delivery_hours(date(2026, 10, 25), LONDON)) == 25  # fall back


def test_published_exactly_at_cutoff_is_included():
    out = pick([(T, "2026-01-14T09:00:00Z", 100)])
    assert out["forecast_mw"].tolist() == [100]


def test_published_one_second_after_cutoff_is_excluded():
    assert pick([(T, "2026-01-14T09:00:01Z", 100)]).empty


def test_latest_before_cutoff_wins():
    out = pick(
        [
            (T, "2026-01-14T03:00:00Z", 100),
            (T, "2026-01-14T08:30:00Z", 120),
            (T, "2026-01-14T10:00:00Z", 999),
        ]
    )
    assert out["forecast_mw"].tolist() == [120]
    assert out["horizon_h"].iloc[0] == 27.5


def test_negative_horizon_never_selected():
    # Published after the target hour itself, so also after the cutoff.
    assert pick([(T, "2026-01-15T13:00:00Z", 5)]).empty


def test_each_target_hour_selected_independently():
    out = pick(
        [
            ("2026-01-15T00:00:00Z", "2026-01-14T08:00:00Z", 1),
            ("2026-01-15T01:00:00Z", "2026-01-14T08:00:00Z", 2),
            ("2026-01-15T01:00:00Z", "2026-01-14T09:30:00Z", 3),
        ]
    )
    assert out["forecast_mw"].tolist() == [1, 2]


def test_empty_input():
    assert pick([]).empty
