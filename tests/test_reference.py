"""Tests for the closed-form delay propagation recurrence."""

from __future__ import annotations

import pytest

from src.simulation.reference import (
    RUNNING_SEC,
    TURNAROUND_SEC,
    propagate,
)


def _trip(trip_id, dep_sec, duration_sec=RUNNING_SEC):
    """Build a trip dict with a per-trip duration_sec."""
    return {
        "trip_id": trip_id,
        "dep_sec": dep_sec,
        "arr_sec": dep_sec + duration_sec,
        "duration_sec": duration_sec,
    }


def test_delay_propagates_when_slack_is_insufficient():
    trips = [
        _trip("A", 21_600, duration_sec=3000),
        _trip("B", 24_900, duration_sec=3000),
    ]

    out = propagate(trips, own_delay_sec=[600, 0])

    # A: on-time dep, but own delay 600 -> actual_dep 22200, actual_arr 25200.
    # B: early_dep 24900. propagated_dep = A.actual_arr + turnaround = 25500.
    #    actual_dep = max(24900, 25500) = 25500.
    #    propagated_delay = 25500 - 24900 = 600.
    assert out[0]["actual_dep"] == 21_600 + 600
    assert out[0]["actual_arr"] == 21_600 + 600 + 3000
    assert out[0]["propagated_delay"] == 0
    assert out[1]["actual_dep"] == 25_500
    assert out[1]["propagated_delay"] == 600


def test_slack_absorbs_delay():
    trips = [
        _trip("A", 21_600, duration_sec=3000),
        _trip("B", 28_800, duration_sec=3000),
    ]

    out = propagate(trips, own_delay_sec=[600, 0])

    # A delayed 600s -> arrives 25200. B scheduled 28800.
    # Propagated dep = 25200 + 300 = 25500, well before 28800.
    # So B departs on time, no propagation.
    assert out[1]["actual_dep"] == 28_800
    assert out[1]["propagated_delay"] == 0


def test_first_trip_has_no_propagated_delay():
    trip = _trip("A", 21_600, duration_sec=3000)

    result = propagate([trip], own_delay_sec=[120])[0]

    assert result["propagated_dep"] is None
    assert result["propagated_delay"] == 0
    assert result["actual_dep"] == 21_720
    assert result["actual_arr"] == 21_720 + 3000


def test_invalid_delays_raise():
    trips = [_trip("A", 21_600, duration_sec=3000)]

    with pytest.raises(ValueError, match="length mismatch"):
        propagate(trips, own_delay_sec=[0, 0])

    with pytest.raises(ValueError, match="must be >= 0"):
        propagate(trips, own_delay_sec=[-1])


@pytest.mark.parametrize(
    "kwargs, match",
    [
        ({"turnaround_sec": -1}, "turnaround_sec"),
        ({"running_sec": -1}, "running_sec"),
    ],
)
def test_negative_timing_parameters_raise(kwargs, match):
    trips = [_trip("A", 21_600, duration_sec=3000)]

    with pytest.raises(ValueError, match=match):
        propagate(trips, own_delay_sec=[0], **kwargs)


def test_zero_delays_do_not_propagate():
    trips = [
        _trip("A", 21_600, duration_sec=3000),
        _trip("B", 24_900, duration_sec=3000),
        _trip("C", 28_200, duration_sec=3000),
    ]

    out = propagate(trips, own_delay_sec=[0] * len(trips))

    for row in out:
        assert row["propagated_delay"] == 0
        assert row["dep_delay"] == 0
        assert row["actual_dep"] == row["sched_dep"]