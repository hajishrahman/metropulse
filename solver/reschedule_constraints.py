"""
CP-SAT constraints for MetroPulse Phase 5 — Disruption Response.

Copy of solver/constraints.py with THREE deliberate Phase 5 changes only:

    (1) NEW: create_dropped_variables(model, trip_vars) — a BoolVar per trip.

    (2) MODIFIED R1: sum(rake_trip[rake, trip]) + dropped[trip] == 1.
        All 250 trips are allowed to drop; the solver decides which.
        Without this, a rake-down scenario would be INFEASIBLE with no
        actionable recommendation.

    (3) MODIFIED OBJECTIVE: adds W_DROP * OBJ_SCALE * sum(dropped) so the
        solver minimizes drops before optimizing rake balance. Without this
        penalty, "N trips dropped" would be arbitrary, not minimized.

Everything else (R3–R12, build_trips, create_trip_intervals,
create_rake_assignment_variables, add_obj6_rake_balance) is IDENTICAL
to solver/constraints.py.

Phase 1's solver/constraints.py is NOT modified.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from ortools.sat.python import cp_model

from solver import config
from solver import reschedule_config as R5
from solver.reschedule_models import RescheduleProblemData


RakeTripVars = Dict[Tuple[str, str], cp_model.IntVar]
DroppedVars = Dict[str, cp_model.IntVar]


# ===========================================================================
# TRIPS
# ===========================================================================
def build_trips(data: RescheduleProblemData) -> List[dict]:
    out = []
    for _, r in data.trips.iterrows():
        out.append({
            "trip_id": r["trip_id"],
            "direction": r["direction"],
            "first_stop": r["first_stop"],
            "last_stop": r["last_stop"],
            "dep_sec": int(r["dep_sec"]),
            "arr_sec": int(r["arr_sec"]),
            "duration_sec": int(r["duration"]),
        })
    return out


# ===========================================================================
# INTERVALS
# ===========================================================================
def create_trip_intervals(model, trips):
    tv = {}
    for t in trips:
        tid = t["trip_id"]
        tv[tid] = {
            "start": t["dep_sec"],
            "end": t["arr_sec"],
            "duration": t["duration_sec"],
            "direction": t["direction"],
            "first_stop": t["first_stop"],
            "last_stop": t["last_stop"],
            "arr_sec": t["arr_sec"],
        }
    return tv


# ===========================================================================
# NEW (Phase 5) — DROPPED VARIABLES
# ===========================================================================
def create_dropped_variables(model, trip_vars) -> DroppedVars:
    """One BoolVar per trip: 1 if the trip is dropped (cancelled), 0 if served.

    All 250 trips are may_drop. The solver picks the minimum set to drop
    subject to capacity — enforced via the W_DROP penalty in build_objective.
    """
    dropped: DroppedVars = {}
    for tid in trip_vars:
        dropped[tid] = model.NewBoolVar(f"dropped_{tid}")
    return dropped


# ===========================================================================
# RAKE / TRIP BOOLEANS  (identical to Phase 1)
# ===========================================================================
def create_rake_assignment_variables(model, trips, data, trip_vars):
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

            # R10: over-threshold rakes never serve
            if mileage >= config.MAINTENANCE_THRESHOLD_KM:
                model.Add(var == 0)
                continue

            # Home-lock: a rake cannot serve the single earliest trip of the
            # opposite terminal (safe, small block). Now also handles MUTTOM.
            if home == "ALVA":
                if earliest_tpht is not None and trip_vars[tid]["start"] == earliest_tpht and trip_vars[tid]["first_stop"] == "TPHT":
                    model.Add(var == 0)
                    continue
                if earliest_mutt is not None and trip_vars[tid]["start"] == earliest_mutt and trip_vars[tid]["first_stop"] == "MUTT":
                    model.Add(var == 0)
                    continue
            if home == "TPHT":
                if earliest_alva is not None and trip_vars[tid]["start"] == earliest_alva and trip_vars[tid]["first_stop"] == "ALVA":
                    model.Add(var == 0)
                    continue
                if earliest_mutt is not None and trip_vars[tid]["start"] == earliest_mutt and trip_vars[tid]["first_stop"] == "MUTT":
                    model.Add(var == 0)
                    continue
            if home == "MUTTOM":
                if earliest_alva is not None and trip_vars[tid]["start"] == earliest_alva and trip_vars[tid]["first_stop"] == "ALVA":
                    model.Add(var == 0)
                    continue
                if earliest_tpht is not None and trip_vars[tid]["start"] == earliest_tpht and trip_vars[tid]["first_stop"] == "TPHT":
                    model.Add(var == 0)
                    continue

    return rake_trip


# ===========================================================================
# R1 — SERVICE COVERAGE  (MODIFIED in Phase 5)
# ===========================================================================
def add_r1_service_coverage(model, trip_vars, rake_trip, data, dropped):
    """Phase 5 R1: every trip is either served by exactly one rake OR dropped.

    sum_{rakes} rake_trip[rake, trip] + dropped[trip] == 1
    """
    rakes = list(data.service_rakes["rake_id"])
    for tid in trip_vars:
        model.Add(
            sum(rake_trip[(rid, tid)] for rid in rakes) + dropped[tid] == 1
        )


# ===========================================================================
# R3 — OPERATING WINDOW  (identical to Phase 1)
# ===========================================================================
def add_r3_operating_window(model, trip_vars):
    for tid, tv in trip_vars.items():
        model.Add(tv["start"] >= config.OPERATING_START_SEC)
        model.Add(tv["start"] < config.OPERATING_END_SEC)


# ===========================================================================
# R4 — FLEET AVAILABILITY  (identical to Phase 1)
# ===========================================================================
def add_r4_fleet_availability(model, trip_vars, rake_trip, data):
    return


# ===========================================================================
# R5 — RAKE NON-OVERLAP  (identical to Phase 1)
# ===========================================================================
def add_r5_rake_non_overlap(model, trip_vars, rake_trip, data):
    for _, r in data.service_rakes.iterrows():
        rid = r["rake_id"]
        opt_intervals = []
        for tid, tv in trip_vars.items():
            opt = model.NewOptionalIntervalVar(
                tv["start"], tv["duration"], tv["end"],
                rake_trip[(rid, tid)],
                f"opt_{rid}_{tid}",
            )
            opt_intervals.append(opt)
        model.AddNoOverlap(opt_intervals)


# ===========================================================================
# R6 — TURNAROUND  (identical to Phase 1)
# ===========================================================================
def add_r6_turnaround(model, trip_vars, rake_trip, data):
    turnaround = config.TERMINAL_TURNAROUND_MIN * 60
    deadhead = config.TERMINAL_TO_TERMINAL_DEADHEAD_MIN * 60
    rakes = list(data.service_rakes["rake_id"])

    tids = list(trip_vars.keys())
    same_pairs = 0
    cross_pairs = 0
    both_impossible = 0
    one_way_only = 0
    both_possible = 0

    for i in range(len(tids)):
        a_id = tids[i]
        a = trip_vars[a_id]
        for j in range(i + 1, len(tids)):
            b_id = tids[j]
            b = trip_vars[b_id]

            gap_ab = turnaround if a["last_stop"] == b["first_stop"] else deadhead
            gap_ba = turnaround if b["last_stop"] == a["first_stop"] else deadhead

            if gap_ab == turnaround or gap_ba == turnaround:
                same_pairs += 1
            if gap_ab == deadhead or gap_ba == deadhead:
                cross_pairs += 1

            a_b_possible = b["start"] >= a["end"] + gap_ab
            b_a_possible = a["start"] >= b["end"] + gap_ba

            if a_b_possible and b_a_possible:
                both_possible += 1
            elif a_b_possible or b_a_possible:
                one_way_only += 1
            else:
                both_impossible += 1
                for rid in rakes:
                    model.Add(rake_trip[(rid, a_id)] + rake_trip[(rid, b_id)] <= 1)

    print(
        f"[r6] pairs: same={same_pairs} cross={cross_pairs} "
        f"| both_impossible={both_impossible} one_way={one_way_only} both_possible={both_possible}"
    )


# ===========================================================================
# R7 — RUNNING TIME  (identical to Phase 1)
# ===========================================================================
def add_r7_running_time(model, trip_vars):
    return


# ===========================================================================
# R8 — SKIPPED  (identical to Phase 1)
# ===========================================================================
def add_r8_depot_capacity(model, trip_vars, rake_trip, data):
    return


# ===========================================================================
# R9 — vacuous  (identical to Phase 1)
# ===========================================================================
def add_r9_maintenance_exclusivity(model, trip_vars, rake_trip, data):
    return


# ===========================================================================
# R10 — maintenance threshold  (identical to Phase 1)
# ===========================================================================
def add_r10_maintenance_threshold(model, trip_vars, rake_trip, data):
    threshold = config.MAINTENANCE_THRESHOLD_KM
    for _, r in data.service_rakes.iterrows():
        rid = r["rake_id"]
        if int(r["initial_mileage_km"]) >= threshold:
            for tid in trip_vars:
                model.Add(rake_trip[(rid, tid)] == 0)


# ===========================================================================
# R11 — TERMINAL CONTINUITY with DEADHEAD  (identical to Phase 1)
# ===========================================================================
def add_r11_terminal_continuity(model, trip_vars, rake_trip, data):
    turnaround = config.TERMINAL_TURNAROUND_MIN * 60
    depot_open = config.OPERATING_START_SEC

    def deadhead_seconds(home, start_stop):
        if home == start_stop:
            return 0
        if home in ("ALVA", "TPHT") and start_stop in ("ALVA", "TPHT"):
            return config.TERMINAL_TO_TERMINAL_DEADHEAD_MIN * 60
        return config.MUTTOM_TO_TERMINAL_DEADHEAD_MIN * 60

    for _, r in data.service_rakes.iterrows():
        rid = r["rake_id"]
        home = r["initial_location"]

        for tid, tv in trip_vars.items():
            if tv["first_stop"] == home:
                continue

            dh = deadhead_seconds(home, tv["first_stop"])
            can_be_first_via_deadhead = tv["start"] >= depot_open + dh

            if can_be_first_via_deadhead:
                continue

            preds = [
                rake_trip[(rid, p)]
                for p, pv in trip_vars.items()
                if pv["last_stop"] == tv["first_stop"]
                and pv["arr_sec"] + turnaround <= tv["start"]
            ]
            if not preds:
                model.Add(rake_trip[(rid, tid)] == 0)
            else:
                model.Add(rake_trip[(rid, tid)] <= sum(preds))


# ===========================================================================
# R12 — no-op  (identical to Phase 1)
# ===========================================================================
def add_r12_nonservice_window(model, trip_vars):
    return


# ===========================================================================
# OBJECTIVE (Phase 1 structure, Phase 5 drop penalty added)
# ===========================================================================
def add_obj6_rake_balance(model, trip_vars, rake_trip, data):
    """Identical to Phase 1."""
    terms = []
    n_rakes = len(data.service_rakes)
    if n_rakes == 0:
        return terms
    target = len(trip_vars) // n_rakes
    for _, r in data.service_rakes.iterrows():
        rid = r["rake_id"]
        count = sum(rake_trip[(rid, tid)] for tid in trip_vars)
        dev = model.NewIntVar(0, len(trip_vars), f"bal_{rid}")
        model.Add(dev >= count - target)
        model.Add(dev >= target - count)
        terms.append(dev)
    return terms


def build_objective(model, o6, dropped):
    """Minimize  OBJ_SCALE * ( W_RAKE_BALANCE * sum(balance_devs)
                             + W_DROP          * sum(dropped) ).

    Same structure as Phase 1, with the drop penalty added.
    """
    scale = config.OBJ_SCALE
    g_bal = int(config.W_RAKE_BALANCE * scale)
    g_drop = int(R5.W_DROP * scale)
    model.Minimize(
        g_bal * sum(o6) + g_drop * sum(dropped.values())
    )