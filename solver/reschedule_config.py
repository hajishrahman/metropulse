"""
MetroPulse Phase 5 — Disruption Response configuration.

Shared constants (operating window, deadhead, objective scale, solver params,
maintenance threshold, etc.) are IMPORTED from solver.config — not redefined —
so Phase 1 and Phase 5 stay consistent if Phase 1 tuning changes.

This file defines ONLY Phase-5-local constants.

Tags:
    [SYNTHETIC]  Phase-5 assumption
"""
from __future__ import annotations

from solver import config  # shared constants — do not redefine

# ===========================================================================
# PHASE 5 — DROP PENALTY  [SYNTHETIC]
# ===========================================================================
# Weight per dropped trip in the objective (before OBJ_SCALE).
# Large enough that the solver drops trips only when capacity forces it.
W_DROP = 1000

# ===========================================================================
# MAINTENANCE TYPES  [SYNTHETIC — schema for rakes_phase5.csv]
# ===========================================================================
MAINTENANCE_TYPE_SERVICE = "service"
MAINTENANCE_TYPE_SCHEDULED = "scheduled"
MAINTENANCE_TYPE_UNSCHEDULED = "unscheduled_repair"

# ===========================================================================
# SENTINEL FOR DROPPED TRIPS IN OUTPUT CSV
# ===========================================================================
# Not a real rake_id (rakes are R###), so no collision risk.
DROPPED_RAKE_SENTINEL = "DROPPED"

# ===========================================================================
# DISRUPTION TIMING  [SYNTHETIC]
# ===========================================================================
# Wall-clock cutoff: any trip whose departure >= DISRUPTION_TIME_SEC is
# unavailable to the downed rake(s). Mid-trip abort is out of scope —
# trips that have already departed complete normally.
DISRUPTION_TIME_SEC = 14 * 3600  # 14:00:00

# ===========================================================================
# PHASE 5 DATA PATHS
# ===========================================================================
RAKES_PHASE5_CSV = f"{config.SYNTHETIC_DIR}/rakes_phase5.csv"

SCENARIO_A_JSON = "data/disruptions/scenario_a.json"
SCENARIO_B_JSON = "data/disruptions/scenario_b.json"

RESCHEDULE_OUT_A = f"{config.GENERATED_DIR}/reschedule_scenario_a.csv"
RESCHEDULE_OUT_B = f"{config.GENERATED_DIR}/reschedule_scenario_b.csv"
RESCHEDULE_DIFF_JSON = f"{config.GENERATED_DIR}/reschedule_diff.json"
RESCHEDULE_SUMMARY_MD = f"{config.GENERATED_DIR}/reschedule_summary.md"

# ===========================================================================
# BASELINE (Phase 1) — read-only reference for the diff
# ===========================================================================
BASELINE_SCHEDULE_CSV = config.SCHEDULE_CSV  # data/processed/schedule.csv