"""
MetroPulse Phase 5 — Disruption Response orchestrator.

Runs Scenario A and Scenario B back-to-back:
    1. Load baseline (Phase 1 schedule.csv + rakes_phase5.csv)
    2. For each scenario: pick activated rakes, apply disruption,
       solve CP-SAT, write schedule CSV
    3. Compute diff in-memory, write reschedule_diff.json
    4. Write reschedule_summary.md

Mirrors solver/solve.py conventions: same status normalization, same gap
formula, same CSV schema, same solver parameter shape.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
from ortools.sat.python import cp_model

from solver import config
from solver import reschedule_config as R5
from solver.reschedule_models import RescheduleProblemData
from solver import reschedule_constraints as RC
from solver.reschedule_diff import (
    compute_diff,
    write_diff_json,
    write_summary_md,
)


OUT_DIR = Path(__file__).parent.parent / "data" / "processed"


# ===========================================================================
# HELPERS
# ===========================================================================
def sec_to_hhmmss(sec: int) -> str:
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _time_to_sec(t: str) -> int:
    h, m, s = (int(part) for part in t.split(":"))
    return h * 3600 + m * 60 + s


def load_scenario_json(path: str) -> dict:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Missing scenario config: {p}")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def pick_activated_rakes(
    data: RescheduleProblemData, n: int
) -> list:
    """Return the n scheduled maintenance rakes with lowest km_since_last_maintenance.

    Sorted ascending. Returns list of rake_id strings.
    """
    sched = data.scheduled_maintenance_rakes.copy()
    if len(sched) < n:
        raise RuntimeError(
            f"Only {len(sched)} scheduled maintenance rakes available, "
            f"need {n}."
        )
    sched = sched.sort_values("km_since_last_maintenance", kind="stable")
    return list(sched["rake_id"].iloc[:n])


def build_active_fleet(
    data: RescheduleProblemData,
    downed_rakes: list,
    activated_rakes: list,
) -> pd.DataFrame:
    """Return a modified rakes DataFrame:

    - downed service rakes -> status = "inactive"
    - activated maintenance rakes -> status = "service",
      initial_location = "MUTTOM", initial_available_time = "00:00"
    - all other rows unchanged
    """
    rakes = data.rakes.copy()

    for rid in downed_rakes:
        mask = rakes["rake_id"] == rid
        if not mask.any():
            raise RuntimeError(f"Rake {rid} not found in rakes_phase5.csv")
        if (rakes.loc[mask, "status"] != "service").any():
            raise RuntimeError(
                f"Rake {rid} is not a service rake; cannot be downed."
            )
        rakes.loc[mask, "status"] = "inactive"

    for rid in activated_rakes:
        mask = rakes["rake_id"] == rid
        if not mask.any():
            raise RuntimeError(f"Rake {rid} not found in rakes_phase5.csv")
        if (rakes.loc[mask, "status"] != "maintenance").any():
            raise RuntimeError(
                f"Rake {rid} is not a maintenance rake; cannot be activated."
            )
        if (
            rakes.loc[mask, "maintenance_type"] != R5.MAINTENANCE_TYPE_SCHEDULED
        ).any():
            raise RuntimeError(
                f"Rake {rid} is not 'scheduled' maintenance; cannot be "
                f"reactivated."
            )
        rakes.loc[mask, "status"] = "service"
        rakes.loc[mask, "initial_location"] = "MUTTOM"
        rakes.loc[mask, "initial_available_time"] = "00:00"

    return rakes


def _withdrawals_for_rake(
    baseline_schedule: pd.DataFrame,
    downed_rakes: list,
    disruption_sec: int,
) -> dict:
    """Return {rake_id: set(trip_ids withdrawn)}.

    Wall-clock cutoff rule (D5 option i): a downed rake's trips with
    departure >= disruption_sec are unavailable to it.
    """
    out = {}
    baseline = baseline_schedule.copy()
    baseline["dep_sec"] = baseline["departure"].apply(_time_to_sec)
    for rid in downed_rakes:
        rows = baseline[baseline["rake_id"] == rid]
        withdrawn = set(
            rows.loc[rows["dep_sec"] >= disruption_sec, "trip_id"]
        )
        out[rid] = withdrawn
    return out

def _in_progress_trips(
    baseline_schedule: pd.DataFrame,
    downed_rakes: list,
    disruption_sec: int,
) -> dict:
    """Return {rake_id: list of {trip_id, departure, arrival}} of trips that
    are in progress at disruption time (departure < disruption_sec <= arrival).

    These trips complete normally. A rake that is BETWEEN trips (no
    in-progress trip) returns an empty list.
    """
    out = {}
    baseline = baseline_schedule.copy()
    baseline["dep_sec"] = baseline["departure"].apply(_time_to_sec)
    baseline["arr_sec"] = baseline["arrival"].apply(_time_to_sec)
    for rid in downed_rakes:
        rows = baseline[baseline["rake_id"] == rid]
        in_prog = rows[
            (rows["dep_sec"] < disruption_sec) & (rows["arr_sec"] > disruption_sec)
        ]
        out[rid] = [
            {
                "trip_id": r["trip_id"],
                "departure": r["departure"],
                "arrival": r["arrival"],
            }
            for _, r in in_prog.iterrows()
        ]
    return out
# ===========================================================================
# SCENARIO RUNNER
# ===========================================================================
def run_scenario(
    scenario_config: dict,
    baseline_data: RescheduleProblemData,
    baseline_schedule: pd.DataFrame,
    num_activated: int,
    time_limit_sec: int | None = None,
) -> dict:
    """Run one disruption scenario and return:
        {
          "schedule": DataFrame (250 rows, same cols as schedule.csv,
                                 with rake_id == "DROPPED" for cancelled),
          "solve_result": {status, elapsed_sec, objective, best_bound, gap_pct},
          "activated_rakes": [rid, ...],
          "rakes_active_count": int,
        }
    """
    sid = scenario_config["scenario_id"]
    downed = list(scenario_config["rakes_down"])
    disruption_sec = _time_to_sec(scenario_config["disruption_time"])

    print(f"\n{'=' * 70}")
    print(f"[scenario {sid.upper()}] disruption: {downed} at "
          f"{scenario_config['disruption_time']}")
    print(f"{'=' * 70}")

    activated = pick_activated_rakes(baseline_data, num_activated)
    print(f"[scenario {sid.upper()}] activating: {activated}")

    active_fleet = build_active_fleet(baseline_data, downed, activated)
    active_count = int((active_fleet["status"] == "service").sum())
    print(f"[scenario {sid.upper()}] rakes active after response: {active_count}")

    # Build a per-scenario ProblemData view (same trips, modified rakes)
    scenario_data = RescheduleProblemData(
        trips=baseline_data.trips.copy(),
        rakes=active_fleet,
        scenario=f"Phase5_{sid}",
    )

    # Withdrawals per downed rake (wall-clock cutoff)
    withdrawals = _withdrawals_for_rake(
        baseline_schedule, downed, disruption_sec
    )
    for rid, w in withdrawals.items():
        print(f"[scenario {sid.upper()}] {rid} withdrawn for "
              f"{len(w)} future trips (dep >= {scenario_config['disruption_time']})")
    in_progress = _in_progress_trips(
        baseline_schedule, downed, disruption_sec
    )
    # ------------------- BUILD MODEL --------------------------------------
    print(f"[scenario {sid.upper()}] building model...")
    model = cp_model.CpModel()

    trips = RC.build_trips(scenario_data)
    trip_vars = RC.create_trip_intervals(model, trips)
    rake_trip = RC.create_rake_assignment_variables(
        model, trips, scenario_data, trip_vars
    )
    dropped = RC.create_dropped_variables(model, trip_vars)

    # Forbid downed rakes from operating their withdrawn trips.
    # (Downed rakes have status="inactive" so they aren't in service_rakes,
    #  but belt-and-braces — if any code path reintroduces them, this holds.)
    for rid, withdraw_set in withdrawals.items():
        for tid in withdraw_set:
            if (rid, tid) in rake_trip:
                model.Add(rake_trip[(rid, tid)] == 0)

    print(f"[scenario {sid.upper()}] applying constraints")
    RC.add_r1_service_coverage(model, trip_vars, rake_trip, scenario_data, dropped)
    RC.add_r3_operating_window(model, trip_vars)
    RC.add_r4_fleet_availability(model, trip_vars, rake_trip, scenario_data)
    RC.add_r5_rake_non_overlap(model, trip_vars, rake_trip, scenario_data)
    RC.add_r6_turnaround(model, trip_vars, rake_trip, scenario_data)
    RC.add_r7_running_time(model, trip_vars)
    RC.add_r8_depot_capacity(model, trip_vars, rake_trip, scenario_data)
    RC.add_r9_maintenance_exclusivity(model, trip_vars, rake_trip, scenario_data)
    RC.add_r10_maintenance_threshold(model, trip_vars, rake_trip, scenario_data)
    RC.add_r11_terminal_continuity(model, trip_vars, rake_trip, scenario_data)
    RC.add_r12_nonservice_window(model, trip_vars)

    print(f"[scenario {sid.upper()}] applying objective")
    o6 = RC.add_obj6_rake_balance(model, trip_vars, rake_trip, scenario_data)
    RC.build_objective(model, o6, dropped)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = (
        config.CP_SAT_TIME_LIMIT_SEC if time_limit_sec is None else time_limit_sec
    )
    solver.parameters.num_search_workers = config.CP_SAT_NUM_WORKERS
    solver.parameters.random_seed = config.CP_SAT_RANDOM_SEED

    print(f"[scenario {sid.upper()}] solving "
          f"(limit {solver.parameters.max_time_in_seconds}s)...")
    t0 = time.perf_counter()
    status = solver.Solve(model)
    elapsed = time.perf_counter() - t0
    status_name = solver.StatusName(status)
    print(f"[scenario {sid.upper()}] status = {status_name}  ({elapsed:.2f}s)")

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(
            f"Scenario {sid} returned {status_name} — cannot write outputs. "
            f"This is a bug, not expected behaviour; report it."
        )

    obj_value = solver.ObjectiveValue()
    best_bound = solver.BestObjectiveBound()
    if status == cp_model.OPTIMAL:
        gap_pct = 0.0
    elif obj_value > 0:
        gap_pct = (obj_value - best_bound) / obj_value * 100
    else:
        gap_pct = None

    print(f"[scenario {sid.upper()}] objective = {obj_value}")
    print(f"[scenario {sid.upper()}] best_bound = {best_bound}")
    print(f"[scenario {sid.upper()}] gap = {gap_pct}")

    # ------------------- EXTRACT SCHEDULE ---------------------------------
    service_rake_ids = scenario_data.service_rakes["rake_id"].tolist()
    schedule_rows = []
    dropped_trip_ids = []

    for tid, tv in trip_vars.items():
        if solver.Value(dropped[tid]) == 1:
            dropped_trip_ids.append(tid)
            schedule_rows.append({
                "trip_id": tid,
                "rake_id": R5.DROPPED_RAKE_SENTINEL,
                "direction": tv["direction"],
                "first_stop": tv["first_stop"],
                "last_stop": tv["last_stop"],
                "departure": "",
                "arrival": "",
                "departure_sec": tv["start"],
                "arrival_sec": tv["end"],
            })
            continue

        assigned_rake = None
        for rid in service_rake_ids:
            if solver.Value(rake_trip[(rid, tid)]) == 1:
                assigned_rake = rid
                break
        if assigned_rake is None:
            raise RuntimeError(
                f"Trip {tid} neither dropped nor assigned — model bug."
            )
        schedule_rows.append({
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

    schedule_rows.sort(key=lambda x: x["departure_sec"])
    schedule_df = pd.DataFrame(schedule_rows)

    print(f"[scenario {sid.upper()}] dropped trips: {len(dropped_trip_ids)}")
    print(f"[scenario {sid.upper()}] done")

    return {
        "schedule": schedule_df,
        "solve_result": {
            "status": status_name,
            "elapsed_sec": elapsed,
            "objective": obj_value,
            "best_bound": best_bound,
            "gap_pct": gap_pct,
        },
        "activated_rakes": activated,
        "rakes_active_count": active_count,
        "dropped_trip_ids": dropped_trip_ids,
        "withdrawals": withdrawals,
        "in_progress": in_progress,
    }


# ===========================================================================
# CSV WRITER — same 7-col schema as schedule.csv
# ===========================================================================
def write_scenario_csv(schedule_df: pd.DataFrame, path: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "trip_id", "rake_id", "direction", "first_stop", "last_stop",
        "departure", "arrival",
    ]
    schedule_df.to_csv(p, columns=fields, index=False, encoding="utf-8")
    print(f"[scenario] wrote {p}  ({len(schedule_df)} rows)")


# ===========================================================================
# MAIN
# ===========================================================================
def main():
    print("[main] loading RescheduleProblemData...")
    data = RescheduleProblemData.load()
    print(data.summary())

    # Baseline schedule DataFrame (for diff), read exactly once.
    baseline_schedule = pd.read_csv(
        R5.BASELINE_SCHEDULE_CSV, encoding="utf-8"
    )
    if len(baseline_schedule) != 250:
        raise RuntimeError(
            f"Expected 250 baseline trips, got {len(baseline_schedule)}"
        )

    # ---- Scenario A -------------------------------------------------------
    cfg_a = load_scenario_json(R5.SCENARIO_A_JSON)
    result_a = run_scenario(
        scenario_config=cfg_a,
        baseline_data=data,
        baseline_schedule=baseline_schedule,
        num_activated=1,
    )
    write_scenario_csv(result_a["schedule"], R5.RESCHEDULE_OUT_A)

    # ---- Scenario B -------------------------------------------------------
    cfg_b = load_scenario_json(R5.SCENARIO_B_JSON)
    result_b = run_scenario(
        scenario_config=cfg_b,
        baseline_data=data,
        baseline_schedule=baseline_schedule,
        num_activated=2,
    )
    write_scenario_csv(result_b["schedule"], R5.RESCHEDULE_OUT_B)

    # ---- Diff (in-memory) -------------------------------------------------
    trips_withdrawn_a = sum(len(w) for w in result_a["withdrawals"].values())
    trips_withdrawn_b = sum(len(w) for w in result_b["withdrawals"].values())

    diff_a = compute_diff(
        original_schedule=baseline_schedule,
        new_schedule=result_a["schedule"],
        solve_result=result_a["solve_result"],
        scenario_config=cfg_a,
        activated_rakes=result_a["activated_rakes"],
        rakes_active_count=result_a["rakes_active_count"],
        rakes_phase5_df=data.rakes,
        trips_withdrawn=trips_withdrawn_a,
        in_progress=result_a["in_progress"],
    )
    diff_a["rakes_activated_reason"] = (
        "lowest km_since_last_maintenance among scheduled"
    )

    diff_b = compute_diff(
        original_schedule=baseline_schedule,
        new_schedule=result_b["schedule"],
        solve_result=result_b["solve_result"],
        scenario_config=cfg_b,
        activated_rakes=result_b["activated_rakes"],
        rakes_active_count=result_b["rakes_active_count"],
        rakes_phase5_df=data.rakes,
        trips_withdrawn=trips_withdrawn_b,
        in_progress=result_b["in_progress"],
        include_capacity_warning=True,
    )
    diff_b["rakes_activated_reason"] = (
        "2 lowest km_since_last_maintenance among scheduled"
    )

    write_diff_json(diff_a, diff_b, R5.RESCHEDULE_DIFF_JSON)
    write_summary_md(diff_a, diff_b, data.rakes, R5.RESCHEDULE_SUMMARY_MD)

    # ---- Console summary --------------------------------------------------
    print("\n" + "=" * 70)
    print("PHASE 5 COMPLETE")
    print("=" * 70)
    for label, d in [("A", diff_a), ("B", diff_b)]:
        print(
            f"Scenario {label}: status={d['solver_status']}, "
            f"obj={d['objective']}, "
            f"gap={d['gap_pct']}%, "
            f"active={d['rakes_active_count']}, "
            f"unchanged={d['trips_unchanged']}, "
            f"reassigned={d['trips_reassigned']}, "
            f"dropped={d['trips_dropped']}, "
            f"elapsed={d['elapsed_sec']}s"
        )


if __name__ == "__main__":
    main()