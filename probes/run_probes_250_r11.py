"""
Surgical R11 probe for the 250-trip case.

Tests which part of R11 breaks 250 trips:
    D: first-trip home rule OFF, pair rule ON
    E: first-trip home rule ON,  pair rule OFF
    F: both OFF (confirmation)

Read-only. Uses actual solver/constraints.py.

Run from project root:
    python probes\run_probes_250_r11.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ortools.sat.python import cp_model

from solver import config
from solver.models import ProblemData
from solver import constraints as C


def add_r11_pair_rule_only(model, trip_vars, rake_trip, data):
    """The pair rule from add_r11_terminal_continuity, without the first-trip rule."""
    turnaround = config.TERMINAL_TURNAROUND_MIN * 60
    rakes = list(data.service_rakes["rake_id"])
    tids = list(trip_vars.keys())
    count = 0
    for i in range(len(tids)):
        a = trip_vars[tids[i]]
        for j in range(i + 1, len(tids)):
            b = trip_vars[tids[j]]
            a_to_b_possible = (a["last_stop"] == b["first_stop"])
            b_to_a_possible = (b["last_stop"] == a["first_stop"])
            if a_to_b_possible or b_to_a_possible:
                continue
            a_b_impossible = b["start"] < a["end"] + turnaround
            b_a_impossible = a["start"] < b["end"] + turnaround
            if a_b_impossible and b_a_impossible:
                continue
            count += 1
            for rid in rakes:
                model.Add(rake_trip[(rid, tids[i])] + rake_trip[(rid, tids[j])] <= 1)
    print(f"[r11-pair] {count} pairs added")


def add_r11_first_trip_rule_only(model, trip_vars, rake_trip, data):
    """The first-trip home rule from add_r11_terminal_continuity, without the pair rule."""
    turnaround = config.TERMINAL_TURNAROUND_MIN * 60
    for _, r in data.service_rakes.iterrows():
        rid = r["rake_id"]
        home = r["initial_location"]
        for tid, tv in trip_vars.items():
            if tv["first_stop"] == home:
                continue
            preds = [
                rake_trip[(rid, p)]
                for p, pv in trip_vars.items()
                if pv["last_stop"] == tv["first_stop"]
                and pv["arr_sec"] + turnaround <= tv["start"]
            ]
            if not preds:
                model.Add(rake_trip[(rid, tid)] == 0)
            else:
                model.Add(rake_trip[(rid, tid)] <= sum(preds))


def build_and_solve(first_rule: bool, pair_rule: bool, time_limit: int = 300):
    data = ProblemData.load()
    model = cp_model.CpModel()
    trips = C.build_trips(data)
    trip_vars = C.create_trip_intervals(model, trips)
    rake_trip = C.create_rake_assignment_variables(model, trips, data, trip_vars)

    C.add_r1_service_coverage(model, trip_vars, rake_trip, data)
    C.add_r3_operating_window(model, trip_vars)
    C.add_r4_fleet_availability(model, trip_vars, rake_trip, data)
    C.add_r5_rake_non_overlap(model, trip_vars, rake_trip, data)
    C.add_r6_turnaround(model, trip_vars, rake_trip, data)
    C.add_r10_maintenance_threshold(model, trip_vars, rake_trip, data)

    if first_rule:
        add_r11_first_trip_rule_only(model, trip_vars, rake_trip, data)
    if pair_rule:
        add_r11_pair_rule_only(model, trip_vars, rake_trip, data)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = config.CP_SAT_NUM_WORKERS
    solver.parameters.random_seed = config.CP_SAT_RANDOM_SEED

    t0 = time.time()
    status = solver.Solve(model)
    elapsed = time.time() - t0
    return solver.StatusName(status), elapsed, len(trip_vars)


def main():
    print("=== Surgical R11 probe (250 trips) ===\n")
    print(f"{'ID':<4} {'FirstRule':>10} {'PairRule':>10} {'Status':<12} {'Elapsed':>8}")
    print("-" * 55)

    variants = [
        ("D", False, True),   # first-trip rule off, pair rule on
        ("E", True,  False),  # first-trip rule on,  pair rule off
        ("F", False, False),  # both off
    ]
    for pid, first, pair in variants:
        try:
            status, elapsed, n = build_and_solve(first, pair)
            print(f"{pid:<4} {str(first):>10} {str(pair):>10} {status:<12} {elapsed:>7.2f}s")
        except Exception as e:
            print(f"{pid:<4} ERROR: {e}")


if __name__ == "__main__":
    main()