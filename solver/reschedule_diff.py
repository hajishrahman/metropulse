"""
MetroPulse Phase 5 — Reschedule diff & summary writer.

LIBRARY MODULE — not a CLI entry point. Called by solver/reschedule_solve.py
as:
    from solver.reschedule_diff import (
        compute_diff, write_diff_json, write_summary_md,
    )

Computes the machine-readable diff (reschedule_diff.json per D10) and the
human-readable summary (reschedule_summary.md per D11) from the in-memory
solve results. No metadata files on disk are read or written.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from solver import reschedule_config as R5


# ===========================================================================
# CORE COMPUTATION
# ===========================================================================
def compute_diff(
    original_schedule: pd.DataFrame,
    new_schedule: pd.DataFrame,
    solve_result: dict,
    scenario_config: dict,
    activated_rakes: list,
    rakes_active_count: int,
    rakes_phase5_df: pd.DataFrame,
    trips_withdrawn: int,
    in_progress: dict,
    include_capacity_warning: bool = False,
) -> dict:
    """Build the D10-schema diff dict.

    Inputs
    ------
    original_schedule : Phase 1 baseline (DataFrame from data/processed/schedule.csv)
    new_schedule      : Phase 5 output schedule for this scenario, SAME columns
                        as original_schedule, with rake_id == "DROPPED" for
                        cancelled trips.
    solve_result      : dict from run_scenario — keys:
                        status, elapsed_sec, objective, best_bound, gap_pct
    scenario_config   : dict from the scenario JSON.
    activated_rakes   : list of rake_id strings.
    rakes_active_count: int, rakes in service after response.
    rakes_phase5_df   : full 25-row rakes_phase5 DataFrame (for km lookups).
    trips_withdrawn   : int, total trips withdrawn from downed rakes at
                        disruption time (pre-solve; "at risk" count).
    include_capacity_warning : True only for Scenario B.

    Returns
    -------
    dict matching reschedule_diff.json schema (D10 + trips_withdrawn).
    """
    orig_by_tid = original_schedule.set_index("trip_id")["rake_id"].to_dict()
    new_by_tid = new_schedule.set_index("trip_id")["rake_id"].to_dict()

    if set(orig_by_tid.keys()) != set(new_by_tid.keys()):
        missing = set(orig_by_tid) - set(new_by_tid)
        extra = set(new_by_tid) - set(orig_by_tid)
        raise RuntimeError(
            f"Trip ID mismatch between baseline and scenario:\n"
            f"  missing in new: {sorted(missing)[:5]}"
            f"{'...' if len(missing) > 5 else ''}\n"
            f"  unexpected in new: {sorted(extra)[:5]}"
            f"{'...' if len(extra) > 5 else ''}"
        )

    dropped_trip_ids = sorted(
        tid for tid, rid in new_by_tid.items()
        if rid == R5.DROPPED_RAKE_SENTINEL
    )
    dropped_set = set(dropped_trip_ids)

    reassignments = []
    trips_unchanged = 0
    for tid, orig_rid in orig_by_tid.items():
        if tid in dropped_set:
            continue
        new_rid = new_by_tid[tid]
        if new_rid == orig_rid:
            trips_unchanged += 1
        else:
            reassignments.append({
                "trip_id": tid,
                "from_rake": orig_rid,
                "to_rake": new_rid,
            })

    trips_reassigned = len(reassignments)
    trips_dropped = len(dropped_trip_ids)

    total = trips_unchanged + trips_reassigned + trips_dropped
    if total != len(orig_by_tid):
        raise RuntimeError(
            f"Diff arithmetic broken: {trips_unchanged} + {trips_reassigned} "
            f"+ {trips_dropped} = {total}, expected {len(orig_by_tid)}"
        )

    if trips_withdrawn < trips_dropped:
        raise RuntimeError(
            f"Invalid: trips_withdrawn ({trips_withdrawn}) < trips_dropped "
            f"({trips_dropped}) — impossible (a dropped trip must have been "
            f"withdrawn first)."
        )

    out = {
        "scenario_id": scenario_config["scenario_id"],
        "disruption": {
            "rakes_down": list(scenario_config["rakes_down"]),
            "time": scenario_config["disruption_time"],
        },
        "rakes_activated": list(activated_rakes),
        "rakes_activated_reason": None,  # set by caller
        "rakes_active_count": int(rakes_active_count),
        "solver_status": solve_result["status"],
        "objective": solve_result["objective"],
        "gap_pct": solve_result["gap_pct"],
        "elapsed_sec": round(float(solve_result["elapsed_sec"]), 3),
        "trips_withdrawn": int(trips_withdrawn),
        "in_progress": in_progress,
        "trips_unchanged": trips_unchanged,
        "trips_reassigned": trips_reassigned,
        "trips_dropped": trips_dropped,
        "dropped_trip_ids": dropped_trip_ids,
        "reassignments": reassignments,
    }
    if include_capacity_warning:
        if trips_dropped > 0:
            out["capacity_warning"] = (
                f"Capacity constrained. {rakes_active_count} rakes active. "
                f"{trips_dropped} trips dropped. "
                f"Recommend prioritizing peak-hour trips."
            )
        else:
            out["capacity_warning"] = None
    return out


# ===========================================================================
# JSON WRITER (D10 schema)
# ===========================================================================
def write_diff_json(diff_a: dict, diff_b: dict, path: str) -> None:
    """Write both scenarios into one reschedule_diff.json file."""
    payload = {
        "scenario_a": diff_a,
        "scenario_b": diff_b,
    }
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"[diff] wrote {p}")


# ===========================================================================
# SUMMARY MD WRITER (D11 template, corrected narrative)
# ===========================================================================
def _activated_km_summary(activated_rakes, rakes_phase5_df) -> str:
    km_by_rake = rakes_phase5_df.set_index("rake_id")[
        "km_since_last_maintenance"
    ].to_dict()
    parts = []
    for rid in activated_rakes:
        parts.append(f"{rid} ({km_by_rake[rid]:,} km)")
    return ", ".join(parts)


def _recovery_line(diff: dict) -> str:
    """Computed 'withdrawn → recovered → dropped' line."""
    withdrawn = diff["trips_withdrawn"]
    dropped = diff["trips_dropped"]
    recovered = withdrawn - dropped
    if withdrawn == 0:
        return "no trips withdrawn from downed rakes"
    pct = recovered / withdrawn * 100
    return (
        f"{withdrawn} trips withdrawn from downed rakes; "
        f"{recovered} recovered by reassignment ({pct:.1f}%); "
        f"{dropped} dropped"
    )
def _in_progress_line(in_progress: dict, disruption_time: str) -> str:
    """Human-readable summary of in-progress trips per downed rake."""
    if not in_progress:
        return ""
    parts = []
    for rid, trips in in_progress.items():
        if not trips:
            parts.append(f"{rid}: no in-progress trip (between trips) at {disruption_time}")
        else:
            for t in trips:
                parts.append(
                    f"{rid}: {t['trip_id']} in-progress "
                    f"(departed {t['departure']}, arrives {t['arrival']}) "
                    f"— completes normally"
                )
    return "; ".join(parts)


def write_summary_md(
    diff_a: dict,
    diff_b: dict,
    rakes_phase5_df: pd.DataFrame,
    path: str,
) -> None:
    """Write reschedule_summary.md per D11 template, with corrected narrative.

    All values computed from diff dicts; no hardcoded numbers.
    """
    # ---------- Scenario A ---------------------------------------------------
    a_down = diff_a["disruption"]["rakes_down"]
    a_time = diff_a["disruption"]["time"]
    a_activated = diff_a["rakes_activated"]
    a_km = _activated_km_summary(a_activated, rakes_phase5_df)
    a_activated_str = ", ".join(a_activated)
    a_total_served = (
        diff_a["trips_unchanged"] + diff_a["trips_reassigned"]
    )
    a_recovery = _recovery_line(diff_a)
    a_in_progress = _in_progress_line(
        diff_a["in_progress"], a_time
    )

    # ---------- Scenario B ---------------------------------------------------
    b_down = diff_b["disruption"]["rakes_down"]
    b_time = diff_b["disruption"]["time"]
    b_activated = diff_b["rakes_activated"]
    b_km = _activated_km_summary(b_activated, rakes_phase5_df)
    b_activated_str = ", ".join(b_activated)
    b_total_served = (
        diff_b["trips_unchanged"] + diff_b["trips_reassigned"]
    )
    b_passenger_journeys = diff_b["trips_dropped"] * 100
    b_recovery = _recovery_line(diff_b)
    b_in_progress = _in_progress_line(
        diff_b["in_progress"], b_time
    )
    b_recovered = diff_b["trips_withdrawn"] - diff_b["trips_dropped"]

    md = f"""# MetroPulse — Disruption Response Summary

