"""
Extract trip-level data from GTFS.

Reads:  data/raw/trips.txt, data/raw/stop_times.txt
Writes: data/trips_full_route.csv
        data/stop_sequences_full_route.csv
        data/trips_partial.csv
        data/stop_sequences_partial.csv

Rules:
- Only WK service.
- Window: 06:00:00 <= departure < 23:00:00  (departure = first stop departure)
- Full route trip: first stop ALVA and last stop TPHT, or first TPHT and last ALVA.
- Direction: UP if last_index > first_index, DOWN if last_index < first_index.
  Station index is taken from the stop order of one normal ALVA->TPHT trip.
- Duration = arrival of last stop - departure of first stop, in seconds.
- Times may exceed 24:00:00. We parse H*3600 + M*60 + S without a day limit.
"""

import csv
from collections import defaultdict
from pathlib import Path

RAW_DIR = Path("data/raw")
OUT_DIR = Path("data")


# ---------- time helpers ----------

def parse_time_to_sec(t):
    """'HH:MM:SS' -> integer seconds. Allows H >= 24."""
    try:
        h, m, s = (int(part) for part in t.split(":"))
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"Invalid GTFS time: {t!r}") from exc
    if h < 0 or not 0 <= m < 60 or not 0 <= s < 60:
        raise ValueError(f"Invalid GTFS time: {t!r}")
    return h * 3600 + m * 60 + s


# ---------- loaders ----------

def load_stop_times():
    """Return {trip_id: [row, ...] sorted by stop_sequence}."""
    by_trip = defaultdict(list)
    with open(RAW_DIR / "stop_times.txt", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            by_trip[row["trip_id"]].append(row)
    for tid in by_trip:
        by_trip[tid].sort(key=lambda r: int(r["stop_sequence"]))
        if any(
            int(previous["stop_sequence"]) == int(current["stop_sequence"])
            for previous, current in zip(by_trip[tid], by_trip[tid][1:])
        ):
            raise ValueError(f"Trip {tid} has duplicate stop_sequence values")
    return by_trip


def load_trips():
    with open(RAW_DIR / "trips.txt", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_station_index(stop_times_by_trip):
    """
    Build station index from one complete UP trip (ALVA first, TPHT last).
    Returns {stop_id: index}. ALVA = 0, TPHT = 24 (or last index).
    """
    for rows in stop_times_by_trip.values():
        if not rows:
            continue
        if rows[0]["stop_id"] == "ALVA" and rows[-1]["stop_id"] == "TPHT":
            return {r["stop_id"]: i for i, r in enumerate(rows)}
    raise RuntimeError("No complete ALVA->TPHT trip found to build station index.")


# ---------- classification ----------

def classify(rows, station_index, trip_row):
    """
    Look at one trip's stop rows.
    Return a dict with trip info, or None if not used.
    Also returns a reason string for exclusions.
    """
    first = rows[0]
    last = rows[-1]

    first_stop = first["stop_id"]
    last_stop = last["stop_id"]

    dep_sec = parse_time_to_sec(first["departure_time"])

    # Window check uses departure of first stop
    if not (6 * 3600 <= dep_sec < 23 * 3600):
        return None, "out_of_window"

    # Direction by station index
    if first_stop not in station_index or last_stop not in station_index:
        return None, "unknown_stop"

    fi = station_index[first_stop]
    li = station_index[last_stop]
    if fi == li:
        return None, "zero_length"
    direction = "UP" if li > fi else "DOWN"

    duration = parse_time_to_sec(last["arrival_time"]) - dep_sec
    if duration <= 0:
        raise ValueError(f"Trip {trip_row['trip_id']} has non-positive duration")

    is_full = (
        (first_stop == "ALVA" and last_stop == "TPHT")
        or (first_stop == "TPHT" and last_stop == "ALVA")
    )

    info = {
        "trip_id": trip_row["trip_id"],
        "origin_stop": first_stop,
        "destination_stop": last_stop,
        "direction": direction,
        "departure_time": first["departure_time"],
        "arrival_time": last["arrival_time"],
        "duration": duration,
        "stop_count": len(rows),
        "first_stop": first_stop,
        "last_stop": last_stop,
    }
    return info, ("full_route" if is_full else "partial")


# ---------- writers ----------

TRIP_FIELDS = [
    "trip_id", "origin_stop", "destination_stop", "direction",
    "departure_time", "arrival_time", "duration",
    "stop_count", "first_stop", "last_stop",
]

SEQ_FIELDS = ["trip_id", "stop_id", "stop_sequence", "arrival_time", "departure_time"]


def write_trips(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=TRIP_FIELDS)
        w.writeheader()
        w.writerows(rows)


def write_sequences(path, trip_ids, stop_times_by_trip):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SEQ_FIELDS)
        w.writeheader()
        for tid in trip_ids:
            for r in stop_times_by_trip[tid]:
                w.writerow({
                    "trip_id": tid,
                    "stop_id": r["stop_id"],
                    "stop_sequence": r["stop_sequence"],
                    "arrival_time": r["arrival_time"],
                    "departure_time": r["departure_time"],
                })


# ---------- main ----------

def main():
    stop_times_by_trip = load_stop_times()
    trips = load_trips()
    station_index = build_station_index(stop_times_by_trip)

    full = []
    partial = []
    out_of_window = []
    unknown = []

    seen_trip_ids = set()
    for trip in trips:
        tid = trip["trip_id"]
        if tid in seen_trip_ids:
            raise ValueError(f"Duplicate trip_id in trips.txt: {tid}")
        seen_trip_ids.add(tid)
        if trip["service_id"] != "WK":
            continue
        rows = stop_times_by_trip.get(tid)
        if not rows:
            continue

        info, label = classify(rows, station_index, trip)

        if info is None:
            if label == "out_of_window":
                out_of_window.append(tid)
            else:
                unknown.append((tid, label))
            continue

        if label == "full_route":
            full.append(info)
        elif label == "partial":
            partial.append(info)

    OUT_DIR.mkdir(exist_ok=True)

    write_trips(OUT_DIR / "trips_full_route.csv", full)
    write_sequences(OUT_DIR / "stop_sequences_full_route.csv",
                    [t["trip_id"] for t in full], stop_times_by_trip)

    write_trips(OUT_DIR / "trips_partial.csv", partial)
    write_sequences(OUT_DIR / "stop_sequences_partial.csv",
                    [t["trip_id"] for t in partial], stop_times_by_trip)

    print("=== Extract summary ===")
    print(f"Full-route trips written: {len(full)}")
    print(f"Partial trips written:    {len(partial)}")
    print(f"Out-of-window trips:      {len(out_of_window)}")
    print(f"Skipped (other):          {len(unknown)}")
    print()
    print("Out-of-window trip_ids:")
    for tid in out_of_window:
        print("  ", tid)
    if unknown:
        print("Skipped (other):")
        for tid, why in unknown:
            print("  ", tid, why)


if __name__ == "__main__":
    main()
