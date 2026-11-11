"""
Real-model probe for the 250-trip case.

Uses the ACTUAL solver/constraints.py (no rewriting).
Runs three variants and prints a table.

Variants:
    A: exactly as solve.py does now    — expect INFEASIBLE
    B: A + skip the "earliest opposite-terminal" block in
       create_rake_assignment_variables
    C: B + 4 MUTTOM-home rakes instead of 2

Run from project root:
    python probes\run_probes_250_real.py
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


def build_with_toggles(skip_earliest_block: bool, rakes_at_muttom: int):
    """
    Build the real model, optionally skipping the earliest-opposite block
    in create_rake_assignment_variables, and optionally re-splitting rakes.
    """
    data = ProblemData.load()

    # Re-split service rakes if requested
    if rakes_at_muttom != 2:
        rakes = data.rakes.copy()
        # Current split is 9 ALVA / 7 TPHT / 2 MUTTOM
        # Move extra TPHT rakes to MUTTOM to reach rakes_at_muttom
        tpht_idx = rakes[(rakes["status"] == "service")
                         & (rakes["initial_location"] == "TPHT")].index
        extra = rakes_at_muttom - 2
        if extra > 0:
            move = tpht_idx[:extra]
            rakes.loc[move, "initial_location"] = "MUTTOM"
        data.rakes = rakes

    model = cp_model.CpModel()
    trips = C.build_trips(data)
    trip_vars = C.create_trip_intervals(model, trips)

    # rake_trip — build manually so we can skip the earliest block
    rake_trip = {}
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
        mileage = int(r["initial_mileage_km"])
        for t in trips:
            tid = t["trip_id"]
            var = model.NewBoolVar(f"rake_{rid}_trip_{tid}")
            rake_trip[(rid, tid)] = var

            if mileage >= config.MAINTENANCE_THRESHOLD_KM:
                model.Add(var == 0)
                continue

            if skip_earliest_block:
                continue

            # The "earliest opposite-terminal" block from constraints.py
            if home == "ALVA":
                if earliest_tpht is not None and trip_vars[tid]["start"] == earliest_tpht and trip_vars[tid]["first_stop"] == "TPHT":
                    model.Add(var == 0); continue
                if earliest_mutt is not None and trip_vars[tid]["start"] == earliest_mutt and trip_vars[tid]["first_stop"] == "MUTT":
                    model.Add(var == 0); continue
            if home == "TPHT":
                if earliest_alva is not None and trip_vars[tid]["start"] == earliest_alva and trip_vars[tid]["first_stop"] == "ALVA":
                    model.Add(var == 0); continue
                if earliest_mutt is not None and trip_vars[tid]["start"] == earliest_mutt and trip_vars[tid]["first_stop"] == "MUTT":
                    model.Add(var == 0); continue
            if home == "MUTTOM":
                if earliest_alva is not None and trip_vars[tid]["start"] == earliest_alva and trip_vars[tid]["first_stop"] == "ALVA":
                    model.Add(var == 0); continue
                if earliest_tpht is not None and trip_vars[tid]["start"] == earliest_tpht and trip_vars[tid]["first_stop"] == "TPHT":
                    model.Add(var == 0); continue

    # Standard rules
    C.add_r1_service_coverage(model, trip_vars, rake_trip, data)
    C.add_r3_operating_window(model, trip_vars)
    C.add_r4_fleet_availability(model, trip_vars, rake_trip, data)
    C.add_r5_rake_non_overlap(model, trip_vars, rake_trip, data)
    C.add_r6_turnaround(model, trip_vars, rake_trip, data)
    C.add_r10_maintenance_threshold(model, trip_vars, rake_trip, data)
    C.add_r11_terminal_continuity(model, trip_vars, rake_trip, data)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 300
    solver.parameters.num_search_workers = config.CP_SAT_NUM_WORKERS
    solver.parameters.random_seed = config.CP_SAT_RANDOM_SEED

    t0 = time.time()
    status = solver.Solve(model)
    elapsed = time.time() - t0
    return solver.StatusName(status), elapsed, len(trip_vars)


def main():
    print("=== Real-model 250-trip probe ===\n")
    print(f"{'ID':<4} {'SkipEarliest':>13} {'MUTT rakes':>11} {'Status':<12} {'Elapsed':>8}")
    print("-" * 60)

    variants = [
        ("A", False, 2),
        ("B", True,  2),
        ("C", True,  4),
    ]
    for pid, skip, mutt in variants:
        try:
            status, elapsed, n = build_with_toggles(skip, mutt)
            print(f"{pid:<4} {str(skip):>13} {mutt:>11} {status:<12} {elapsed:>7.2f}s")
        except Exception as e:
            print(f"{pid:<4} ERROR: {e}")


if __name__ == "__main__":
    main()