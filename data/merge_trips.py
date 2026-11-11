"""
Merge full-route trips (232) + partial trips (18) into one dataset (250).

Reads:
    data/trips_full_route.csv
    data/trips_partial.csv

Writes:
    data/trips_all.csv   (same schema, 250 rows)

Verifies:
    - 250 rows total
    - No duplicate trip_id
    - Sum of durations, first/last stop distribution printed

Run:
    python data/merge_trips.py
"""
import csv
from collections import Counter
from pathlib import Path

DATA_DIR = Path("data")
FULL = DATA_DIR / "trips_full_route.csv"
PARTIAL = DATA_DIR / "trips_partial.csv"
OUT = DATA_DIR / "trips_all.csv"

FIELDS = [
    "trip_id", "origin_stop", "destination_stop", "direction",
    "departure_time", "arrival_time", "duration",
    "stop_count", "first_stop", "last_stop",
]


def read(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    full = read(FULL)
    partial = read(PARTIAL)
    all_trips = full + partial

    # Sanity checks
    ids = [t["trip_id"] for t in all_trips]
    dup = [tid for tid, n in Counter(ids).items() if n > 1]
    if dup:
        raise SystemExit(f"DUPLICATE trip_ids: {dup[:10]}")
    if len(all_trips) != 250:
        raise SystemExit(f"Expected 250 trips, got {len(all_trips)}")

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(all_trips)

    print("=== Merge summary ===")
    print(f"  Full-route : {len(full)}")
    print(f"  Partial    : {len(partial)}")
    print(f"  Total      : {len(all_trips)}")
    print(f"  Written    : {OUT}")
    print()
    print("=== First-stop distribution ===")
    for k, v in sorted(Counter(t["first_stop"] for t in all_trips).items()):
        print(f"  {k}: {v}")
    print()
    print("=== Last-stop distribution ===")
    for k, v in sorted(Counter(t["last_stop"] for t in all_trips).items()):
        print(f"  {k}: {v}")
    print()
    print("=== Direction distribution ===")
    for k, v in sorted(Counter(t["direction"] for t in all_trips).items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()