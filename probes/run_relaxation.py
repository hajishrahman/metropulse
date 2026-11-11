"""
Relaxation probe. Tells us WHY the 20-rake 10/10 baseline is INFEASIBLE.

Runs three variants in memory (no disk writes):
    R0: baseline (same as C10_10) — all rules on
    R1: skip R11 (no terminal continuity / no home-lock)
    R2: skip R11 AND ignore initial_location (any rake can do any trip)

Run from project root:
    python probes\run_relaxation.py
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


def solve_variant(use_r11: bool, use_home_lock: bool, time_limit: int = 300):
    data = ProblemData.load()

    model = cp_model.CpModel()
    trips = C.build_trips(data)
    trip_vars = C.create_trip_intervals(model, trips)

    # Use all service rakes (20 rakes after the C-stage regeneration)
    rake_trip = {}
    for _, r in data.service_rakes.iterrows():
        rid = r["rake_id"]
        for t in trips:
            tid = t["trip_id"]
            rake_trip[(rid, tid)] = model.NewBoolVar(f"rake_{rid}_trip_{tid}")

    # Same hard constraints as solve.py
    C.add_r1_service_coverage(model, trip_vars, rake_trip, data)
    C.add_r3_operating_window(model, trip_vars)
    C.add_r4_fleet_availability(model, trip_vars, rake_trip, data)
    C.add_r5_rake_non_overlap(model, trip_vars, rake_trip, data)
    C.add_r6_turnaround(model, trip_vars, rake_trip, data)
    C.add_r10_maintenance_threshold(model, trip_vars, rake_trip, data)

    # R11 (optional)
    if use_r11:
        C.add_r11_terminal_continuity(model, trip_vars, rake_trip, data)

    # Home lock (optional): block first-trip violations of initial_location
    if use_home_lock:
        # Only block the very earliest trip at each terminal from the
        # opposite home (same safe rule used in constraints.py)
        earliest_alva = min(
            (tv["start"] for tv in trip_vars.values() if tv["first_stop"] == "ALVA"),
            default=None,
        )
        earliest_tpht = min(
            (tv["start"] for tv in trip_vars.values() if tv["first_stop"] == "TPHT"),
            default=None,
        )
        for _, r in data.service_rakes.iterrows():
            rid = r["rake_id"]
            home = r["initial_location"]
            for tid, tv in trip_vars.items():
                if home == "ALVA" and earliest_tpht is not None:
                    if tv["first_stop"] == "TPHT" and tv["start"] == earliest_tpht:
                        model.Add(rake_trip[(rid, tid)] == 0)
                if home == "TPHT" and earliest_alva is not None:
                    if tv["first_stop"] == "ALVA" and tv["start"] == earliest_alva:
                        model.Add(rake_trip[(rid, tid)] == 0)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = config.CP_SAT_NUM_WORKERS
    solver.parameters.random_seed = config.CP_SAT_RANDOM_SEED

    t0 = time.time()
    status = solver.Solve(model)
    elapsed = time.time() - t0
    return solver.StatusName(status), elapsed, len(trip_vars)


def main():
    print("=== Relaxation Probe (20 rakes, 10/10) ===\n")
    print(f"{'ID':<4} {'R11':<5} {'HomeLock':<9} {'Status':<12} {'Elapsed':>8} {'Trips':>6}")
    print("-" * 60)

    variants = [
        ("R0", True,  True),   # baseline
        ("R1", False, True),   # no terminal continuity
        ("R2", False, False),  # no continuity + no home lock
    ]

    for pid, r11, home in variants:
        try:
            status, elapsed, n = solve_variant(r11, home)
            print(f"{pid:<4} {str(r11):<5} {str(home):<9} {status:<12} {elapsed:>7.2f}s {n:>6}")
        except Exception as e:
            print(f"{pid:<4} ERROR: {e}")


if __name__ == "__main__":
    main()