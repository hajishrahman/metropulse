# src/simulation/schedule_loader.py
"""
Load data/processed/schedule.csv and return trips grouped by rake.

Both the SimPy runner and the closed-form reference consume this loader,
so they see identical input order.

Units: integer seconds since midnight.

Provenance:
  [EXTERNAL]  data/processed/schedule.csv (CP-SAT output, Phase 1)
  [DERIVED]   dep_sec, arr_sec (HH:MM -> seconds)

Guards:
  - bad HH:MM format  -> ValueError with the offending row
  - duplicate trip_id -> ValueError
  - duration outside [MIN_DURATION_SEC, MAX_DURATION_SEC] -> ValueError
  - trip count vs solution.json (if present) -> mismatch raises
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

SCHEDULE_PATH = Path("data/processed/schedule.csv")
SOLUTION_PATH = Path("data/processed/solution.json")

# [DERIVED] Sanity range for per-trip GTFS durations (constraints-v2.1 R7).
# The old fixed 3000 s constant is removed. Each trip uses its own GTFS
# duration (arr - dep) as loaded from schedule.csv.
MIN_DURATION_SEC = 300    # 5 min  (safe lower bound — shortest partial is MUTT→ALVA ~8 min)
MAX_DURATION_SEC = 4500   # 75 min (safe upper bound — longest full trip ~54 min)


def parse_hhmm_to_sec(value: str) -> int:
    """Parse 'HH:MM' or 'HH:MM:SS' -> integer seconds since midnight.

    Accepts both forms. Raises ValueError on malformed input.

    HH may be up to 24 (GTFS allows times past midnight, e.g. 24:03:45).
    MM and SS must be 0-59.
    """
    if not isinstance(value, str):
        raise ValueError(f"bad time format (expected HH:MM or HH:MM:SS): {value!r}")
    parts = value.strip().split(":")
    if len(parts) not in (2, 3):
        raise ValueError(f"bad time format (expected HH:MM or HH:MM:SS): {value!r}")
    if any(
        len(part) != 2 or not part.isascii() or not part.isdigit()
        for part in parts
    ):
        raise ValueError(f"bad time format (expected HH:MM or HH:MM:SS): {value!r}")
    if len(parts) == 2:
        hh, mm = parts
        ss = "00"
    else:
        hh, mm, ss = parts
    h, m, s = int(hh), int(mm), int(ss)
    if not (0 <= h <= 24 and 0 <= m <= 59 and 0 <= s <= 59):
        raise ValueError(f"time out of range: {value!r}")
    return h * 3600 + m * 60 + s


def load_schedule(path: Path = SCHEDULE_PATH) -> list[dict]:
    """Load schedule.csv -> list of trip dicts (unsorted)."""
    if not path.is_file():
        raise FileNotFoundError(f"schedule not found: {path}")

    rows: list[dict] = []
    seen_ids: set[str] = set()
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        required = {"trip_id", "rake_id", "direction", "departure", "arrival"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"schedule.csv missing columns: {sorted(missing)}")

        for line_no, row in enumerate(reader, start=2):
            values = {key: (row[key] or "").strip() for key in required}
            tid = values["trip_id"]
            for field in ("trip_id", "rake_id", "direction"):
                if not values[field]:
                    raise ValueError(f"empty {field} at line {line_no}")
            if tid in seen_ids:
                raise ValueError(f"duplicate trip_id {tid!r} at line {line_no}")
            seen_ids.add(tid)

            try:
                dep_sec = parse_hhmm_to_sec(values["departure"])
                arr_sec = parse_hhmm_to_sec(values["arrival"])
            except ValueError as exc:
                raise ValueError(f"line {line_no}: {exc}") from exc

            duration_sec = arr_sec - dep_sec
            if not (MIN_DURATION_SEC <= duration_sec <= MAX_DURATION_SEC):
                raise ValueError(
                    f"trip {tid!r}: arr - dep = {duration_sec}s"
                    f" outside sane range [{MIN_DURATION_SEC}, {MAX_DURATION_SEC}]"
                )

            rows.append(
                {
                    "trip_id": tid,
                    "rake_id": values["rake_id"],
                    "direction": values["direction"],
                    "dep_sec": dep_sec,
                    "arr_sec": arr_sec,
                    "duration_sec": duration_sec,
                }
            )

    return rows


def group_by_rake(rows: list[dict]) -> dict[str, list[dict]]:
    """Group trips by rake, sorted by (dep_sec, trip_id)."""
    by_rake: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_rake[r["rake_id"]].append(r)
    for rake in by_rake:
        by_rake[rake].sort(key=lambda t: (t["dep_sec"], t["trip_id"]))
    return dict(by_rake)


def load_schedule_grouped(
    path: Path = SCHEDULE_PATH,
    solution_path: Path = SOLUTION_PATH,
) -> dict[str, list[dict]]:
    """Load + group. Cross-checks trip count against solution.json if present."""
    rows = load_schedule(path)
    if solution_path.is_file():
        with solution_path.open() as f:
            sol = json.load(f)
        if not isinstance(sol, dict):
            raise ValueError("solution.json must contain a JSON object")
        expected = sol.get("num_trips")
        if expected is not None:
            if isinstance(expected, bool) or not isinstance(expected, int) or expected < 0:
                raise ValueError("solution.json num_trips must be a non-negative integer")
            if expected != len(rows):
                raise ValueError(
                    f"trip count mismatch: schedule.csv has {len(rows)},"
                    f" solution.json says {expected}"
                )
    return group_by_rake(rows)


def total_trips(grouped: dict[str, list[dict]]) -> int:
    return sum(len(v) for v in grouped.values())
