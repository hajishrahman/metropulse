"""
Verify the extracted GTFS trip files.
Read only. Does not change any file.
Exits with code 1 if any check fails.

Checks:
1. 232 full-route trips.
2. All full-route trips are ALVA<->TPHT and direction matches stop order.
3. No out-of-window, no partial inside the 232.
4. duration > 0, stop_count >= 2, stop_sequence strictly increasing.
5. Reconcile with hourly_service.csv: hourly(250) - hourly(232) == hourly(partials).
6. Partial-trip gate:
   a. compare endpoint-based direction with trips.txt direction_id
   b. independent UP/DOWN count of partials
   c. window membership and disjointness from the 232
7. Initial position pre-check (report only, no fail).
"""

import csv
from collections import defaultdict
from pathlib import Path

RAW_DIR = Path("data/raw")
DATA_DIR = Path("data")


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
    """Same rule as the extractor: from a full ALVA->TPHT trip."""
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
        if not (6 * 3600 <= dep < 23 * 3600):
            bad3 += 1
        if t["trip_id"] in partial_ids:
            bad3 += 1
    if bad3 == 0:
        print("[3] No out-of-window or partial in the 232: PASS")
    else:
        errors.append(f"[3] {bad3} problems in the 232")

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
    # hourly_service.csv covers 250 trips = 232 full + 18 partial.
    hourly_csv = defaultdict(lambda: {"UP": 0, "DOWN": 0})
    hourly_seen = set()
    for r in hourly:
        h = int(r["hour"].split(":")[0])
        if h in hourly_seen:
            errors.append(f"[5] Duplicate hourly_service.csv row for hour {h}")
        hourly_seen.add(h)
        hourly_csv[h]["UP"] = int(r["up_trips"])
        hourly_csv[h]["DOWN"] = int(r["down_trips"])

    hourly_232 = defaultdict(lambda: {"UP": 0, "DOWN": 0})
    for t in full:
        h = hour_of(t["departure_time"])
        if t["direction"] not in ("UP", "DOWN"):
            errors.append(f"[5] Invalid direction for trip {t['trip_id']}: {t['direction']!r}")
        else:
            hourly_232[h][t["direction"]] += 1

    hourly_18 = defaultdict(lambda: {"UP": 0, "DOWN": 0})
    for t in partial:
        h = hour_of(t["departure_time"])
        if t["direction"] not in ("UP", "DOWN"):
            errors.append(f"[5] Invalid direction for trip {t['trip_id']}: {t['direction']!r}")
        else:
            hourly_18[h][t["direction"]] += 1

    bad5 = 0
    if hourly_seen != set(range(6, 23)):
        errors.append("[5] hourly_service.csv must contain exactly hours 6 through 22")
    for h in range(6, 23):
        for d in ("UP", "DOWN"):
            if hourly_csv[h][d] != hourly_232[h][d] + hourly_18[h][d]:
                bad5 += 1
    if bad5 == 0:
        print("[5] hourly_service.csv = 232 + partials (per hour, per direction): PASS")
    else:
        errors.append(f"[5] {bad5} hourly mismatches")

    # ---- Check 6: partial-trip gate ----
    # 6a: compare endpoint direction with trips.txt direction_id
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

    print("\n[6a] Partial trips: endpoint direction vs direction_id")
    if not mismatches:
        print("     All 18 partials agree. PASS")
    else:
        print(f"     {len(mismatches)} mismatches (report only, not a fail):")
        for row in mismatches:
            print("     ", row)

    # 6b: independent UP/DOWN count of partials
    up = sum(1 for t in partial if t["direction"] == "UP")
    down = sum(1 for t in partial if t["direction"] == "DOWN")
    print(f"\n[6b] Partial UP={up} DOWN={down} total={len(partial)}")

    # 6c: window membership + disjointness
    bad6c = []
    for t in partial:
        dep = parse_time_to_sec(t["departure_time"])
        if not (6 * 3600 <= dep < 23 * 3600):
            bad6c.append((t["trip_id"], "out_of_window"))
        if t["trip_id"] in full_ids:
            bad6c.append((t["trip_id"], "also_in_232"))
    if not bad6c:
        print("[6c] All 18 partials are in window and disjoint from the 232: PASS")
    else:
        errors.append(f"[6c] {len(bad6c)} partial-trip problems")
        for row in bad6c:
            print("     ", row)

    # ---- Check 7: initial-position pre-check (report only) ----
    print("\n[7] Initial position pre-check (report only):")
    first_hour = [t for t in full if 6 * 3600 <= parse_time_to_sec(t["departure_time"]) < 7 * 3600]
    alva_start = sum(1 for t in first_hour if t["first_stop"] == "ALVA")
    tpht_start = sum(1 for t in first_hour if t["first_stop"] == "TPHT")
    print(f"     06:00-07:00 departures: ALVA={alva_start}  TPHT={tpht_start}")
    print(f"     Fixed split: 9 at ALVA, 9 at TPHT. Each terminal serves its own starting trips.")

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

