# src/simulation/kpis.py
"""
KPI computation for Phase 2. Pure functions. No SimPy, no file I/O.

Inputs are the per-rake result dicts from run_simpy() and the grouped
trip dicts from schedule_loader. Both must cover the same trip IDs —
this is enforced by a guard.

Provenance:
  [SYNTHETIC] all delay values (clipped normal, mean -48s pre-clip,
              std swept E1-E4, clip [0, 300] s)
  [DERIVED]   on-time %, propagation %, headway counts

Notes on interpretation:
  - Delays are never negative. "On time" means "late by at most N seconds".
    The symbol +/- is one-sided in this model.
  - Own delay is capped at 300 s (= 5 min inclusive). So a trip that is
    late by more than 5 min at +/-5 tolerance must be late because of
    PROPAGATION, not its own delay. That makes on_time_5min a pure
    propagation metric. on_time_3min and on_time_1min mix own delay
    and propagation.
  - Propagation percent counts trips with propagated_delay > 0.
    That is NOT the same as "trips with any delay" (which would also
    include own delay).
"""

from __future__ import annotations

from collections import defaultdict


def _assert_covers(per_rake_results: dict, grouped: dict) -> None:
    if set(per_rake_results.keys()) != set(grouped.keys()):
        raise ValueError(
            f"rake set mismatch: results={sorted(per_rake_results)},"
            f" grouped={sorted(grouped)}"
        )
    for rake in grouped:
        trips = grouped[rake]
        results = per_rake_results[rake]
        if len(trips) != len(results):
            raise ValueError(
                f"rake {rake}: {len(trips)} trips vs {len(results)} results"
            )
        trip_ids = {t["trip_id"] for t in trips}
        result_ids = {r["trip_id"] for r in results}
        if trip_ids != result_ids:
            missing = trip_ids - result_ids
            extra = result_ids - trip_ids
            raise ValueError(
                f"rake {rake}: trip_id mismatch"
                f" (missing={sorted(missing)}, extra={sorted(extra)})"
            )


def compute_on_time(
    per_rake_results: dict,
    grouped: dict,
    tolerance_sec: int,
) -> dict:
    """
    On-time percentage at a given tolerance (seconds).

    Headline denominator: all trips (250).
    Secondary denominator: eligible trips (all trips minus each rake's first),
    which cannot propagate.

    On-time means actual_dep - sched_dep <= tolerance_sec.
    """
    if tolerance_sec < 0:
        raise ValueError("tolerance_sec must be >= 0")
    _assert_covers(per_rake_results, grouped)

    total = 0
    on_time_total = 0
    eligible = 0
    on_time_eligible = 0

    for rake, results in per_rake_results.items():
        first_trip_id = grouped[rake][0]["trip_id"] if grouped[rake] else None
        for r in results:
            total += 1
            is_on = (r["actual_dep"] - r["sched_dep"]) <= tolerance_sec
            if is_on:
                on_time_total += 1
            if r["trip_id"] == first_trip_id:
                continue
            eligible += 1
            if is_on:
                on_time_eligible += 1

    return {
        "tolerance_sec": tolerance_sec,
        "on_time_250_pct": round(100.0 * on_time_total / total, 2) if total else 0.0,
        "on_time_250_count": on_time_total,
        "trips_total": total,
        "on_time_232_eligible_pct": (
            round(100.0 * on_time_eligible / eligible, 2) if eligible else 0.0
        ),
        "on_time_232_eligible_count": on_time_eligible,
        "trips_eligible": eligible,
    }


