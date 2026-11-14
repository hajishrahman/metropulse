# MetroPulse — Current Project Status

**Last Updated:** 2026-11-14

## Current Project Direction

MetroPulse is an AI-driven train induction planning and scheduling system for Kochi Metro Rail Limited (KMRL).

The project migrated to a verified-data approach on 2026-10-15 and was **rebuilt on real GTFS trip records on 2026-11-12**. The earlier synthetic-trip schedule (250 `T0000` trips, FEASIBLE, ~306 s, 93.4% gap) is superseded.

Sources of truth:
- KMRL GTFS static feed (2024-25) — real trip records
- KMRL Annual Report 2024-25 — route length, operating hours
- 2026 news article — fleet breakdown
- Synthetic assumptions where verified operational data is unavailable (clearly tagged)

## Current Technology Stack

- Python 3.12 (venv)
- pandas
- NetworkX
- SimPy
- Google OR-Tools CP-SAT
- Streamlit

## How to Run

From a fresh PowerShell session:

```powershell
cd Z:\metropulse
.\venv\Scripts\Activate.ps1

# Phase 1 — rebuild trip files (only if needed)
python data\extract_gtfs_trips.py
python data\verify_gtfs_trips.py
python data\merge_trips.py

# Phase 1 — synthetic fleet
python data\generate_synthetic_v2.py

# Phase 1 — solve and validate
python -m solver.solve
python -m solver.validator

# Phase 2 — regenerate outputs (only if needed)
python -m src.simulation.preflight
python -m src.simulation.experiments

# Phase 3 — generate drivers (one-time; deterministic)
python -m data.generate_drivers

# Phase 3 — solve all three pool sizes
python -m solver.crew_solve

# Phase 3 — validate crew assignments
python -m solver.crew_validator

# Phase 4 — generate the explainability report
python -m src.explainability.report_generator

# Phase 5 — run both disruption scenarios (writes 4 outputs)
python -m solver.reschedule_solve

# Tests
pytest tests\ -v

python -m solver.solve → Status: OPTIMAL, Trips: 255, Objective: 900.0, Gap: 0.0%, elapsed ~60 s

python -m solver.validator → Overall: PASS (10 PASS + 1 SKIPPED, R8 skipped)

pytest tests\ -v → 59 passed

Output files:

data/processed/schedule.csv — 255 scheduled trips
data/processed/solution.json — solver result
data/processed/validation.json — validator checks
data/processed/schedule_250_trips.csv — frozen 250-trip baseline
data/processed/solution_250_trips.json
data/processed/validation_250_trips.json
data/processed_backup/ — pre-rerun baseline snapshot (created 2026-11-12 before the objective restore; not part of the active pipeline)

Phase 2 output files:

data/processed/simulation_kpis.json — KPIs for E1–E4 + 100-seed Monte Carlo (regenerated 2026-11-12 on 250-trip real-GTFS schedule)
data/processed/simulation_timeline.csv — 1020 rows (4 experiments × 255 trips)

Phase 3 output files:

data/processed/crew_schedule.csv — 765 rows (255 trips × 3 pools)
data/processed/crew_solution.json — all 3 runs keyed by "45" / "50" / "55"
data/processed/crew_validation.json — per-pool checks + overall PASS

Phase 4 output files:

data/processed/explainability_report.md — 7 sections, all sources cited
data/processed/utilization_stats.json — machine-readable stats

Phase 5 output files:

data/processed/reschedule_scenario_a.csv — 255 rows, 7 columns, 0 DROPPED
data/processed/reschedule_scenario_b.csv — 255 rows, 7 columns, 7 DROPPED rows
data/processed/reschedule_diff.json — D10 schema, plus trips_withdrawn + in_progress fields
data/processed/reschedule_summary.md — D11 template, corrected narrative + per-rake in-progress disclosure + honest limitations

Current Data Configuration
Parameter	Current Value
GTFS feed	KMRL static GTFS, 2024-25
Feed validity	2024-08-12 to 2025-12-31
Weekday trips in GTFS	255
Excluded by window (out-of-policy)	0 (all 255 WK trips included)
Full-route trips (ALVA ↔ TPHT)	232
Partial trips (Muttom ↔ terminals)	23
Trips used by scheduler	255 (232 full-route + 23 partial)
Initial rake split	9 ALVA / 9 TPHT / 0 service MUTTOM (7 maintenance at MUTTOM)
Model operating window	04:40 ≤ departure < 24:00
Running time used by solver	Per-trip GTFS duration
Median one-way running time (summary only)	50.47 min
Route length	28.144 km (Annual Report)
Total fleet	25 rakes
Service rakes	18
Maintenance rakes	7
[SYNTHETIC]
Turnaround time	5 min [SYNTHETIC]
Terminal ↔ terminal deadhead	15 min [SYNTHETIC]
MUTTOM ↔ terminal deadhead	8 min [SYNTHETIC]
Maintenance threshold	1,000,000 km [SYNTHETIC]
Info Park-2 capacity	2 [SYNTHETIC]
Initial rake mileage	20,000–200,000 km [SYNTHETIC]
Timezone	Asia/Kolkata
```
## Latest Phase 1 Results (2026-11-15)

