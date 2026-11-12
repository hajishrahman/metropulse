# src/simulation/preflight.py
"""
Phase 2 pre-flight checks — read-only.

Reads data/processed/schedule.csv, reports:
  - trip count, rake count, eligible trips (trips - rakes)
  - rake chain continuity (UP/DOWN alternation)
  - scheduled slack distribution per consecutive same-rake pair
  - scheduled same-direction headway violations (expected 0 per R2a)

Writes nothing. Prints a report to stdout.

Provenance tags:
  [EXTERNAL]   schedule.csv (CP-SAT output from GTFS 2024-25)
  [DERIVED]    eligible trips, slack, headways
  [SYNTHETIC]  turnaround = 300 s (5 min, project assumption)
"""

from __future__ import annotations
from collections import defaultdict

from pathlib import Path

from src.simulation.reference import TURNAROUND_SEC
from src.simulation.schedule_loader import group_by_rake, load_schedule

SCHEDULE_PATH = Path("data/processed/schedule.csv")


def continuity_report(by_rake: dict[str, list[dict]]) -> dict:
    """
    Check each rake's sorted chain alternates UP/DOWN.
    Physically, a rake that ends a trip at TPHT must next depart from TPHT (DOWN),
    and vice versa. Non-alternating chains imply deadhead repositioning that
    V1 does not model (constraints-v2 R11 not configured).
    """
    per_rake = {}
    total_pairs = 0
    total_alternating = 0
    offenders = []

    for rake, trips in by_rake.items():
        chain_pairs = 0
        chain_ok = 0
        for prev, nxt in zip(trips, trips[1:]):
            chain_pairs += 1
            if prev["direction"] != nxt["direction"]:
                chain_ok += 1
            else:
                offenders.append(
                    {
                        "rake": rake,
                        "prev_trip": prev["trip_id"],
                        "prev_dir": prev["direction"],
                        "prev_arr_sec": prev["arr_sec"],
                        "next_trip": nxt["trip_id"],
                        "next_dir": nxt["direction"],
                        "next_dep_sec": nxt["dep_sec"],
                    }
                )
        per_rake[rake] = {
            "trips": len(trips),
            "pairs": chain_pairs,
            "alternating_pairs": chain_ok,
        }
        total_pairs += chain_pairs
        total_alternating += chain_ok

    return {
        "per_rake": per_rake,
        "total_pairs": total_pairs,
        "alternating_pairs": total_alternating,
        "all_alternating": total_alternating == total_pairs,
        "offenders": offenders,
    }


def slack_report(by_rake: dict[str, list[dict]]) -> dict:
    """
    Slack = (next scheduled departure - prev scheduled arrival) - turnaround.
    Propagation only occurs when the propagated delay exceeds slack.
    Report distribution so KPIs can be interpreted.
    """
    slacks = []
    for rake, trips in by_rake.items():
        for prev, nxt in zip(trips, trips[1:]):
            slack = (nxt["dep_sec"] - prev["arr_sec"]) - TURNAROUND_SEC
            slacks.append(slack)

    slacks_sorted = sorted(slacks)
    n = len(slacks_sorted)

    def pct(p: float) -> int:
        if n == 0:
            return 0
        idx = min(n - 1, max(0, int(round((p / 100.0) * (n - 1)))))
        return slacks_sorted[idx]

    return {
        "count": n,
        "min_sec": slacks_sorted[0] if n else 0,
        "p05_sec": pct(5),
        "p25_sec": pct(25),
        "median_sec": pct(50),
        "p75_sec": pct(75),
        "p95_sec": pct(95),
        "max_sec": slacks_sorted[-1] if n else 0,
        "zero_slack_count": sum(1 for s in slacks if s == 0),
        "negative_slack_count": sum(1 for s in slacks if s < 0),
        "lt_60s_count": sum(1 for s in slacks if s < 60),
        "lt_300s_count": sum(1 for s in slacks if s < 300),
    }


