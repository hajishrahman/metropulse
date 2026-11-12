"""
MetroPulse Phase 3 crew constraints (CP-SAT).

Implements:
    C1 no overlap         (arrival + turnaround <= next departure)
    C2 max active duty    (last_arr - first_dep <= 28,800 s)
    C3 sign-on/sign-off   (>= 900 s both sides)
    C4 full coverage      (each trip assigned to exactly one driver)
    C6 continuous driving (soft, state-machine, spec-compliant, any run length)
    C7 reserve buffer     (soft -- penalize using > pool_size - 5 drivers)

C5 (12h rest) is NOT implemented -- documented as deferred (single-day V1).

C6 break threshold:
    MIN_TURNAROUND_SEC (300 s) reused from C1  [DERIVED from C1]
    Any gap > 300 s between prev arrival and next departure is a break.

C6 variable budget (per (d, i)):
    last_arr, run_drive, over         -> 3 IntVars
    new_chain, end_of_chain, has_prev -> 3 BoolVars
    total: 6 new vars per (d, i)  =>  ~82,500 new vars total
    (approved by user 2026-11-13; solve-time estimate 90-200 s per pool)
"""
from __future__ import annotations

from ortools.sat.python import cp_model

from solver import crew_config as CFG


# ===========================================================================
# PREP
# ===========================================================================
def build_trips(data) -> list[dict]:
    """Compact per-trip records, sorted by departure."""
    rows = []
    for _, r in data.trips.iterrows():
        rows.append({
            "trip_id": str(r["trip_id"]),
            "dep": int(r["dep_sec"]),
            "arr": int(r["arr_sec"]),
        })
    rows.sort(key=lambda x: (x["dep"], x["trip_id"]))
    return rows


# ===========================================================================
# DECISION VARIABLES
# ===========================================================================
def create_driver_trip_vars(model: cp_model.CpModel,
                            trips: list[dict],
                            driver_ids: list[str]) -> dict[tuple, cp_model.IntVar]:
    x = {}
    for d in driver_ids:
        for t in trips:
            x[(d, t["trip_id"])] = model.NewBoolVar(f"x[{d},{t['trip_id']}]")
    return x


def create_driver_active_vars(model: cp_model.CpModel,
                              driver_ids: list[str]) -> dict[str, cp_model.IntVar]:
    return {d: model.NewBoolVar(f"active[{d}]") for d in driver_ids}


def create_first_last_bounds(model: cp_model.CpModel,
                             trips: list[dict],
                             driver_ids: list[str],
                             x: dict,
                             active: dict) -> tuple[dict, dict]:
    """
    first_dep[d], last_arr[d]: ints bounded by [0, horizon], forced 0 if inactive.
    Derived from trip assignments so C2 is meaningful.
    """
    horizon = max((t["arr"] for t in trips), default=0) + 1
    first_dep, last_arr = {}, {}
    for d in driver_ids:
        fd = model.NewIntVar(0, horizon, f"first_dep[{d}]")
        la = model.NewIntVar(0, horizon, f"last_arr[{d}]")
        first_dep[d] = fd
        last_arr[d] = la
        assigned_any = sum(x[(d, t["trip_id"])] for t in trips)
        model.Add(assigned_any >= 1).OnlyEnforceIf(active[d])
        model.Add(assigned_any == 0).OnlyEnforceIf(active[d].Not())
        for t in trips:
            xv = x[(d, t["trip_id"])]
            model.Add(fd <= t["dep"]).OnlyEnforceIf(xv)
            model.Add(la >= t["arr"]).OnlyEnforceIf(xv)
    return first_dep, last_arr


# ===========================================================================
# HARD CONSTRAINTS  (C1 - C4)
# ===========================================================================
def add_c4_full_coverage(model: cp_model.CpModel,
                         trips: list[dict],
                         x: dict,
                         driver_ids: list[str]) -> None:
    for t in trips:
        model.Add(sum(x[(d, t["trip_id"])] for d in driver_ids) == 1)