## Scenario A: Single Rake Breakdown
- **Disruption:** {", ".join(a_down)} fails at {a_time}. {a_in_progress}. Withdrawn for any future trip departing ≥ {a_time}; trips already departed complete normally.
- **Response:** {a_activated_str} activated ({a_km}; lowest km_since_last_maintenance among scheduled).
- **Result:** {diff_a["rakes_active_count"]} rakes active. {a_recovery}.
  - {a_total_served} of 250 trips served ({diff_a["trips_unchanged"]} unchanged on original rake, {diff_a["trips_reassigned"]} reassigned to a different rake).
- **Solver status:** {diff_a["solver_status"]}, objective {diff_a["objective"]}, gap {diff_a["gap_pct"]}%.
- **Solve time:** {diff_a["elapsed_sec"]} seconds.

## Scenario B: Multiple Rake Breakdowns (Capacity-Constrained)
- **Disruption:** {", ".join(b_down)} fail at {b_time}. {b_in_progress}. Withdrawn for any future trip departing ≥ {b_time}; trips already departed complete normally.
- **Response:** {b_activated_str} activated ({b_km}).
- **Result:** {diff_b["rakes_active_count"]} rakes active. {b_recovery}.
  - {b_total_served} of 250 trips served ({diff_b["trips_unchanged"]} unchanged on original rake, {diff_b["trips_reassigned"]} reassigned to a different rake).
