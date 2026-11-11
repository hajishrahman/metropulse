"""
Probe runner. Builds the CP-SAT model in memory for three configurations,
solves each, prints a table. Does not touch schedule.csv or solution.json.

Probes:
    P1: 8 rakes at ALVA / 10 at TPHT
    P2: 10 rakes at ALVA / 8 at TPHT
    P3: 9 / 9 with turnaround 3 min (instead of 5)

Run from project root:
    python probes\run_probes.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

# make sure project root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ortools.sat.python import cp_model

from solver import config
from solver.models import ProblemData
from solver import constraints as C


def build_and_solve(data, num_rakes_alva, num_rakes_tpht, turnaround_min, time_limit=300):
    """
    Rebuild the model with the requested split and turnaround.
    Returns (status_name, elapsed, num_trips_scheduled_or_None).
    """
    # Override config values in-memory only
    config.INITIAL_RAKES_AT_ALVA = num_rakes_alva
    config.INITIAL_RAKES_AT_TPHT = num_rakes_tpht
    config.TERMINAL_TURNAROUND_MIN = turnaround_min

    # Filter rakes to the requested split (keep only the specified count per home)
    rakes = data.rakes.copy()
    service = rakes[rakes["status"] == "service"].copy()
    alva = service[service["initial_location"] == "ALVA"].head(num_rakes_alva)
    tpht = service[service["initial_location"] == "TPHT"].head(num_rakes_tpht)
    allowed_ids = set(alva["rake_id"]) | set(tpht["rake_id"])
    rakes = rakes[rakes["rake_id"].isin(allowed_ids) | (rakes["status"] != "service")]
    data.rakes = rakes

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
    C.add_r11_terminal_continuity(model, trip_vars, rake_trip, data)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = config.CP_SAT_NUM_WORKERS
    solver.parameters.random_seed = config.CP_SAT_RANDOM_SEED

    t0 = time.time()
    status = solver.Solve(model)
    elapsed = time.time() - t0
    status_name = solver.StatusName(status)

    if status in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        # count how many trips got a rake
        assigned = 0
        for tid in trip_vars:
            for rid in data.service_rakes["rake_id"]:
                if solver.Value(rake_trip[(rid, tid)]) == 1:
                    assigned += 1
                    break
        return status_name, elapsed, assigned
    return status_name, elapsed, None


def main():
    print("=== Probe Runner ===\n")
    print("Loading ProblemData (fresh each probe)...\n")

    probes = [
        ("C10_10", 10, 10, 5),
    
    ]

    print(f"{'ID':<4} {'ALVA':>5} {'TPHT':>5} {'Turn':>5}  {'Status':<12} {'Elapsed':>8}  {'Trips':>6}")
    print("-" * 60)

    for pid, n_alva, n_tpht, turn in probes:
        data = ProblemData.load()  # fresh copy
        try:
            status, elapsed, assigned = build_and_solve(data, n_alva, n_tpht, turn)
            trips_str = str(assigned) if assigned is not None else "-"
            print(f"{pid:<4} {n_alva:>5} {n_tpht:>5} {turn:>5}  {status:<12} {elapsed:>7.2f}s  {trips_str:>6}")
        except Exception as e:
            print(f"{pid:<4} ERROR: {e}")


if __name__ == "__main__":
    main()