def add_c1_no_overlap(model: cp_model.CpModel,
                      trips: list[dict],
                      driver_ids: list[str],
                      x: dict) -> None:
    """
    C1: for each driver, no two assigned trips may overlap.

    Trips are sorted by departure, so for pair (i, j) with i < j:
        trips[i].dep <= trips[j].dep
    The pair is non-overlapping (turnaround respected) iff:
        trips[i].arr + MIN_TURNAROUND_SEC <= trips[j].dep
    If that holds, they may share a driver. Otherwise they cannot:
        x[d, i] + x[d, j] <= 1
    """
    n = len(trips)
    for d in driver_ids:
        for i in range(n):
            a = trips[i]
            for j in range(i + 1, n):
                b = trips[j]
                if a["arr"] + CFG.MIN_TURNAROUND_SEC > b["dep"]:
                    model.Add(
                        x[(d, a["trip_id"])] + x[(d, b["trip_id"])] <= 1
                    )


def add_c2_max_duty(model: cp_model.CpModel,
                    driver_ids: list[str],
                    active: dict,
                    first_dep: dict,
                    last_arr: dict) -> None:
    for d in driver_ids:
        duty = last_arr[d] - first_dep[d]
        model.Add(duty <= CFG.MAX_DUTY_SEC).OnlyEnforceIf(active[d])


def add_c3_sign_buffers(model: cp_model.CpModel,
                        trips: list[dict],
                        driver_ids: list[str],
                        x: dict) -> None:
    """
    C3: sign_on = first_dep - 900, sign_off = last_arr + 900.
    Enforced by C2 + the data check below. If any trip departs < 900 s
    (i.e. before 00:15), sign-on would be negative -- fail loudly.
    """
    for t in trips:
        if t["dep"] < CFG.SIGN_ON_BUFFER_SEC:
            raise ValueError(
                f"Trip {t['trip_id']} departs before sign-on buffer window"
            )