Solver status: OPTIMAL

Trips scheduled: 255 (232 full-route + 23 partial)

Rakes: 18 service (9 ALVA / 9 TPHT / 0 service MUTTOM)

Solve time: 60.15 s

Solver time limit: 300 s

Objective: 900.0

Best bound: 900.0 (proven optimal)

Optimality gap: 0.0%

Rake distribution: 3 rakes × 15 trips, 15 rakes × 14 trips = 255

R6 pruning: same=14828 cross15=14642 cross8=2915 | both_impossible=3539 one_way=28846 both_possible=0

Validator Results
PASS: 10

SKIPPED: 0

FAIL: 0

Overall: PASS

Validator checks (10): R1, R3, R4, R5, R6, R7, R9, R10, R11, D. R8 and R12 removed from validator scope. R9 and D added. R6 uses per-pair deadhead (5/8/15 min). R11 uses KVTR-aware rule. Objective O6 active — validator PASS confirms the optimized schedule still satisfies all hard constraints.

## Latest Phase 2 Results (2026-11-15, regenerated on 255-trip real schedule)

The Phase 2 SimPy simulation was **rebuilt** on the new 250-trip schedule. `simulation_kpis.json` and `simulation_timeline.csv` now describe the current schedule.

- Loaded: 255 trips, 18 rakes, 237 eligible
- Timeline: 1020 rows (4 experiments × 255 trips)
- **Tests: 59 passed** (loader, reference, SimPy parity, KPIs)

### Headline (seed 42)

| Exp | std (s) | ±5 on-time 255 | ±5 on-time 237 | Propagation % | HW actual |
|---|---:|---:|---:|---:|---:|
| E1 | 0 | 100.00 | 100.00 | 0.00 | 3 |
| E2 | 60 | 100.00 | 100.00 | 0.42 | 4 |
| E3 | 120 | 100.00 | 100.00 | 1.27 | 4 |
| E4 | 300 | 100.00 | 100.00 | 2.53 | 7 |

*(These are the values in the current `data/processed/simulation_kpis.json`. If a future rerun produces a different OPTIMAL schedule, the numbers will shift — CP-SAT is non-deterministic with `num_search_workers > 1`. The JSON is authoritative.)*

### 100-seed Monte Carlo (mean, p5–p95)

| Exp | ±5 | ±3 (mean; p5–p95) | ±1 | Propagation % (mean; p5–p95) |
|---|---:|---|---:|---:|
| E1 | 100.00 | 100.00 (100.00–100.00) | 100.00 | 0.00 (0.00–0.00) |
| E2 | 100.00 | 100.00 (100.00–100.00) | 96.40 | 0.32 (0.00–0.84) |
| E3 | 100.00 | 97.10 (94.94–98.75) | 81.10 | 1.15 (0.00–2.13) |
| E4 | 100.00 | 76.72 (71.76–80.78) | 62.00 | 4.11 (2.53–6.33) |

