"""Check that SimPy and the closed-form model return identical results."""

from __future__ import annotations

import numpy as np
import pytest

from src.simulation.reference import RUNNING_SEC, propagate
from src.simulation.schedule_loader import load_schedule_grouped
from src.simulation.simpy_runner import run_simpy


def _assert_match(grouped, delays, sim_out):
    assert sim_out == {
        rake: propagate(trips, delays[rake]) for rake, trips in grouped.items()
    }


# ---------------------------------------------------------------------------
# Hand-built cases
# ---------------------------------------------------------------------------
def test_match_small_hand_built():
    grouped = {
        "R1": [
            {"trip_id": "A", "rake_id": "R1", "direction": "UP",
             "dep_sec": 21600, "arr_sec": 21600 + RUNNING_SEC},
            {"trip_id": "B", "rake_id": "R1", "direction": "DOWN",
             "dep_sec": 24900, "arr_sec": 24900 + RUNNING_SEC},
        ],
        "R2": [
            {"trip_id": "C", "rake_id": "R2", "direction": "UP",
             "dep_sec": 21600, "arr_sec": 21600 + RUNNING_SEC},
        ],
    }
    delays = {"R1": [600, 0], "R2": [120]}
    sim_out = run_simpy(grouped, delays)
    _assert_match(grouped, delays, sim_out)


def test_match_exact_slack_boundary():
    """
    Slack = exactly 0 (next dep - prev arr = 300s turnaround).
    With own delay 0 on both: no propagation.
    With own delay 300 on A: A arrives 300s late, next dep must wait exactly,
    then B propagates. Tests the boundary of 'slack >= delay vs slack < delay'.
    """
    # A: dep 21600, arr 24600. B: dep 24900 (= 24600 + 300 exactly).
    grouped = {
        "R1": [
            {"trip_id": "A", "rake_id": "R1", "direction": "UP",
             "dep_sec": 21600, "arr_sec": 24600},
            {"trip_id": "B", "rake_id": "R1", "direction": "DOWN",
             "dep_sec": 24900, "arr_sec": 24900 + RUNNING_SEC},
        ],
    }
    # Case 1: no delay — no propagation.
    delays0 = {"R1": [0, 0]}
    _assert_match(grouped, delays0, run_simpy(grouped, delays0))

    # Case 2: A has 300s delay. Slack was 0, so propagation fires at B.
    delays300 = {"R1": [300, 0]}
    _assert_match(grouped, delays300, run_simpy(grouped, delays300))


def test_match_three_trip_chain():
    """
    A -> B -> C on one rake. A is delayed. B's own delay is 0.
    Slack is tight so propagation must reach C.
    """
    grouped = {
        "R1": [
            {"trip_id": "A", "rake_id": "R1", "direction": "UP",
             "dep_sec": 21600, "arr_sec": 24600},
            {"trip_id": "B", "rake_id": "R1", "direction": "DOWN",
             "dep_sec": 24900, "arr_sec": 24900 + RUNNING_SEC},
            {"trip_id": "C", "rake_id": "R1", "direction": "UP",
             "dep_sec": 28200, "arr_sec": 28200 + RUNNING_SEC},
        ],
    }
    delays = {"R1": [600, 0, 0]}  # A delayed 600s, others on time
    sim_out = run_simpy(grouped, delays)
    _assert_match(grouped, delays, sim_out)
    # Sanity: C should also be delayed because B propagated.
    assert sim_out["R1"][2]["propagated_delay"] > 0


def test_match_own_delay_larger_than_carried():
    """
    Prev trip on time, next trip has own delay 300s.
    propagated_delay[next] must be 0 (own delay is not propagation).
    dep_delay[next] must be 300.
    """
    grouped = {
        "R1": [
            {"trip_id": "A", "rake_id": "R1", "direction": "UP",
             "dep_sec": 21600, "arr_sec": 24600},
            {"trip_id": "B", "rake_id": "R1", "direction": "DOWN",
             "dep_sec": 28800, "arr_sec": 28800 + RUNNING_SEC},
        ],
    }
    delays = {"R1": [0, 300]}
    sim_out = run_simpy(grouped, delays)
    _assert_match(grouped, delays, sim_out)
    assert sim_out["R1"][1]["propagated_delay"] == 0
    assert sim_out["R1"][1]["dep_delay"] == 300


# ---------------------------------------------------------------------------
# Real schedule, all four std values
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("std", [0.0, 60.0, 120.0, 300.0])
def test_match_real_schedule_all_stds(std: float):
    grouped = load_schedule_grouped()

    rng = np.random.default_rng(42)
    n_total = sum(len(v) for v in grouped.values())
    z_all = rng.standard_normal(n_total)

    all_trip_ids = sorted(t["trip_id"] for trips in grouped.values() for t in trips)
    assert all_trip_ids == [f"T{i:04d}" for i in range(n_total)]
    z_by_trip = dict(zip(all_trip_ids, z_all))

    mean = -48.0
    delays: dict[str, list[int]] = {}
    for rake, trips in grouped.items():
        delays[rake] = [
            round(min(max(mean + std * z_by_trip[t["trip_id"]], 0.0), 300.0))
            for t in trips
        ]

    sim_out = run_simpy(grouped, delays)
    _assert_match(grouped, delays, sim_out)


def test_std_zero_produces_no_delays():
    """Sanity: at std=0 with pre-clip mean -48s, every delay clips to 0."""
    grouped = load_schedule_grouped()
    rng = np.random.default_rng(42)
    n_total = sum(len(v) for v in grouped.values())
    z_all = rng.standard_normal(n_total)
    all_trip_ids = sorted(t["trip_id"] for trips in grouped.values() for t in trips)
    z_by_trip = dict(zip(all_trip_ids, z_all))
    mean, std = -48.0, 0.0
    delays = {
        rake: [
            round(min(max(mean + std * z_by_trip[t["trip_id"]], 0.0), 300.0))
            for t in trips
        ]
        for rake, trips in grouped.items()
    }
    assert all(d == 0 for ds in delays.values() for d in ds)