def scheduled_headway_report(rows: list[dict], min_headway_sec: int = 120) -> dict:
    """
    Count scheduled same-direction headway violations.
    R2a (constraints-v2) requires >= 2 min between consecutive same-direction departures.
    Expected 0 because the solver enforces R2a.
    """
    by_dir: dict[str, list[int]] = defaultdict(list)
    for r in rows:
        by_dir[r["direction"]].append(r["dep_sec"])

    violations = []
    min_gap = None
    for direction, deps in by_dir.items():
        deps_sorted = sorted(deps)
        for a, b in zip(deps_sorted, deps_sorted[1:]):
            gap = b - a
            if min_gap is None or gap < min_gap:
                min_gap = gap
            if gap < min_headway_sec:
                violations.append({"direction": direction, "gap_sec": gap, "a": a, "b": b})

    return {
        "min_headway_sec": min_headway_sec,
        "min_gap_observed_sec": min_gap,
        "violation_count": len(violations),
        "violations": violations,
    }


def main() -> None:
    if not SCHEDULE_PATH.is_file():
        raise SystemExit(f"ERROR: {SCHEDULE_PATH} not found")

    rows = load_schedule(SCHEDULE_PATH)
    by_rake = group_by_rake(rows)

    n_trips = len(rows)
    n_rakes = len(by_rake)
    n_eligible = n_trips - n_rakes

    print("=" * 72)
    print("Phase 2 pre-flight report")
    print("=" * 72)
    print(f"Trips total:      {n_trips}")
    print(f"Rakes used:       {n_rakes}  ({sorted(by_rake)})")
    print(f"Eligible trips:   {n_eligible}  (trips - rakes; excludes each rake's first)")
    print()

    cont = continuity_report(by_rake)
    print("-" * 72)
    print("Rake chain continuity (UP/DOWN alternation)")
    print("-" * 72)
    print(f"Total consecutive pairs: {cont['total_pairs']}")
    print(f"Alternating pairs:       {cont['alternating_pairs']}")
    print(f"All alternating:         {cont['all_alternating']}")
    if cont["offenders"]:
        print(f"OFFENDERS ({len(cont['offenders'])}):")
        for o in cont["offenders"][:20]:
            print(
                f"  {o['rake']}: {o['prev_trip']}({o['prev_dir']}, arr {o['prev_arr_sec']})"
                f" -> {o['next_trip']}({o['next_dir']}, dep {o['next_dep_sec']})"
            )
        if len(cont["offenders"]) > 20:
            print(f"  ... and {len(cont['offenders']) - 20} more")
    print()

    sl = slack_report(by_rake)
    print("-" * 72)
    print(f"Scheduled slack distribution (gap - {TURNAROUND_SEC}s turnaround)")
    print("-" * 72)
    print(f"Count:            {sl['count']}")
    print(f"Min:              {sl['min_sec']}s")
    print(f"p05:              {sl['p05_sec']}s")
    print(f"p25:              {sl['p25_sec']}s")
    print(f"Median:           {sl['median_sec']}s")
    print(f"p75:              {sl['p75_sec']}s")
    print(f"p95:              {sl['p95_sec']}s")
    print(f"Max:              {sl['max_sec']}s")
    print(f"Zero-slack pairs: {sl['zero_slack_count']}")
    print(f"Negative slack:   {sl['negative_slack_count']}")
    print(f"Slack < 60s:      {sl['lt_60s_count']}")
    print(f"Slack < 300s:     {sl['lt_300s_count']}")
    print()

    hw = scheduled_headway_report(rows)
    print("-" * 72)
    print(f"Scheduled same-direction headway (>= {hw['min_headway_sec']}s per R2a)")
    print("-" * 72)
    print(f"Min observed gap: {hw['min_gap_observed_sec']}s")
    print(f"Violations:       {hw['violation_count']}  (expected 0)")
    print()


if __name__ == "__main__":
    main()