*(Authoritative source: `data/processed/simulation_kpis.json`. Values are tied to the current schedule; a rerun of `solver.solve` will change the schedule and therefore these KPIs.)*

### Notes

- **3 scheduled same-direction pairs at 0 s gap** in the raw GTFS timetable (06:15, 08:00, 08:21). Each is a full trip (TPHT→ALVA) and a partial trip (MUTT→ALVA) departing the same minute on different rakes. Not a solver or simulation bug. R2a removed in v2.1 §5 because departure times are fixed by GTFS.
- Actual violations rise with std: E1 = 3, E2 = 4, E3 = 4, E4 = 7. The 3 structural violations are a GTFS data fact; additional violations at higher std are delay-induced.
- **Real GTFS schedule shows less propagation than the old synthetic one** (E4 mean 6.89% vs 11.64% before) because real slack is larger.
- All Phase 2 delay values are `[SYNTHETIC]`. Results describe model behaviour, not real KMRL performance.

## 3.7 Phase 3 Results (2026-11-15, regenerated on 255-trip Phase 1 baseline)

Phase 3 crew scheduling is **complete** on the current 255-trip Phase 1 baseline. All 255 trips are assigned to SC/TO drivers at three pool sizes (45 / 50 / 55).

> **Regeneration note (2026-11-15):** Phase 1 was reworked to 255 trips (was 250). Phase 3 was regenerated against the new `data/processed/schedule.csv` (255 rows, 18 service rakes at 9/9/0 split). No Phase 3 code changes were made. Old 250-trip outputs preserved as `crew_schedule_250_before_255.csv`, `crew_solution_250_before_255.json`, `crew_validation_250_before_255.json`.

### Inputs

- `data/processed/schedule.csv` — 255 trips (Phase 1 output, read-only)
- `data/synthetic/drivers.csv` — 55 synthetic drivers `D001`–`D055`, `driver_id` column only `[SYNTHETIC]`

Fields `qualification`, `availability`, `shift_preference`, `weekly_availability` are **deferred to V2** — same honesty pattern as C5 (min rest).

### Constraints

- **C1** no overlap (`arr + 300 s ≤ next dep`) — hard
- **C2** max active duty (`last_arr − first_dep ≤ 28,800 s`) — hard
- **C3** sign-on / sign-off (≥ 900 s each side) — hard
- **C4** full coverage (255 / 255 trips) — hard
- **C5** min rest 12 h — **DEFERRED to V2**, no solver constraint, no validator check
- **C6** continuous driving ≤ 5 h — **soft**, weight 10; break threshold = `MIN_TURNAROUND_SEC` (300 s) `[DERIVED from C1]`
- **C7** reserve ≥ 5 drivers — **soft**, weight 15

### Results

| Pool | Status | Time | Active | Reserve | Objective | Gap |
|---|---|---:|---:|---:|---:|---:|
| 45 | **OPTIMAL** | 59.61 s | 40 | 5 | 0.0 | 0.0% |
| 50 | **OPTIMAL** | 62.10 s | 45 | 5 | 0.0 | 0.0% |
| 55 | **OPTIMAL** | 70.10 s | 50 | 5 | 0.0 | 0.0% |

### Validator (independent of solver)

- pool=45: C1 PASS, C2 PASS, C3 PASS, C4 PASS, C7 PASS → **pool PASS**
- pool=50: C1 PASS, C2 PASS, C3 PASS, C4 PASS, C7 PASS → **pool PASS**
- pool=55: C1 PASS, C2 PASS, C3 PASS, C4 PASS, C7 PASS → **pool PASS**
- **Overall: PASS**

### Notes

