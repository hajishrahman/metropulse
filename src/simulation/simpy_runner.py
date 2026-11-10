# src/simulation/simpy_runner.py
"""
SimPy engine for Phase 2 delay propagation.

One SimPy process per rake. Pre-drawn delays are passed in (common random
numbers). The output must equal src.simulation.reference.propagate()
bit-for-bit; that equality is asserted by tests/test_simpy_matches_reference.py.

Units: integer seconds throughout.

Provenance:
  [SYNTHETIC] turnaround 300 s (constraints-v2 R6)
  [DERIVED]   running time 3000 s (50 min integer, constraints-v2 R7)
  [SYNTHETIC] delay model: clipped normal, pre-clip mean -48 s,
              std swept E1-E4, clip [0, 300] s (constraints-v2 §2.2)
"""

from __future__ import annotations

import simpy

from src.simulation.reference import RUNNING_SEC, TURNAROUND_SEC


def run_simpy(
    grouped: dict[str, list[dict]],
    own_delay_sec_by_rake: dict[str, list[int]],
    turnaround_sec: int = TURNAROUND_SEC,
    running_sec: int = RUNNING_SEC,
) -> dict[str, list[dict]]:
    """
    Run SimPy for all rakes.

    Args:
        grouped: {rake_id: [trips sorted by (dep_sec, trip_id)]}
        own_delay_sec_by_rake: {rake_id: [int >= 0, same length as trips]}

    Returns:
        {rake_id: [result dict per trip]} with keys:
          trip_id, sched_dep, sched_arr, own_delay,
          propagated_dep, actual_dep, actual_arr,
          propagated_delay, dep_delay
        (early_dep is not included here; add it in tests if needed.)
    """
    if set(grouped) != set(own_delay_sec_by_rake):
        raise ValueError(
            f"rake set mismatch: grouped={sorted(grouped)},"
            f" delays={sorted(own_delay_sec_by_rake)}"
        )
    for rake, trips in grouped.items():
        if len(trips) != len(own_delay_sec_by_rake[rake]):
            raise ValueError(
                f"rake {rake}: {len(trips)} trips vs"
                f" {len(own_delay_sec_by_rake[rake])} delays"
            )
        if any(d < 0 for d in own_delay_sec_by_rake[rake]):
            raise ValueError(f"rake {rake}: negative own delay")
        if any(t["arr_sec"] - t["dep_sec"] != running_sec for t in trips):
            raise ValueError(f"rake {rake}: running-time mismatch vs argument")

    env = simpy.Environment()
    results: dict[str, list[dict]] = {rake: [] for rake in grouped}

    def rake_process(rake: str, trips: list[dict], delays: list[int]):
         prev_actual_arr = None
         for trip, own in zip(trips, delays):
            sched_dep = trip["dep_sec"]
            sched_arr = trip["arr_sec"]
            early_dep = sched_dep + own
            propagated_dep = (
                None
                if prev_actual_arr is None
                else prev_actual_arr + turnaround_sec
            )

            # Wait until early departure.
            if env.now < early_dep:
                yield env.timeout(early_dep - env.now)

            actual_dep = env.now
            propagated_delay = max(0, actual_dep - early_dep)

            # Run.
            yield env.timeout(running_sec)
            actual_arr = env.now
            prev_actual_arr = actual_arr

            results[rake].append(
                {
                    "trip_id": trip["trip_id"],
                    "sched_dep": sched_dep,
                    "sched_arr": sched_arr,
                    "own_delay": own,
                    "early_dep": early_dep,
                    "propagated_dep": propagated_dep,
                    "actual_dep": actual_dep,
                    "actual_arr": actual_arr,
                    "propagated_delay": propagated_delay,
                    "dep_delay": actual_dep - sched_dep,
                }
            )

            # Turnaround before next trip (also acts as the propagation buffer).
            yield env.timeout(turnaround_sec)

    for rake, trips in grouped.items():
        env.process(rake_process(rake, trips, own_delay_sec_by_rake[rake]))

    env.run()
    return results