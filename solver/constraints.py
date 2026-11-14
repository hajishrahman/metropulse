"""
CP-SAT constraints for MetroPulse — V1 (255 GTFS trips, window [04:40, 24:00)).

R6  — turnaround + deadhead, applied PER ORDER with per-pair deadhead:
        5 min  same terminal         (TERMINAL_TURNAROUND_MIN)
        15 min ALVA <-> TPHT         (TERMINAL_TO_TERMINAL_DEADHEAD_MIN)
        8 min  MUTT <-> terminal     (MUTTOM_TO_TERMINAL_DEADHEAD_MIN)

R11 — first-trip home rule with deadhead allowance.
        A rake whose home is H may start the day at stop S if either:
          - S == H, or
          - deadhead(H, S) is defined AND departure >= depot_open + deadhead(H, S)
        Stops that are neither terminals nor MUTT (e.g., KVTR) have NO valid
        deadhead — a trip starting there can only be taken by a rake that
        ends a previous trip at that same stop (predecessor rule).

Notes
-----
- Home-lock removed: the earlier "block the earliest opposite-terminal trip"
  pruning is gone. It made the 255-trip case INFEASIBLE under correct R11.
- R2 (headway) is not modelled — trip times are fixed by GTFS.
- R4 (fleet availability) has no solver function — enforced by construction:
  only service_rakes are iterated in create_rake_assignment_variables, so
  maintenance rakes have no trip variables at all.
- R7 (running time) has no solver function — enforced at load time:
  models.py::ProblemData.load() raises ValueError if duration != arrival - departure.
- R8 / R9 / R12 also have no solver function:
    * R8 (depot capacity) is not modelled in V1.
    * R9 (maintenance exclusivity) is vacuous — maintenance.csv is empty.
    * R12 (non-service window) is subsumed by R3.
  All of R4, R7, R8, R9, R12 are still re-checked by solver/validator.py.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from ortools.sat.python import cp_model

from solver import config
from solver.models import ProblemData


RakeTripVars = Dict[Tuple[str, str], cp_model.IntVar]

_TERMINALS = ("ALVA", "TPHT")


# ===========================================================================
# Deadhead helpers
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
def build_trips(data: ProblemData) -> List[dict]:
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
# RAKE / TRIP BOOLEANS
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
# R1 — SERVICE COVERAGE
# ===========================================================================
def add_r1_service_coverage(model, trip_vars, rake_trip, data):
    rakes = list(data.service_rakes["rake_id"])
    for tid in trip_vars:
        model.Add(sum(rake_trip[(rid, tid)] for rid in rakes) == 1)


# ===========================================================================
# R3 — OPERATING WINDOW
# ===========================================================================
def add_r3_operating_window(model, trip_vars):
    for _, tv in trip_vars.items():
        model.Add(tv["start"] >= config.OPERATING_START_SEC)
        model.Add(tv["start"] < config.OPERATING_END_SEC)


# ===========================================================================
# R5 — RAKE NON-OVERLAP
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
# R6 — TURNAROUND + DEADHEAD (per-order, per-pair)
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
# R10 — maintenance threshold (redundant with create_rake_assignment_variables)
# ===========================================================================
def add_r10_maintenance_threshold(model, trip_vars, rake_trip, data):
    threshold = config.MAINTENANCE_THRESHOLD_KM
    for _, r in data.service_rakes.iterrows():
        rid = r["rake_id"]
        if int(r["initial_mileage_km"]) >= threshold:
            for tid in trip_vars:
                model.Add(rake_trip[(rid, tid)] == 0)


# ===========================================================================
# R11 — TERMINAL CONTINUITY with KVTR-aware deadhead (first-trip rule only)
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
# OBJECTIVE — O6 rake balance
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


def build_objective(model, o6):
    scale = config.OBJ_SCALE
    g = int(config.W_RAKE_BALANCE * scale)
    model.Minimize(g * sum(o6))