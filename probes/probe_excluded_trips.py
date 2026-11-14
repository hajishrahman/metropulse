"""
Probe: why are the 5 excluded trips excluded?

Question:
    For each of the 5 documented excluded trips (WK_253, WK_4, WK_256,
    WK_12, WK_18), what is its departure, arrival, first_stop, last_stop,
    and which rule excludes it: departure < 06:00, departure >= 23:00,
    or arrival >= 24:00?

Also:
    Report all 255 WK trips that are excluded by departure-outside-window
    OR arrival-past-midnight, so we can confirm the full set.

Read-only. No files on disk written.

Run from project root:
    python probes\\probe_excluded_trips.py
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

RAW = Path("data/raw")


def read_csv(name):
    with open(RAW / name, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def to_sec(t: str) -> int:
    h, m, s = (int(p) for p in t.split(":"))
    return h * 3600 + m * 60 + s


def main():
    trips = read_csv("trips.txt")
    stop_times = read_csv("stop_times.txt")

    # Build per-trip ordered stop list
    stops_by_trip = defaultdict(list)
    for row in stop_times:
        stops_by_trip[row["trip_id"]].append(row)
    for tid in stops_by_trip:
        stops_by_trip[tid].sort(key=lambda x: int(x["stop_sequence"]))

    # Only WK service
    wk_trips = [t for t in trips if t["service_id"] == "WK"]
    print(f"Total WK trips in trips.txt: {len(wk_trips)}")

    # Documented 5 excluded
    documented = {"WK_253", "WK_4", "WK_256", "WK_12", "WK_18"}

    print("\n=== Documented 5 excluded trips ===")
    print(f"{'trip_id':<10} {'first':<6} {'last':<6} {'dep':<10} {'arr':<10} "
          f"{'dep<6':<7} {'dep>=23':<9} {'arr>=24':<9} {'stop_count':>10}")
    print("-" * 85)

    for tid in sorted(documented):
        records = stops_by_trip.get(tid, [])
        if not records:
            print(f"{tid:<10} NOT FOUND IN stop_times")
            continue
        first = records[0]
        last = records[-1]
        dep = to_sec(first["departure_time"])
        arr = to_sec(last["arrival_time"])
        stop_count = len(records)

        dep_lt_6 = dep < 6 * 3600
        dep_ge_23 = dep >= 23 * 3600
        arr_ge_24 = arr >= 24 * 3600

        print(f"{tid:<10} {first['stop_id']:<6} {last['stop_id']:<6} "
              f"{first['departure_time']:<10} {last['arrival_time']:<10} "
              f"{str(dep_lt_6):<7} {str(dep_ge_23):<9} {str(arr_ge_24):<9} "
              f"{stop_count:>10}")

    # Now: what does the CURRENT filter exclude?
    # Docs say: departure in [06:00, 23:00). We'll reproduce that filter.
    print("\n=== Current filter (departure in [06:00, 23:00)) ===")
    kept = []
    excluded_by_dep = []
    for t in wk_trips:
        tid = t["trip_id"]
        records = stops_by_trip.get(tid, [])
        if not records:
            continue
        dep = to_sec(records[0]["departure_time"])
        if 6 * 3600 <= dep < 23 * 3600:
            kept.append(tid)
        else:
            excluded_by_dep.append((tid, records[0]["departure_time"],
                                    records[-1]["arrival_time"]))

    print(f"Kept by departure rule: {len(kept)}")
    print(f"Excluded by departure rule: {len(excluded_by_dep)}")
    for tid, dep, arr in sorted(excluded_by_dep):
        print(f"  {tid}: dep={dep}, arr={arr}")

    # Compare to docs' claim of 250
    print(f"\n=== Reconciliation ===")
    print(f"Docs claim: 255 WK trips, 5 excluded by departure, 250 kept")
    print(f"Actual:     {len(wk_trips)} WK trips, "
          f"{len(excluded_by_dep)} excluded by departure, "
          f"{len(kept)} kept")

    # Full WK excluded list, with departure AND arrival filters
    print("\n=== Alternative filter: departure in [04:40, 24:00), arrival any ===")
    kept2 = 0
    excluded2 = []
    for t in wk_trips:
        tid = t["trip_id"]
        records = stops_by_trip.get(tid, [])
        if not records:
            continue
        dep = to_sec(records[0]["departure_time"])
        if 4 * 3600 + 40 * 60 <= dep < 24 * 3600:
            kept2 += 1
        else:
            excluded2.append((tid, records[0]["departure_time"],
                              records[-1]["arrival_time"]))
    print(f"Kept by [04:40, 24:00): {kept2}")
    print(f"Excluded by [04:40, 24:00): {len(excluded2)}")
    for tid, dep, arr in sorted(excluded2):
        print(f"  {tid}: dep={dep}, arr={arr}")

    # Specifically: is WK_253 excluded by departure rule?
    print("\n=== WK_253 detail ===")
    records = stops_by_trip.get("WK_253", [])
    if records:
        print(f"  first stop: {records[0]['stop_id']} at {records[0]['departure_time']}")
        print(f"  last stop:  {records[-1]['stop_id']} at {records[-1]['arrival_time']}")
        print(f"  stop_count: {len(records)}")
        print(f"  departure in [06:00, 23:00)? "
              f"{6*3600 <= to_sec(records[0]['departure_time']) < 23*3600}")
        print(f"  arrival >= 24:00? {to_sec(records[-1]['arrival_time']) >= 24*3600}")
    else:
        print("  WK_253 not found in stop_times.")

    print("\n[done] no files written.")


if __name__ == "__main__":
    main()