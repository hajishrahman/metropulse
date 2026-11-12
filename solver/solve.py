"""
MetroPulse CP-SAT solver — orchestrator.

Builds the model from real GTFS trips, solves, writes solution.json + schedule.csv.
"""
from __future__ import annotations

import csv
import json
import time
from pathlib import Path

from ortools.sat.python import cp_model

from solver import config
from solver.models import ProblemData
from solver import constraints as C


OUT_DIR = Path(__file__).parent.parent / "data" / "processed"


def sec_to_hhmmss(sec: int) -> str:
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def solve(data: ProblemData, verbose: bool = False,
          time_limit_sec: int | None = None) -> dict:
    time_limit = config.CP_SAT_TIME_LIMIT_SEC if time_limit_sec is None else time_limit_sec
    if time_limit <= 0:
        raise ValueError("time_limit_sec must be positive")

    print("[solve] building model...")
    model = cp_model.CpModel()

    trips = C.build_trips(data)
    print(f"[solve] {len(trips)} trips to schedule")

    trip_vars = C.create_trip_intervals(model, trips)
    rake_trip = C.create_rake_assignment_variables(model, trips, data, trip_vars)

    print("[solve] applying constraints")
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

    print("[solve] applying objective")
    o6 = C.add_obj6_rake_balance(model, trip_vars, rake_trip, data)
    C.build_objective(model, o6)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = config.CP_SAT_NUM_WORKERS
    solver.parameters.random_seed = config.CP_SAT_RANDOM_SEED
    if verbose:
        solver.parameters.log_search_progress = True

    print(f"[solve] solving (limit {time_limit}s)...")
    t0 = time.perf_counter()
    status = solver.Solve(model)
    elapsed = time.perf_counter() - t0
    status_name = solver.StatusName(status)
    print(f"[solve] status = {status_name}  ({elapsed:.2f}s)")

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            "status": status_name,
            "elapsed_sec": elapsed,
            "objective": None,
            "best_bound": None,
            "gap_pct": None,
            "num_trips": 0,
            "schedule": [],
        }

    obj_value = solver.ObjectiveValue()
    best_bound = solver.BestObjectiveBound()
    if status == cp_model.OPTIMAL:
        gap_pct = 0.0
    elif obj_value > 0:
        gap_pct = (obj_value - best_bound) / obj_value * 100
    else:
        gap_pct = None

    print(f"[solve] objective = {obj_value}")
    print(f"[solve] best_bound = {best_bound}")
    print(f"[solve] gap = {gap_pct}")

    schedule = []
    service_rake_ids = data.service_rakes["rake_id"].tolist()
    for tid, tv in trip_vars.items():
        assigned_rake = None
        for rid in service_rake_ids:
            if solver.Value(rake_trip[(rid, tid)]) == 1:
                assigned_rake = rid
                break
        if assigned_rake is None:
            raise RuntimeError(f"No service rake assigned to trip {tid}")
        schedule.append({
            "trip_id": tid,
            "rake_id": assigned_rake,
            "direction": tv["direction"],
            "first_stop": tv["first_stop"],
            "last_stop": tv["last_stop"],
            "departure": sec_to_hhmmss(tv["start"]),
            "arrival": sec_to_hhmmss(tv["end"]),
            "departure_sec": tv["start"],
            "arrival_sec": tv["end"],
        })

    schedule.sort(key=lambda x: x["departure_sec"])

    return {
        "status": status_name,
        "elapsed_sec": elapsed,
        "objective": obj_value,
        "best_bound": best_bound,
        "gap_pct": gap_pct,
        "num_trips": len(schedule),
        "schedule": schedule,
    }


def write_outputs(result: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    sol_path = OUT_DIR / "solution.json"
    with open(sol_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"[solve] wrote {sol_path}")

    csv_path = OUT_DIR / "schedule.csv"
    fields = ["trip_id", "rake_id", "direction", "first_stop", "last_stop",
              "departure", "arrival"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(result["schedule"])
    print(f"[solve] wrote {csv_path}")


def main():
    print("[main] loading ProblemData...")
    data = ProblemData.load()
    print(data.summary())
    print()

    result = solve(data)

    if not result["schedule"]:
        print("\nNo feasible schedule found.")
        return

    write_outputs(result)

    print("\n=== Summary ===")
    print(f"Status:    {result['status']}")
    print(f"Objective: {result['objective']}")
    print(f"Trips:     {result['num_trips']}")
    print(f"Elapsed:   {result['elapsed_sec']:.2f}s")


if __name__ == "__main__":
    main()
