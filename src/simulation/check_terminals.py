# src/simulation/check_terminals.py
"""
Read-only check: does each rake's next trip start where the previous ended?

Reads:
  data/raw/trips.txt        -- trip_id -> direction_id, service_id
  data/raw/stop_times.txt   -- trip_id -> first stop, last stop
  data/processed/schedule.csv -- trip_id -> rake_id, direction, times

For each rake's consecutive pair (prev, next):
  prev_last_stop  =?=  next_first_stop

Prints summary. Writes nothing.
"""

from __future__ import annotations
import csv
from collections import defaultdict
from pathlib import Path

TRIPS = Path("data/raw/trips.txt")
STOP_TIMES = Path("data/raw/stop_times.txt")
SCHEDULE = Path("data/processed/schedule.csv")


def load_trip_terminals() -> dict[str, tuple[str, str]]:
    """trip_id -> (first_stop_id, last_stop_id)."""
    # stop_times can be large; only keep first and last per trip.
    first: dict[str, tuple[int, str]] = {}
    last: dict[str, tuple[int, str]] = {}
    with STOP_TIMES.open(newline="", encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        for row in r:
            tid = row["trip_id"]
            try:
                seq = int(row["stop_sequence"])
            except (KeyError, ValueError):
                continue
            sid = row["stop_id"]
            if tid not in first or seq < first[tid][0]:
                first[tid] = (seq, sid)
            if tid not in last or seq > last[tid][0]:
                last[tid] = (seq, sid)
    out = {}
    for tid in first:
        out[tid] = (first[tid][1], last[tid][1])
    return out


def load_schedule() -> list[dict]:
    rows = []
    with SCHEDULE.open(newline="") as f:
        for r in csv.DictReader(f):
            rows.append(
                {
                    "trip_id": r["trip_id"],
                    "rake_id": r["rake_id"],
                    "direction": r["direction"],
                    "dep": r["departure"],
                    "arr": r["arrival"],
                }
            )
    return rows


def parse_hhmm_to_sec(s: str) -> int:
    hh, mm = s.strip().split(":")
    return int(hh) * 3600 + int(mm) * 60


def main() -> None:
    if not TRIPS.exists() or not STOP_TIMES.exists():
        raise SystemExit("ERROR: GTFS raw files not found in data/raw/")
    if not SCHEDULE.exists():
        raise SystemExit("ERROR: schedule.csv not found")

    terminals = load_trip_terminals()
    rows = load_schedule()

    by_rake: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_rake[r["rake_id"]].append(r)
    for rake in by_rake:
        by_rake[rake].sort(key=lambda t: (parse_hhmm_to_sec(t["dep"]), t["trip_id"]))

    # Map direction label -> (origin, dest) using GTFS stop terminals
    # and see which stop pair each label corresponds to.
    label_pairs: dict[str, set[tuple[str, str]]] = defaultdict(set)
    missing = 0
    for r in rows:
        t = terminals.get(r["trip_id"])
        if t is None:
            missing += 1
            continue
        label_pairs[r["direction"]].add(t)

    print("=" * 72)
    print("Terminal / direction label check")
    print("=" * 72)
    print(f"Trips in schedule: {len(rows)}")
    print(f"Missing GTFS stop info: {missing}")
    for label, pairs in sorted(label_pairs.items()):
        print(f"direction '{label}':")
        for a, b in sorted(pairs):
            print(f"    {a} -> {b}")
    print()

    # Now the real check: does arrival stop of prev == departure stop of next?
    total = 0
    matched = 0
    mismatched_examples = []
    for rake, trips in by_rake.items():
        for prev, nxt in zip(trips, trips[1:]):
            pt = terminals.get(prev["trip_id"])
            nt = terminals.get(nxt["trip_id"])
            if pt is None or nt is None:
                continue
            total += 1
            prev_end = pt[1]
            next_start = nt[0]
            if prev_end == next_start:
                matched += 1
            else:
                mismatched_examples.append(
                    {
                        "rake": rake,
                        "prev": prev["trip_id"],
                        "prev_dir": prev["direction"],
                        "prev_end": prev_end,
                        "next": nxt["trip_id"],
                        "next_dir": nxt["direction"],
                        "next_start": next_start,
                    }
                )

    print("-" * 72)
    print("Physical continuity (prev last stop == next first stop)")
    print("-" * 72)
    print(f"Pairs checked:  {total}")
    print(f"Matched:        {matched}")
    print(f"Mismatched:     {total - matched}")
    if mismatched_examples:
        print("Mismatch examples (first 15):")
        for m in mismatched_examples[:15]:
            print(
                f"  {m['rake']}: {m['prev']}({m['prev_dir']}) ends at {m['prev_end']}"
                f" -> {m['next']}({m['next_dir']}) starts at {m['next_start']}"
            )
    print()


if __name__ == "__main__":
    main()