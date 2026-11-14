"""
9/9 feasibility probe — Phase 1 R6-fixed.

Question:
    After the R6 MUTT-deadhead fix (8 min for MUTT pairs), is the
    9 ALVA / 9 TPHT / 0 MUTTOM split feasible for the 250-trip case?

What it does:
    - Loads trips_all.csv and rakes.csv from disk.
    - Makes an in-memory copy of rakes.
    - Moves R017 and R018 from MUTTOM -> TPHT.
    - Overrides config.INITIAL_RAKES_AT_* in memory only.
    - Builds the full model using the CURRENT constraints.py (R6-fixed).
    - Solves with 300 s limit.
    - Prints status, objective, bound, gap, trip distribution.
    - Does NOT write schedule.csv, solution.json, or validation.json.
    - Does NOT modify rakes.csv, rakes_phase5.csv, or any config file.

Run from project root:
    python probes\\probe_9_9.py
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


def main():
    print("=== 9/9 feasibility probe (R6-fixed) ===\n")

    # Load real data
    data = ProblemData.load()
    print(f"Loaded {len(data.trips)} trips, {len(data.service_rakes)} service rakes\n")

    # Sanity check: initial split must be 9/7/2 before we change it
    alva = (data.service_rakes["initial_location"] == "ALVA").sum()
    tpht = (data.service_rakes["initial_location"] == "TPHT").sum()
    mutt = (data.service_rakes["initial_location"] == "MUTTOM").sum()
    print(f"Initial service rake split: ALVA={alva}, TPHT={tpht}, MUTTOM={mutt}")
    if (alva, tpht, mutt) != (9, 7, 2):
        print("  WARNING: initial split is not 9/7/2. Probe may behave unexpectedly.")
        print("  Continuing anyway — result will reflect current rakes.csv.\n")
    else:
        print()

    # Move R017 and R018 to TPHT (in-memory only)
    rakes = data.rakes.copy()
    moves = rakes["rake_id"].isin(["R017", "R018"])
    if not moves.any():
        print("  ERROR: R017 or R018 not found in rakes. Aborting.")
        return
    rakes.loc[moves, "initial_location"] = "TPHT"
    data.rakes = rakes

    # Override config in memory only
    saved = (
        config.INITIAL_RAKES_AT_ALVA,
        config.INITIAL_RAKES_AT_TPHT,
        config.INITIAL_RAKES_AT_MUTTOM,
    )
    config.INITIAL_RAKES_AT_ALVA = 9
    config.INITIAL_RAKES_AT_TPHT = 9
    config.INITIAL_RAKES_AT_MUTTOM = 0

    try:
        # Re-check
        new_alva = (data.service_rakes["initial_location"] == "ALVA").sum()
        new_tpht = (data.service_rakes["initial_location"] == "TPHT").sum()
        new_mutt = (data.service_rakes["initial_location"] == "MUTTOM").sum()
        print(f"Probe split: ALVA={new_alva}, TPHT={new_tpht}, MUTTOM={new_mutt}\n")

        # Build the model exactly as solve.py does
        model = cp_model.CpModel()
        trips = C.build_trips(data)
        trip_vars = C.create_trip_intervals(model, trips)
        rake_trip = C.create_rake_assignment_variables(model, trips, data, trip_vars)

        C.add_r1_service_coverage(model, trip_vars, rake_trip, data)
        C.add_r3_operating_window(model, trip_vars)
        C.add_r4_fleet_availability(model, trip_vars, rake_trip, data)
        C.add_r5_rake_non_overlap(model, trip_vars, rake_trip, data)
        C.add_r6_turnaround(model, trip_vars, rake_trip, data)
        C.add_r7_running_time(model, trip_vars)
        C.add_r8_depot_capacity(model, trip_vars, rake_trip, data)
        C.add_r9_maintenance_exclusivity(model, trip_vars, rake_trip, data)
        C.add_r10_maintenance_threshold(model, trip_vars, rake_trip, data)
        C.add_r11_terminal_continuity(model, trip_vars, rake_trip, data)
        C.add_r12_nonservice_window(model, trip_vars)

        o6 = C.add_obj6_rake_balance(model, trip_vars, rake_trip, data)
        C.build_objective(model, o6)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 300
        solver.parameters.num_search_workers = config.CP_SAT_NUM_WORKERS
        solver.parameters.random_seed = config.CP_SAT_RANDOM_SEED

        print("[probe] solving (limit 300 s)...")
        t0 = time.perf_counter()
        status = solver.Solve(model)
        elapsed = time.perf_counter() - t0
        status_name = solver.StatusName(status)
        print(f"[probe] status = {status_name}  ({elapsed:.2f}s)\n")

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            obj = solver.ObjectiveValue()
            bound = solver.BestObjectiveBound()
            gap = 0.0 if status == cp_model.OPTIMAL else (obj - bound) / obj * 100 if obj > 0 else None
            print(f"[probe] objective    = {obj}")
            print(f"[probe] best_bound   = {bound}")
            print(f"[probe] gap          = {gap}%\n")

            # Count trips per rake
            counts = {rid: 0 for rid in data.service_rakes["rake_id"]}
            for tid in trip_vars:
                for rid in data.service_rakes["rake_id"]:
                    if solver.Value(rake_trip[(rid, tid)]) == 1:
                        counts[rid] += 1
                        break
            print("Trip distribution:")
            for rid in sorted(counts):
                print(f"  {rid}: {counts[rid]}")
            total = sum(counts.values())
            print(f"  Total: {total}")
            dev = sum(abs(c - (len(trip_vars) // len(data.service_rakes))) for c in counts.values())
            print(f"  Sum dev from target: {dev}")
            print(f"  Expected objective (3 * 100 * dev): {3 * 100 * dev}\n")

            if status_name == "INFEASIBLE":
                print("VERDICT: 9/9 is INFEASIBLE under correct R6.")
                print("         The 9/7/2 split is required. Update docs to say")
                print("         'required under correct R6' (currently says 'required').")
            elif status_name == "OPTIMAL":
                print("VERDICT: 9/9 is OPTIMAL. The fleet split can change.")
                print("         Next step: update config.py, rakes.csv, and docs.")
            else:
                print("VERDICT: FEASIBLE but not proven optimal within 300 s.")
                print("         Increase time limit and re-run before deciding.")
        else:
            print(f"VERDICT: {status_name}. 9/9 is INFEASIBLE under correct R6.")
            print("         The 9/7/2 split is required. Update docs to say")
            print("         'required under correct R6' (currently says 'required').")

        # Also print pre-solve r6 counters from the model build
        # (they come from add_r6_turnaround's internal print)

    finally:
        # Restore config
        config.INITIAL_RAKES_AT_ALVA = saved[0]
        config.INITIAL_RAKES_AT_TPHT = saved[1]
        config.INITIAL_RAKES_AT_MUTTOM = saved[2]

    print("\n[done] no files on disk were written.")


if __name__ == "__main__":
    main()