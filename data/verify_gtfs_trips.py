"""
Verify the extracted GTFS trip files.
Read only. Does not change any file.
Exits with code 1 if any check fails.

Model: 255-trip V1 (window [04:40, 24:00)).
  - 232 full-route trips (unchanged)
  - 23 partial trips (was 18, +5 from WK_4, WK_256, WK_18, WK_12, WK_253)

Checks:
1. 232 full-route trips.
2. Full-route endpoints and direction.
3. Window membership for full + partial, no cross-contamination.
4. Durations, stop_count, stop_sequence order.
5. Reconcile with hourly_service.csv: hourly(total) == hourly(full) + hourly(partial)
   for hours 4..23.
6. Partial-trip gate (endpoint direction vs direction_id; UP/DOWN counts;
   window membership + disjointness).
7. Initial-position pre-check (report only).
"""

import csv
from collections import defaultdict
from pathlib import Path

RAW_DIR = Path("data/raw")
DATA_DIR = Path("data")

WINDOW_START_SEC = 4 * 3600 + 40 * 60   # 04:40
WINDOW_END_SEC = 24 * 3600              # 24:00
HOUR_RANGE = range(4, 24)


def parse_time_to_sec(t):
    try:
        h, m, s = (int(part) for part in t.split(":"))
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"Invalid GTFS time: {t!r}") from exc
    if h < 0 or not 0 <= m < 60 or not 0 <= s < 60:
        raise ValueError(f"Invalid GTFS time: {t!r}")
    return h * 3600 + m * 60 + s


