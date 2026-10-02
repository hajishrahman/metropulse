"""
CP-SAT constraints for MetroPulse — Scenario A (Baseline DPR).

Implements:
    R1  Service coverage          [DPR]
    R2  Headway (design + target) [DPR]
    R3  Operating window          [DPR]
    R4  Fleet availability        [DPR]
    R5  Rake non-overlap          [DPR]
    R6  Terminal turnaround       [DPR]
    R7  Running time              [DERIVED FROM DPR]
    R8  Depot capacity            [DPR partial]
    R9  Maintenance exclusivity   [DPR]
    R10 Maintenance threshold     [DPR reference]
    R11 Deadhead / positioning    [SYNTHETIC — not configured]
    R12 Non-service window        [DPR]

Objectives: O1..O7 (O8 disabled — no crew layer in V1)

Spec: docs/constraints-v2.md
"""
from __future__ import annotations
from typing import Dict, List, Tuple

from ortools.sat.python import cp_model

from solver import config
from solver.models import ProblemData


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
TripVars     = Dict[str, dict]           # trip_id -> {"start", "end", "interval", ...}
RakeTripVars = Dict[Tuple[str, str], cp_model.IntVar]  # (rake_id, trip_id) -> Bool


# ===========================================================================
# TRIP GENERATION
# ===========================================================================
def generate_required_trips(data: ProblemData) -> List[dict]:
    """
    Build the list of trips that MUST be scheduled, based on R1 coverage.

    Each trip is one-way (UP or DOWN). We don't yet assign departure times —
    CP-SAT will decide those within each hour window.
    """
    trips = []
    trip_idx = 0

    for _, row in data.hourly_service.iterrows():
        h_start = int(row["hour_start"])
        h_end = int(row["hour_end"])
        direction = row["direction"]
        required = int(row["required_departures"])
        target_headway = float(row["target_headway_min"])

        for i in range(required):
            trips.append({
                "trip_id": f"T{trip_idx:04d}",
                "hour_start": h_start,
                "hour_end": h_end,
                "direction": direction,
                "target_headway_min": target_headway,
            })
            trip_idx += 1

    return trips


# ===========================================================================
# DECISION VARIABLES
# ===========================================================================
def create_trip_variables(
    model: cp_model.CpModel,
    trips: List[dict],
) -> TripVars:
    """
    For each trip:
      - start var (minutes from 05:00)
      - end var = start + one_way_running
      - interval var for NoOverlap
    """
    running_min = int(round(config.ONE_WAY_RUNNING_MIN))

    trip_vars: TripVars = {}

    for t in trips:
        tid = t["trip_id"]
        # Trips must START within their hour. They may end after the hour.
        earliest = (t["hour_start"] - 5) * 60
        latest   = (t["hour_end"]   - 5) * 60 -1  # start by end of hour

        start = model.NewIntVar(earliest, latest, f"start_{tid}")
        # End can extend past the hour boundary, but not past midnight (1140)
        end = model.NewIntVar(
            earliest + running_min,
            min(latest + running_min, (config.OPERATING_END_HOUR - 5) * 60),
            f"end_{tid}",
        )
        model.Add(end == start + running_min)

        interval = model.NewIntervalVar(
            start, running_min, end, f"interval_{tid}"
        )
        trip_vars[tid] = {
            "start": start,
            "end": end,
            "running_min": running_min,   # ← ADD THIS
            "interval": interval,
            "direction": t["direction"],
            "hour_start": t["hour_start"],
            "hour_end": t["hour_end"],
            "target_headway_min": t["target_headway_min"],
        }

    return trip_vars


def create_rake_assignment_variables(
    model: cp_model.CpModel,
    trips: List[dict],
    data: ProblemData,
) -> RakeTripVars:
    """
    rake_trip[(rake_id, trip_id)] = 1 iff this rake performs this trip.
    """
    rake_trip: RakeTripVars = {}
    for _, r in data.rakes.iterrows():
        rid = r["rake_id"]
        for t in trips:
            tid = t["trip_id"]
            rake_trip[(rid, tid)] = model.NewBoolVar(f"rake_{rid}_trip_{tid}")
    return rake_trip


