"""
255-trip feasibility probe (window [04:40, 24:00), all WK trips included).

Tests 3 fleet variants under the full 255-trip model:
    V1: 9 ALVA / 7 TPHT / 2 MUTT  (current), home-lock ON
    V2: 8 ALVA / 7 TPHT / 3 MUTT,           home-lock ON
    V3: 9 ALVA / 9 TPHT / 0 MUTT,           home-lock OFF

Read-only: no files are written.

Run from project root:
    python probes\\probe_255_trips.py
"""
from __future__ import annotations

import csv
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ortools.sat.python import cp_model

from solver import config
from solver.models import ProblemData
from solver import constraints as C


RAW = Path("data/raw")


def read_csv_raw(name):
    with open(RAW / name, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def to_sec(t: str) -> int:
    h, m, s = (int(p) for p in t.split(":"))
    return h * 3600 + m * 60 + s


def build_255_trips():
    """
    Build the full 255-trip list from raw GTFS (all WK trips).
    Returns a list of dicts in the schema expected by constraints.build_trips:
      trip_id, direction, first_stop, last_stop, dep_sec, arr_sec, duration, ...
    """
    trips_raw = read_csv_raw("trips.txt")
    stop_times = read_csv_raw("stop_times.txt")

    stops_by_trip = defaultdict(list)
    for row in stop_times:
        stops_by_trip[row["trip_id"]].append(row)
    for tid in stops_by_trip:
        stops_by_trip[tid].sort(key=lambda x: int(x["stop_sequence"]))

    # Station order for direction: ALVA=0 ... TPHT=24
    # From stops.txt order in the earlier feed; hardcode small mapping.
    station_order = {
        "ALVA": 0, "PNCU": 1, "CPPY": 2, "ATTK": 3, "MUTT": 4,
        "KLMT": 5, "CCUV": 6, "PDPM": 7, "EDAP": 8, "CGPP": 9,
        "PARV": 10, "JLSD": 11, "KALR": 12, "TNHL": 13, "MGRD": 14,
        "MACE": 15, "ERSH": 16, "KVTR": 17, "EMKM": 18, "VYTA": 19,
        "THYK": 20, "PETT": 21, "VAKK": 22, "SNJN": 23, "TPHT": 24,
    }

    out = []
    for t in trips_raw:
        if t["service_id"] != "WK":
            continue
        tid = t["trip_id"]
        recs = stops_by_trip.get(tid, [])
        if not recs:
            continue
        first = recs[0]
        last = recs[-1]
        first_stop = first["stop_id"]
        last_stop = last["stop_id"]
        dep = to_sec(first["departure_time"])
        arr = to_sec(last["arrival_time"])
        duration = arr - dep
        if duration <= 0:
            print(f"[warn] {tid}: non-positive duration {duration}s")
            continue

        # Direction from stop order
        i_first = station_order.get(first_stop)
        i_last = station_order.get(last_stop)
        if i_first is None or i_last is None:
            print(f"[warn] {tid}: unknown stop {first_stop}->{last_stop}")
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


def counts_from_solution(solver, rake_trip, trip_vars, service_rakes):
    counts = {rid: 0 for rid in service_rakes}
    for tid in trip_vars:
        for rid in service_rakes:
            if solver.Value(rake_trip[(rid, tid)]) == 1:
                counts[rid] += 1
                break
    return counts


def chain_exists(solver, rake_trip, service_rakes, trip_a, trip_b):
    """Return the rake that does trip_a immediately followed by trip_b, or None."""
    if trip_a not in [t for t in
                      []]:
        return None
    # Check per rake
    for rid in service_rakes:
        if (rid, trip_a) not in rake_trip or (rid, trip_b) not in rake_trip:
            continue
        try:
            a_val = solver.Value(rake_trip[(rid, trip_a)])
            b_val = solver.Value(rake_trip[(rid, trip_b)])
        except Exception:
            continue
        if a_val == 1 and b_val == 1:
            return rid
    return None


def solve_variant(name, fleet_alva, fleet_tpht, fleet_mutt, use_home_lock,
                  trips_255, time_limit=300):
    print(f"\n--- {name}  (ALVA={fleet_alva}, TPHT={fleet_tpht}, MUTT={fleet_mutt}, "
          f"home_lock={use_home_lock}) ---")

    # Load fresh data (trips_all.csv is not used here — we build trips_255)
    data = ProblemData.load()

    # Replace trips with 255-trip set, recompute dep_sec / arr_sec
    import pandas as pd
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

    # Assign rakes by location
    rakes = data.rakes.copy()
    service = rakes[rakes["status"] == "service"].copy()
    alva_ids = service[service["initial_location"] == "ALVA"]["rake_id"].tolist()
    tpht_ids = service[service["initial_location"] == "TPHT"]["rake_id"].tolist()
    mutt_ids = service[service["initial_location"] == "MUTTOM"]["rake_id"].tolist()

    # Reassign: use first fleet_alva ALVA, next fleet_tpht (must total 18 with mutt)
    all_service_ids = service["rake_id"].tolist()
    # Reassign by position
    new_homes = (
        ["ALVA"] * fleet_alva
        + ["TPHT"] * fleet_tpht
        + ["MUTTOM"] * fleet_mutt
    )
    assert len(new_homes) == len(all_service_ids) == 18, \
        f"Fleet counts must sum to 18, got {len(new_homes)}"
    rakes.loc[rakes["rake_id"].isin(all_service_ids), "initial_location"] = new_homes
    data.rakes = rakes

    print(f"  Fleet after reassignment: "
          f"ALVA={(data.service_rakes['initial_location']=='ALVA').sum()}, "
          f"TPHT={(data.service_rakes['initial_location']=='TPHT').sum()}, "
          f"MUTT={(data.service_rakes['initial_location']=='MUTTOM').sum()}")

    # Build model
    model = cp_model.CpModel()
    trips = C.build_trips(data)
    print(f"  Trips in model: {len(trips)}")
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
    C.add_r11_terminal_continuity(model, trip_vars, rake_trip, data)
    C.add_r12_nonservice_window(model, trip_vars)

    o6 = C.add_obj6_rake_balance(model, trip_vars, rake_trip, data)
    C.build_objective(model, o6)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = config.CP_SAT_NUM_WORKERS
    solver.parameters.random_seed = config.CP_SAT_RANDOM_SEED

    print(f"  Solving (limit {time_limit}s)...")
    t0 = time.perf_counter()
    status = solver.Solve(model)
    elapsed = time.perf_counter() - t0
    status_name = solver.StatusName(status)
    print(f"  STATUS = {status_name}  ({elapsed:.2f}s)")

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        obj = solver.ObjectiveValue()
        bound = solver.BestObjectiveBound()
        gap = 0.0 if status == cp_model.OPTIMAL else (obj - bound) / obj * 100 if obj > 0 else None
        print(f"  objective = {obj}")
        print(f"  best_bound = {bound}")
        print(f"  gap = {gap}%")

        service_ids = list(data.service_rakes["rake_id"])
        counts = counts_from_solution(solver, rake_trip, trip_vars, service_ids)
        print("  Trip counts:")
        for rid in sorted(counts):
            print(f"    {rid}: {counts[rid]}")

        # Check WK_256 -> WK_12 chain
        if "WK_256" in trip_vars and "WK_12" in trip_vars:
            chain_rake = chain_exists(solver, rake_trip, service_ids, "WK_256", "WK_12")
            if chain_rake:
                print(f"  WK_256 -> WK_12 chain: SAME RAKE {chain_rake}")
            else:
                print(f"  WK_256 -> WK_12 chain: DIFFERENT rakes (or one is dropped)")
        return status_name, elapsed, obj, counts
    else:
        return status_name, elapsed, None, None


def main():
    print("=== 255-trip feasibility probe ===")
    print("Window: [04:40, 24:00), all WK trips included\n")

    # Save + override window in memory
    saved_start = config.OPERATING_START_SEC
    saved_end = config.OPERATING_END_SEC
    config.OPERATING_START_SEC = 4 * 3600 + 40 * 60  # 04:40
    config.OPERATING_END_SEC = 24 * 3600             # 24:00

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
                status, elapsed, obj, counts = solve_variant(
                    name, a, t, m, hl, trips_255
                )
                results.append((name, status, elapsed, obj))
            except Exception as e:
                print(f"\n[{name}] ERROR: {e}")
                import traceback
                traceback.print_exc()
                results.append((name, "ERROR", 0, None))

        print("\n=== SUMMARY ===")
        print(f"{'Variant':<25} {'Status':<12} {'Elapsed':>9} {'Objective':>12}")
        print("-" * 65)
        for name, status, elapsed, obj in results:
            obj_str = f"{obj:.1f}" if obj is not None else "-"
            print(f"{name:<25} {status:<12} {elapsed:>8.2f}s {obj_str:>12}")

    finally:
        config.OPERATING_START_SEC = saved_start
        config.OPERATING_END_SEC = saved_end

    print("\n[done] no files written.")


if __name__ == "__main__":
    main()