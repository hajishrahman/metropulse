"""
MetroPulse CP-SAT solver — orchestrator.

Loads ProblemData, builds the model (variables + constraints + objective),
solves, and writes solution.json + schedule.csv to data/processed/.

Spec: docs/constraints-v2.md
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from ortools.sat.python import cp_model

from solver import config
from solver.models import ProblemData
from solver import constraints as C


OUT_DIR = Path(__file__).parent.parent / "data" / "processed"
BASE_HOUR = config.OPERATING_START_HOUR  # 5


# ---------------------------------------------------------------------------
# Solve
# ---------------------------------------------------------------------------
def solve(data: ProblemData, verbose: bool = False,
          time_limit_sec: int | None = None) -> dict:
    """
    Build and solve the CP-SAT model. Returns a result dict.
    """
    time_limit = time_limit_sec or config.CP_SAT_TIME_LIMIT_SEC

    print(f"[solve] building model...")
    model = cp_model.CpModel()

    # -------------------------------------------------------------------
    # 1. Generate required trips (from DPR hourly plan)
    # -------------------------------------------------------------------
    trips = C.generate_required_trips(data)
    print(f"[solve] {len(trips)} trips to schedule")

    # -------------------------------------------------------------------
    # 2. Decision variables
    # -------------------------------------------------------------------
    trip_vars = C.create_trip_variables(model, trips)
    rake_trip = C.create_rake_assignment_variables(model, trips, data)

    # -------------------------------------------------------------------
    # 3. Hard constraints R1..R12
    # -------------------------------------------------------------------
    print(f"[solve] applying R1..R12")
    C.add_r1_service_coverage(model, trip_vars, rake_trip, data)
    C.add_r2a_design_headway(model, trip_vars)
    C.add_r3_operating_window(model, trip_vars)
    C.add_r4_fleet_availability(model, trip_vars, rake_trip, data)
    C.add_r5_rake_non_overlap(model, trip_vars, rake_trip, data)
    C.add_r6_turnaround(model, trip_vars, rake_trip, data)
    C.add_r7_running_time(model, trip_vars)
    C.add_r8_depot_capacity(model, trip_vars, rake_trip, data)
    C.add_r9_maintenance_exclusivity(model, trip_vars, rake_trip, data)
    C.add_r10_maintenance_threshold(model, trip_vars, rake_trip, data)
    C.add_r11_deadhead(model, trip_vars, rake_trip, data)
    C.add_r12_nonservice_window(model, trip_vars)

    # -------------------------------------------------------------------
    # 4. Soft objectives O1, O6, O7
    # -------------------------------------------------------------------
    print(f"[solve] applying objectives")
    o1 = C.add_obj1_waiting_proxy(model, trip_vars)
    o6 = C.add_obj6_rake_balance(model, trip_vars, rake_trip, data)
    o7 = C.add_obj7_reserve_activation(model, trip_vars, rake_trip, data)
    C.build_objective(model, o1, o6, o7)

    # -------------------------------------------------------------------
    # 5. Solve
    # -------------------------------------------------------------------
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = config.CP_SAT_NUM_WORKERS
    solver.parameters.random_seed = config.CP_SAT_RANDOM_SEED
    if verbose:
        solver.parameters.log_search_progress = True

    print(f"[solve] solving (limit {time_limit}s)...")
    t0 = time.time()
    status = solver.Solve(model)
    elapsed = time.time() - t0

    status_name = solver.StatusName(status)
    print(f"[solve] status = {status_name}")
    print(f"[solve] elapsed = {elapsed:.2f}s")

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            "status": status_name,
            "elapsed_sec": elapsed,
            "objective": None,
            "schedule": None,
        }

    print(f"[solve] objective = {solver.ObjectiveValue()}")

    # -------------------------------------------------------------------
    # 6. Extract solution
    # -------------------------------------------------------------------
    schedule = []
    for tid, tv in trip_vars.items():
        # Find the rake that got this trip
        assigned_rake = None
        for _, r in data.rakes.iterrows():
            rid = r["rake_id"]
            if solver.Value(rake_trip[(rid, tid)]) == 1:
                assigned_rake = rid
                break

        if assigned_rake is None:
            continue   # shouldn't happen

        start_min = solver.Value(tv["start"])
        end_min = solver.Value(tv["end"])

        schedule.append({
            "trip_id": tid,
            "rake_id": assigned_rake,
            "direction": tv["direction"],
            "hour_start": tv["hour_start"],
            "hour_end": tv["hour_end"],
            "departure_min_from_base": start_min,
            "arrival_min_from_base": end_min,
            "departure": _min_to_hhmm(start_min),
            "arrival": _min_to_hhmm(end_min),
        })

    # Sort by departure time
    schedule.sort(key=lambda x: x["departure_min_from_base"])

    return {
        "status": status_name,
        "elapsed_sec": elapsed,
        "objective": solver.ObjectiveValue(),
        "num_trips": len(schedule),
        "schedule": schedule,
    }


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------
def _min_to_hhmm(min_from_base: int) -> str:
    """Convert minutes from 05:00 base to 'HH:MM'."""
    total_min = BASE_HOUR * 60 + min_from_base
    h = total_min // 60
    m = total_min % 60
    return f"{h:02d}:{m:02d}"


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
def write_outputs(result: dict) -> None:
    """Write solution.json and schedule.csv to data/processed/."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    sol_path = OUT_DIR / "solution.json"
    with open(sol_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"[solve] wrote {sol_path}")

    if result["schedule"]:
        csv_path = OUT_DIR / "schedule.csv"
        with open(csv_path, "w") as f:
            f.write("trip_id,rake_id,direction,departure,arrival\n")
            for row in result["schedule"]:
                f.write(
                    f"{row['trip_id']},{row['rake_id']},"
                    f"{row['direction']},{row['departure']},{row['arrival']}\n"
                )
        print(f"[solve] wrote {csv_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    print("[main] loading ProblemData...")
    data = ProblemData.load()
    print(data.summary())
    print()

    result = solve(data)
    write_outputs(result)

    if result["schedule"] is None:
        print("\nNo feasible schedule found.")
        return

    print(f"\n=== Summary ===")
    print(f"Status:     {result['status']}")
    print(f"Objective:  {result['objective']}")
    print(f"Trips:      {result['num_trips']}")
    print(f"Elapsed:    {result['elapsed_sec']:.2f}s")


if __name__ == "__main__":
    main()