- **Objective = 0 at all pools.** The solver found schedules with zero C6 and C7 penalty. This proves the penalty term is zero; it does not prove no driver neared the 5-h chain limit. Individual chain lengths are in `crew_solution.json` under `assignments`.
- **C6 is implemented as a state machine** (6 vars per driver-trip pair, ~82,500 new vars total). An earlier O(n²) run-enumeration approach was rejected at ~3.4M vars.
- **CP-SAT is non-deterministic** with `num_search_workers = 4` — results may vary between runs. Documented, not hidden.
- **Handoff §8 success criteria — all met:** (1) all three pools FEASIBLE/OPTIMAL with 255 trips, (2) C1–C4 PASS independent validation, (3) sensitivity table across pool sizes reported, (4) all docs updated.
- **Identical structure to 250-trip run.** Same active counts (pool_size − 5), same reserve (5), same objective (0.0), same gap (0.0%). Only trip count (255 vs 250) and elapsed_sec changed. The new 255-trip schedule has more slack; the solver handled the extra trips comfortably.

### Bugs found and fixed during Phase 3 (2026-11-13 original build)

1. `[FINDING]` **C6 first formulation was O(n²)** (~3.4M vars). Reworked to state machine.
2. `[FINDING]` **C6 chain-continuity bug** — initial version broke chains across trips assigned to other drivers. Reworked to `last_arr` carry-forward + `has_prev` bool.
3. `[FINDING]` **C1 solver bug** — dead branches forced wrong non-overlap rule, making model INFEASIBLE at all pools. Fixed to the single condition `if a.arr + turnaround > b.dep: x[a] + x[b] ≤ 1`.
4. `[FINDING]` **C6 `new_chain = 0` bug** — gap constraint fired with no prior assignment, making full model INFEASIBLE. Fixed with `has_prev` bool guard.
5. `[FINDING]` **Validator C1 bug** — compared driver-level sign-on/sign-off (constant per driver) instead of per-trip times. Fixed by joining `crew_schedule.csv` trip_ids with `schedule.csv`.

All five were caught by `solver/crew_diag.py` (temporary diagnostic, deleted 2026-11-13) and by the independent validator — not by guesswork.

### Outputs

- `data/processed/crew_schedule.csv` — 765 rows (255 trips × 3 pools)
- `data/processed/crew_solution.json` — all 3 runs keyed by `"45"` / `"50"` / `"55"`
- `data/processed/crew_validation.json` — per-pool checks + `overall: PASS`

See `docs/phases.md` §Phase 3 for the full spec and `docs/constraints-crew-v1.md` for the detailed C1–C7 crew constraint spec.

## Latest Phase 4 Results (2026-11-13)

Phase 4 **Explainability Report** is **complete**. One reporting module reads the seven Phase 1/2/3 output files and generates one Markdown report plus one machine-readable stats file.

> **Regeneration note (2026-11-15):** Phase 4 outputs were regenerated against the 255-trip Phase 1 baseline. `report_generator.py` was updated to (a) read `trips_total` / `eligible_trips` from `simulation_kpis.json` metadata for the Section 6 column labels (data-driven, not hardcoded), (b) handle both old and new R6 detail-key shapes (`cross_terminal_pairs` vs `cross_terminal_15_pairs` + `cross_terminal_8_mutt_pairs`), (c) add explicit branches for R9 and D_direction_consistency, and (d) make Section 2's "Notes" prose version-neutral (lists which checks are actually present, no stale claims about R8/R9/R12). No Phase 1/2/3 output was modified. A CP1252 encoding bug in `src/simulation/experiments.py`'s JSON writer was found during regeneration and fixed (`encoding="utf-8"` added to the file open) - Phase 2 output files now stay UTF-8 clean across reruns.

### Scope
Phase 4 is a **reporting layer only** — not an optimizer, not a simulator, not a conflict analyzer, not a per-trip reasoning engine.

- ❌ **No conflict analyzer.** The solver returns OPTIMAL in every phase (Phase 1 objective 4800 gap 0.0%; Phase 3 all pools objective 0.0 gap 0.0%). There is no infeasibility to analyze.
- ❌ **No per-trip "why" claims.** CP-SAT returns a global solution, not per-assignment reasons. The report frames explanations as "context + consistency," not "reason."
- ❌ **No hardcoded numbers.** Every number traces to one of the seven source files, cited below each table.

