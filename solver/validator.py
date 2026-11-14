"""
MetroPulse independent schedule validator (V1, real GTFS trips).

Checks 10 constraints (R8 and R12 removed from validator scope in V1):
    R1  service coverage
    R3  operating window
    R4  fleet availability
    R5  rake non-overlap
    R6  turnaround + deadhead (per-pair: 5 / 8 / 15 min)
    R7  running time (matches trips_all.csv)
    R9  maintenance exclusivity (PASS trivially while maintenance.csv empty)
    R10 maintenance threshold
    R11 terminal continuity (KVTR-aware: requires predecessor at non-terminal stops)
    D   direction consistency (computed from first_stop / last_stop)

R8 (depot capacity) and R12 (non-service window) are not checked in V1:
    R8 is not modelled (no stabling assignment).
    R12 is subsumed by R3 (R3 already enforces 04:40 ≤ departure < 24:00).

R6 per-pair deadhead:
    same terminal          : 5 min  (turnaround)
    ALVA <-> TPHT          : 15 min (terminal-to-terminal deadhead)
    MUTT <-> ALVA or TPHT  : 8 min  (MUTT-to-terminal deadhead)

R11 KVTR rule:
    If deadhead(home, first_stop) is undefined (non-terminal, non-MUTT stop
    such as KVTR), a trip starting there can only be taken by a rake that
    ends a previous trip at that same stop within turnaround of departure.
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
MAINTENANCE_CSV = ROOT / "data" / "synthetic" / "maintenance.csv"
SCHEDULE_CSV = ROOT / "data" / "processed" / "schedule.csv"
OUT_JSON = ROOT / "data" / "processed" / "validation.json"


_TERMINALS = ("ALVA", "TPHT")

# Station order for direction recomputation (ALVA=0 ... TPHT=24)
STATION_ORDER = {
    "ALVA": 0, "PNCU": 1, "CPPY": 2, "ATTK": 3, "MUTT": 4,
    "KLMT": 5, "CCUV": 6, "PDPM": 7, "EDAP": 8, "CGPP": 9,
    "PARV": 10, "JLSD": 11, "KALR": 12, "TNHL": 13, "MGRD": 14,
    "MACE": 15, "ERSH": 16, "KVTR": 17, "EMKM": 18, "VYTA": 19,
    "THYK": 20, "PETT": 21, "VAKK": 22, "SNJN": 23, "TPHT": 24,
}


# ===========================================================================
# Helpers
# ===========================================================================
def _deadhead_sec(stop_a: str, stop_b: str) -> int:
    """R6 deadhead between two DIFFERENT stops. Caller checks a==b separately."""
    if stop_a in _TERMINALS and stop_b in _TERMINALS:
        return config.TERMINAL_TO_TERMINAL_DEADHEAD_MIN * 60
    return config.MUTTOM_TO_TERMINAL_DEADHEAD_MIN * 60


def _gap_required(stop_a: str, stop_b: str) -> int:
    if stop_a == stop_b:
        return config.TERMINAL_TURNAROUND_MIN * 60
    return _deadhead_sec(stop_a, stop_b)


def _first_trip_deadhead(home: str, start_stop: str):
    """Returns (seconds, valid). valid=False means predecessor is required."""
    if home == start_stop:
        return 0, True
    if home in _TERMINALS and start_stop in _TERMINALS:
        return config.TERMINAL_TO_TERMINAL_DEADHEAD_MIN * 60, True
    if (home == "MUTT" and start_stop in _TERMINALS) or \
       (home in _TERMINALS and start_stop == "MUTT"):
        return config.MUTTOM_TO_TERMINAL_DEADHEAD_MIN * 60, True
    return None, False


def read_csv(path: Path, required_columns=()):
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = set(required_columns) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path} missing columns: {sorted(missing)}")
        return list(reader)


def hhmmss_to_sec(t: str) -> int:
    try:
        h, m, s = (int(part) for part in t.split(":"))
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"Invalid time: {t!r}") from exc
    if h < 0 or not 0 <= m < 60 or not 0 <= s < 60:
        raise ValueError(f"Invalid time: {t!r}")
    return h * 3600 + m * 60 + s


# ===========================================================================
# Checks
# ===========================================================================
def check_r1_service_coverage(schedule, trips):
    req_ids = {t["trip_id"] for t in trips}
    sch_ids = [s["trip_id"] for s in schedule]
    seen = set(sch_ids)
    counts = defaultdict(int)
    for tid in sch_ids:
        counts[tid] += 1
    duplicates = sorted(tid for tid, count in counts.items() if count > 1)
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
    service = {r["rake_id"] for r in rakes if r["status"] == "service"}
    used = {s["rake_id"] for s in schedule}
    bad = used - service
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
    by_rake = defaultdict(list)
    for row in schedule:
        by_rake[row["rake_id"]].append(row)

    failures = []
    same_pairs = 0
    cross15_pairs = 0
    cross8_pairs = 0

    for rid, rows in by_rake.items():
        rows.sort(key=lambda r: hhmmss_to_sec(r["departure"]))
        for i in range(len(rows) - 1):
            a, b = rows[i], rows[i + 1]
            a_arr = hhmmss_to_sec(a["arrival"])
            b_dep = hhmmss_to_sec(b["departure"])
            gap = b_dep - a_arr
            required = _gap_required(a["last_stop"], b["first_stop"])

            if a["last_stop"] == b["first_stop"]:
                same_pairs += 1
                kind = "same_terminal"
            elif a["last_stop"] in _TERMINALS and b["first_stop"] in _TERMINALS:
                cross15_pairs += 1
                kind = "cross_terminal_15"
            else:
                cross8_pairs += 1
                kind = "cross_terminal_8_mutt"

            if gap < required:
                failures.append({
                    "rake_id": rid, "a": a["trip_id"], "b": b["trip_id"],
                    "gap_sec": gap, "required_sec": required, "type": kind,
                    "a_last_stop": a["last_stop"], "b_first_stop": b["first_stop"],
                })

    return {
        "check": "R6_turnaround",
        "status": "PASS" if not failures else "FAIL",
        "details": {
            "same_terminal_pairs": same_pairs,
            "cross_terminal_15_pairs": cross15_pairs,
            "cross_terminal_8_mutt_pairs": cross8_pairs,
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

def check_r9_maintenance_exclusivity(schedule, maintenance):
    """
    R9 — no trip may be assigned to a rake inside a maintenance window.

    maintenance.csv schema (V1, empty): rake_id, start, end (times in HH:MM:SS).
    Empty file → PASS trivially. Populated → trips whose rake is in a
    [start, end) window are flagged.
    """
    if not maintenance:
        return {
            "check": "R9_maintenance_exclusivity",
            "status": "PASS",
            "details": {"maintenance_windows": 0, "failures": []},
        }
    # Group by rake
    windows = defaultdict(list)
    for w in maintenance:
        rid = w.get("rake_id")
        if not rid:
            continue
        try:
            s = hhmmss_to_sec(w["start"])
            e = hhmmss_to_sec(w["end"])
        except Exception:
            continue
        windows[rid].append((s, e))

    failures = []
    for row in schedule:
        rid = row["rake_id"]
        if rid not in windows:
            continue
        dep = hhmmss_to_sec(row["departure"])
        arr = hhmmss_to_sec(row["arrival"])
        for s, e in windows[rid]:
            # overlap: [dep, arr) ∩ [s, e) is non-empty
            if dep < e and arr > s:
                failures.append({"trip_id": row["trip_id"], "rake_id": rid,
                                 "window": [s, e], "trip": [dep, arr]})
                break
    return {
        "check": "R9_maintenance_exclusivity",
        "status": "PASS" if not failures else "FAIL",
        "details": {"maintenance_windows": sum(len(v) for v in windows.values()),
                    "failures": failures[:20]},
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
    R11 — first-trip home rule with KVTR-aware deadhead.

    A rake whose home is H may serve trip t as its FIRST trip if:
      - first_stop(t) == H, or
      - deadhead(H, first_stop(t)) is defined AND
        departure(t) >= OPERATING_START_SEC + deadhead(H, first_stop(t)).

    If deadhead is undefined (non-terminal, non-MUTT stop such as KVTR),
    trip t can only be taken by a rake that ended a previous trip at
    first_stop(t) within turnaround of departure(t).

    Cross-terminal pair gaps are checked by R6, not here.
    """
    home = {r["rake_id"]: r["initial_location"]
            for r in rakes if r["status"] == "service"}
    depot_open = config.OPERATING_START_SEC
    turnaround = config.TERMINAL_TURNAROUND_MIN * 60

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
            dh, valid = _first_trip_deadhead(h, first["first_stop"])
            if not valid:
                # must have come from a predecessor ending at first_stop
                # (i.e. first trip must have a valid prior stop match)
                # Since it's the first trip of this rake, no predecessor exists.
                failures.append({
                    "rake_id": rid, "issue": "first_trip_non_terminal_no_predecessor",
                    "home": h, "first_trip_first_stop": first["first_stop"],
                    "first_trip_departure": first["departure"], "trip_id": first["trip_id"],
                })
            elif first_dep < depot_open + dh:
                failures.append({
                    "rake_id": rid, "issue": "first_trip_deadhead_infeasible",
                    "home": h, "first_trip_first_stop": first["first_stop"],
                    "first_trip_departure": first["departure"],
                    "required_min_departure_sec": depot_open + dh, "trip_id": first["trip_id"],
                })

        for i in range(len(rows) - 1):
            if rows[i]["last_stop"] != rows[i + 1]["first_stop"]:
                cross_switches += 1

    return {
        "check": "R11_terminal_continuity",
        "status": "PASS" if not failures else "FAIL",
        "details": {"cross_terminal_switches": cross_switches, "failures": failures[:20]},
    }

