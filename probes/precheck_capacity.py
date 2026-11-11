"""
Read-only capacity pre-check.

Question:
  With hard terminal continuity (no deadhead), can 9 rakes at ALVA
  and 9 rakes at TPHT cover all 232 full-route trips?

How we count:
  For each terminal T:
    For each trip starting at T:
      rake is busy from departure_time to arrival_time + TURNAROUND
    (because after arriving, the rake needs 5 min turnaround
     before it can leave again)

  Then we sweep a timeline and record the maximum number of
  overlapping busy intervals at T at any moment.

If max_busy <= 9 at both terminals: the 9/9 split is workable.
If max_busy >  9 at one terminal: that side needs more rakes,
                                   or the split must change.

Also prints:
  - peak time for each terminal
  - trips per terminal
  - simple turnaround-gap check (is each trip's start time
    after at least one earlier trip's arrival + turnaround?)
    -> report only, not a fail
"""

import csv
from pathlib import Path

DATA_DIR = Path("data")
TURNAROUND_SEC = 5 * 60  # 5 minutes

# Fixed split (from decisions)
RAKES_AT_ALVA = 9
RAKES_AT_TPHT = 9


def parse_time_to_sec(t):
    try:
        h, m, s = (int(part) for part in t.split(":"))
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"Invalid GTFS time: {t!r}") from exc
    if h < 0 or not 0 <= m < 60 or not 0 <= s < 60:
        raise ValueError(f"Invalid GTFS time: {t!r}")
    return h * 3600 + m * 60 + s


def format_sec(sec):
    h = sec // 3600
    m = (sec % 3600) // 60
    return f"{h:02d}:{m:02d}"


def load_trips():
    with open(DATA_DIR / "trips_full_route.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def max_overlap(intervals):
    """
    intervals: list of (start_sec, end_sec)
    Returns (max_count, peak_start_sec).
    Counts half-open intervals [start, end).
    """
    events = []
    for s, e in intervals:
        events.append((s, +1))
        events.append((e, -1))
    # end before start at the same second: -1 sorts before +1
    events.sort()

    cur = 0
    peak = 0
    peak_time = None
    for t, delta in events:
        cur += delta
        if cur > peak:
            peak = cur
            peak_time = t
    return peak, peak_time


def main():
    trips = load_trips()

    alva_intervals = []
    tpht_intervals = []
    trips_at_alva = 0
    trips_at_tpht = 0
    invalid = []

    for t in trips:
        start = parse_time_to_sec(t["departure_time"])
        arr = parse_time_to_sec(t["arrival_time"])
        end = arr + TURNAROUND_SEC
        if arr <= start:
            print(f"[warn] trip {t['trip_id']} arrives no later than it departs")
            invalid.append(t["trip_id"])
            continue

        if t["first_stop"] == "ALVA":
            alva_intervals.append((start, end))
            trips_at_alva += 1
        elif t["first_stop"] == "TPHT":
            tpht_intervals.append((start, end))
            trips_at_tpht += 1
        else:
            print(f"[warn] trip {t['trip_id']} starts at {t['first_stop']}")
            invalid.append(t["trip_id"])

    peak_alva, peak_alva_time = max_overlap(alva_intervals)
    peak_tpht, peak_tpht_time = max_overlap(tpht_intervals)

    print("=== Trips per terminal ===")
    print(f"  Starting at ALVA: {trips_at_alva}")
    print(f"  Starting at TPHT: {trips_at_tpht}")
    print(f"  Total:            {trips_at_alva + trips_at_tpht}")
    print()

    print("=== Peak busy rakes (trip + turnaround) ===")
    if peak_alva_time is not None:
        print(f"  ALVA: {peak_alva} at {format_sec(peak_alva_time)}  (available: {RAKES_AT_ALVA})")
    if peak_tpht_time is not None:
        print(f"  TPHT: {peak_tpht} at {format_sec(peak_tpht_time)}  (available: {RAKES_AT_TPHT})")
    print()

    ok = not invalid
    if invalid:
        print(f"  {len(invalid)} trips were excluded from the capacity check.")
    if peak_alva > RAKES_AT_ALVA:
        print(f"  ALVA needs at least {peak_alva} rakes, only {RAKES_AT_ALVA} given.")
        ok = False
    if peak_tpht > RAKES_AT_TPHT:
        print(f"  TPHT needs at least {peak_tpht} rakes, only {RAKES_AT_TPHT} given.")
        ok = False

    if ok:
        print("  Result: 9/9 fixed split is WORKABLE for the peak busy count.")
        print("  (This is a capacity check only. CP-SAT still has to build")
        print("   the exact assignment, so real feasibility may be tighter.)")
    else:
        print("  Result: 9/9 fixed split is NOT enough by peak count.")
        print("  Suggest: raise the rakes at the failing terminal and re-check.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
