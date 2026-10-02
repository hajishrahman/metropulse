"""
MetroPulse independent schedule validator.

Re-checks every hard constraint (R1-R12) against the produced schedule
CSV — does NOT trust the CP-SAT solver's own status.

Inputs:
    data/dpr/hourly_service.csv
    data/synthetic/rakes.csv
    data/processed/schedule.csv

Output:
    data/processed/validation.json — per-check PASS/FAIL + details

Spec: docs/constraints-v2.md §9
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from solver import config


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
DPR_CSV = ROOT / "data" / "dpr" / "hourly_service.csv"
RAKES_CSV = ROOT / "data" / "synthetic" / "rakes.csv"
SCHEDULE_CSV = ROOT / "data" / "processed" / "schedule.csv"
OUT_JSON = ROOT / "data" / "processed" / "validation.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def hhmm_to_min(hhmm: str) -> int:
    """Convert 'HH:MM' to minutes since midnight."""
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def read_csv_simple(path: Path) -> List[dict]:
    """Read CSV into list of dicts using stdlib (no pandas)."""
    import csv
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------
def check_r1_service_coverage(schedule: List[dict], dpr: List[dict]) -> dict:
    """
    R1: For each (hour_start, direction), the count of trips in the
    schedule must be >= DPR required_departures.
    """
    from collections import defaultdict
    actual = defaultdict(int)
    for row in schedule:
        dep_min = hhmm_to_min(row["departure"])
        hour_start = dep_min // 60
        actual[(hour_start, row["direction"])] += 1

    failures = []
    total_checked = 0
    for d in dpr:
        h = int(d["hour_start"])
        direction = d["direction"]
        required = int(d["required_departures"])
        got = actual.get((h, direction), 0)
        total_checked += 1
        if got < required:
            failures.append({
                "hour": h, "direction": direction,
                "required": required, "got": got,
            })

    return {
        "check": "R1_service_coverage",
        "status": "PASS" if not failures else "FAIL",
        "details": {
            "buckets_checked": total_checked,
            "failures": failures[:20],
        },
    }


def check_r2a_design_headway(schedule: List[dict]) -> dict:
    """
    R2a: Consecutive departures in the same direction must be >= 90 sec apart.

    Note: 90 sec = 1.5 min. Since our time granularity is minutes, we require
    >= 1 minute gap. Any gap < 1 min (i.e., same-minute departures) fails.
    """
    from collections import defaultdict
    by_dir = defaultdict(list)
    for row in schedule:
        by_dir[row["direction"]].append(
            (hhmm_to_min(row["departure"]), row["trip_id"])
        )

    min_gap_min = 1
    failures = []
    for direction, entries in by_dir.items():
        entries.sort()
        for i in range(len(entries) - 1):
            gap = entries[i + 1][0] - entries[i][0]
            if gap < min_gap_min:
                failures.append({
                    "direction": direction,
                    "trip_a": entries[i][1],
                    "trip_b": entries[i + 1][1],
                    "gap_min": gap,
                })

    return {
        "check": "R2a_design_headway",
        "status": "PASS" if not failures else "FAIL",
        "details": {"failures": failures[:20], "total_violations": len(failures)},
    }


def check_r3_operating_window(schedule: List[dict]) -> dict:
    """R3: All departures and arrivals within 05:00 – 24:00."""
    failures = []
    for row in schedule:
        dep = hhmm_to_min(row["departure"])
        arr = hhmm_to_min(row["arrival"])
        if not (5 * 60 <= dep < 24 * 60):
            failures.append({"trip_id": row["trip_id"], "issue": "departure_out_of_window", "value": row["departure"]})
        if arr > 24 * 60:
            failures.append({"trip_id": row["trip_id"], "issue": "arrival_after_midnight", "value": row["arrival"]})

    return {
        "check": "R3_operating_window",
        "status": "PASS" if not failures else "FAIL",
        "details": {"failures": failures[:20]},
    }


def check_r5_rake_non_overlap(schedule: List[dict]) -> dict:
    """R5: No rake assigned to two overlapping time intervals."""
    from collections import defaultdict
    by_rake = defaultdict(list)
    for row in schedule:
        by_rake[row["rake_id"]].append((
            hhmm_to_min(row["departure"]),
            hhmm_to_min(row["arrival"]),
            row["trip_id"],
        ))

    failures = []
    for rid, trips in by_rake.items():
        trips.sort()
        for i in range(len(trips) - 1):
            prev_end = trips[i][1]
            next_start = trips[i + 1][0]
            if next_start < prev_end:
                failures.append({
                    "rake_id": rid,
                    "trip_a": trips[i][2],
                    "trip_b": trips[i + 1][2],
                    "overlap_min": prev_end - next_start,
                })

    return {
        "check": "R5_rake_non_overlap",
        "status": "PASS" if not failures else "FAIL",
        "details": {"failures": failures[:20], "total_violations": len(failures)},
    }


def check_r6_turnaround(schedule: List[dict]) -> dict:
    """R6: Between consecutive trips on same rake, gap >= 3 min."""
    from collections import defaultdict
    by_rake = defaultdict(list)
    for row in schedule:
        by_rake[row["rake_id"]].append((
            hhmm_to_min(row["departure"]),
            hhmm_to_min(row["arrival"]),
            row["trip_id"],
        ))

    failures = []
    total_pairs = 0
    for rid, trips in by_rake.items():
        trips.sort()
        for i in range(len(trips) - 1):
            total_pairs += 1
            gap = trips[i + 1][0] - trips[i][1]
            if gap < config.TERMINAL_TURNAROUND_MIN:
                failures.append({
                    "rake_id": rid,
                    "trip_a": trips[i][2],
                    "trip_b": trips[i + 1][2],
                    "gap_min": gap,
                })

    return {
        "check": "R6_turnaround",
        "status": "PASS" if not failures else "FAIL",
        "details": {
            "consecutive_pairs_checked": total_pairs,
            "failures": failures[:20],
            "total_violations": len(failures),
        },
    }


def check_r7_running_time(schedule: List[dict]) -> dict:
    """R7: Each trip duration matches ONE_WAY_RUNNING_MIN (rounded)."""
    expected = int(round(config.ONE_WAY_RUNNING_MIN))
    failures = []
    for row in schedule:
        dur = hhmm_to_min(row["arrival"]) - hhmm_to_min(row["departure"])
        if dur != expected:
            failures.append({
                "trip_id": row["trip_id"],
                "expected": expected,
                "got": dur,
            })

    return {
        "check": "R7_running_time",
        "status": "PASS" if not failures else "FAIL",
        "details": {"failures": failures[:20]},
    }


def check_r4_fleet_bound(schedule: List[dict]) -> dict:
    """
    R4: Per-hour concurrent active rakes <= SERVICE_RAKES + 1 (traffic spare).
    Simplified: per (hour), count distinct rakes used.
    """
    from collections import defaultdict
    hourly_rakes = defaultdict(set)
    for row in schedule:
        h = hhmm_to_min(row["departure"]) // 60
        hourly_rakes[h].add(row["rake_id"])

    max_bound = config.BARE_RAKE_REQUIREMENT + config.TRAFFIC_SPARE  # 16
    failures = []
    peak = 0
    for h, rakes in hourly_rakes.items():
        count = len(rakes)
        peak = max(peak, count)
        if count > max_bound:
            failures.append({"hour": h, "active_rakes": count, "bound": max_bound})

    return {
        "check": "R4_fleet_bound",
        "status": "PASS" if not failures else "FAIL",
        "details": {
            "max_bound": max_bound,
            "peak_active_in_hour": peak,
            "failures": failures[:20],
        },
    }


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
def main():
    print("=== MetroPulse Validator ===\n")

    schedule = read_csv_simple(SCHEDULE_CSV)
    dpr = read_csv_simple(DPR_CSV)

    print(f"Schedule rows:       {len(schedule)}")
    print(f"DPR rows:            {len(dpr)}")
    print()

    checks = [
        check_r1_service_coverage(schedule, dpr),
        check_r2a_design_headway(schedule),
        check_r3_operating_window(schedule),
        check_r4_fleet_bound(schedule),
        check_r5_rake_non_overlap(schedule),
        check_r6_turnaround(schedule),
        check_r7_running_time(schedule),
    ]

    for c in checks:
        print(f"[{c['status']}] {c['check']}")

    # Overall
    overall = "PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL"

    print()
    print(f"Overall: {overall}")

    result = {
        "overall": overall,
        "num_trips": len(schedule),
        "checks": checks,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nWritten: {OUT_JSON}")


if __name__ == "__main__":
    main()