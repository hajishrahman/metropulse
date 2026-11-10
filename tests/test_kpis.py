"""Unit tests for kpis.py — hand-built data, no SimPy, no file I/O."""

from __future__ import annotations

import pytest

from src.simulation.kpis import (
    compute_headway_violations,
    compute_kpis,
    compute_on_time,
    compute_propagation,
    compute_total_propagated_delay,
)
from src.simulation.reference import RUNNING_SEC, TURNAROUND_SEC


def _trip(tid: str, rake: str, direction: str, dep: int) -> dict:
    return {
        "trip_id": tid,
        "rake_id": rake,
        "direction": direction,
        "dep_sec": dep,
        "arr_sec": dep + RUNNING_SEC,
    }


def _result(tid: str, sched_dep: int, own: int, prev_arr: int | None = None) -> dict:
    """Build a fake SimPy result dict consistent with the reference recurrence."""
    early_dep = sched_dep + own
    propagated_dep = None if prev_arr is None else prev_arr + TURNAROUND_SEC
    actual_dep = (
        early_dep if propagated_dep is None else max(early_dep, propagated_dep)
    )
    actual_arr = actual_dep + RUNNING_SEC
    propagated_delay = (
        0 if propagated_dep is None else max(0, propagated_dep - early_dep)
    )
    return {
        "trip_id": tid,
        "sched_dep": sched_dep,
        "sched_arr": sched_dep + RUNNING_SEC,
        "own_delay": own,
        "early_dep": early_dep,
        "propagated_dep": propagated_dep,
        "actual_dep": actual_dep,
        "actual_arr": actual_arr,
        "propagated_delay": propagated_delay,
        "dep_delay": actual_dep - sched_dep,
    }


# ---------------------------------------------------------------------------
# On-time boundaries
# ---------------------------------------------------------------------------
def test_on_time_exactly_300s():
    grouped = {"R1": [_trip("A", "R1", "UP", 21600), _trip("B", "R1", "DOWN", 24900)]}
    results = {"R1": [
        _result("A", 21600, own=300),
        _result("B", 24900, own=0, prev_arr=21600 + 300 + RUNNING_SEC),
    ]}
    k = compute_on_time(results, grouped, 300)
    assert k["on_time_250_count"] == 2
    assert k["on_time_232_eligible_pct"] == 100.0
    assert k["trips_total"] == 2
    assert k["trips_eligible"] == 1


def test_on_time_61s_is_late_at_60s():
    grouped = {"R1": [_trip("A", "R1", "UP", 21600)]}
    results = {"R1": [_result("A", 21600, own=61)]}
    k = compute_on_time(results, grouped, 60)
    assert k["on_time_250_count"] == 0


# ---------------------------------------------------------------------------
# Propagation
# ---------------------------------------------------------------------------
def test_propagation_zero_when_no_delays():
    grouped = {"R1": [_trip("A", "R1", "UP", 21600), _trip("B", "R1", "DOWN", 24900)]}
    results = {"R1": [
        _result("A", 21600, own=0),
        _result("B", 24900, own=0, prev_arr=21600 + RUNNING_SEC),
    ]}
    k = compute_propagation(results, grouped)
    assert k["propagation_pct"] == 0.0
    assert k["trips_with_propagation"] == 0
    assert k["trips_eligible"] == 1


def test_propagation_one_trip():
    # A's 300s delay propagates to B when there is no scheduled slack.
    grouped = {"R1": [_trip("A", "R1", "UP", 21600), _trip("B", "R1", "DOWN", 24900)]}
    results = {"R1": [
        _result("A", 21600, own=300),
        _result("B", 24900, own=0, prev_arr=21600 + 300 + RUNNING_SEC),
    ]}
    k = compute_propagation(results, grouped)
    assert k["trips_eligible"] == 1
    assert k["trips_with_propagation"] == 1
    assert k["propagation_pct"] == 100.0


def test_propagation_zero_eligible_no_division_by_zero():
    # One rake, one trip: eligible = 0.
    grouped = {"R1": [_trip("A", "R1", "UP", 21600)]}
    results = {"R1": [_result("A", 21600, own=0)]}
    k = compute_propagation(results, grouped)
    assert k["trips_eligible"] == 0
    assert k["trips_with_propagation"] == 0
    assert k["propagation_pct"] == 0.0


