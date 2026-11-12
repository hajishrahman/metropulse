"""
CP-SAT constraints for MetroPulse — V1 (232 full-route GTFS trips).

R11 updated: cross-terminal switches are ALLOWED, but the rake must have
            TERMINAL_TO_TERMINAL_DEADHEAD_MIN minutes between the arrival
            of the previous trip and the departure of the next trip.

The rest of the rules are unchanged.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from ortools.sat.python import cp_model

from solver import config
from solver.models import ProblemData


RakeTripVars = Dict[Tuple[str, str], cp_model.IntVar]


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
        tid = t["trip_id"]
        start = t["dep_sec"]
        end = t["arr_sec"]
        dur = t["duration_sec"]
        tv[tid] = {
            "start": start,
            "end": end,
            "duration": dur,
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
    for tid, tv in trip_vars.items():
        model.Add(tv["start"] >= config.OPERATING_START_SEC)
        model.Add(tv["start"] < config.OPERATING_END_SEC)


# ===========================================================================
# R4 — FLEET AVAILABILITY
# ===========================================================================
def add_r4_fleet_availability(model, trip_vars, rake_trip, data):
    return


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
# R6 — TURNAROUND (same-terminal minimum gap; deadhead covers cross-terminal)
# ===========================================================================
def add_r6_turnaround(model, trip_vars, rake_trip, data):
    """
    R6 — terminal turnaround + deadhead, applied per ORDER.

    Trip times are fixed, so each pair is either compatible in at least one
    order or cannot share a rake. Forbid only pairs where neither order has
    enough turnaround or deadhead time.
    """
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

            # Required gap in each direction, based on terminal match
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
                # Fixed trip times make both orders impossible for this rake.
                both_impossible += 1
                for rid in rakes:
                    model.Add(rake_trip[(rid, a_id)] + rake_trip[(rid, b_id)] <= 1)

    print(
        f"[r6] pairs: same={same_pairs} cross={cross_pairs} "
        f"| both_impossible={both_impossible} one_way={one_way_only} both_possible={both_possible}"
    )

# ===========================================================================
# R7 — RUNNING TIME (fixed)
# ===========================================================================
def add_r7_running_time(model, trip_vars):
    return


# ===========================================================================
# R8 — SKIPPED
# ===========================================================================
def add_r8_depot_capacity(model, trip_vars, rake_trip, data):
    return


# ===========================================================================
# R9 — vacuous
# ===========================================================================
def add_r9_maintenance_exclusivity(model, trip_vars, rake_trip, data):
    return


# ===========================================================================
# R10 — maintenance threshold
# ===========================================================================
def add_r10_maintenance_threshold(model, trip_vars, rake_trip, data):
    threshold = config.MAINTENANCE_THRESHOLD_KM
    for _, r in data.service_rakes.iterrows():
        rid = r["rake_id"]
        if int(r["initial_mileage_km"]) >= threshold:
            for tid in trip_vars:
                model.Add(rake_trip[(rid, tid)] == 0)


# ===========================================================================
# R11 — TERMINAL CONTINUITY with DEADHEAD
# ===========================================================================
def add_r11_terminal_continuity(model, trip_vars, rake_trip, data):
    """
    R11 — first-trip home rule with depot-opening relaxation.

    A rake whose home is H can take a trip starting at S as its FIRST trip if:
      - S == H, OR
      - the trip departs no earlier than
            DEPOT_OPENING_TIME + deadhead(H, S)

    DEPOT_OPENING_TIME = 06:00:00 (config.OPERATING_START_SEC)
    Deadhead times:
      ALVA <-> TPHT:       15 min
      MUTTOM <-> terminal:  8 min

    Otherwise, the trip must follow an earlier trip ending at that
    terminal with turnaround room.

    Pair gaps are enforced by R6. R11 adds only the first-trip rule.
    """
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
                continue  # same terminal — always allowed as first trip

            # Can this trip be a first trip via a pre-trip deadhead from home?
            dh = deadhead_seconds(home, tv["first_stop"])
            can_be_first_via_deadhead = tv["start"] >= depot_open + dh

            if can_be_first_via_deadhead:
                continue  # allowed as a first trip

            # Otherwise requires a predecessor ending at tv.first_stop
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
# R12 — no-op (covered by R3)
# ===========================================================================
def add_r12_nonservice_window(model, trip_vars):
    return


# ===========================================================================
# OBJECTIVE (kept for later; feasibility probe skips it)
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
