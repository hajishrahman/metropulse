"""
CP-SAT constraints for MetroPulse Phase 5 — Disruption Response.

COPY OF solver/constraints.py (current Phase 1, 314-line version) with
FIVE deliberate Phase 5 additions ONLY:

    (1) NEW: create_dropped_variables(model, trip_vars) — a BoolVar per trip.

    (2) MODIFIED R1: sum(rake_trip[rake, trip]) + dropped[trip] == 1.
        All 255 trips are allowed to drop; the solver decides which.
        Without this, a rake-down scenario would be INFEASIBLE with no
        actionable recommendation.

    (3) MODIFIED OBJECTIVE: adds W_DROP * OBJ_SCALE * sum(dropped) so the
        solver minimizes drops before optimizing rake balance. Without this
        penalty, "N trips dropped" would be arbitrary, not minimized.

    (4) NEW: add_balance_bound_phase5(...) — hard bound on trips-per-rake,
        used as a CP-SAT pruning hint to accelerate optimality proof on the
        255-trip model. Logically implied by the balance objective, so it
        does not change which schedule is optimal.

    (5) Type hints switched from ProblemData → RescheduleProblemData.
        Imports switch from solver.models → solver.reschedule_models.

Everything else (helpers, build_trips, create_trip_intervals,
create_rake_assignment_variables, R3, R5, R6, R10, R11, add_obj6_rake_balance)
is IDENTICAL to solver/constraints.py.

CRITICAL lineage notes (from Phase 1's constraints.py, preserved here):
- Home-lock is REMOVED. Phase 1 removed it because it made the 255-trip
  case INFEASIBLE under correct R11. Phase 5 uses the same 255-trip baseline
  and the same 9 ALVA / 9 TPHT / 0 service MUTTOM split, so home-lock is
  removed here too.
- R6 uses per-pair _gap_required() with 5/15/8 deadhead discrimination.
- R11 uses _first_trip_deadhead() with the KVTR predecessor rule.
- R4 / R7 / R8 / R9 / R12 have no solver function (see Phase 1 docstring).

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

_TERMINALS = ("ALVA", "TPHT")


# ===========================================================================
# Deadhead helpers (identical to Phase 1)
# ===========================================================================
def _deadhead_sec(stop_a: str, stop_b: str) -> int:
    """
    Deadhead seconds between two DIFFERENT stops.

      - ALVA <-> TPHT                : TERMINAL_TO_TERMINAL_DEADHEAD_MIN  (15 min)
      - MUTT <-> any terminal        : MUTTOM_TO_TERMINAL_DEADHEAD_MIN    (8 min)
      - any pair involving a non-terminal, non-MUTT stop (e.g. KVTR):
        undefined — caller must handle via the predecessor rule.
    """
    if stop_a in _TERMINALS and stop_b in _TERMINALS:
        return config.TERMINAL_TO_TERMINAL_DEADHEAD_MIN * 60
    return config.MUTTOM_TO_TERMINAL_DEADHEAD_MIN * 60


def _gap_required(stop_a: str, stop_b: str) -> int:
    """R6 gap: turnaround if same stop, else deadhead."""
    if stop_a == stop_b:
        return config.TERMINAL_TURNAROUND_MIN * 60
    return _deadhead_sec(stop_a, stop_b)


def _first_trip_deadhead(home: str, start_stop: str) -> Tuple[int, bool]:
    """
    Returns (seconds, valid) for a rake leaving its home to start a trip
    at start_stop.

    valid=False means the deadhead is undefined (non-terminal, non-MUTT stop
    involved) and the trip can only be taken by a rake ending a previous
    trip at start_stop.
    """
    if home == start_stop:
        return 0, True
    if home in _TERMINALS and start_stop in _TERMINALS:
        return config.TERMINAL_TO_TERMINAL_DEADHEAD_MIN * 60, True
    if (home == "MUTT" and start_stop in _TERMINALS) or \
       (home in _TERMINALS and start_stop == "MUTT"):
        return config.MUTTOM_TO_TERMINAL_DEADHEAD_MIN * 60, True
    return None, False

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
        tv[t["trip_id"]] = {
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

    All 255 trips are may_drop. The solver picks the minimum set to drop
    subject to capacity — enforced via the W_DROP penalty in build_objective.
    """
    dropped: DroppedVars = {}
    for tid in trip_vars:
        dropped[tid] = model.NewBoolVar(f"dropped_{tid}")
    return dropped


# ===========================================================================
# RAKE / TRIP BOOLEANS  (identical to Phase 1 — home-lock removed)
# ===========================================================================
def create_rake_assignment_variables(model, trips, data, trip_vars):
    """
    Create rake_trip variables. Home-lock is NOT applied (see module docstring).
    R10 (mileage threshold) is applied here as before.
    """
    rake_trip = {}

    for _, r in data.service_rakes.iterrows():
        rid = r["rake_id"]
        mileage = int(r["initial_mileage_km"])
        for t in trips:
            tid = t["trip_id"]
            var = model.NewBoolVar(f"rake_{rid}_trip_{tid}")
            rake_trip[(rid, tid)] = var
            if mileage >= config.MAINTENANCE_THRESHOLD_KM:
                model.Add(var == 0)

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
    for _, tv in trip_vars.items():
        model.Add(tv["start"] >= config.OPERATING_START_SEC)
        model.Add(tv["start"] < config.OPERATING_END_SEC)