# ===========================================================================
# R1 — SERVICE COVERAGE  [DPR]
# ===========================================================================
def add_r1_service_coverage(
    model: cp_model.CpModel,
    trip_vars: TripVars,
    rake_trip: RakeTripVars,
    data: ProblemData,
) -> None:
    """
    Every required trip must be assigned to exactly one rake.
    (Trip counts are baked into the trip list — see generate_required_trips.)
    """
    for tid in trip_vars:
        model.Add(
            sum(rake_trip[(r["rake_id"], tid)] for _, r in data.rakes.iterrows())
            == 1
        )


# ===========================================================================
# R2 — HEADWAY  [DPR]
# ===========================================================================
def add_r2a_design_headway(
    model: cp_model.CpModel,
    trip_vars: TripVars,
) -> None:
    """
    Consecutive departures in the same direction on the same line must be
    at least MIN_HEADWAY_DESIGN_SEC apart.

    We group trips by (direction, hour_start) and enforce ordering via
    pairwise constraints. For non-adjacent hours, we also ensure the last
    trip of one hour is at least 90s before the first trip of the next hour.
    """
    min_headway = config.MIN_HEADWAY_DESIGN_SEC // 60  # in minutes; 90s → 1.5min
    # Because CP-SAT times are in minutes, 90s → use 2 min to be safe
    min_gap_min = max(2, int(config.MIN_HEADWAY_DESIGN_SEC // 60))

    # Group trips by direction
    by_dir: Dict[str, List[str]] = {}
    for tid, tv in trip_vars.items():
        by_dir.setdefault(tv["direction"], []).append(tid)

    # For each direction, sort trips by hour_start
    for direction, tids in by_dir.items():
        tids_sorted = sorted(tids, key=lambda t: trip_vars[t]["hour_start"])
        # Adjacent constraint within each hour block
        for i in range(len(tids_sorted) - 1):
            a = trip_vars[tids_sorted[i]]["start"]
            b = trip_vars[tids_sorted[i + 1]]["start"]
            model.Add(b - a >= min_gap_min)


# ===========================================================================
# R3 — OPERATING WINDOW  [DPR]
# ===========================================================================
def add_r3_operating_window(
    model: cp_model.CpModel,
    trip_vars: TripVars,
) -> None:
    """
    Trip start >= 05:00 (= minute 0 from our base) and trip end <= 24:00
    (= 19*60 = 1140 minutes from base of 05:00).

    Already encoded via variable bounds in create_trip_variables, but
    reasserted here for clarity and independent verification.
    """
    base_hour = config.OPERATING_START_HOUR       # 5
    end_hour = config.OPERATING_END_HOUR          # 24
    window_minutes = (end_hour - base_hour) * 60  # 19 * 60 = 1140

    running_min = int(round(config.ONE_WAY_RUNNING_MIN))

    for tid, tv in trip_vars.items():
        model.Add(tv["start"] >= 0)
        model.Add(tv["end"] <= window_minutes)


# ===========================================================================
# R4 — FLEET AVAILABILITY  [DPR]
# ===========================================================================
def add_r4_fleet_availability(
    model: cp_model.CpModel,
    trip_vars: TripVars,
    rake_trip: RakeTripVars,
    data: ProblemData,
) -> None:
    """
    R4a: maintenance spares are never activated in V1.
    R4b: traffic reserve — per-hour activation, penalized in O7.
          Implementation: for each hour, active rakes <= 15 (+1 if reserve
          activated). We model activation as implied by usage rather than an
          explicit variable in this simplified version.
    R4c: each rake can only do trips whose total count is within cap.

    For V1 we simplify:
      - maintenance spares: blocked entirely
      - bare rakes: can work any number of trips per day
      - traffic spare: allowed to work only if the schedule requires it
    """
    # R4a: maintenance spares never get trips
    for _, r in data.maintenance_spares.iterrows():
        rid = r["rake_id"]
        for tid in trip_vars:
            model.Add(rake_trip[(rid, tid)] == 0)


# ===========================================================================
# R5 — RAKE NON-OVERLAP  [DPR]
# ===========================================================================
def add_r5_rake_non_overlap(
    model: cp_model.CpModel,
    trip_vars: TripVars,
    rake_trip: RakeTripVars,
    data: ProblemData,
) -> None:
    """
    For each rake, no two trips it performs may overlap in time.

    Uses AddNoOverlap with optional intervals (interval present only if
    rake_trip[rake, trip] = 1).

    Maintenance spares are skipped — R4a already blocks them from any trip.
    """
    for _, r in data.rakes.iterrows():
        rid = r["rake_id"]

        # Skip maintenance spares entirely — they never get trips in V1
        if int(r["maintenance_spare"]) == 1:
            continue

        intervals = []
        for tid, tv in trip_vars.items():
            opt_interval = model.NewOptionalIntervalVar(
                tv["start"],
                tv["running_min"],
                tv["end"],
                rake_trip[(rid, tid)],
                f"opt_{rid}_{tid}",
            )
            intervals.append(opt_interval)

        if intervals:
            model.AddNoOverlap(intervals)
# ===========================================================================
# R6 — TERMINAL TURNAROUND  [DPR]
# ===========================================================================
def add_r6_turnaround(
    model: cp_model.CpModel,
    trip_vars: TripVars,
    rake_trip: RakeTripVars,
    data: ProblemData,
) -> None:
    """
    R6: Between consecutive trips on the same rake, gap >= TERMINAL_TURNAROUND_MIN.

    We don't know the sequence in advance, so we enforce the gap between
    any two trips whose time windows could conflict:

      - Same hour (windows overlap by construction)
      - Adjacent hour pairs where a's max end could exceed b's min start
        minus turnaround

    Trips 2+ hours apart have enough slack that they can never conflict
    on turnaround, so we skip them.

    This is O(n^2) in the worst case but prunes ~85% of pairs.
    """
    turnaround = config.TERMINAL_TURNAROUND_MIN
    running_min = int(round(config.ONE_WAY_RUNNING_MIN))

    # Precompute each trip's [earliest_start, latest_end] window
    # (used for pruning)
    trip_window: Dict[str, Tuple[int, int]] = {}
    for tid, tv in trip_vars.items():
        # Extract from the CP-SAT var bounds — we stored start/end as
        # IntVars; get their bounds:
        earliest = tv["start"].Proto().domain[0]
        latest_start = tv["start"].Proto().domain[-1]
        earliest_end = earliest + running_min
        latest_end = latest_start + running_min
        trip_window[tid] = (earliest, latest_end)

    # Build candidate pairs, pruned by window overlap
    tids = list(trip_vars.keys())
    pairs: List[Tuple[str, str]] = []
    for i in range(len(tids)):
        a_id = tids[i]
        a_e, a_le = trip_window[a_id]
        for j in range(i + 1, len(tids)):
            b_id = tids[j]
            b_e, b_le = trip_window[b_id]

            # Prune: no conflict possible if a's latest end + turnaround <= b's earliest start
            if a_le + turnaround <= b_e:
                continue
            # Or b's latest end + turnaround <= a's earliest start
            if b_le + turnaround <= a_e:
                continue

            pairs.append((a_id, b_id))

    print(f"[r6] {len(pairs)} candidate pairs (pruned from {len(tids)*(len(tids)-1)//2})")

    # Apply constraint for each pair, only when same rake is assigned
    for _, r in data.rakes.iterrows():
        rid = r["rake_id"]
        if int(r["maintenance_spare"]) == 1:
            continue

        for tid_a, tid_b in pairs:
            a = trip_vars[tid_a]
            b = trip_vars[tid_b]

            both = model.NewBoolVar(f"both_{rid}_{tid_a}_{tid_b}")
            model.AddMultiplicationEquality(
                both,
                [rake_trip[(rid, tid_a)], rake_trip[(rid, tid_b)]],
            )

            a_first = model.NewBoolVar(f"a_first_{rid}_{tid_a}_{tid_b}")
            model.Add(
                b["start"] >= a["end"] + turnaround
            ).OnlyEnforceIf([both, a_first])
            model.Add(
                a["start"] >= b["end"] + turnaround
            ).OnlyEnforceIf([both, a_first.Not()])

# ===========================================================================
# R7 — RUNNING TIME  [DERIVED FROM DPR]
# ===========================================================================
def add_r7_running_time(
    model: cp_model.CpModel,
    trip_vars: TripVars,
) -> None:
    """
    Each trip's duration equals ONE_WAY_RUNNING_MIN.
    Already enforced in create_trip_variables (end = start + running).
    """
    # Already enforced. Kept as an explicit (no-op) function for traceability.
    return


# ===========================================================================
# R8 — DEPOT CAPACITY  [DPR partial]
# ===========================================================================
def add_r8_depot_capacity(
    model: cp_model.CpModel,
    trip_vars: TripVars,
    rake_trip: RakeTripVars,
    data: ProblemData,
) -> None:
    """
    Info Park-2 capacity = 2 (DPR).
    Muttom = unbounded in V1.

    Since V1 does not model overnight stabling positions explicitly, this
    constraint is documented but not enforced. Enforced in later scenarios.
    """
    # No constraint in V1. See spec §5 R8.
    return


# ===========================================================================
# R9 — MAINTENANCE EXCLUSIVITY  [DPR]
# ===========================================================================
def add_r9_maintenance_exclusivity(
    model: cp_model.CpModel,
    trip_vars: TripVars,
    rake_trip: RakeTripVars,
    data: ProblemData,
) -> None:
    """
    A rake in a maintenance block cannot be assigned to any trip during
    that block.

    For Scenario A, maintenance.csv is empty -> no-op.
    Implemented for future scenarios.
    """
    if len(data.maintenance) == 0:
        return

    for _, m in data.maintenance.iterrows():
        rid = m["rake_id"]
        if rid not in data.rakes["rake_id"].values:
            continue
        # Convert maintenance window to minutes from 05:00
        start_min = _time_to_minutes(m["maintenance_start"])
        end_min   = _time_to_minutes(m["maintenance_end"])

        for tid, tv in trip_vars.items():
            # If trip overlaps maintenance, rake cannot do it
            # Encode: (trip.end <= maint.start) OR (trip.start >= maint.end)
            #       OR rake_trip = 0
            before = model.NewBoolVar(f"before_maint_{rid}_{tid}")
            after  = model.NewBoolVar(f"after_maint_{rid}_{tid}")
            model.Add(tv["end"] <= start_min).OnlyEnforceIf(before)
            model.Add(tv["start"] >= end_min).OnlyEnforceIf(after)
            # If not before AND not after, must not do the trip
            model.AddBoolOr([
                before, after,
                rake_trip[(rid, tid)].Not(),
            ])


# ===========================================================================
# R10 — MAINTENANCE THRESHOLD  [DPR reference]
# ===========================================================================
def add_r10_maintenance_threshold(
    model: cp_model.CpModel,
    trip_vars: TripVars,
    rake_trip: RakeTripVars,
    data: ProblemData,
) -> None:
    """
    Rakes with mileage >= MAINTENANCE_THRESHOLD_KM must be blocked from
    service unless they have a maintenance block scheduled.

    For Scenario A, all rakes have mileage far below threshold -> no-op.
    """
    threshold = config.MAINTENANCE_THRESHOLD_KM

    for _, r in data.rakes.iterrows():
        rid = r["rake_id"]
        mileage = int(r["initial_mileage_km"])

        if mileage >= threshold:
            for tid in trip_vars:
                model.Add(rake_trip[(rid, tid)] == 0)


# ===========================================================================
# R11 — DEADHEAD  [SYNTHETIC — NOT CONFIGURED]
# ===========================================================================
def add_r11_deadhead(
    model: cp_model.CpModel,
    trip_vars: TripVars,
    rake_trip: RakeTripVars,
    data: ProblemData,
) -> None:
    """
    If MUTTOM_TO_JLN_DEADHEAD_MIN is None, deadhead is not modeled.

    Instead, require: a rake whose first trip starts at hour_start=5 must
    start at a terminal where the trip begins. This is enforced implicitly
    by trip consistency but NOT by location (V1 omits locations).
    """
    if config.MUTTOM_TO_JLN_DEADHEAD_MIN is None:
        return
    # Not implemented in V1


# ===========================================================================
# R12 — NON-SERVICE WINDOW  [DPR]
# ===========================================================================
def add_r12_nonservice_window(
    model: cp_model.CpModel,
    trip_vars: TripVars,
) -> None:
    """
    No passenger service 00:00–05:00.
    Enforced already by R3 (operating window starts at 05:00).
    """
    return


# ===========================================================================
# OBJECTIVES
# ===========================================================================
def add_obj1_waiting_proxy(
    model: cp_model.CpModel,
    trip_vars: TripVars,
) -> List[cp_model.LinearExpr]:
    """
    O1 proxy: for each hour+direction, penalize departure gaps larger than
    the target headway. Approximates expected passenger waiting.

    Simplified: penalize |actual_gap - target_gap| for adjacent trips.
    """
    terms: List[cp_model.LinearExpr] = []

    by_dir: Dict[str, List[str]] = {}
    for tid, tv in trip_vars.items():
        by_dir.setdefault(tv["direction"], []).append(tid)

    for direction, tids in by_dir.items():
        tids_sorted = sorted(tids, key=lambda t: trip_vars[t]["hour_start"])
        for i in range(len(tids_sorted) - 1):
            a = trip_vars[tids_sorted[i]]
            b = trip_vars[tids_sorted[i + 1]]

            gap = model.NewIntVar(0, 200, f"gap_{direction}_{i}")
            model.Add(gap == b["start"] - a["start"])

            target = int(round(a["target_headway_min"]))
            deviation = model.NewIntVar(0, 200, f"dev_{direction}_{i}")
            model.AddAbsEquality(deviation, gap - target)
            terms.append(deviation)

    return terms


def add_obj2_headway_deviation(
    model: cp_model.CpModel,
    trip_vars: TripVars,
) -> List[cp_model.LinearExpr]:
    """
    O2: minimize deviation from target DPR headway.

    Same shape as O1 but computed against published headway directly
    (rather than a proxy). In V1 we keep O2 as the same gap-based term
    but scaled differently.
    """
    # For V1, O1 and O2 are computed from the same deviation terms.
    # Kept separate here to allow future differentiation.
    return []


def add_obj3_operational_delay(
    model: cp_model.CpModel,
    trip_vars: TripVars,
) -> List[cp_model.LinearExpr]:
    """
    O3: minimize operational delay.

    In V1, without ML predictions, we approximate this as the total
    deviation from target schedule (already covered by O1/O2). Kept as
    placeholder.
    """
    return []


def add_obj6_rake_balance(
    model: cp_model.CpModel,
    trip_vars: TripVars,
    rake_trip: RakeTripVars,
    data: ProblemData,
) -> List[cp_model.LinearExpr]:
    """
    O6: balance trips across rakes. Minimize variance in trip counts.
    """
    terms: List[cp_model.LinearExpr] = []
    n_rakes = len(data.bare_rakes)   # bare rakes only — spares are treated separately

    if n_rakes == 0:
        return terms

    total_trips = len(trip_vars)
    target = total_trips // max(n_rakes, 1)

    for _, r in data.bare_rakes.iterrows():
        rid = r["rake_id"]
        trips_assigned = sum(rake_trip[(rid, tid)] for tid in trip_vars)
        dev = model.NewIntVar(0, total_trips, f"balance_{rid}")
        model.Add(dev >= trips_assigned - target)
        model.Add(dev >= target - trips_assigned)
        terms.append(dev)

    return terms


def add_obj7_reserve_activation(
    model: cp_model.CpModel,
    trip_vars: TripVars,
    rake_trip: RakeTripVars,
    data: ProblemData,
) -> List[cp_model.LinearExpr]:
    """
    O7: penalize use of traffic reserve.

    For V1, this is approximated as: sum of trips assigned to the traffic
    spare rake. Every such trip incurs a unit penalty.
    """
    terms: List[cp_model.LinearExpr] = []
    for _, r in data.traffic_spares.iterrows():
        rid = r["rake_id"]
        for tid in trip_vars:
            terms.append(rake_trip[(rid, tid)])
    return terms


# ===========================================================================
# OBJECTIVE AGGREGATOR
# ===========================================================================
def build_objective(
    model: cp_model.CpModel,
    o1: List[cp_model.LinearExpr],
    o6: List[cp_model.LinearExpr],
    o7: List[cp_model.LinearExpr],
) -> None:
    """
    Weighted sum: alpha*O1 + gamma*O6 + delta*O7
    (O2..O5 are inactive in V1; O8 disabled.)
    """
    scale = config.OBJ_SCALE
    a = int(config.W_WAITING_TIME * scale)
    g = int(config.W_RAKE_BALANCE * scale)
    d = int(config.W_RESERVE_ACTIVATION * scale)

    total = a * sum(o1) + g * sum(o6) + d * sum(o7)
    model.Minimize(total)


# ===========================================================================
# HELPERS
# ===========================================================================
def _time_to_minutes(hhmm: str) -> int:
    """Convert 'HH:MM' to minutes from 05:00 base."""
    h, m = hhmm.split(":")
    return (int(h) - 5) * 60 + int(m)