"""
255-trip probe with R11-KVTR fix.

Fixes the R11 bug where deadhead_seconds(home, KVTR) returns 8 min (MUTT
default), which is physically wrong (KVTR is not a terminal, not MUTT).

Correct behaviour:
    deadhead to a non-terminal, non-MUTT stop is INVALID.
    A trip starting at such a stop can ONLY be taken if a predecessor trip
    ends there.

This activates only for the 255-trip case (WK_12 starts at KVTR).
With 250 trips, no trip starts at KVTR, so the bug is dormant.

Runs 3 variants (9/7/2, 8/7/3, 9/9/0), reports:
    - status, objective
    - trip counts per rake
    - which rake (if any) does WK_256 and which does WK_12
    - which rake (if any) does BOTH WK_256 and WK_12 (the chain)

Read-only: no files written.

Run from project root:
    python probes\\probe_255_r11_fix.py
"""
from __future__ import annotations

import csv
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
from ortools.sat.python import cp_model

from solver import config
from solver.models import ProblemData
from solver import constraints as C


RAW = Path("data/raw")
_TERMINALS = ("ALVA", "TPHT")


# ===========================================================================
# Raw GTFS loaders (same as before)
# ===========================================================================
def read_csv_raw(name):
    with open(RAW / name, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def to_sec(t: str) -> int:
    h, m, s = (int(p) for p in t.split(":"))
    return h * 3600 + m * 60 + s


STATION_ORDER = {
    "ALVA": 0, "PNCU": 1, "CPPY": 2, "ATTK": 3, "MUTT": 4,
    "KLMT": 5, "CCUV": 6, "PDPM": 7, "EDAP": 8, "CGPP": 9,
    "PARV": 10, "JLSD": 11, "KALR": 12, "TNHL": 13, "MGRD": 14,
    "MACE": 15, "ERSH": 16, "KVTR": 17, "EMKM": 18, "VYTA": 19,
    "THYK": 20, "PETT": 21, "VAKK": 22, "SNJN": 23, "TPHT": 24,
}


def build_255_trips():
    trips_raw = read_csv_raw("trips.txt")
    stop_times = read_csv_raw("stop_times.txt")

    stops_by_trip = defaultdict(list)
    for row in stop_times:
        stops_by_trip[row["trip_id"]].append(row)
    for tid in stops_by_trip:
        stops_by_trip[tid].sort(key=lambda x: int(x["stop_sequence"]))

    out = []
    for t in trips_raw:
        if t["service_id"] != "WK":
            continue
        tid = t["trip_id"]
        recs = stops_by_trip.get(tid, [])
        if not recs:
            continue
        first, last = recs[0], recs[-1]
        first_stop, last_stop = first["stop_id"], last["stop_id"]
        dep, arr = to_sec(first["departure_time"]), to_sec(last["arrival_time"])
        duration = arr - dep
        if duration <= 0:
            continue
        i_first, i_last = STATION_ORDER.get(first_stop), STATION_ORDER.get(last_stop)
        if i_first is None or i_last is None:
            continue
        direction = "UP" if i_last > i_first else "DOWN"
        out.append({
            "trip_id": tid,
            "direction": direction,
            "first_stop": first_stop,
            "last_stop": last_stop,
            "dep_sec": dep,
            "arr_sec": arr,
            "duration": duration,
            "stop_count": len(recs),
        })
    return out


# ===========================================================================
# R11 with KVTR fix
# ===========================================================================
def deadhead_seconds_correct(home, start_stop):
    """
    Returns (seconds, is_valid).

    - home == start_stop: (0, True)  -- same stop, no deadhead
    - both in terminals:  (15min, True)
    - one is MUTT and other is a terminal: (8min, True)
    - one is non-terminal non-MUTT (e.g., KVTR): (None, False) -- INVALID
      Means: cannot start here without a predecessor.
    """
    if home == start_stop:
        return 0, True
    if home in _TERMINALS and start_stop in _TERMINALS:
        return config.TERMINAL_TO_TERMINAL_DEADHEAD_MIN * 60, True
    if (home == "MUTT" and start_stop in _TERMINALS) or \
       (home in _TERMINALS and start_stop == "MUTT"):
        return config.MUTTOM_TO_TERMINAL_DEADHEAD_MIN * 60, True
    # Anything involving a non-terminal, non-MUTT stop (KVTR) as the
    # start or home is invalid as a first-trip deadhead.
    return None, False


def add_r11_kvtr_fixed(model, trip_vars, rake_trip, data):
    """
    Same as original add_r11_terminal_continuity, but with KVTR fix:
    if deadhead(home, first_stop) is invalid, the trip can only be taken
    if a predecessor trip ends at that stop.
    """
    turnaround = config.TERMINAL_TURNAROUND_MIN * 60
    depot_open = config.OPERATING_START_SEC

    for _, r in data.service_rakes.iterrows():
        rid = r["rake_id"]
        home = r["initial_location"]

        for tid, tv in trip_vars.items():
            if tv["first_stop"] == home:
                continue  # same stop -- always allowed

            dh, valid = deadhead_seconds_correct(home, tv["first_stop"])

            if valid and tv["start"] >= depot_open + dh:
                continue  # allowed as first trip via deadhead

            # Otherwise requires predecessor at tv.first_stop
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
# Solve one variant
# ===========================================================================
def solve_variant(name, fleet_alva, fleet_tpht, fleet_mutt, use_home_lock,
                  trips_255, time_limit=300):
    print(f"\n--- {name}  (ALVA={fleet_alva}, TPHT={fleet_tpht}, MUTT={fleet_mutt}, "
          f"home_lock={use_home_lock}) ---")

    data = ProblemData.load()

    trips_df = pd.DataFrame([{
        "trip_id": t["trip_id"],
        "departure_time": f"{t['dep_sec']//3600:02d}:{(t['dep_sec']%3600)//60:02d}:{t['dep_sec']%60:02d}",
        "arrival_time":   f"{t['arr_sec']//3600:02d}:{(t['arr_sec']%3600)//60:02d}:{t['arr_sec']%60:02d}",
        "duration": t["duration"],
        "direction": t["direction"],
        "first_stop": t["first_stop"],
        "last_stop": t["last_stop"],
        "dep_sec": t["dep_sec"],
        "arr_sec": t["arr_sec"],
    } for t in trips_255])
    data.trips = trips_df

    # Reassign rake homes
    rakes = data.rakes.copy()
    service = rakes[rakes["status"] == "service"].copy()
    all_service_ids = service["rake_id"].tolist()
    new_homes = (["ALVA"] * fleet_alva + ["TPHT"] * fleet_tpht + ["MUTTOM"] * fleet_mutt)
    assert len(new_homes) == 18, f"Fleet counts sum != 18: {len(new_homes)}"
    rakes.loc[rakes["rake_id"].isin(all_service_ids), "initial_location"] = new_homes
    data.rakes = rakes

    print(f"  Fleet: ALVA={(data.service_rakes['initial_location']=='ALVA').sum()}, "
          f"TPHT={(data.service_rakes['initial_location']=='TPHT').sum()}, "
          f"MUTT={(data.service_rakes['initial_location']=='MUTTOM').sum()}")

    model = cp_model.CpModel()
    trips = C.build_trips(data)
    trip_vars = C.create_trip_intervals(model, trips)

    if use_home_lock:
        rake_trip = C.create_rake_assignment_variables(model, trips, data, trip_vars)
    else:
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

    C.add_r1_service_coverage(model, trip_vars, rake_trip, data)
    C.add_r3_operating_window(model, trip_vars)
    C.add_r4_fleet_availability(model, trip_vars, rake_trip, data)
    C.add_r5_rake_non_overlap(model, trip_vars, rake_trip, data)
    C.add_r6_turnaround(model, trip_vars, rake_trip, data)
    C.add_r7_running_time(model, trip_vars)
    C.add_r8_depot_capacity(model, trip_vars, rake_trip, data)
    C.add_r9_maintenance_exclusivity(model, trip_vars, rake_trip, data)
    C.add_r10_maintenance_threshold(model, trip_vars, rake_trip, data)
    # USE THE FIXED R11 HERE
    add_r11_kvtr_fixed(model, trip_vars, rake_trip, data)
    C.add_r12_nonservice_window(model, trip_vars)

    o6 = C.add_obj6_rake_balance(model, trip_vars, rake_trip, data)
    C.build_objective(model, o6)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = config.CP_SAT_NUM_WORKERS
    solver.parameters.random_seed = config.CP_SAT_RANDOM_SEED

    print(f"  Solving...")
    t0 = time.perf_counter()
    status = solver.Solve(model)
    elapsed = time.perf_counter() - t0
    status_name = solver.StatusName(status)
    print(f"  STATUS = {status_name}  ({elapsed:.2f}s)")

    result = {
        "name": name,
        "status": status_name,
        "elapsed": elapsed,
        "objective": None,
        "wk256_rake": None,
        "wk12_rake": None,
        "chain_rake": None,
    }

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        obj = solver.ObjectiveValue()
        bound = solver.BestObjectiveBound()
        gap = 0.0 if status == cp_model.OPTIMAL else (
            (obj - bound) / obj * 100 if obj > 0 else None
        )
        print(f"  objective = {obj}")
        print(f"  best_bound = {bound}")
        print(f"  gap = {gap}%")
        result["objective"] = obj

        service_ids = list(data.service_rakes["rake_id"])
        counts = {rid: 0 for rid in service_ids}
        for tid in trip_vars:
            for rid in service_ids:
                if solver.Value(rake_trip[(rid, tid)]) == 1:
                    counts[rid] += 1
                    break
        print("  Trip counts:")
        for rid in sorted(counts):
            print(f"    {rid}: {counts[rid]}")

        # Which rakes do WK_256 and WK_12?
        if "WK_256" in trip_vars:
            for rid in service_ids:
                if solver.Value(rake_trip[(rid, "WK_256")]) == 1:
                    result["wk256_rake"] = rid
                    break
        if "WK_12" in trip_vars:
            for rid in service_ids:
                if solver.Value(rake_trip[(rid, "WK_12")]) == 1:
                    result["wk12_rake"] = rid
                    break

        print(f"  WK_256 assigned to: {result['wk256_rake'] or 'NOBODY'}")
        print(f"  WK_12  assigned to: {result['wk12_rake'] or 'NOBODY'}")

        if result["wk256_rake"] and result["wk256_rake"] == result["wk12_rake"]:
            result["chain_rake"] = result["wk256_rake"]
            print(f"  CHAIN: SAME RAKE ({result['chain_rake']}) does WK_256 -> WK_12")
        else:
            print(f"  CHAIN: DIFFERENT rakes / missing")

    return result


# ===========================================================================
# Main
# ===========================================================================
def main():
    print("=== 255-trip feasibility probe WITH R11-KVTR FIX ===")
    print("Window: [04:40, 24:00), all WK trips included\n")

    saved_start = config.OPERATING_START_SEC
    saved_end = config.OPERATING_END_SEC
    config.OPERATING_START_SEC = 4 * 3600 + 40 * 60
    config.OPERATING_END_SEC = 24 * 3600

    try:
        trips_255 = build_255_trips()
        print(f"Built {len(trips_255)} trips from raw GTFS.")
        dep_range = min(t["dep_sec"] for t in trips_255), max(t["dep_sec"] for t in trips_255)
        arr_range = min(t["arr_sec"] for t in trips_255), max(t["arr_sec"] for t in trips_255)
        print(f"Departure range: {dep_range[0]//3600:02d}:{(dep_range[0]%3600)//60:02d} "
              f"to {dep_range[1]//3600:02d}:{(dep_range[1]%3600)//60:02d}")
        print(f"Arrival range:   {arr_range[0]//3600:02d}:{(arr_range[0]%3600)//60:02d} "
              f"to {arr_range[1]//3600:02d}:{(arr_range[1]%3600)//60:02d}")

        variants = [
            ("V1_9_7_2_homelock",   9, 7, 2, True),
            ("V2_8_7_3_homelock",   8, 7, 3, True),
            ("V3_9_9_0_nohomelock", 9, 9, 0, False),
        ]
        results = []
        for name, a, t, m, hl in variants:
            try:
                r = solve_variant(name, a, t, m, hl, trips_255)
                results.append(r)
            except Exception as e:
                print(f"\n[{name}] ERROR: {e}")
                import traceback
                traceback.print_exc()
                results.append({"name": name, "status": "ERROR", "elapsed": 0,
                                "objective": None, "wk256_rake": None,
                                "wk12_rake": None, "chain_rake": None})

        print("\n=== SUMMARY ===")
        print(f"{'Variant':<25} {'Status':<12} {'Elapsed':>9} {'Objective':>12} "
              f"{'WK_256':>8} {'WK_12':>8} {'Chain':>8}")
        print("-" * 95)
        for r in results:
            obj = f"{r['objective']:.1f}" if r['objective'] is not None else "-"
            print(f"{r['name']:<25} {r['status']:<12} {r['elapsed']:>8.2f}s "
                  f"{obj:>12} {r['wk256_rake'] or '-':>8} {r['wk12_rake'] or '-':>8} "
                  f"{r['chain_rake'] or '-':>8}")

    finally:
        config.OPERATING_START_SEC = saved_start
        config.OPERATING_END_SEC = saved_end

    print("\n[done] no files written.")


if __name__ == "__main__":
    main()