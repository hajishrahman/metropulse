"""Tests for the closed-form delay propagation recurrence."""

from __future__ import annotations

import pytest

from src.simulation.reference import RUNNING_SEC, TURNAROUND_SEC, propagate


def test_delay_propagates_when_slack_is_insufficient():
    trips = [
        {"trip_id": "A", "dep_sec": 21_600, "arr_sec": 24_600},
        {"trip_id": "B", "dep_sec": 24_900, "arr_sec": 27_900},
    ]

    out = propagate(trips, own_delay_sec=[600, 0])

    assert [trip["trip_id"] for trip in out] == ["A", "B"]
    assert out[0]["actual_dep"] == 22_200
    assert out[0]["actual_arr"] == out[0]["actual_dep"] + RUNNING_SEC
    assert out[0]["propagated_dep"] is None
    assert out[1]["propagated_dep"] == out[0]["actual_arr"] + TURNAROUND_SEC
    assert out[1]["actual_dep"] == out[1]["propagated_dep"] == 25_500
    assert out[1]["propagated_delay"] == out[1]["dep_delay"] == 600


def test_slack_absorbs_delay():
    trips = [
        {"trip_id": "A", "dep_sec": 21_600, "arr_sec": 24_600},
        {"trip_id": "B", "dep_sec": 28_800, "arr_sec": 31_800},
    ]

    out = propagate(trips, own_delay_sec=[600, 0])

    assert out[1]["propagated_dep"] == out[0]["actual_arr"] + TURNAROUND_SEC
    assert out[1]["propagated_dep"] < out[1]["early_dep"]
    assert out[1]["actual_dep"] == out[1]["early_dep"] == 28_800
    assert out[1]["propagated_delay"] == 0


def test_first_trip_has_no_propagated_delay():
    trip = {"trip_id": "A", "dep_sec": 21_600, "arr_sec": 24_600}

    result = propagate([trip], own_delay_sec=[120])[0]

    assert result["propagated_dep"] is None
    assert result["propagated_delay"] == 0
    assert result["actual_dep"] == 21_720
    assert result["dep_delay"] == 120


@pytest.mark.parametrize(
    ("delays", "message"),
    [([], "length mismatch"), ([-10], "must be >= 0")],
)
def test_invalid_delays_raise(delays, message):
    trip = {"trip_id": "A", "dep_sec": 0, "arr_sec": 3_000}

    with pytest.raises(ValueError, match=message):
        propagate([trip], delays)


@pytest.mark.parametrize(
    ("timing", "message"),
    [({"turnaround_sec": -1}, "turnaround_sec"), ({"running_sec": -1}, "running_sec")],
)
def test_negative_timing_parameters_raise(timing, message):
    trip = {"trip_id": "A", "dep_sec": 0, "arr_sec": 3_000}

    with pytest.raises(ValueError, match=message):
        propagate([trip], [0], **timing)


def test_zero_delays_do_not_propagate():
    trips = [
        {"trip_id": "A", "dep_sec": 21_600, "arr_sec": 24_600},
        {"trip_id": "B", "dep_sec": 24_900, "arr_sec": 27_900},
        {"trip_id": "C", "dep_sec": 28_200, "arr_sec": 31_200},
    ]

    out = propagate(trips, own_delay_sec=[0] * len(trips))

    assert all(result["propagated_delay"] == 0 for result in out)
    assert all(result["actual_dep"] == result["sched_dep"] for result in out)