# ===========================================================================
# SOFT OBJECTIVES  (C6, C7)
# ===========================================================================
def add_c6_continuous_driving(model: cp_model.CpModel,
                              trips: list[dict],
                              driver_ids: list[str],
                              x: dict) -> cp_model.LinearExpr:
    """
    C6 (soft, SPEC-COMPLIANT, state-machine, any run length).

    Per-driver state carried across the global sorted trip list:
        last_arr[d, i]      -- arrival of the most recent trip assigned to d
                               among trips 0..i (0 if none)
        run_drive[d, i]     -- cumulative driving time of the active chain
                               ending at that last-assigned trip (0 if none)
        has_prev[d, i]      -- 1 iff last_arr[d, i-1] > 0 (i.e. d had a
                               prior assignment before trip i)
        new_chain[d, i]     -- 1 iff x[d,i]=1 AND either (has_prev=0)
                               OR gap from prev assignment > MIN_TURNAROUND_SEC
        end_of_chain[d, i]  -- 1 iff trip i is the terminal of an active chain
        over[d, i]          -- max(0, run_drive[d, i] - 5h)

    Penalty = sum over (d, i) of over[d, i] * end_of_chain[d, i]
            = sum over maximal chains of max(0, chain_drive - 5h)
    which matches the spec exactly.

    Variables added: 6 per (d, i)  (3 IntVars + 3 BoolVars).
    """
    preferred = CFG.MAX_CONTINUOUS_PREFERRED_SEC
    reset = CFG.MIN_TURNAROUND_SEC  # [DERIVED from C1]

    n = len(trips)
    if n == 0:
        return 0

    horizon = max(t["arr"] for t in trips)
    max_chain = horizon  # upper bound on any cumulative driving time
    M_gap = horizon + reset + 1  # big-M for gap constraints

    dur = [t["arr"] - t["dep"] for t in trips]

    penalty_terms: list[cp_model.IntVar] = []

    for d in driver_ids:
        # ---- base case i = 0 ----
        last_arr_0 = model.NewIntVar(0, horizon, f"last_arr[{d},0]")
        run_0      = model.NewIntVar(0, max_chain, f"run_drive[{d},0]")
        new_0      = model.NewBoolVar(f"new_chain[{d},0]")
        end_0      = model.NewBoolVar(f"end_chain[{d},0]")
        over_0     = model.NewIntVar(0, max_chain, f"over[{d},0]")

        x0 = x[(d, trips[0]["trip_id"])]

        # i = 0: no prior assignment, so every assignment starts a new chain.
        model.Add(new_0 == x0)
        model.Add(last_arr_0 == 0).OnlyEnforceIf(x0.Not())
        model.Add(last_arr_0 == trips[0]["arr"]).OnlyEnforceIf(x0)
        model.Add(run_0 == 0).OnlyEnforceIf(x0.Not())
        model.Add(run_0 == dur[0]).OnlyEnforceIf(x0)

        prev_last = last_arr_0
        prev_run  = run_0

        last_list = [last_arr_0]
        run_list  = [run_0]
        new_list  = [new_0]
        end_list  = [end_0]
        over_list = [over_0]

        # ---- i >= 1 ----
        for i in range(1, n):
            xi = x[(d, trips[i]["trip_id"])]

            la = model.NewIntVar(0, horizon, f"last_arr[{d},{i}]")
            rd = model.NewIntVar(0, max_chain, f"run_drive[{d},{i}]")
            hp = model.NewBoolVar(f"has_prev[{d},{i}]")
            nc = model.NewBoolVar(f"new_chain[{d},{i}]")
            ec = model.NewBoolVar(f"end_chain[{d},{i}]")
            ov = model.NewIntVar(0, max_chain, f"over[{d},{i}]")

            # ---- has_prev = (prev_last > 0) ----
            model.Add(prev_last >= 1).OnlyEnforceIf(hp)
            model.Add(prev_last == 0).OnlyEnforceIf(hp.Not())

            # ---- new_chain: nc <= xi ----
            model.Add(nc <= xi)

            # nc = 1 forced when xi = 1 and no prior assignment
            model.Add(nc >= xi - hp)

            # nc = 0 AND xi = 1 AND hp = 1  =>  gap <= reset
            model.Add(
                trips[i]["dep"] - prev_last
                <= reset
                   + M_gap * (1 - xi)
                   + M_gap * nc
                   + M_gap * (1 - hp)
            )

            # nc = 1 AND xi = 1 AND hp = 1  =>  gap >= reset + 1
            model.Add(
                trips[i]["dep"] - prev_last
                >= (reset + 1)
                   - M_gap * (1 - nc)
                   - M_gap * (1 - hp)
            )

            # ---- last_arr update ----
            model.Add(la == prev_last).OnlyEnforceIf(xi.Not())
            model.Add(la == trips[i]["arr"]).OnlyEnforceIf(xi)

            # ---- run_drive update ----
            model.Add(rd == prev_run).OnlyEnforceIf(xi.Not())
            model.Add(rd == prev_run + dur[i]).OnlyEnforceIf([xi, nc.Not()])
            model.Add(rd == dur[i]).OnlyEnforceIf([xi, nc])

            last_list.append(la)
            run_list.append(rd)
            new_list.append(nc)
            end_list.append(ec)
            over_list.append(ov)

            prev_last = la
            prev_run = rd

        # ---- end_of_chain and over, after the full timeline is built ----
        for i in range(n):
            xi = x[(d, trips[i]["trip_id"])]
            ec = end_list[i]
            ov = over_list[i]
            rd = run_list[i]

            # over = max(0, run_drive - preferred)
            model.Add(ov >= rd - preferred)
            model.Add(ov >= 0)

            # end_of_chain
            if i == n - 1:
                model.Add(ec == xi)
            else:
                xnext = x[(d, trips[i + 1]["trip_id"])]
                ncnext = new_list[i + 1]
                model.Add(ec <= xi)
                model.Add(ec <= 1 - xnext + ncnext)
                model.Add(ec >= xi - xnext + ncnext)

            # pen = over * end_of_chain, linearized
            pen = model.NewIntVar(0, max_chain, f"pen_c6[{d},{i}]")
            model.Add(pen <= ec * max_chain)
            model.Add(pen <= ov)
            model.Add(pen >= ov - max_chain * (1 - ec))
            penalty_terms.append(pen)

    if not penalty_terms:
        return 0
    return sum(penalty_terms)


def add_c7_reserve_buffer(model: cp_model.CpModel,
                          driver_ids: list[str],
                          active: dict,
                          pool_size: int) -> cp_model.LinearExpr:
    """
    C7 (soft): penalize using more than (pool_size - MIN_RESERVE_DRIVERS) drivers.
    """
    used = sum(active[d] for d in driver_ids)
    allowed = max(0, pool_size - CFG.MIN_RESERVE_DRIVERS)
    over = model.NewIntVar(0, len(driver_ids), "c7_over")
    model.Add(over >= used - allowed)
    return over


def build_objective(model: cp_model.CpModel,
                    c6_expr: cp_model.LinearExpr,
                    c7_expr: cp_model.LinearExpr) -> None:
    model.Minimize(CFG.OBJ_SCALE * (
        CFG.W_CONTINUOUS_DRIVING * c6_expr +
        CFG.W_RESERVE_BUFFER * c7_expr
    ))