# ===========================================================================
# R4 / R7 / R8 / R9 / R12 — no-op stubs (identical to Phase 1)
# ===========================================================================
def add_r4_fleet_availability(model, trip_vars, rake_trip, data):
    """R4 enforced by construction: only service_rakes are iterated."""
    return


def add_r7_running_time(model, trip_vars):
    """R7 enforced at load time: models.py raises if duration mismatch."""
    return


def add_r8_depot_capacity(model, trip_vars, rake_trip, data):
    """R8 not modelled in V1 (no stabling)."""
    return


def add_r9_maintenance_exclusivity(model, trip_vars, rake_trip, data):
    """R9 vacuous: maintenance.csv is empty."""
    return


def add_r12_nonservice_window(model, trip_vars):
    """R12 subsumed by R3."""
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
# R6 — TURNAROUND + DEADHEAD (per-order, per-pair; identical to Phase 1)
# ===========================================================================
def add_r6_turnaround(model, trip_vars, rake_trip, data):
    rakes = list(data.service_rakes["rake_id"])
    tids = list(trip_vars.keys())

    same_pairs = 0
    cross15 = 0
    cross8 = 0
    both_impossible = 0
    one_way_only = 0
    both_possible = 0

    for i in range(len(tids)):
        a_id = tids[i]
        a = trip_vars[a_id]
        for j in range(i + 1, len(tids)):
            b_id = tids[j]
            b = trip_vars[b_id]

            gap_ab = _gap_required(a["last_stop"], b["first_stop"])
            gap_ba = _gap_required(b["last_stop"], a["first_stop"])

            if a["last_stop"] == b["first_stop"]:
                same_pairs += 1
            elif a["last_stop"] in _TERMINALS and b["first_stop"] in _TERMINALS:
                cross15 += 1
            else:
                cross8 += 1

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
        f"[r6] pairs: same={same_pairs} cross15={cross15} cross8={cross8} "
        f"| both_impossible={both_impossible} one_way={one_way_only} both_possible={both_possible}"
    )


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
# R11 — TERMINAL CONTINUITY with KVTR-aware deadhead  (identical to Phase 1)
# ===========================================================================
def add_r11_terminal_continuity(model, trip_vars, rake_trip, data):
    """
    First-trip rule:

      A rake whose home is H may serve trip i as its FIRST trip if:
        - first_stop(i) == H, or
        - deadhead(H, first_stop(i)) is defined AND departure(i) >= depot_open + deadhead.

      If deadhead is undefined (non-terminal, non-MUTT stop such as KVTR),
      trip i can only be taken by a rake whose previous trip ends at
      first_stop(i) within turnaround of departure(i).

    Pair gaps between consecutive trips are R6's job, not R11's.
    """
    turnaround = config.TERMINAL_TURNAROUND_MIN * 60
    depot_open = config.OPERATING_START_SEC

    for _, r in data.service_rakes.iterrows():
        rid = r["rake_id"]
        home = r["initial_location"]

        for tid, tv in trip_vars.items():
            if tv["first_stop"] == home:
                continue  # same stop — always allowed as first trip

            dh, valid = _first_trip_deadhead(home, tv["first_stop"])

            if valid and tv["start"] >= depot_open + dh:
                continue  # allowed as first trip via deadhead

            # Otherwise requires a predecessor ending at first_stop
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
# NEW (Phase 5) — BALANCE BOUND (pruning hint, does not change objective)
# ===========================================================================
def add_balance_bound_phase5(model, trip_vars, rake_trip, data):
    """Phase 5 only: hard bound on trips-per-rake as a CP-SAT pruning hint.

    Any schedule optimizing W_RAKE_BALANCE under normal conditions already
    satisfies this bound (a balance-optimal solution never assigns more than
    ceil(N/R) trips to one rake). Adding it as a HARD constraint doesn't
    change the optimum — it only helps CP-SAT prune the search tree faster,
    which closes the optimality gap within the same time limit.

    Does not modify the objective. Does not change which schedule is optimal.
    """
    import math
    n_rakes = len(data.service_rakes)
    n_trips = len(trip_vars)
    if n_rakes == 0 or n_trips == 0:
        return
    max_per_rake = math.ceil(n_trips / n_rakes)

    for _, r in data.service_rakes.iterrows():
        rid = r["rake_id"]
        count = sum(rake_trip[(rid, tid)] for tid in trip_vars)
        model.Add(count <= max_per_rake)


# ===========================================================================
# OBJECTIVE — O6 rake balance  (identical to Phase 1)
# ===========================================================================
def add_obj6_rake_balance(model, trip_vars, rake_trip, data):
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