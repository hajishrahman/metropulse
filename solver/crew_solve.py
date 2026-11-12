"""
MetroPulse Phase 3 crew solver — CP-SAT, loops over POOL_SIZES.

Reads schedule.csv + drivers.csv once, solves for each POOL_SIZE, writes
crew_schedule.csv and crew_solution.json keyed by pool size.

CP-SAT with num_search_workers > 1 may be non-deterministic across runs —
that is expected and documented, not hidden.
"""
from __future__ import annotations

import csv
import json
import time
from pathlib import Path

from ortools.sat.python import cp_model

from solver import crew_config as CFG
from solver.crew_models import CrewProblemData
from solver import crew_constraints as CC


OUT_DIR = Path(__file__).parent.parent / "data" / "processed"


def sec_to_hhmmss(sec: int) -> str:
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def solve_crew(data: CrewProblemData,
               pool_size: int,
               verbose: bool = False,
               time_limit_sec: int | None = None) -> dict:
    if pool_size <= 0:
        raise ValueError("pool_size must be positive")
    if pool_size > data.num_drivers:
        raise ValueError(
            f"pool_size {pool_size} > drivers available {data.num_drivers}"
        )
    time_limit = CFG.CP_SAT_TIME_LIMIT_SEC if time_limit_sec is None else time_limit_sec
    if time_limit <= 0:
        raise ValueError("time_limit_sec must be positive")

    print(f"[crew] pool_size={pool_size} building model...")
    model = cp_model.CpModel()

    trips = CC.build_trips(data)
    print(f"[crew] {len(trips)} trips, using {pool_size} drivers from pool")

    # restrict active pool to the first `pool_size` drivers
    driver_ids = data.driver_ids[:pool_size]
    if len(driver_ids) < pool_size:
        raise ValueError("Not enough drivers to fill pool")

    x = CC.create_driver_trip_vars(model, trips, driver_ids)
    active = CC.create_driver_active_vars(model, driver_ids)
    first_dep, last_arr = CC.create_first_last_bounds(model, trips, driver_ids, x, active)

    print("[crew] applying constraints C1-C4 (hard) ...")
    CC.add_c4_full_coverage(model, trips, x, driver_ids)
    CC.add_c1_no_overlap(model, trips, driver_ids, x)
    CC.add_c2_max_duty(model, driver_ids, active, first_dep, last_arr)
    CC.add_c3_sign_buffers(model, trips, driver_ids, x)

    print("[crew] building objectives C6 (soft), C7 (soft) ...")
    c6 = CC.add_c6_continuous_driving(model, trips, driver_ids, x)
    c7 = CC.add_c7_reserve_buffer(model, driver_ids, active, pool_size)
    CC.build_objective(model, c6, c7)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = CFG.CP_SAT_NUM_WORKERS
    solver.parameters.random_seed = CFG.CP_SAT_RANDOM_SEED
    if verbose:
        solver.parameters.log_search_progress = True

    print(f"[crew] solving (limit {time_limit}s)...")
    t0 = time.perf_counter()
    status = solver.Solve(model)
    elapsed = time.perf_counter() - t0
    status_name = solver.StatusName(status)
    print(f"[crew] status = {status_name}  ({elapsed:.2f}s)")

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            "status": status_name,
            "pool_size": pool_size,
            "elapsed_sec": elapsed,
            "objective": None,
            "best_bound": None,
            "gap_pct": None,
            "num_trips": 0,
            "num_active_drivers": 0,
            "reserve": None,
            "assignments": [],
        }

    obj_value = solver.ObjectiveValue()
    best_bound = solver.BestObjectiveBound()
    if status == cp_model.OPTIMAL:
        gap_pct = 0.0
    elif obj_value > 0:
        gap_pct = (obj_value - best_bound) / obj_value * 100
    else:
        gap_pct = None

    assignments = []
    active_count = 0
    for d in driver_ids:
        d_trips = []
        for t in trips:
            if solver.Value(x[(d, t["trip_id"])]) == 1:
                d_trips.append(t)
        if not d_trips:
            continue
        active_count += 1
        d_trips.sort(key=lambda t: t["dep"])
        first = d_trips[0]
        last = d_trips[-1]
        sign_on = first["dep"] - CFG.SIGN_ON_BUFFER_SEC
        sign_off = last["arr"] + CFG.SIGN_OFF_BUFFER_SEC
        for t in d_trips:
            assignments.append({
                "trip_id": t["trip_id"],
                "driver_id": d,
                "sign_on": sec_to_hhmmss(sign_on),
                "sign_off": sec_to_hhmmss(sign_off),
                "pool_size": pool_size,
                "dep_sec": t["dep"],
                "arr_sec": t["arr"],
            })

    assignments.sort(key=lambda r: r["dep_sec"])

    reserve = pool_size - active_count
    print(f"[crew] active_drivers = {active_count}, reserve = {reserve}")
    print(f"[crew] objective = {obj_value}, best_bound = {best_bound}, gap = {gap_pct}")

    return {
        "status": status_name,
        "pool_size": pool_size,
        "elapsed_sec": elapsed,
        "objective": obj_value,
        "best_bound": best_bound,
        "gap_pct": gap_pct,
        "num_trips": len(assignments),
        "num_active_drivers": active_count,
        "reserve": reserve,
        "assignments": assignments,
    }


def write_outputs(all_results: dict[int, dict]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    sol_path = OUT_DIR / CFG.CREW_SOLUTION_JSON
    with open(sol_path, "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in all_results.items()}, f, indent=2)
    print(f"[crew] wrote {sol_path}")

    csv_path = OUT_DIR / CFG.CREW_SCHEDULE_CSV
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=CFG.CREW_SCHEDULE_FIELDS, extrasaction="ignore"
        )
        writer.writeheader()
        for pool in sorted(all_results):
            writer.writerows(all_results[pool]["assignments"])
    print(f"[crew] wrote {csv_path}")


def main() -> None:
    print("[crew] loading CrewProblemData...")
    data = CrewProblemData.load()
    print(data.summary())
    print()

    all_results: dict[int, dict] = {}
    for pool_size in CFG.POOL_SIZES:
        print(f"\n=== pool_size = {pool_size} ===")
        result = solve_crew(data, pool_size)
        all_results[pool_size] = result

    write_outputs(all_results)

    print("\n=== Sensitivity ===")
    for pool in sorted(all_results):
        r = all_results[pool]
        print(f"pool={pool:<3}  status={r['status']:<9} "
              f"active={r['num_active_drivers']:<3} "
              f"reserve={r['reserve']}  gap={r['gap_pct']}")


if __name__ == "__main__":
    main()