def compute_propagation(per_rake_results: dict, grouped: dict) -> dict:
    """
    Propagation percentage.

    Numerator: trips with propagated_delay > 0 (delay carried from a
    preceding trip on the same rake).
    Denominator: eligible trips = all trips minus each rake's first trip.
    """
    _assert_covers(per_rake_results, grouped)

    eligible = 0
    with_propagation = 0
    total = 0
    for rake, results in per_rake_results.items():
        first_trip_id = grouped[rake][0]["trip_id"] if grouped[rake] else None
        for r in results:
            total += 1
            if r["trip_id"] == first_trip_id:
                continue
            eligible += 1
            if r["propagated_delay"] > 0:
                with_propagation += 1

    pct = round(100.0 * with_propagation / eligible, 2) if eligible else 0.0
    return {
        "trips_with_propagation": with_propagation,
        "trips_eligible": eligible,
        "trips_total": total,
        "propagation_pct": pct,
    }


def compute_total_propagated_delay(per_rake_results: dict) -> dict:
    """
    Sum of propagated_delay across all trips. Reported in both seconds
    (exact) and minutes (rounded to 1 decimal). Also reports max single value.
    """
    total_sec = 0
    max_sec = 0
    for results in per_rake_results.values():
        for r in results:
            d = r["propagated_delay"]
            total_sec += d
            if d > max_sec:
                max_sec = d
    return {
        "total_propagated_delay_sec": total_sec,
        "total_propagated_delay_min": round(total_sec / 60.0, 1),
        "max_single_propagated_delay_sec": max_sec,
        "max_single_propagated_delay_min": round(max_sec / 60.0, 1),
    }


def compute_headway_violations(
    per_rake_results: dict,
    grouped: dict,
    threshold_sec: int = 120,
) -> dict:
    """
    Same-direction headway violations.

    Groups by direction only (not rake). Sorts by (actual_dep, trip_id) for
    deterministic tie-break. A violation is a gap STRICTLY BELOW threshold_sec.

    Reports actual-gap violations AND scheduled-gap violations separately.
    """
    _assert_covers(per_rake_results, grouped)
    if threshold_sec < 0:
        raise ValueError("threshold_sec must be >= 0")

    # Build direction-indexed lists.
    by_dir_actual: dict[str, list[tuple[int, str]]] = defaultdict(list)
    by_dir_sched: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for rake, results in per_rake_results.items():
        directions = {t["trip_id"]: t["direction"] for t in grouped[rake]}
        for r in results:
            direction = directions[r["trip_id"]]
            by_dir_actual[direction].append((r["actual_dep"], r["trip_id"]))
            by_dir_sched[direction].append((r["sched_dep"], r["trip_id"]))

    def count_violations(pairs: dict[str, list[tuple[int, str]]]) -> tuple[int, int]:
        count = 0
        min_gap = None
        for direction, items in pairs.items():
            items.sort()
            for (a_t, _), (b_t, _) in zip(items, items[1:]):
                gap = b_t - a_t
                if min_gap is None or gap < min_gap:
                    min_gap = gap
                if gap < threshold_sec:
                    count += 1
        return count, (min_gap if min_gap is not None else 0)

    actual_count, actual_min = count_violations(by_dir_actual)
    sched_count, sched_min = count_violations(by_dir_sched)

    return {
        "threshold_sec": threshold_sec,
        "actual_violations": actual_count,
        "actual_min_gap_sec": actual_min,
        "scheduled_violations": sched_count,
        "scheduled_min_gap_sec": sched_min,
    }


def compute_kpis(per_rake_results: dict, grouped: dict) -> dict:
    """
    Full KPI bundle for one experiment. No metadata here; the caller
    adds metadata separately (see experiments.py).
    """
    _assert_covers(per_rake_results, grouped)
    return {
        "on_time_5min": compute_on_time(per_rake_results, grouped, 300),
        "on_time_3min": compute_on_time(per_rake_results, grouped, 180),
        "on_time_1min": compute_on_time(per_rake_results, grouped, 60),
        "propagation": compute_propagation(per_rake_results, grouped),
        "total_propagated_delay": compute_total_propagated_delay(per_rake_results),
        "headway": compute_headway_violations(per_rake_results, grouped, 120),
    }
