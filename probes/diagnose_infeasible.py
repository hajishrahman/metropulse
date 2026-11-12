"""
Diagnose WHICH rule group causes 250-trip INFEASIBLE.

Strategy: drop one rule at a time. If dropping that rule gives FEASIBLE
or OPTIMAL, that rule is (one of) the bottleneck(s).

Runs six solves in-memory, no files on disk are changed.

Run from project root:
    python probes\diagnose_infeasible.py
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


def solve_with_drop(data: ProblemData, drop: str, time_limit: int = 60):
    """Drop one explicit rule group; the R10 threshold is also built into rake variables."""
    if drop not in {"none", "R1", "R5", "R6", "R10", "R11", "ALL"}:
        raise ValueError(f"Unknown rule group: {drop}")
    if time_limit <= 0:
        raise ValueError("time_limit must be positive")

    model = cp_model.CpModel()
    trips = C.build_trips(data)
    trip_vars = C.create_trip_intervals(model, trips)
    rake_trip = C.create_rake_assignment_variables(model, trips, data, trip_vars)

    C.add_r3_operating_window(model, trip_vars)
    if drop not in ("R1", "ALL"):
        C.add_r1_service_coverage(model, trip_vars, rake_trip, data)
    if drop not in ("R5", "ALL"):
        C.add_r5_rake_non_overlap(model, trip_vars, rake_trip, data)
    if drop not in ("R6", "ALL"):
        C.add_r6_turnaround(model, trip_vars, rake_trip, data)
    if drop not in ("R10", "ALL"):
        C.add_r10_maintenance_threshold(model, trip_vars, rake_trip, data)
    if drop not in ("R11", "ALL"):
        C.add_r11_terminal_continuity(model, trip_vars, rake_trip, data)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = config.CP_SAT_NUM_WORKERS
    solver.parameters.random_seed = config.CP_SAT_RANDOM_SEED

    t0 = time.perf_counter()
    status = solver.Solve(model)
    elapsed = time.perf_counter() - t0
    return solver.StatusName(status), elapsed


def main():
    print("=== Which rule causes INFEASIBLE? (250 trips) ===\n")
    print(f"{'Drop':<8} {'Status':<12} {'Elapsed':>9}")
    print("-" * 35)

    data = ProblemData.load()
    cases = ["none", "R1", "R5", "R6", "R10", "R11", "ALL"]
    for drop in cases:
        try:
            status, elapsed = solve_with_drop(data, drop)
            print(f"{drop:<8} {status:<12} {elapsed:>8.2f}s")
        except Exception as e:
            print(f"{drop:<8} ERROR: {e}")


if __name__ == "__main__":
    main()