### Code

- `src/explainability/__init__.py` — one-line package docstring
- `src/explainability/report_generator.py` — ~27.7 KB, runs clean (`python -m src.explainability.report_generator`)
- Mirror `solver/solve.py` / `solver/validator.py` conventions: `Path(__file__).parent.parent...`, `[report]` print prefix, one `main()`, explicit `FileNotFoundError` / `ValueError`
- No imports of `solver` or `src.simulation` — Phase 4 is standalone

### Report sections (7, all present)

1. **Executive Summary** — total trips (250), total rakes (18), active drivers per pool. States that Phase 1 OPTIMAL is under the O6 rake-balance objective only; other objectives disabled in V1.
2. **Phase 1 Constraint Status** — from `validation.json`; reports the 10 checks present for the current run (R1, R3, R4, R5, R6, R7, R9, R10, R11, D). R8/R12 no longer run; R9 is a dedicated PASS; D is direction consistency.
3. **Phase 3 Constraint Status (C1–C7, per pool)** — from `crew_validation.json`; C5 deferred, C6 soft-objective.
4. **Rake Utilization** — from `schedule.csv`; `utilization_pct = busy_sec / span_sec × 100`, defined before the table.
5. **Driver Utilization** — from `crew_schedule.csv` + `crew_solution.json`; `total_depot_hours = (max sign_off − min sign_on)/3600` per driver per pool, documented as total depot time including 900 s buffers (not C2 `duty`).
6. **Simulation Results** — from `simulation_kpis.json`; headline + 100-seed Monte Carlo. ±5 = 100% stated as **model property** (300 s cap + inclusive tolerance), not operational guarantee.
7. **Sensitivity Analysis & Honest Limitations** — pool-size table (45/50/55) presented as-is; no recommendation drawn.

### Outputs

- `data/processed/explainability_report.md` — 7 sections, sources cited below every table
- `data/processed/utilization_stats.json` — machine-readable stats, derivation formulas restated for reproducibility

### Audit

- ✅ Every number in the report traced to `validation.json`, `solution.json`, `schedule.csv`, `simulation_kpis.json`, `crew_solution.json`, `crew_validation.json`, or `crew_schedule.csv`
- ✅ No hardcoded numbers anywhere in the module
- ✅ No conflict analyzer built (solver OPTIMAL in all phases)
- ✅ No per-trip "why" claims anywhere in the report
- ✅ No Phase 1/2/3 source file modified — Phase 4 reads them read-only

See `docs/phases.md` §Phase 4 for the full scope and rationale for what was and was not built. See `src/explainability/report_generator.py` for the implementation.

## Latest Phase 5 Results (2026-11-15, regenerated on 255-trip Phase 1 baseline)

Phase 5 **Disruption Response** is **complete** on the current 255-trip Phase 1 baseline. A planned disruption response engine re-optimizes the Phase 1 schedule when rakes become unavailable. Two scenarios verified end-to-end.

> **Revision note (2026-11-15):** Phase 1 was regenerated to 255 trips (was 250), with a new rake distribution (3 × 15 + 15 × 14). Phase 5 was regenerated against this new baseline. All numbers below are from the 255-trip run. Old 250-trip numbers are superseded. Backups preserved as `data/processed/reschedule_*_250_before_255.*` and `reschedule_*_feasible_4rake.*`.

### Scope

Phase 5 is a **planned disruption response engine** — not a near-real-time control system, not a warm-start optimizer, not a passenger-flow simulator.