def load_csv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_station_index():
    stop_times = defaultdict(list)
    with open(RAW_DIR / "stop_times.txt", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            stop_times[row["trip_id"]].append(row)
    for tid in stop_times:
        stop_times[tid].sort(key=lambda r: int(r["stop_sequence"]))
    for tid, rows in stop_times.items():
        if rows and rows[0]["stop_id"] == "ALVA" and rows[-1]["stop_id"] == "TPHT":
            return {r["stop_id"]: i for i, r in enumerate(rows)}
    raise RuntimeError("No full ALVA->TPHT trip found.")


def hour_of(dep_time):
    return parse_time_to_sec(dep_time) // 3600


def main():
    errors = []

    full = load_csv(DATA_DIR / "trips_full_route.csv")
    partial = load_csv(DATA_DIR / "trips_partial.csv")
    seq_full = load_csv(DATA_DIR / "stop_sequences_full_route.csv")
    hourly = load_csv(DATA_DIR / "hourly_service.csv")

    station_index = build_station_index()

    # ---- Check 1 ----
    if len(full) != 232:
        errors.append(f"[1] Expected 232 full-route trips, got {len(full)}")
    else:
        print("[1] 232 full-route trips: PASS")

    # ---- Check 2 ----
    bad2 = 0
    for t in full:
        f, l = t["first_stop"], t["last_stop"]
        if not ((f == "ALVA" and l == "TPHT") or (f == "TPHT" and l == "ALVA")):
            bad2 += 1
            continue
        fi, li = station_index[f], station_index[l]
        expected = "UP" if li > fi else "DOWN"
        if t["direction"] != expected:
            bad2 += 1
    if bad2 == 0:
        print("[2] Full-route endpoints and direction: PASS")
    else:
        errors.append(f"[2] {bad2} trips fail endpoint/direction check")

    # ---- Check 3 ----
    full_ids = {t["trip_id"] for t in full}
    partial_ids = {t["trip_id"] for t in partial}
    bad3 = 0
    bad3 += len(full) - len(full_ids)
    bad3 += len(partial) - len(partial_ids)
    for t in full:
        dep = parse_time_to_sec(t["departure_time"])
        if not (WINDOW_START_SEC <= dep < WINDOW_END_SEC):
            bad3 += 1
        if t["trip_id"] in partial_ids:
            bad3 += 1
    for t in partial:
        dep = parse_time_to_sec(t["departure_time"])
        if not (WINDOW_START_SEC <= dep < WINDOW_END_SEC):
            bad3 += 1
        if t["trip_id"] in full_ids:
            bad3 += 1
    if bad3 == 0:
        print("[3] Window membership and disjointness (full + partial): PASS")
    else:
        errors.append(f"[3] {bad3} window/disjointness problems")

    # ---- Check 4 ----
    bad4 = 0
    for t in full:
        duration = (parse_time_to_sec(t["arrival_time"])
                    - parse_time_to_sec(t["departure_time"]))
        if duration <= 0 or duration != int(t["duration"]) or int(t["stop_count"]) < 2:
            bad4 += 1

    seq_by_trip = defaultdict(list)
    for r in seq_full:
        seq_by_trip[r["trip_id"]].append(int(r["stop_sequence"]))
    full_by_id = {t["trip_id"]: t for t in full}
    for tid in full_ids | seq_by_trip.keys():
        seq = seq_by_trip.get(tid, [])
        if (tid not in full_by_id or len(seq) != int(full_by_id[tid]["stop_count"])
                or any(a >= b for a, b in zip(seq, seq[1:]))):
            bad4 += 1

    if bad4 == 0:
        print("[4] Durations, stop_count and stop_sequence order: PASS")
    else:
        errors.append(f"[4] {bad4} problems in duration/stop_count/sequence")

    # ---- Check 5: reconcile hourly_service.csv ----
    hourly_csv = defaultdict(lambda: {"UP": 0, "DOWN": 0})
    hourly_seen = set()
    for r in hourly:
        h = int(r["hour"].split(":")[0])
        if h in hourly_seen:
            errors.append(f"[5] Duplicate hourly_service.csv row for hour {h}")
        hourly_seen.add(h)
        hourly_csv[h]["UP"] = int(r["up_trips"])
        hourly_csv[h]["DOWN"] = int(r["down_trips"])

    hourly_full = defaultdict(lambda: {"UP": 0, "DOWN": 0})
    for t in full:
        h = hour_of(t["departure_time"])
        if t["direction"] not in ("UP", "DOWN"):
            errors.append(f"[5] Invalid direction for trip {t['trip_id']}: {t['direction']!r}")
        else:
            hourly_full[h][t["direction"]] += 1

    hourly_partial = defaultdict(lambda: {"UP": 0, "DOWN": 0})
    for t in partial:
        h = hour_of(t["departure_time"])
        if t["direction"] not in ("UP", "DOWN"):
            errors.append(f"[5] Invalid direction for trip {t['trip_id']}: {t['direction']!r}")
        else:
            hourly_partial[h][t["direction"]] += 1

    bad5 = 0
    if hourly_seen != set(HOUR_RANGE):
        errors.append(f"[5] hourly_service.csv must contain exactly hours "
                      f"{HOUR_RANGE.start} through {HOUR_RANGE.stop - 1}, got {sorted(hourly_seen)}")
    for h in HOUR_RANGE:
        for d in ("UP", "DOWN"):
            if hourly_csv[h][d] != hourly_full[h][d] + hourly_partial[h][d]:
                bad5 += 1
    if bad5 == 0:
        print("[5] hourly_service.csv = full + partial (per hour 04..23): PASS")
    else:
        errors.append(f"[5] {bad5} hourly mismatches")

    # ---- Check 6: partial-trip gate ----
    direction_id_map = {}
    with open(RAW_DIR / "trips.txt", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            direction_id_map[row["trip_id"]] = row.get("direction_id", "")

    mismatches = []
    for t in partial:
        raw = direction_id_map.get(t["trip_id"], "")
        expected_from_endpoint = t["direction"]
        expected_from_id = "UP" if raw == "0" else ("DOWN" if raw == "1" else "?")
        if expected_from_id != expected_from_endpoint:
            mismatches.append(
                (t["trip_id"], t["origin_stop"], t["destination_stop"],
                 expected_from_endpoint, expected_from_id)
            )

    print(f"\n[6a] Partial trips: endpoint direction vs direction_id")
    if not mismatches:
        print(f"     All {len(partial)} partials agree. PASS")
    else:
        print(f"     {len(mismatches)} mismatches (report only, not a fail):")
        for row in mismatches:
            print("     ", row)

    up = sum(1 for t in partial if t["direction"] == "UP")
    down = sum(1 for t in partial if t["direction"] == "DOWN")
    print(f"\n[6b] Partial UP={up} DOWN={down} total={len(partial)}")

    bad6c = []
    for t in partial:
        dep = parse_time_to_sec(t["departure_time"])
        if not (WINDOW_START_SEC <= dep < WINDOW_END_SEC):
            bad6c.append((t["trip_id"], "out_of_window"))
        if t["trip_id"] in full_ids:
            bad6c.append((t["trip_id"], "also_in_full"))
    if not bad6c:
        print(f"[6c] All {len(partial)} partials are in window and disjoint from full: PASS")
    else:
        errors.append(f"[6c] {len(bad6c)} partial-trip problems")
        for row in bad6c:
            print("     ", row)

    # ---- Check 7: initial-position pre-check (report only) ----
    print("\n[7] Initial position pre-check (report only):")
    first_hour = [t for t in full
                  if WINDOW_START_SEC <= parse_time_to_sec(t["departure_time"]) < 5 * 3600 + 40 * 60]
    alva_start = sum(1 for t in first_hour if t["first_stop"] == "ALVA")
    tpht_start = sum(1 for t in first_hour if t["first_stop"] == "TPHT")
    print(f"     Early departures (< 05:40): ALVA={alva_start}  TPHT={tpht_start}")
    print(f"     Fixed split: 9 ALVA / 9 TPHT / 0 service MUTT.")

    # ---- final ----
    print("\n=== Result ===")
    if errors:
        print("FAIL")
        for e in errors:
            print("  ", e)
        raise SystemExit(1)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()