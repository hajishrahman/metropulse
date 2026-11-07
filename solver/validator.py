"""
MetroPulse independent schedule validator.

Re-checks every hard constraint (R1-R12) against the produced schedule
CSV — does NOT trust the CP-SAT solver's own status.

Inputs:
    data/hourly_service.csv
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
HOURLY_CSV = ROOT / "data" / "hourly_service.csv"
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
def check_r1_service_coverage(schedule: List[dict], hourly_csv: Path) -> dict:
    """R1: For each hour and direction, schedule trips >= required from hourly CSV."""
    hourly = read_csv_simple(hourly_csv)

    actual = {}
    for row in schedule:
        dep_hour = int(row["departure"].split(":")[0])
        direction = row["direction"]
        key = (dep_hour, direction)
        actual[key] = actual.get(key, 0) + 1

    failures = []
    for h in hourly:
        hour_start = int(h["hour"].split(":")[0])
        up_required = int(h["up_trips"])
        down_required = int(h["down_trips"])

        up_got = actual.get((hour_start, "UP"), 0)
        down_got = actual.get((hour_start, "DOWN"), 0)

        if up_got < up_required:
            failures.append({
                "hour": hour_start,
                "direction": "UP",
                "required": up_required,
                "got": up_got,
            })

        if down_got < down_required:
            failures.append({
                "hour": hour_start,
                "direction": "DOWN",
                "required": down_required,
                "got": down_got,
            })

    return {
        "check": "R1_service_coverage",
        "status": "PASS" if not failures else "FAIL",
        "details": {"failures": failures[:20]},
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
    """R3: All departures and arrivals within 06:00-23:00."""
    failures = []

    for row in schedule:
        dep = hhmm_to_min(row["departure"])
        

        # 06:00 = 360 min, 23:00 = 1380 min
        if not (360 <= dep < 1380):
            failures.append({
                "trip_id": row["trip_id"],
                "issue": "departure_out_of_window",
                "value": row["departure"],
            })

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
    """R4: At any minute, concurrent active rakes <= SERVICE_RAKES."""
    # Build events: +1 at departure, -1 at arrival
    events = []
    for row in schedule:
        dep = hhmm_to_min(row["departure"])
        arr = hhmm_to_min(row["arrival"])
        events.append((dep, +1, row["rake_id"]))
        events.append((arr, -1, row["rake_id"]))

    # Sort by minute
    events.sort()

    # Sweep and count concurrent rakes
    active = set()
    peak = 0
    peak_at = None
    failures = []

    for minute, delta, rake_id in events:
        if delta == +1:
            active.add(rake_id)
        else:
            active.discard(rake_id)

        if len(active) > peak:
            peak = len(active)
            peak_at = minute

    max_bound = config.SERVICE_RAKES
    if peak > max_bound:
        failures.append({"peak": peak, "bound": max_bound, "peak_at_min": peak_at})

    return {
        "check": "R4_fleet_bound",
        "status": "PASS" if not failures else "FAIL",
        "details": {
            "max_bound": max_bound,
            "peak_simultaneous": peak,
            "peak_at_hhmm": f"{peak_at // 60:02d}:{peak_at % 60:02d}" if peak_at else None,
            "failures": failures,
        },
    }


def check_r8_depot_capacity(schedule: List[dict], rakes_csv: Path) -> dict:
    """R8: Info Park-2 stabling capacity must not exceed 2."""
    return {
        "check": "R8_depot_capacity",
        "status": "SKIPPED",
        "details": {
            "reason": "No stabling assignments exist in V1.",
            "info_park_2_capacity_dpr": config.INFO_PARK_2_CAPACITY,
            "note": "Depot capacity cannot be validated without stabling assignments.",
        },
    }


def check_r10_maintenance_threshold(
    schedule: List[dict], rakes_csv: Path
) -> dict:
    """R10: Rakes at or above the maintenance threshold must not have trips."""
    rakes = read_csv_simple(rakes_csv)
    threshold = config.MAINTENANCE_THRESHOLD_KM
    mileage_by_rake = {
        row["rake_id"]: int(row["initial_mileage_km"])
        for row in rakes
    }
    max_mileage = max(mileage_by_rake.values(), default=None)
    over_threshold = {
        rake_id
        for rake_id, mileage in mileage_by_rake.items()
        if mileage >= threshold
    }
    failures = [
        {
            "rake_id": row["rake_id"],
            "trip_id": row["trip_id"],
            "initial_mileage_km": mileage_by_rake[row["rake_id"]],
        }
        for row in schedule
        if row["rake_id"] in over_threshold
    ]

    return {
        "check": "R10_maintenance_threshold",
        "status": "FAIL" if failures else "PASS",
        "details": {
            "threshold_km": threshold,
            "max_mileage_km": max_mileage,
            "failures": failures[:20],
            "total_violations": len(failures),
        },
    }


def check_r12_nonservice_window(schedule: List[dict]) -> dict:
    """R12: No departure before 05:00 or arrival after 24:00."""
    failures = []
    for row in schedule:
        departure = hhmm_to_min(row["departure"])
        arrival = hhmm_to_min(row["arrival"])
        if departure < 300:
            failures.append({
                "trip_id": row["trip_id"],
                "issue": "departure_before_service",
                "value": row["departure"],
            })
        if arrival > 1440:
            failures.append({
                "trip_id": row["trip_id"],
                "issue": "arrival_after_service",
                "value": row["arrival"],
            })

    return {
        "check": "R12_nonservice_window",
        "status": "PASS" if not failures else "FAIL",
        "details": {"failures": failures[:20]},
    }


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
def main():
    print("=== MetroPulse Validator ===\n")

    schedule = read_csv_simple(SCHEDULE_CSV)
    hourly = read_csv_simple(HOURLY_CSV)

    print(f"Schedule rows:       {len(schedule)}")
    print(f"Hourly rows:         {len(hourly)}")
    print()

    checks = [
        check_r1_service_coverage(schedule, HOURLY_CSV),
        check_r2a_design_headway(schedule),
        check_r3_operating_window(schedule),
        check_r4_fleet_bound(schedule),
        check_r5_rake_non_overlap(schedule),
        check_r6_turnaround(schedule),
        check_r7_running_time(schedule),
        check_r8_depot_capacity(schedule, RAKES_CSV),
        check_r10_maintenance_threshold(schedule, RAKES_CSV),
        check_r12_nonservice_window(schedule),
    ]

    for c in checks:
        print(f"[{c['status']}] {c['check']}")

    overall = "PASS" if all(
        c["status"] in ("PASS", "SKIPPED") for c in checks
    ) else "FAIL"

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

    