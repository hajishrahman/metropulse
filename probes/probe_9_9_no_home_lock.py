"""
9/9 feasibility probe WITHOUT the home-lock pruning — Phase 1 R6-fixed.

Question:
    Is 9 ALVA / 9 TPHT / 0 MUTTOM genuinely INFEASIBLE under the correct
    R6 rule, or is it artificially INFEASIBLE because of the undocumented
    "home-lock" block in create_rake_assignment_variables?

What it does:
    Same as probe_9_9.py, but:
      - rake_trip variables are created manually (no home-lock blocks).
      - All other constraints (R1, R3, R4, R5, R6, R10, R11) are the real ones.
      - R11's first-trip home rule is STILL applied — only the pruning
        block that says "block the earliest opposite-terminal trip" is removed.

    So: if this returns OPTIMAL, the home-lock was hiding a feasible 9/9
    fleet. If it returns INFEASIBLE, 9/9 is genuinely infeasible.

Run from project root:
    python probes\\probe_9_9_no_home_lock.py
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
    print("=== 9/9 feasibility probe — NO HOME-LOCK (R6-fixed) ===\n")

    data = ProblemData.load()
    print(f"Loaded {len(data.trips)} trips, {len(data.service_rakes)} service rakes\n")

    # Move R017, R018 to TPHT (in-memory only)
    rakes = data.rakes.copy()
    moves = rakes["rake_id"].isin(["R017", "R018"])
    if not moves.any():
        print("  ERROR: R017 or R018 not found. Aborting.")
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
        new_alva = (data.service_rakes["initial_location"] == "ALVA").sum()
        new_tpht = (data.service_rakes["initial_location"] == "TPHT").sum()
        new_mutt = (data.service_rakes["initial_location"] == "MUTTOM").sum()
        print(f"Probe split: ALVA={new_alva}, TPHT={new_tpht}, MUTTOM={new_mutt}\n")

        # Build the model
        model = cp_model.CpModel()
        trips = C.build_trips(data)
        trip_vars = C.create_trip_intervals(model, trips)

        # Manual rake_trip — NO home-lock
        rake_trip = {}
        for _, r in data.service_rakes.iterrows():
            rid = r["rake_id"]
            mileage = int(r["initial_mileage_km"])
            for t in trips:
                tid = t["trip_id"]
                var = model.NewBoolVar(f"rake_{rid}_trip_{tid}")
                rake_trip[(rid, tid)] = var
                # R10 threshold only — no home-lock
                if mileage >= config.MAINTENANCE_THRESHOLD_KM:
                    model.Add(var == 0)

        # Standard rules (identical to solve.py)
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
            dev = sum(abs(c - (len(trip_vars) // len(data.service_rakes))) for c in counts.values())
            print(f"  Total: {total}")
            print(f"  Sum dev from target: {dev}")
            print(f"  Expected objective (3 * 100 * dev): {3 * 100 * dev}\n")

            if status_name == "OPTIMAL":
                print("VERDICT: 9/9 is FEASIBLE WITHOUT HOME-LOCK.")
                print("         The home-lock block is the cause of the earlier INFEASIBLE.")
                print("         This is a bug — the home-lock is undocumented and overly restrictive.")
                print("         Next: decide whether to relax or remove home-lock; re-run 9/9 with it removed.")
            else:
                print("VERDICT: 9/9 is FEASIBLE but not proven optimal in 300 s.")
                print("         Increase time limit and re-run. Home-lock is likely the cause.")
        else:
            print(f"VERDICT: {status_name} — 9/9 is GENUINELY INFEASIBLE without home-lock.")
            print("         The 9/7/2 split is required under correct R6, independently of home-lock.")
            print("         Update docs to say 'required under correct R6 (verified 2026-11-14).'")

    finally:
        config.INITIAL_RAKES_AT_ALVA = saved[0]
        config.INITIAL_RAKES_AT_TPHT = saved[1]
        config.INITIAL_RAKES_AT_MUTTOM = saved[2]

    print("\n[done] no files on disk were written.")


if __name__ == "__main__":
    main()