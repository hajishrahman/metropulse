"""
MetroPulse Phase 3 crew validator (independent of solver).

Checks C1-C4 + C7 per pool size. C5 and C6 are NOT validated (C5 deferred,
C6 soft / informational only).

Writes crew_validation.json shaped:
    {"overall": "PASS"/"FAIL",
     "pools": {"45": {"checks": [...], "pool_status": "PASS"/"WARN"/"FAIL"},
               "50": ..., "55": ...}}
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

from solver import crew_config as CFG


ROOT = Path(__file__).parent.parent
CREW_SCHEDULE_CSV = ROOT / "data" / "processed" / CFG.CREW_SCHEDULE_CSV
SCHEDULE_CSV = ROOT / "data" / "processed" / "schedule.csv"
OUT_JSON = ROOT / "data" / "processed" / CFG.CREW_VALIDATION_JSON


# ==== helpers ====
def read_csv(path: Path, required_columns=()) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = set(required_columns) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path} missing columns: {sorted(missing)}")
        return list(reader)


def hhmmss_to_sec(t: str) -> int:
    try:
        h, m, s = (int(part) for part in str(t).split(":"))
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"Invalid time: {t!r}") from exc
    if h < 0 or not 0 <= m < 60 or not 0 <= s < 60:
        raise ValueError(f"Invalid time: {t!r}")
    return h * 3600 + m * 60 + s


def _group_by_driver(rows: list[dict]) -> dict[str, list[dict]]:
    by_driver = defaultdict(list)
    for r in rows:
        by_driver[r["driver_id"]].append(r)
    for d in by_driver:
        by_driver[d].sort(key=lambda r: hhmmss_to_sec(r["sign_on"]))
    return by_driver


# ==== checks ====
def check_c1_no_overlap(rows: list[dict]) -> dict:
    """
    C1: for each driver, no two assigned trips may overlap.

    crew_schedule.csv does NOT carry per-trip departure/arrival times --
    sign_on / sign_off are the driver's DAILY values, constant across all
    rows for the same driver. So we join each row with schedule.csv via
    trip_id to get the actual per-trip departure/arrival times, then check
    consecutive trips per driver in departure order.
    """
    trip_truth = {r["trip_id"]: r for r in read_csv(
        SCHEDULE_CSV, {"trip_id", "departure", "arrival"})}

    # Group by driver, but sort by actual trip departure (from schedule.csv)
    by_driver: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        t = trip_truth.get(r["trip_id"])
        if t is None:
            # Unknown trip_id -- treat as a hard failure; C4 will also catch it
            by_driver[r["driver_id"]].append({
                "trip_id": r["trip_id"], "dep": None, "arr": None,
            })
            continue
        by_driver[r["driver_id"]].append({
            "trip_id": r["trip_id"],
            "dep": hhmmss_to_sec(t["departure"]),
            "arr": hhmmss_to_sec(t["arrival"]),
        })

    failures = []
    for d, drs in by_driver.items():
        # Filter out any unknown-trip rows for the sort; they cause failures
        valid = [r for r in drs if r["dep"] is not None]
        unknown = [r for r in drs if r["dep"] is None]
        for r in unknown:
            failures.append({"driver_id": d, "trip_id": r["trip_id"],
                             "issue": "unknown_trip_in_schedule"})

        valid.sort(key=lambda r: r["dep"])
        for i in range(len(valid) - 1):
            a = valid[i]
            b = valid[i + 1]
            if b["dep"] < a["arr"] + CFG.MIN_TURNAROUND_SEC:
                failures.append({
                    "driver_id": d,
                    "a_trip": a["trip_id"],
                    "b_trip": b["trip_id"],
                    "a_arr": a["arr"],
                    "b_dep": b["dep"],
                    "gap_sec": b["dep"] - a["arr"],
                    "required_sec": CFG.MIN_TURNAROUND_SEC,
                })

    return {
        "check": "C1_no_overlap",
        "status": "PASS" if not failures else "FAIL",
        "details": {"failures": failures[:20], "total": len(failures)},
    }


def check_c2_max_duty(rows: list[dict]) -> dict:
    by_driver = _group_by_driver(rows)
    failures = []
    for d, drs in by_driver.items():
        first = min(hhmmss_to_sec(r["sign_on"]) for r in drs)
        last  = max(hhmmss_to_sec(r["sign_off"]) for r in drs)
        duty = last - first - CFG.SIGN_ON_BUFFER_SEC - CFG.SIGN_OFF_BUFFER_SEC
        if duty > CFG.MAX_DUTY_SEC:
            failures.append({"driver_id": d, "duty_sec": duty})
    return {
        "check": "C2_max_duty",
        "status": "PASS" if not failures else "FAIL",
        "details": {"failures": failures[:20], "total": len(failures)},
    }


def check_c3_sign_buffers(rows: list[dict]) -> dict:
    """
    C3: sign_on <= first_departure - 900 AND sign_off >= last_arrival + 900.
    We don't have raw trips here, so we recompute from schedule.csv by trip_id.
    """
    trip_truth = {r["trip_id"]: r for r in read_csv(
        SCHEDULE_CSV, {"trip_id", "departure", "arrival"})}
    failures = []
    for r in rows:
        t = trip_truth.get(r["trip_id"])
        if t is None:
            failures.append({"trip_id": r["trip_id"], "issue": "unknown_trip"})
            continue
        dep = hhmmss_to_sec(t["departure"])
        arr = hhmmss_to_sec(t["arrival"])
        son = hhmmss_to_sec(r["sign_on"])
        soff = hhmmss_to_sec(r["sign_off"])
        if dep - son < CFG.SIGN_ON_BUFFER_SEC:
            failures.append({"trip_id": r["trip_id"], "issue": "sign_on_too_late"})
        if soff - arr < CFG.SIGN_OFF_BUFFER_SEC:
            failures.append({"trip_id": r["trip_id"], "issue": "sign_off_too_early"})
    return {
        "check": "C3_sign_buffers",
        "status": "PASS" if not failures else "FAIL",
        "details": {"failures": failures[:20], "total": len(failures)},
    }


def check_c4_coverage(rows: list[dict], required_trip_ids: set[str]) -> dict:
    seen = [r["trip_id"] for r in rows]
    counts = defaultdict(int)
    for tid in seen:
        counts[tid] += 1
    duplicates = sorted(tid for tid, c in counts.items() if c > 1)
    missing = required_trip_ids - set(seen)
    extra = set(seen) - required_trip_ids
    failures = []
    if duplicates:
        failures.append({"duplicates": duplicates[:10]})
    if missing:
        failures.append({"missing": sorted(missing)[:10]})
    if extra:
        failures.append({"extra": sorted(extra)[:10]})
    return {
        "check": "C4_coverage",
        "status": "PASS" if not failures else "FAIL",
        "details": {
            "required": len(required_trip_ids),
            "scheduled": len(seen),
            "failures": failures,
        },
    }


def check_c7_reserve(rows: list[dict], pool_size: int) -> dict:
    active = len({r["driver_id"] for r in rows})
    reserve = pool_size - active
    if active > pool_size:
        status = "FAIL"
    elif reserve < CFG.MIN_RESERVE_DRIVERS:
        status = "WARN"
    else:
        status = "PASS"
    return {
        "check": "C7_reserve",
        "status": status,
        "details": {"pool_size": pool_size, "active": active, "reserve": reserve,
                    "min_reserve": CFG.MIN_RESERVE_DRIVERS},
    }


# ==== main ====
def main() -> None:
    print("=== MetroPulse Crew Validator ===\n")

    rows_all = read_csv(CREW_SCHEDULE_CSV, set(CFG.CREW_SCHEDULE_FIELDS))
    required_trip_ids = {r["trip_id"] for r in read_csv(
        SCHEDULE_CSV, {"trip_id"})}
    print(f"crew_schedule rows: {len(rows_all)}")
    print(f"trips in schedule:  {len(required_trip_ids)}")

    by_pool: dict[str, list[dict]] = defaultdict(list)
    for r in rows_all:
        by_pool[str(r["pool_size"])].append(r)

    pools_report = {}
    all_statuses = []
    for pool_key in sorted(by_pool, key=lambda k: int(k)):
        pool_rows = by_pool[pool_key]
        pool_size = int(pool_key)
        checks = [
            check_c1_no_overlap(pool_rows),
            check_c2_max_duty(pool_rows),
            check_c3_sign_buffers(pool_rows),
            check_c4_coverage(pool_rows, required_trip_ids),
            check_c7_reserve(pool_rows, pool_size),
        ]
        pool_status = "PASS"
        for c in checks:
            if c["status"] == "FAIL":
                pool_status = "FAIL"
                break
            if c["status"] == "WARN" and pool_status == "PASS":
                pool_status = "WARN"
        pools_report[pool_key] = {"checks": checks, "pool_status": pool_status}
        all_statuses.append(pool_status)

        print(f"\n--- pool_size {pool_key} ---")
        for c in checks:
            print(f"  [{c['status']}] {c['check']}")
        print(f"  pool_status: {pool_status}")

    overall = "PASS" if all(s in ("PASS", "WARN", "SKIPPED") for s in all_statuses) else "FAIL"
    print(f"\nOverall: {overall}")

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"overall": overall, "pools": pools_report}, f, indent=2)
    print(f"Written: {OUT_JSON}")


if __name__ == "__main__":
    main()