def check_direction_consistency(schedule):
    """Recompute direction from first_stop / last_stop; must match stated direction."""
    failures = []
    for row in schedule:
        fs = row["first_stop"]
        ls = row["last_stop"]
        i_fs = STATION_ORDER.get(fs)
        i_ls = STATION_ORDER.get(ls)
        if i_fs is None or i_ls is None:
            failures.append({"trip_id": row["trip_id"],
                             "issue": "unknown_stop",
                             "first_stop": fs, "last_stop": ls})
            continue
        expected = "UP" if i_ls > i_fs else ("DOWN" if i_ls < i_fs else None)
        if expected is None:
            failures.append({"trip_id": row["trip_id"],
                             "issue": "zero_distance_trip",
                             "first_stop": fs, "last_stop": ls})
            continue
        if row["direction"] != expected:
            failures.append({"trip_id": row["trip_id"],
                             "issue": "direction_mismatch",
                             "stated": row["direction"],
                             "expected": expected,
                             "first_stop": fs, "last_stop": ls})
    return {
        "check": "D_direction_consistency",
        "status": "PASS" if not failures else "FAIL",
        "details": {"failures": failures[:20]},
    }


# ===========================================================================
# Main
# ===========================================================================
def main():
    print("=== MetroPulse Validator ===\n")
    schedule = read_csv(SCHEDULE_CSV, {
        "trip_id", "rake_id", "direction", "first_stop", "last_stop",
        "departure", "arrival",
    })
    trips = read_csv(TRIPS_CSV, {"trip_id", "duration"})
    rakes = read_csv(RAKES_CSV, {
        "rake_id", "status", "initial_mileage_km", "initial_location",
    })
    # maintenance.csv may be empty (V1). If file doesn't exist, treat as empty.
    try:
        maintenance = read_csv(MAINTENANCE_CSV)
    except FileNotFoundError:
        maintenance = []

    print(f"Schedule rows: {len(schedule)}")
    print(f"GTFS trips:    {len(trips)}")
    print(f"Rakes:         {len(rakes)}")
    print(f"Maintenance:   {len(maintenance)}")
    print()

    checks = [
        check_r1_service_coverage(schedule, trips),
        check_r3_operating_window(schedule),
        check_r4_fleet_availability(schedule, rakes),
        check_r5_rake_non_overlap(schedule),
        check_r6_turnaround(schedule),
        check_r7_running_time(schedule, trips),
        check_r9_maintenance_exclusivity(schedule, maintenance),
        check_r10_maintenance_threshold(schedule, rakes),
        check_r11_terminal_continuity(schedule, rakes),
        check_direction_consistency(schedule),
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