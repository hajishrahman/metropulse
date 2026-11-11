"""
MetroPulse independent schedule validator (V1, real GTFS trips).

R11 check: same-terminal switch requires >= turnaround (5 min).
           cross-terminal switch requires >= deadhead (15 min).
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

from solver import config


ROOT = Path(__file__).parent.parent
TRIPS_CSV = ROOT / "data" / "trips_all.csv"
RAKES_CSV = ROOT / "data" / "synthetic" / "rakes.csv"
SCHEDULE_CSV = ROOT / "data" / "processed" / "schedule.csv"
OUT_JSON = ROOT / "data" / "processed" / "validation.json"


def read_csv(path: Path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def hhmmss_to_sec(t: str) -> int:
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)


def check_r1_service_coverage(schedule, trips):
    req_ids = {t["trip_id"] for t in trips}
    sch_ids = [s["trip_id"] for s in schedule]
    seen = set(sch_ids)
    duplicates = sorted({tid for tid in sch_ids if sch_ids.count(tid) > 1})
    missing = req_ids - seen
    extra = seen - req_ids
    failures = []
    if duplicates:
        failures.append({"duplicates": duplicates[:10]})
    if missing:
        failures.append({"missing": sorted(missing)[:10]})
    if extra:
        failures.append({"extra": sorted(extra)[:10]})
    return {
        "check": "R1_service_coverage",
        "status": "PASS" if not failures else "FAIL",
        "details": {"required": len(req_ids), "scheduled": len(sch_ids), "failures": failures},
    }


def check_r3_operating_window(schedule):
    failures = []
    for row in schedule:
        dep = hhmmss_to_sec(row["departure"])
        if not (config.OPERATING_START_SEC <= dep < config.OPERATING_END_SEC):
            failures.append({"trip_id": row["trip_id"], "departure": row["departure"]})
    return {
        "check": "R3_operating_window",
        "status": "PASS" if not failures else "FAIL",
        "details": {"failures": failures[:20]},
    }


def check_r4_fleet_availability(schedule, rakes):
    maintenance = {r["rake_id"] for r in rakes if r["status"] != "service"}
    used = {s["rake_id"] for s in schedule}
    bad = used & maintenance
    return {
        "check": "R4_fleet_availability",
        "status": "PASS" if not bad else "FAIL",
        "details": {"bad_rakes": sorted(bad)},
    }


def check_r5_rake_non_overlap(schedule):
    by_rake = defaultdict(list)
    for row in schedule:
        by_rake[row["rake_id"]].append(
            (hhmmss_to_sec(row["departure"]), hhmmss_to_sec(row["arrival"]), row["trip_id"])
        )
    failures = []
    for rid, rows in by_rake.items():
        rows.sort()
        for i in range(len(rows) - 1):
            if rows[i + 1][0] < rows[i][1]:
                failures.append({"rake_id": rid, "a": rows[i][2], "b": rows[i + 1][2]})
    return {
        "check": "R5_rake_non_overlap",
        "status": "PASS" if not failures else "FAIL",
        "details": {"failures": failures[:20], "total": len(failures)},
    }


def check_r6_turnaround(schedule):
    """Same-terminal gap >= turnaround; cross-terminal gap >= deadhead."""
    turn = config.TERMINAL_TURNAROUND_MIN * 60
    deadhead = config.TERMINAL_TO_TERMINAL_DEADHEAD_MIN * 60
    by_rake = defaultdict(list)
    for row in schedule:
        by_rake[row["rake_id"]].append(row)

    failures = []
    same_pairs = 0
    cross_pairs = 0
    for rid, rows in by_rake.items():
        rows.sort(key=lambda r: hhmmss_to_sec(r["departure"]))
        for i in range(len(rows) - 1):
            a, b = rows[i], rows[i + 1]
            a_arr = hhmmss_to_sec(a["arrival"])
            b_dep = hhmmss_to_sec(b["departure"])
            gap = b_dep - a_arr
            if a["last_stop"] == b["first_stop"]:
                same_pairs += 1
                if gap < turn:
                    failures.append({"rake_id": rid, "a": a["trip_id"], "b": b["trip_id"],
                                     "gap_sec": gap, "required_sec": turn, "type": "same_terminal"})
            else:
                cross_pairs += 1
                if gap < deadhead:
                    failures.append({"rake_id": rid, "a": a["trip_id"], "b": b["trip_id"],
                                     "gap_sec": gap, "required_sec": deadhead, "type": "cross_terminal"})
    return {
        "check": "R6_turnaround",
        "status": "PASS" if not failures else "FAIL",
        "details": {
            "same_terminal_pairs": same_pairs,
            "cross_terminal_pairs": cross_pairs,
            "failures": failures[:20],
        },
    }


def check_r7_running_time(schedule, trips):
    truth = {t["trip_id"]: int(t["duration"]) for t in trips}
    failures = []
    for row in schedule:
        got = hhmmss_to_sec(row["arrival"]) - hhmmss_to_sec(row["departure"])
        exp = truth.get(row["trip_id"])
        if exp is None or got != exp:
            failures.append({"trip_id": row["trip_id"], "expected": exp, "got": got})
    return {
        "check": "R7_running_time",
        "status": "PASS" if not failures else "FAIL",
        "details": {"failures": failures[:20]},
    }


def check_r8_depot_capacity(schedule, rakes):
    return {
        "check": "R8_depot_capacity",
        "status": "SKIPPED",
        "details": {"reason": "No stabling assignment in V1.",
                    "info_park_2_capacity": config.INFO_PARK_2_CAPACITY},
    }


def check_r10_maintenance_threshold(schedule, rakes):
    threshold = config.MAINTENANCE_THRESHOLD_KM
    over = {r["rake_id"] for r in rakes if int(r["initial_mileage_km"]) >= threshold}
    bad = [s for s in schedule if s["rake_id"] in over]
    max_mileage = max((int(r["initial_mileage_km"]) for r in rakes), default=None)
    return {
        "check": "R10_maintenance_threshold",
        "status": "PASS" if not bad else "FAIL",
        "details": {"threshold_km": threshold, "max_mileage_km": max_mileage,
                    "rakes_over_threshold": sorted(over),
                    "failures": [{"trip_id": s["trip_id"], "rake_id": s["rake_id"]} for s in bad[:20]]},
    }


def check_r11_terminal_continuity(schedule, rakes):
    """
    R11 — first-trip home rule with depot-opening relaxation.

    A rake whose home is H may take a first trip starting at S if:
      - S == H, OR
      - trip.departure >= DEPOT_OPENING_TIME + deadhead(H, S)

    Cross-terminal gaps between consecutive trips are checked by R6.
    """
    home = {r["rake_id"]: r["initial_location"]
            for r in rakes if r["status"] == "service"}
    depot_open = config.OPERATING_START_SEC

    def deadhead_seconds(h, s):
        if h == s:
            return 0
        if h in ("ALVA", "TPHT") and s in ("ALVA", "TPHT"):
            return config.TERMINAL_TO_TERMINAL_DEADHEAD_MIN * 60
        return config.MUTTOM_TO_TERMINAL_DEADHEAD_MIN * 60

    by_rake = defaultdict(list)
    for row in schedule:
        by_rake[row["rake_id"]].append(row)

    failures = []
    cross_switches = 0

    for rid, rows in by_rake.items():
        rows.sort(key=lambda r: hhmmss_to_sec(r["departure"]))
        first = rows[0]
        h = home.get(rid)
        if h and first["first_stop"] != h:
            first_dep = hhmmss_to_sec(first["departure"])
            dh = deadhead_seconds(h, first["first_stop"])
            if first_dep < depot_open + dh:
                failures.append({
                    "rake_id": rid, "issue": "first_trip_deadhead_infeasible",
                    "home": h, "first_trip_first_stop": first["first_stop"],
                    "first_trip_departure": first["departure"],
                    "required_min_departure_sec": depot_open + dh,
                    "trip_id": first["trip_id"],
                })

        for i in range(len(rows) - 1):
            if rows[i]["last_stop"] != rows[i + 1]["first_stop"]:
                cross_switches += 1

    return {
        "check": "R11_terminal_continuity",
        "status": "PASS" if not failures else "FAIL",
        "details": {
            "cross_terminal_switches": cross_switches,
            "failures": failures[:20],
        },
    }

def check_r12_nonservice_window(schedule):
    """R12: no departure before 06:00 (arrivals may extend past 23:00)."""
    failures = []
    for row in schedule:
        dep = hhmmss_to_sec(row["departure"])
        if dep < config.OPERATING_START_SEC:
            failures.append({"trip_id": row["trip_id"], "departure": row["departure"]})
    return {
        "check": "R12_nonservice_window",
        "status": "PASS" if not failures else "FAIL",
        "details": {"failures": failures[:20]},
    }

def main():
    print("=== MetroPulse Validator ===\n")
    schedule = read_csv(SCHEDULE_CSV)
    trips = read_csv(TRIPS_CSV)
    rakes = read_csv(RAKES_CSV)
    print(f"Schedule rows: {len(schedule)}")
    print(f"GTFS trips:    {len(trips)}")
    print(f"Rakes:         {len(rakes)}")
    print()

    checks = [
        check_r1_service_coverage(schedule, trips),
        check_r3_operating_window(schedule),
        check_r4_fleet_availability(schedule, rakes),
        check_r5_rake_non_overlap(schedule),
        check_r6_turnaround(schedule),
        check_r7_running_time(schedule, trips),
        check_r8_depot_capacity(schedule, rakes),
        check_r10_maintenance_threshold(schedule, rakes),
        check_r11_terminal_continuity(schedule, rakes),
        check_r12_nonservice_window(schedule),
    ]
    for c in checks:
        print(f"[{c['status']}] {c['check']}")
    overall = "PASS" if all(c["status"] in ("PASS", "SKIPPED") for c in checks) else "FAIL"
    print()
    print(f"Overall: {overall}")

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump({"overall": overall, "num_trips": len(schedule), "checks": checks}, f, indent=2)
    print(f"\nWritten: {OUT_JSON}")


if __name__ == "__main__":
    main()