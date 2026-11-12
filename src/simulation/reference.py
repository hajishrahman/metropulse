# src/simulation/reference.py
"""
Closed-form delay propagation recurrence for Phase 2.

This is a pure-Python reference model. No SimPy. No I/O.
The SimPy runner (Step 3) must produce identical output.

Units: integer seconds throughout.

Provenance:
  [SYNTHETIC] turnaround = 300 s (5 min, constraints-v2 R6)
  [DERIVED]   running time = 3000 s (50 min integer, constraints-v2 R7)
  [SYNTHETIC] delay clip [0, 300] s (constraints-v2 §2.2)

Known limitation (Phase 2, 2026-11-10):
  The Phase 1 schedule stores internal trip IDs only ('Txxxx').
  No mapping to GTFS trip IDs exists in the outputs.
  Terminal continuity cannot be verified. Propagation models delay flow
  only, not physical route movement. Deadhead is not modeled (R11 not
  configured in V1). See docs/constraints-v2.md R11.
"""

from __future__ import annotations

TURNAROUND_SEC = 300    # [SYNTHETIC] same-terminal turnaround

# DEPRECATED — kept so legacy imports do not break.
# The recurrence itself does NOT use this constant. It uses
# trip["duration_sec"] per trip (real GTFS durations).
# Remove once simpy_runner.py and the tests are migrated.
RUNNING_SEC = 3000      # 50 min integer — legacy only


def propagate(
    trips: list[dict],
    own_delay_sec: list[int],
    turnaround_sec: int = TURNAROUND_SEC,
    running_sec: int | None = None,
) -> list[dict]:
    """
    Apply the closed-form propagation recurrence.

    Args:
        trips: List of trips for ONE rake, already sorted by
               (scheduled_dep_sec, trip_id). Each trip has:
                 - trip_id: str
                 - dep_sec: int  (scheduled departure, seconds from base)
                 - arr_sec: int  (scheduled arrival)
        own_delay_sec: Same length as trips. own delay in seconds, >= 0.
        turnaround_sec: Turnaround between consecutive trips.
        running_sec: Trip running time.

    Returns:
        List of result dicts, one per trip, in the same order. Each has:
          trip_id, sched_dep, sched_arr,
          own_delay, early_dep, propagated_dep,
          actual_dep, actual_arr,
          propagated_delay, dep_delay

    Recurrence (per rake, first trip special-cased):
      early_dep       = sched_dep + own_delay
      propagated_dep  = actual_arr[prev] + turnaround       (prev exists)
                      = -inf                                (first trip)
      actual_dep      = max(early_dep, propagated_dep)
      actual_arr      = actual_dep + running
      propagated_delay = max(0, propagated_dep - early_dep)
      dep_delay        = actual_dep - sched_dep
    """
    if len(trips) != len(own_delay_sec):
        raise ValueError(
            f"length mismatch: {len(trips)} trips vs {len(own_delay_sec)} delays"
        )
    if any(d < 0 for d in own_delay_sec):
        raise ValueError("own_delay_sec must be >= 0 (clip before calling)")
    if turnaround_sec < 0:
        raise ValueError("turnaround_sec must be >= 0")
    if running_sec is not None and running_sec < 0:
        raise ValueError("running_sec must be >= 0 when provided")

    # Validate that every trip has a positive duration.
    for t in trips:
        d = t.get("duration_sec")
        if not isinstance(d, int) or d <= 0:
            raise ValueError(
                f"trip {t.get('trip_id')!r}: missing or invalid duration_sec={d!r}"
            )

    results = []
    prev_actual_arr = None

    for trip, own in zip(trips, own_delay_sec):
        early_dep = trip["dep_sec"] + own

        if prev_actual_arr is None:
            # First trip on this rake: no propagation.
            propagated_dep = None
            propagated_delay = 0
        else:
            propagated_dep = prev_actual_arr + turnaround_sec
            propagated_delay = max(0, propagated_dep - early_dep)

        actual_dep = early_dep if propagated_dep is None else max(
            early_dep, propagated_dep
        )
        trip_running = running_sec if running_sec is not None else trip["duration_sec"]
        actual_arr = actual_dep + trip_running
        dep_delay = actual_dep - trip["dep_sec"]

        results.append(
            {
                "trip_id": trip["trip_id"],
                "sched_dep": trip["dep_sec"],
                "sched_arr": trip["arr_sec"],
                "own_delay": own,
                "early_dep": early_dep,
                "propagated_dep": propagated_dep,
                "actual_dep": actual_dep,
                "actual_arr": actual_arr,
                "propagated_delay": propagated_delay,
                "dep_delay": dep_delay,
            }
        )
        prev_actual_arr = actual_arr

    return results
