"""
Probe 250-trip case to find which rule causes INFEASIBLE.

Four variants, all in-memory, no files written:
    Q0: all rules on            (expect INFEASIBLE — matches current solve)
    Q1: deadhead = 0 min        (instead of 15)
    Q2: home-lock OFF           (rakes can start at any terminal)
    Q3: 2 rakes start at MUTTOM (instead of only ALVA/TPHT)

Run from project root:
    python probes\run_probes_250.py
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


def solve_variant(deadhead_min: int, use_home_lock: bool,
                  rakes_at_muttom: int, time_limit: int = 300):
    data = ProblemData.load()

    # Build a custom rake set for this probe:
    # - service rakes as configured
    # - if rakes_at_muttom > 0, move that many "TPHT" rakes to MUTTOM in memory
    rakes = data.rakes.copy()
    if rakes_at_muttom > 0:
        tpht_rakes = rakes[(rakes["status"] == "service")
                           & (rakes["initial_location"] == "TPHT")].index
        move = tpht_rakes[:rakes_at_muttom]
        rakes.loc[move, "initial_location"] = "MUTTOM"
    data.rakes = rakes

    model = cp_model.CpModel()
    trips = C.build_trips(data)
    trip_vars = C.create_trip_intervals(model, trips)

    # Create rake_trip without home-lock (we will apply home-lock manually)
    rake_trip = {}
    for _, r in data.service_rakes.iterrows():
        rid = r["rake_id"]
        for t in trips:
            tid = t["trip_id"]
            rake_trip[(rid, tid)] = model.NewBoolVar(f"rake_{rid}_trip_{tid}")

    # Home-lock (optional): block the earliest trip of each other-terminal
    if use_home_lock:
        earliest_alva = min(
            (tv["start"] for tv in trip_vars.values() if tv["first_stop"] == "ALVA"),
            default=None,
        )
        earliest_tpht = min(
            (tv["start"] for tv in trip_vars.values() if tv["first_stop"] == "TPHT"),
            default=None,
        )
        earliest_mutt = min(
            (tv["start"] for tv in trip_vars.values() if tv["first_stop"] == "MUTT"),
            default=None,
        )
        for _, r in data.service_rakes.iterrows():
            rid = r["rake_id"]
            home = r["initial_location"]
            for tid, tv in trip_vars.items():
                if home == "ALVA":
                    if earliest_tpht is not None and tv["first_stop"] == "TPHT" and tv["start"] == earliest_tpht:
                        model.Add(rake_trip[(rid, tid)] == 0)
                    if earliest_mutt is not None and tv["first_stop"] == "MUTT" and tv["start"] == earliest_mutt:
                        model.Add(rake_trip[(rid, tid)] == 0)
                if home == "TPHT":
                    if earliest_alva is not None and tv["first_stop"] == "ALVA" and tv["start"] == earliest_alva:
                        model.Add(rake_trip[(rid, tid)] == 0)
                    if earliest_mutt is not None and tv["first_stop"] == "MUTT" and tv["start"] == earliest_mutt:
                        model.Add(rake_trip[(rid, tid)] == 0)
                if home == "MUTTOM":
                    if earliest_alva is not None and tv["first_stop"] == "ALVA" and tv["start"] == earliest_alva:
                        model.Add(rake_trip[(rid, tid)] == 0)
                    if earliest_tpht is not None and tv["first_stop"] == "TPHT" and tv["start"] == earliest_tpht:
                        model.Add(rake_trip[(rid, tid)] == 0)

    # Temporarily override deadhead in config for this solve
    saved_deadhead = config.TERMINAL_TO_TERMINAL_DEADHEAD_MIN
    config.TERMINAL_TO_TERMINAL_DEADHEAD_MIN = deadhead_min

    C.add_r1_service_coverage(model, trip_vars, rake_trip, data)
    C.add_r3_operating_window(model, trip_vars)
    C.add_r4_fleet_availability(model, trip_vars, rake_trip, data)
    C.add_r5_rake_non_overlap(model, trip_vars, rake_trip, data)
    C.add_r6_turnaround(model, trip_vars, rake_trip, data)
    C.add_r10_maintenance_threshold(model, trip_vars, rake_trip, data)
    # We are skipping R11 (home-lock) because we did it manually above.
    # R11's pair rule is already covered by R6 (deadhead-aware).

    config.TERMINAL_TO_TERMINAL_DEADHEAD_MIN = saved_deadhead

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = config.CP_SAT_NUM_WORKERS
    solver.parameters.random_seed = config.CP_SAT_RANDOM_SEED

    t0 = time.time()
    status = solver.Solve(model)
    elapsed = time.time() - t0
    return solver.StatusName(status), elapsed, len(trip_vars)


def main():
    print("=== 250-trip Relaxation Probe ===\n")
    print(f"{'ID':<4} {'Deadhead':>9} {'HomeLock':>9} {'MuttRakes':>10} {'Status':<12} {'Elapsed':>8}")
    print("-" * 70)

    variants = [
        ("Q0", 15, True, 0),
        ("Q1", 0,  True, 0),
        ("Q2", 15, False, 0),
        ("Q3", 15, True, 2),
    ]

    for pid, dh, hl, mr in variants:
        try:
            status, elapsed, n = solve_variant(dh, hl, mr)
            print(f"{pid:<4} {dh:>9} {str(hl):>9} {mr:>10} {status:<12} {elapsed:>7.2f}s")
        except Exception as e:
            print(f"{pid:<4} ERROR: {e}")


if __name__ == "__main__":
    main()