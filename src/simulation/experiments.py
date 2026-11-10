# src/simulation/experiments.py
"""
Phase 2 experiment runner. Runs E1-E4 on the real schedule, writes:
  - data/processed/simulation_kpis.json
  - data/processed/simulation_timeline.csv

All delay values are [SYNTHETIC]. The schedule is from synthetic fleet
assumptions. Terminal continuity and deadhead are not verified (see
docs/constraints-v2.md R11). Results describe model behaviour, not
real KMRL prediction.

Run:
  python -m src.simulation.experiments
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from src.simulation.kpis import compute_kpis
from src.simulation.schedule_loader import load_schedule_grouped, total_trips
from src.simulation.simpy_runner import run_simpy

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EXPERIMENTS: list[tuple[str, float]] = [
    ("E1", 0.0),
    ("E2", 60.0),
    ("E3", 120.0),
    ("E4", 300.0),
]
N_SEEDS = 100
SEEDS = list(range(42, 42 + N_SEEDS))
HEADLINE_SEED = 42
assert HEADLINE_SEED == SEEDS[0]

MEAN_PRE_CLIP = -48.0
CLIP_MIN = 0.0
CLIP_MAX = 300.0

HEADWAY_THRESHOLD_SEC = 120
ON_TIME_TOLERANCES = (300, 180, 60)  # 5min, 3min, 1min

KPIS_PATH = Path("data/processed/simulation_kpis.json")
TIMELINE_PATH = Path("data/processed/simulation_timeline.csv")


# ---------------------------------------------------------------------------
# Delay generation
# ---------------------------------------------------------------------------
def make_own_delay(mean: float, std: float, z: float) -> int:
    """Clip-then-round. Documented rounding rule for all Phase 2 delay generation."""
    return round(min(max(mean + std * z, CLIP_MIN), CLIP_MAX))


def draw_z_by_trip(all_trip_ids: list[str], seed: int) -> dict[str, float]:
    """One standard normal per trip id, in sorted trip_id order."""
    rng = np.random.default_rng(seed)
    z_all = rng.standard_normal(len(all_trip_ids))
    return dict(zip(sorted(all_trip_ids), z_all.tolist()))


def build_delays(
    grouped: dict[str, list[dict]],
    z_by_trip: dict[str, float],
    std: float,
) -> dict[str, list[int]]:
    return {
        rake: [make_own_delay(MEAN_PRE_CLIP, std, z_by_trip[t["trip_id"]]) for t in trips]
        for rake, trips in grouped.items()
    }


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------
def run_one(
    grouped: dict[str, list[dict]],
    std: float,
    seed: int,
) -> dict[str, list[dict]]:
    all_trip_ids = [t["trip_id"] for trips in grouped.values() for t in trips]
    z_by_trip = draw_z_by_trip(all_trip_ids, seed)
    delays = build_delays(grouped, z_by_trip, std)
    return run_simpy(grouped, delays)


def run_headline(grouped: dict[str, list[dict]]) -> dict[str, dict[str, list[dict]]]:
    """Seed 42, all 4 experiments. Used for timeline and hard assertions."""
    return {
        name: run_one(grouped, std, HEADLINE_SEED)
        for name, std in EXPERIMENTS
    }


def run_monte_carlo(
    grouped: dict[str, list[dict]],
) -> dict[str, dict[str, dict]]:
    """All seeds, all experiments. Aggregates per KPI metric across seeds."""
    aggregate: dict[str, dict] = {}
    for name, std in EXPERIMENTS:
        per_seed_kpis = []
        for seed in SEEDS:
            results = run_one(grouped, std, seed)
            per_seed_kpis.append(compute_kpis(results, grouped))
        aggregate[name] = _aggregate_kpis(per_seed_kpis)
    return aggregate


def _aggregate_kpis(per_seed: list[dict]) -> dict:
    """Mean + p5 + p95 per metric across seeds. Percentages averaged per seed."""
    def stat(values: list[float]) -> dict:
        arr = np.asarray(values, dtype=float)
        return {
            "mean": round(float(np.mean(arr)), 4),
            "p5": round(float(np.percentile(arr, 5)), 4),
            "p95": round(float(np.percentile(arr, 95)), 4),
        }

    def collect(path: tuple[str, ...]) -> list[float]:
        out = []
        for k in per_seed:
            v = k
            for key in path:
                v = v[key]
            out.append(float(v))
        return out

    return {
        "n_seeds": len(per_seed),
        "on_time_5min_250_pct": stat(collect(("on_time_5min", "on_time_250_pct"))),
        "on_time_5min_232_pct": stat(collect(("on_time_5min", "on_time_232_eligible_pct"))),
        "on_time_3min_250_pct": stat(collect(("on_time_3min", "on_time_250_pct"))),
        "on_time_3min_232_pct": stat(collect(("on_time_3min", "on_time_232_eligible_pct"))),
        "on_time_1min_250_pct": stat(collect(("on_time_1min", "on_time_250_pct"))),
        "on_time_1min_232_pct": stat(collect(("on_time_1min", "on_time_232_eligible_pct"))),
        "propagation_pct": stat(collect(("propagation", "propagation_pct"))),
        "total_propagated_delay_sec": stat(collect(("total_propagated_delay", "total_propagated_delay_sec"))),
        "total_propagated_delay_min": stat(collect(("total_propagated_delay", "total_propagated_delay_min"))),
        "max_single_propagated_delay_sec": stat(collect(("total_propagated_delay", "max_single_propagated_delay_sec"))),
        "headway_actual_violations": stat(collect(("headway", "actual_violations"))),
        "headway_scheduled_violations": stat(collect(("headway", "scheduled_violations"))),
    }


# ---------------------------------------------------------------------------
# Hard assertions and soft warnings
# ---------------------------------------------------------------------------
def assert_e1_zero_delays(headline: dict) -> None:
    """E1: all own delays, propagated delays, and actual departures are zero-delta."""
    for rake, results in headline["E1"].items():
        for r in results:
            if r["own_delay"] != 0:
                raise AssertionError(f"E1 own_delay != 0 at {rake}/{r['trip_id']}")
            if r["propagated_delay"] != 0:
                raise AssertionError(f"E1 propagated_delay != 0 at {rake}/{r['trip_id']}")
            if r["actual_dep"] != r["sched_dep"]:
                raise AssertionError(f"E1 actual_dep != sched_dep at {rake}/{r['trip_id']}")


def assert_headline_trends(
    headline_kpis: dict,
    exp_order: list[str],
) -> None:
    """Hard: on-time % non-increasing E1->E4; propagation % non-decreasing."""
    for tol in ("on_time_5min", "on_time_3min", "on_time_1min"):
        prev = None
        for name in exp_order:
            v = headline_kpis[name][tol]["on_time_250_pct"]
            if prev is not None and v > prev + 1e-9:
                raise AssertionError(
                    f"headline {tol} on_time_250_pct increased from {prev} to {v} at {name}"
                )
            prev = v
    prev = None
    for name in exp_order:
        v = headline_kpis[name]["propagation"]["propagation_pct"]
        if prev is not None and v < prev - 1e-9:
            raise AssertionError(
                f"headline propagation_pct decreased from {prev} to {v} at {name}"
            )
        prev = v


def soft_warn_monte_carlo_trends(aggregate: dict, exp_order: list[str]) -> None:
    """Soft: warn if 100-seed means drift in wrong direction."""
    for tol in ("on_time_5min_250_pct", "on_time_3min_250_pct", "on_time_1min_250_pct"):
        vals = [aggregate[name][tol]["mean"] for name in exp_order]
        if any(b > a + 1e-9 for a, b in zip(vals, vals[1:])):
            print(f"WARNING: {tol} mean is not monotonically non-increasing: {vals}")
    prop_vals = [aggregate[name]["propagation_pct"]["mean"] for name in exp_order]
    if any(b < a - 1e-9 for a, b in zip(prop_vals, prop_vals[1:])):
        print(f"WARNING: propagation_pct mean is not monotonically non-decreasing: {prop_vals}")


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------
def write_timeline(
    headline_results: dict[str, dict[str, list[dict]]],
    grouped: dict[str, list[dict]],
    path: Path,
) -> None:
    # Build trip lookup for rake_id and direction.
    trip_lookup: dict[str, dict] = {}
    for rake, trips in grouped.items():
        for t in trips:
            trip_lookup[t["trip_id"]] = {"rake_id": rake, "direction": t["direction"]}

    fieldnames = [
        "experiment",
        "trip_id",
        "rake_id",
        "direction",
        "sched_dep_sec",
        "sched_arr_sec",
        "own_delay_sec",
        "early_dep_sec",
        "propagated_dep_sec",
        "actual_dep_sec",
        "actual_arr_sec",
        "propagated_delay_sec",
        "dep_delay_sec",
        "on_time_5min",
        "on_time_3min",
        "on_time_1min",
    ]

    rows_expected = len(headline_results) * total_trips(grouped)
    rows_written = sum(
        len(results)
        for per_rake in headline_results.values()
        for results in per_rake.values()
    )
    assert rows_written == rows_expected, (
        f"timeline row mismatch: {rows_written} vs {rows_expected}"
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for name, per_rake in headline_results.items():
            for rake, results in per_rake.items():
                for r in results:
                    info = trip_lookup[r["trip_id"]]
                    dep_delay = r["dep_delay"]
                    w.writerow({
                        "experiment": name,
                        "trip_id": r["trip_id"],
                        "rake_id": info["rake_id"],
                        "direction": info["direction"],
                        "sched_dep_sec": r["sched_dep"],
                        "sched_arr_sec": r["sched_arr"],
                        "own_delay_sec": r["own_delay"],
                        "early_dep_sec": r["early_dep"],
                        "propagated_dep_sec": (
                            "" if r["propagated_dep"] is None else r["propagated_dep"]
                        ),
                        "actual_dep_sec": r["actual_dep"],
                        "actual_arr_sec": r["actual_arr"],
                        "propagated_delay_sec": r["propagated_delay"],
                        "dep_delay_sec": dep_delay,
                        "on_time_5min": int(dep_delay <= 300),
                        "on_time_3min": int(dep_delay <= 180),
                        "on_time_1min": int(dep_delay <= 60),
                    })


def write_kpis(
    metadata: dict,
    headline_kpis: dict,
    aggregate_kpis: dict,
    path: Path,
) -> None:
    payload = {
        "metadata": metadata,
        "headline_seed_run": headline_kpis,
        "monte_carlo_aggregate": aggregate_kpis,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(payload, f, indent=2, allow_nan=False)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    grouped = load_schedule_grouped()
    n_trips = total_trips(grouped)
    n_rakes = len(grouped)
    n_eligible = n_trips - n_rakes

    print(f"Loaded {n_trips} trips, {n_rakes} rakes, {n_eligible} eligible.")
    print(f"Running headline seed {HEADLINE_SEED} for E1-E4 ...")
    headline = run_headline(grouped)

    print("Running hard assertions ...")
    assert_e1_zero_delays(headline)
    headline_kpis = {name: compute_kpis(headline[name], grouped) for name, _ in EXPERIMENTS}
    assert_headline_trends(headline_kpis, [name for name, _ in EXPERIMENTS])

    print(f"Running Monte Carlo ({N_SEEDS} seeds) ...")
    aggregate = run_monte_carlo(grouped)
    soft_warn_monte_carlo_trends(aggregate, [name for name, _ in EXPERIMENTS])

    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "schedule_file": "data/processed/schedule.csv",
        "trips_total": n_trips,
        "rakes": n_rakes,
        "eligible_trips": n_eligible,
        "running_time_sec": 3000,
        "turnaround_sec": 300,
        "delay_model": {
            "type": "clipped_normal",
            "preclip_mean_sec": MEAN_PRE_CLIP,
            "std_sweep_sec": [std for _, std in EXPERIMENTS],
            "clip_min_sec": CLIP_MIN,
            "clip_max_sec": CLIP_MAX,
            "rounding_rule": "clip-then-round (Python round, half-to-even)",
        },
        "experiments": [name for name, _ in EXPERIMENTS],
        "n_seeds_monte_carlo": N_SEEDS,
        "seed_list": SEEDS,
        "headline_seed": HEADLINE_SEED,
        "headway_threshold_sec": HEADWAY_THRESHOLD_SEC,
        "on_time_tolerances_sec": list(ON_TIME_TOLERANCES),
        "provenance_note": (
            "All delay values are [SYNTHETIC]. Schedule is from synthetic fleet "
            "assumptions. Terminal continuity and deadhead are not verified "
            "(constraints-v2 R11 not configured). Results describe model "
            "behaviour, not real KMRL prediction."
        ),
    }

    write_timeline(headline, grouped, TIMELINE_PATH)
    write_kpis(metadata, headline_kpis, aggregate, KPIS_PATH)

    print()
    print(f"Wrote {TIMELINE_PATH} (expect {4 * n_trips} data rows)")
    print(f"Wrote {KPIS_PATH}")
    print()
    print("Headline summary (seed 42):")
    header = f"{'exp':4s} {'on_t_5m_250':>12s} {'on_t_5m_232':>12s} {'prop_%':>8s} {'total_prop_min':>15s} {'hw_act':>7s}"
    print(header)
    for name, _ in EXPERIMENTS:
        k = headline_kpis[name]
        print(
            f"{name:4s} "
            f"{k['on_time_5min']['on_time_250_pct']:12.2f} "
            f"{k['on_time_5min']['on_time_232_eligible_pct']:12.2f} "
            f"{k['propagation']['propagation_pct']:8.2f} "
            f"{k['total_propagated_delay']['total_propagated_delay_min']:15.1f} "
            f"{k['headway']['actual_violations']:7d}"
        )


if __name__ == "__main__":
    main()