- ✅ **Full CP-SAT re-solve** (A ~270 s, B ~94 s on 255 trips), not warm-start.
- ✅ **Two scenarios:** A = single-rake evening failure (happy path), B = 4-rake morning-peak mass failure (capacity-constrained).
- ✅ **Parallel fleet file** `rakes_phase5.csv` — Phase 1's `rakes.csv` untouched.
- ✅ **Drop-aware R1** in `solver/reschedule_constraints.py`.
- ✅ **`W_DROP = 1000` penalty** — empirically verified load-bearing.
- ✅ **`add_balance_bound_phase5`** — optimality-gap acceleration (pruning hint, does not change objective).
- ❌ **No warm-start** (`src/realtime/warm_start.py` not built).
- ❌ **No dynamic disruption handler** (the two scenario JSONs are the only inputs).
- ❌ **No separate validator** (diff JSON's `compute_diff` performs the equivalent integrity checks).

### Data

Parallel fleet file `data/synthetic/rakes_phase5.csv` — 25 rakes + 2 new columns. **R017/R018 moved to TPHT** (were MUTTOM) in the 255-trip migration:

| Location | Count |
|---|---:|
| ALVA | 9 service |
| TPHT | 9 service |
| MUTTOM | 7 maintenance only |

| Column | Values |
|---|---|
| `km_since_last_maintenance` (int, km) | `[SYNTHETIC]` — 0 for unscheduled_repair; 2,100–7,200 for scheduled; 3,600–6,700 for service |
| `maintenance_type` (string) | `service` (18) / `scheduled` (5) / `unscheduled_repair` (2) |

**Maintenance split (derived from D2's rule applied to actual `rakes.csv`):**

- **Unscheduled repair (blocked):** R020 (176,838 km), R023 (199,479 km) — the 2 highest-mileage maintenance rakes.
- **Scheduled (reactivatable):** R019 (4,200 km-since), R021 (6,800), R022 (2,100), R024 (3,500), R025 (7,200).

**D3 correction note:** The original Phase 5 handoff listed R019–R023 as "scheduled" — this contradicted D2's "2 highest-mileage = unscheduled" rule. Applied D2 on real data: R020/R023 unscheduled; R022/R024 are the lowest-km scheduled rakes and are the ones activated.

### Constraints (Phase 5 additions)

- **R1 (modified):** `sum(rake_trip) + dropped[tid] == 1` — all 255 trips may_drop.
- **Objective:** `W_RAKE_BALANCE × OBJ_SCALE × Σ balance_devs + W_DROP × OBJ_SCALE × Σ dropped`, with `W_DROP = 1000`.
- **`add_balance_bound_phase5`** — hard constraint `trips_per_rake ≤ ceil(255/active_rakes)`, pruning hint that accelerates optimality proof without changing the objective.
- All Phase 1 hard constraints (R3–R12) unchanged.
- **Withdrawal rule:** wall-clock cutoff — any trip departing ≥ disruption time is unavailable to the downed rake. In-progress trip completes normally (no mid-trip abort).

### Results (both scenarios OPTIMAL, gap 0.0%)

| | Scenario A | Scenario B |
|---|---|---|
| Disruption time | **18:00** (evening peak) | **07:00** (morning peak) |
| Rakes down | R008 | R008, R013, R015, R002 |
| Rakes activated | R022 (2,100 km-since) | R022 + R024 (2,100 + 3,500) |
| Active rakes after response | 18 | 16 |
| Trips withdrawn from downed rakes | 4 | 53 |
| Recovered by reassignment | 4 (100%) | 46 (86.8%) |
| **Dropped** | **0** | **7** |
| Solver status | OPTIMAL | OPTIMAL |
| Objective | 900.0 | 702,400.0 |
| Gap | 0.0% | 0.0% |
| Elapsed | ~270 s | ~94 s |

**Scenario A** — happy path: one rake fails late evening, only 4 trips at risk, all 4 reassigned, 0 dropped. R008 in-progress: **WK_181** (17:45:55 → 18:36:42, mid-trip) — completes normally.

**Scenario B** — capacity-constrained: 4 rakes fail at morning-peak start, 53 trips at risk, solver recovers 46 (86.8%) and drops 7. Drop IDs: `WK_165, WK_178, WK_179, WK_211, WK_23, WK_39, WK_60`. In-progress at 07:00: R008 = **WK_8** (06:30:00 → 07:23:38, mid-trip); R013, R015, R002 = between trips.

### Optimality-gap acceleration (2a)

**Problem:** Initial 255-trip Scenario B (with 4 rakes down) returned FEASIBLE at **14.19% gap** in 300 s — solver found 7 drops but couldn't prove 7 minimal because the search tree contained many balance-tied arrangements (each trip could go to several rakes at equal balance cost).

**Fix:** Added `add_balance_bound_phase5` — a hard constraint `trips_per_rake ≤ ceil(255/active_rakes)` which is **logically implied** by the balance objective (any optimal schedule satisfies it). This prunes the redundant balance-tied arrangements without changing the objective.

**Result:** OPTIMAL at **gap 0.0% in 93.8 s** (vs FEASIBLE at 300 s timeout). The bound only accelerates proof of optimality — it does not change which schedule is optimal. Same 7 drops, same objective 702,400.

### Honest limitations (documented in `reschedule_summary.md`)

1. **Full re-solve (A ~270 s, B ~94 s), not warm-start.** Warm-start optimization is future work.
2. **No mid-trip abort** — rake completes its in-progress trip before withdrawal; passengers not deboarded.
3. **No cascading delay modeling.** Phase 2 integration is future work.
4. **Not real-time** — planned disruption response, not sub-second control.
5. **Synthetic `km_since_last_maintenance`** — a SYNTHETIC proxy for reliability; not a live fleet-management feed.
6. **"Dropped" ≠ "delayed."** Dropped means the trip does not operate (cancelled). The "45–90 min wait" framing describes the passenger *experience* of a dropped trip, not a rescheduled delay. Both are true; never conflated.
7. **`add_balance_bound_phase5` is a pruning hint, not an objective change.** The 255-trip Scenario B initially returned FEASIBLE at 14.19% gap. The bound closed it to OPTIMAL at 0.0% without changing which schedule is optimal.

### Code

| File | Purpose |
|---|---|
| `data/synthetic/rakes_phase5.csv` | 25 rakes + 2 new columns (R017/R018 at TPHT) |
| `data/disruptions/scenario_a.json` | R008 @ 18:00:00 |
| `data/disruptions/scenario_b.json` | R008, R013, R015, R002 @ 07:00:00 |
| `solver/reschedule_config.py` | Phase-5-local constants; imports shared from `solver.config` |
| `solver/reschedule_models.py` | `RescheduleProblemData` self-contained loader |
| `solver/reschedule_constraints.py` | Drop-aware R1 + `W_DROP` penalty + `add_balance_bound_phase5` |
| `solver/reschedule_diff.py` | Library: `compute_diff`, `write_diff_json`, `write_summary_md` |
| `solver/reschedule_solve.py` | Orchestrator |

### Outputs

- `data/processed/reschedule_scenario_a.csv` — 255 rows, 7 columns, 0 DROPPED
- `data/processed/reschedule_scenario_b.csv` — 255 rows, 7 columns, 7 DROPPED rows with empty departure/arrival
- `data/processed/reschedule_diff.json` — D10 schema + `trips_withdrawn` + `in_progress`
- `data/processed/reschedule_summary.md` — D11 template, corrected narrative, per-rake in-progress disclosure, honest limitations

All numbers computed from actual solve output.

### Verification

- ✅ Scenario A: 255 rows, 0 DROPPED, 7 columns
- ✅ Scenario B: 255 rows, 7 DROPPED, 7 columns
- ✅ Arithmetic identity: A = 14+241+0 = 255 ✅; B = 15+233+7 = 255 ✅
- ✅ No Phase 1/2/3/4 files modified
- ✅ All 8 handoff success criteria met
- ✅ **Both scenarios OPTIMAL at gap 0.0%**

See `docs/phases.md` §Phase 5 for full design. See `data/processed/reschedule_summary.md` for live narrative output.

### Next

Phase 7 — Dashboard (or Phase 6 ML if historical delay data becomes available).



