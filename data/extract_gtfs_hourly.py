"""
Extract hourly service plan from GTFS.

Reads: data/raw/{trips,stop_times}.txt
Writes: data/hourly_service.csv

Output schema: hour, up_trips, down_trips, total_trips
Where:
  - hour is "04:00-05:00" format
  - up_trips = trips from ALVA to TPHT in that hour
  - down_trips = trips from TPHT to ALVA in that hour

Window: 04:40 ≤ departure < 24:00, all WK trips (255-trip V1 model).
Legacy reconciliation only — the solver does not read hourly_service.csv.
"""

import csv
from collections import defaultdict
from pathlib import Path

RAW_DIR = Path("data/raw")
OUT_DIR = Path("data")
OUT_FILE = OUT_DIR / "hourly_service.csv"

OUT_DIR.mkdir(exist_ok=True)

WINDOW_START_SEC = 4 * 3600 + 40 * 60   # 04:40
WINDOW_END_SEC = 24 * 3600              # 24:00


def load_stop_times():
    stops = defaultdict(list)

    with open(RAW_DIR / "stop_times.txt", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            stops[row["trip_id"]].append(row)

    for tid in stops:
        stops[tid].sort(key=lambda r: int(r["stop_sequence"]))

    return stops


def load_trips():
    trips = []
    with open(RAW_DIR / "trips.txt", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            trips.append(row)
    return trips


def parse_time_to_sec(t):
    try:
        h, m, s = (int(part) for part in t.split(":"))
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"Invalid GTFS time: {t!r}") from exc
    if h < 0 or not 0 <= m < 60 or not 0 <= s < 60:
        raise ValueError(f"Invalid GTFS time: {t!r}")
    return h * 3600 + m * 60 + s


def get_direction(first_stop, last_stop, direction_id):
    """Determine UP/DOWN from stops, fallback to direction_id."""
    if first_stop == "ALVA":
        return "UP"
    if last_stop == "ALVA":
        return "DOWN"
    if first_stop == "TPHT":
        return "DOWN"
    if last_stop == "TPHT":
        return "UP"
    # Fallback
    if direction_id == "0":
        return "UP"
    elif direction_id == "1":
        return "DOWN"
    return None


def main():
    stop_times = load_stop_times()
    trips = load_trips()

    counts = defaultdict(lambda: {"UP": 0, "DOWN": 0})
    total = 0
    skipped = 0

    for trip in trips:
        if trip["service_id"] != "WK":
            continue
        tid = trip["trip_id"]
        if tid not in stop_times:
            skipped += 1
            continue
        stops = stop_times[tid]
        if not stops:
            skipped += 1
            continue
        first = stops[0]
        last = stops[-1]
        direction = get_direction(first["stop_id"], last["stop_id"],
                                  trip.get("direction_id", ""))
        if direction is None:
            skipped += 1
            continue
        dep_sec = parse_time_to_sec(first["departure_time"])
        if not (WINDOW_START_SEC <= dep_sec < WINDOW_END_SEC):
            continue
        hour = dep_sec // 3600
        counts[hour][direction] += 1
        total += 1

    print(f"Total WK trips counted: {total}")
    print(f"Skipped trips: {skipped}")

    with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["hour", "up_trips", "down_trips", "total_trips"])
        for h in range(4, 24):
            up = counts[h]["UP"]
            down = counts[h]["DOWN"]
            hour_label = f"{h:02d}:00-{h+1:02d}:00"
            w.writerow([hour_label, up, down, up + down])

    print(f"\nWrote: {OUT_FILE}")
    print("\nHourly distribution:")
    for h in range(4, 24):
        up = counts[h]["UP"]
        down = counts[h]["DOWN"]
        print(f"  {h:02d}:00-{h+1:02d}:00: {up} UP + {down} DOWN = {up + down} total")


if __name__ == "__main__":
    main()