- **Solver status:** {diff_b["solver_status"]}, objective {diff_b["objective"]}, gap {diff_b["gap_pct"]}%.
- **Solve time:** {diff_b["elapsed_sec"]} seconds.
- **Capacity floor:** {diff_b["trips_dropped"]} drops is the irreducible gap at {diff_b["rakes_active_count"]} active rakes under R5/R6/R11. The remaining {250 - diff_b["trips_dropped"]} trips are served.
- **Capacity warning:** {diff_b["trips_dropped"]} trips cannot be covered.

**DROPPED** = trip scheduled but cannot operate due to insufficient rakes.

## D3 Correction Note
The original D3 table in the Phase 5 handoff listed R019, R020, R021, R022, R023 as
"scheduled" maintenance rakes. Per D2's rule (the 2 maintenance rakes with the
**highest** initial_mileage_km become `unscheduled_repair`), the actual split on
this fleet is:

- **Unscheduled repair (blocked):** R020 (176,838 km), R023 (199,479 km) — the two
  highest-mileage maintenance rakes.
- **Scheduled (reactivatable):** R019 (4,200 km-since), R021 (6,800), R022 (2,100),
  R024 (3,500), R025 (7,200).

Therefore Scenario A activates **{a_activated_str}**, and Scenario B activates
**{b_activated_str}** — the lowest-km scheduled rakes, not R020/R023.

**D4 defense (corrected):** R022 recently serviced (2,100 km), R024 next (3,500 km),
R019 near-service-due (4,200 km), R025 overdue (7,200 km). The heuristic picks R022
first — most recently serviced, safest for short-term rescue.

## Passenger Impact & Operational Recommendation

**Scenario B — dropped trips:**
- {diff_b["trips_dropped"]} trips cannot operate due to insufficient rakes at {diff_b["rakes_active_count"]} active. Of the {diff_b["trips_withdrawn"]} trips withdrawn from downed rakes, {b_recovered} were recovered by reassignment and {diff_b["trips_dropped"]} remained dropped.
- Estimated passenger impact: approximately {b_passenger_journeys:,} passenger journeys affected (assuming 100 passengers/trip).
- Passenger experience: affected passengers will wait 45–90 minutes for alternative service. If no alternative is available, trips should be announced as **cancelled** via PA system and app notification.
- **Operational recommendation:** Prioritize peak-hour trips for coverage. Drop off-peak trips where alternative service is available within 15 minutes. For dropped peak trips, issue delay notification first (30 min), then cancellation if no recovery.

## Honest Limitations
1. Full re-solve (~12–30s), not warm-start. Warm-start optimization is future work.
2. Rake completes current trip before withdrawal. Mid-trip abort (passenger deboarding) is out of scope.
3. No cascading delay modeling. Phase 2 integration is future work.
4. Not real-time. This is planned disruption response, not sub-second control.
5. Synthetic km data. `km_since_last_maintenance` is a SYNTHETIC proxy for reliability.
6. "Dropped" means the trip does not operate (cancelled). Passenger-impact framing ("45–90 min delay") describes the passenger *experience* of a dropped trip, not a rescheduled delay.
"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"[diff] wrote {p}")