def test_eligibility_uses_first_scheduled_trip_when_results_are_reordered():
    grouped = {
        "R1": [
            _trip("A", "R1", "UP", 21600),
            _trip("B", "R1", "DOWN", 24900),
            _trip("C", "R1", "UP", 28400),
        ]
    }
    a = _result("A", 21600, own=300)
    b = _result("B", 24900, own=0, prev_arr=a["actual_arr"])
    c = _result("C", 28400, own=0, prev_arr=b["actual_arr"])
    results = {"R1": [c, b, a]}

    on_time = compute_on_time(results, grouped, tolerance_sec=150)
    propagation = compute_propagation(results, grouped)

    assert on_time["on_time_232_eligible_count"] == 1
    assert on_time["on_time_232_eligible_pct"] == 50.0
    assert propagation["trips_with_propagation"] == 2
    assert propagation["propagation_pct"] == 100.0


# ---------------------------------------------------------------------------
# Total propagated delay
# ---------------------------------------------------------------------------
def test_total_propagated_delay_sum():
    results = {"R1": [
        {"propagated_delay": 100},
        {"propagated_delay": 250},
    ]}
    k = compute_total_propagated_delay(results)
    assert k["total_propagated_delay_sec"] == 350
    assert k["total_propagated_delay_min"] == round(350 / 60.0, 1)
    assert k["max_single_propagated_delay_sec"] == 250
    assert k["max_single_propagated_delay_min"] == round(250 / 60.0, 1)


# ---------------------------------------------------------------------------
# Headway boundaries
# ---------------------------------------------------------------------------
def test_headway_exactly_120s_not_a_violation():
    grouped = {
        "R1": [_trip("A", "R1", "UP", 21600)],
        "R2": [_trip("B", "R2", "UP", 21600 + 120)],
    }
    results = {
        "R1": [_result("A", 21600, own=0)],
        "R2": [_result("B", 21600 + 120, own=0)],
    }
    k = compute_headway_violations(results, grouped, threshold_sec=120)
    assert k["actual_violations"] == 0
    assert k["actual_min_gap_sec"] == 120


def test_headway_119s_is_violation():
    grouped = {
        "R1": [_trip("A", "R1", "UP", 21600)],
        "R2": [_trip("B", "R2", "UP", 21600 + 119)],
    }
    results = {
        "R1": [_result("A", 21600, own=0)],
        "R2": [_result("B", 21600 + 119, own=0)],
    }
    k = compute_headway_violations(results, grouped, threshold_sec=120)
    assert k["actual_violations"] == 1
    assert k["actual_min_gap_sec"] == 119


def test_headway_reorder_after_delays():
    # A's delay reverses the order and creates an actual violation despite a safe scheduled gap.
    grouped = {
        "R1": [_trip("A", "R1", "UP", 21600)],
        "R2": [_trip("B", "R2", "UP", 21800)],
    }
    results = {
        "R1": [_result("A", 21600, own=300)],
        "R2": [_result("B", 21800, own=0)],
    }
    k = compute_headway_violations(results, grouped, threshold_sec=120)
    assert k["actual_violations"] == 1
    assert k["actual_min_gap_sec"] == 100
    assert k["scheduled_violations"] == 0
    assert k["scheduled_min_gap_sec"] == 200


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------
def test_rake_set_mismatch_raises():
    grouped = {"R1": [_trip("A", "R1", "UP", 21600)]}
    results = {"R2": [_result("A", 21600, own=0)]}
    with pytest.raises(ValueError, match="rake set mismatch"):
        compute_kpis(results, grouped)


def test_trip_id_mismatch_raises():
    grouped = {"R1": [_trip("A", "R1", "UP", 21600)]}
    results = {"R1": [_result("Z", 21600, own=0)]}
    with pytest.raises(ValueError, match="trip_id mismatch"):
        compute_kpis(results, grouped)


def test_result_count_mismatch_raises():
    grouped = {"R1": [_trip("A", "R1", "UP", 21600), _trip("B", "R1", "DOWN", 24900)]}
    results = {"R1": [_result("A", 21600, own=0)]}
    with pytest.raises(ValueError, match="trips vs"):
        compute_kpis(results, grouped)


def test_negative_tolerance_and_threshold_raise():
    with pytest.raises(ValueError, match="tolerance_sec"):
        compute_on_time({}, {}, -1)
    with pytest.raises(ValueError, match="threshold_sec"):
        compute_headway_violations({}, {}, -1)
