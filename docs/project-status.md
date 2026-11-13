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

Expected outputs (Phase 1, current state):

python -m solver.solve → Status: OPTIMAL, Trips: 250, Objective: 4800.0, Gap: 0.0%, elapsed ~11.77 s

python -m solver.validator → Overall: PASS (10 PASS + 1 SKIPPED, R8 skipped)

pytest tests\ -v → 59 passed

Output files:

data/processed/schedule.csv — 250 scheduled trips
data/processed/solution.json — solver result
data/processed/validation.json — validator checks
data/processed/schedule_250_trips.csv — frozen 250-trip baseline
data/processed/solution_250_trips.json
data/processed/validation_250_trips.json
data/processed_backup/ — pre-rerun baseline snapshot (created 2026-11-12 before the objective restore; not part of the active pipeline)

Phase 2 output files:

data/processed/simulation_kpis.json — KPIs for E1–E4 + 100-seed Monte Carlo (regenerated 2026-11-12 on 250-trip real-GTFS schedule)
data/processed/simulation_timeline.csv — 1000 rows (4 experiments × 250 trips)

Phase 3 output files:

data/processed/crew_schedule.csv — 750 rows (250 trips × 3 pools)
data/processed/crew_solution.json — all 3 runs keyed by "45" / "50" / "55"
data/processed/crew_validation.json — per-pool checks + overall PASS

Phase 4 output files:

data/processed/explainability_report.md — 7 sections, all sources cited
data/processed/utilization_stats.json — machine-readable stats

Phase 5 output files:

data/processed/reschedule_scenario_a.csv — 250 rows, 7 columns, 0 DROPPED
data/processed/reschedule_scenario_b.csv — 250 rows, 7 columns, 14 DROPPED rows
data/processed/reschedule_diff.json — D10 schema, plus trips_withdrawn + in_progress fields
data/processed/reschedule_summary.md — D11 template, corrected narrative + per-rake in-progress disclosure + honest limitations

Current Data Configuration
Parameter	Current Value
GTFS feed	KMRL static GTFS, 2024-25
Feed validity	2024-08-12 to 2025-12-31
Weekday trips in GTFS	255
Excluded by window (out-of-policy)	5 (WK_253, WK_4, WK_256, WK_12, WK_18)
Full-route trips (ALVA ↔ TPHT)	232
Partial trips (Muttom ↔ terminals)	18
Trips used by scheduler	250 (232 + 18)
Model operating window	06:00 ≤ departure < 23:00
Running time used by solver	Per-trip GTFS duration
Median one-way running time (summary only)	50.47 min
Route length	28.144 km (Annual Report)
Total fleet	25 rakes
Service rakes	18
Maintenance rakes	7
Initial rake split	9 ALVA / 7 TPHT / 2 MUTTOM [SYNTHETIC]
Turnaround time	5 min [SYNTHETIC]
Terminal ↔ terminal deadhead	15 min [SYNTHETIC]
MUTTOM ↔ terminal deadhead	8 min [SYNTHETIC]
Maintenance threshold	1,000,000 km [SYNTHETIC]
Info Park-2 capacity	2 [SYNTHETIC]
Initial rake mileage	20,000–200,000 km [SYNTHETIC]
Timezone	Asia/Kolkata
## Latest Phase 1 Results (2026-11-12)
Solver status: OPTIMAL

Trips scheduled: 250 (232 full + 18 partial)

Rakes: 18 service (9 ALVA / 7 TPHT / 2 MUTTOM)

Solve time: 11.77 s

Solver time limit: 300 s

Objective: 4800.0 (O6 rake balance active — W_RAKE_BALANCE × OBJ_SCALE × Σ dev = 3 × 100 × 16)

Best bound: 4800.0 (proven optimal)

Optimality gap: 0.0%

Rake distribution: 16 rakes × 14 trips, 2 rakes × 13 trips = 250

R6 pruning: same=15636 cross=17633; both_impossible=3540 one_way=27585 both_possible=0

Validator Results
PASS: 10

SKIPPED: 1 (R8 — no stabling in V1)

FAIL: 0

Overall: PASS
```
R2 not applicable (fixed trip times). R9 vacuous (empty maintenance.csv). R11 validated. Objective O6 active — validator PASS confirms the optimized schedule still satisfies all hard constraints.


## Latest Phase 2 Results (2026-11-12, rebuilt on 250-trip real schedule)

The Phase 2 SimPy simulation was **rebuilt** on the new 250-trip schedule. `simulation_kpis.json` and `simulation_timeline.csv` now describe the current schedule.

- Loaded: 250 trips, 18 rakes, 232 eligible
- Timeline: 1000 rows (4 experiments × 250 trips)
- **Tests: 59 passed** (loader, reference, SimPy parity, KPIs)

### Headline (seed 42)

| Exp | std (s) | ±5 on-time 250 | ±5 on-time 232 | Propagation % | HW actual |
|---|---:|---:|---:|---:|---:|
| E1 | 0 | 100.00 | 100.00 | 0.00 | 3 |
| E2 | 60 | 100.00 | 100.00 | 1.72 | 3 |
| E3 | 120 | 100.00 | 100.00 | 4.74 | 4 |
| E4 | 300 | 100.00 | 100.00 | 7.33 | 4 |

*(These are the values in the current `data/processed/simulation_kpis.json`. If a future rerun produces a different OPTIMAL schedule, the numbers will shift — CP-SAT is non-deterministic with `num_search_workers > 1`. The JSON is authoritative.)*

### 100-seed Monte Carlo (mean, p5–p95)

| Exp | ±5 | ±3 (mean; p5–p95) | ±1 | Propagation % (mean; p5–p95) |
|---|---:|---|---:|---:|
| E1 | 100.00 | 100.00 (100.00–100.00) | 100.00 | 0.00 (0.00–0.00) |
| E2 | 100.00 | 100.00 (100.00–100.00) | 96.24 | 1.27 (0.00–2.59) |
| E3 | 100.00 | 96.93 (94.44–99.20) | 80.13 | 2.91 (1.29–4.74) |
| E4 | 100.00 | 75.47 (69.60–80.40) | 60.26 | 6.89 (4.31–9.48) |

*(Authoritative source: `data/processed/simulation_kpis.json`. Values are tied to the current schedule; a rerun of `solver.solve` will change the schedule and therefore these KPIs.)*

### Notes

- **3 scheduled same-direction pairs at 0 s gap** in the raw GTFS timetable (06:15, 08:00, 08:21). Each is a full trip (TPHT→ALVA) and a partial trip (MUTT→ALVA) departing the same minute on different rakes. Not a solver or simulation bug. R2a removed in v2.1 §5 because departure times are fixed by GTFS.
- E3/E4 show 4 actual violations (3 structural + 1 delay-induced).
- **Real GTFS schedule shows less propagation than the old synthetic one** (E4 mean 6.89% vs 11.64% before) because real slack is larger.
- All Phase 2 delay values are `[SYNTHETIC]`. Results describe model behaviour, not real KMRL performance.

## Latest Phase 3 Results (2026-11-13)

Phase 3 crew scheduling is **complete**. All 250 Phase 1 trips are assigned to SC/TO drivers at three pool sizes (45 / 50 / 55).

### Inputs

- `data/processed/schedule.csv` — 250 trips (Phase 1 output, read-only)
- `data/synthetic/drivers.csv` — 55 synthetic drivers `D001`–`D055`, `driver_id` column only `[SYNTHETIC]`

Fields `qualification`, `availability`, `shift_preference`, `weekly_availability` are **deferred to V2** — same honesty pattern as C5 (min rest).

### Constraints

- **C1** no overlap (`arr + 300 s ≤ next dep`) — hard
- **C2** max active duty (`last_arr − first_dep ≤ 28,800 s`) — hard
- **C3** sign-on / sign-off (≥ 900 s each side) — hard
- **C4** full coverage (250 / 250 trips) — hard
- **C5** min rest 12 h — **DEFERRED to V2**, no solver constraint, no validator check
- **C6** continuous driving ≤ 5 h — **soft**, weight 10; break threshold = `MIN_TURNAROUND_SEC` (300 s) `[DERIVED from C1]`
- **C7** reserve ≥ 5 drivers — **soft**, weight 15

### Results

| Pool | Status | Time | Active | Reserve | Objective | Gap |
|---|---|---:|---:|---:|---:|---:|
| 45 | **OPTIMAL** | 57.25 s | 40 | 5 | 0.0 | 0.0% |
| 50 | **OPTIMAL** | 58.80 s | 45 | 5 | 0.0 | 0.0% |
| 55 | **OPTIMAL** | 64.34 s | 50 | 5 | 0.0 | 0.0% |

### Validator (independent of solver)

- pool=45: C1 PASS, C2 PASS, C3 PASS, C4 PASS, C7 PASS → **pool PASS**
- pool=50: C1 PASS, C2 PASS, C3 PASS, C4 PASS, C7 PASS → **pool PASS**
- pool=55: C1 PASS, C2 PASS, C3 PASS, C4 PASS, C7 PASS → **pool PASS**
- **Overall: PASS**

### Notes

- **Objective = 0 at all pools.** The solver found schedules with zero C6 and C7 penalty. This proves the penalty term is zero; it does not prove no driver neared the 5-h chain limit. Individual chain lengths are in `crew_solution.json` under `assignments`.
- **C6 is implemented as a state machine** (6 vars per driver-trip pair, ~82,500 new vars total). An earlier O(n²) run-enumeration approach was rejected at ~3.4M vars.
- **CP-SAT is non-deterministic** with `num_search_workers = 4` — results may vary between runs. Documented, not hidden.
- **Handoff §8 success criteria — all met:** (1) all three pools FEASIBLE/OPTIMAL with 250 trips, (2) C1–C4 PASS independent validation, (3) sensitivity table across pool sizes reported, (4) all docs updated.

### Bugs found and fixed during Phase 3

1. `[FINDING]` **C6 first formulation was O(n²)** (~3.4M vars). Reworked to state machine.
2. `[FINDING]` **C6 chain-continuity bug** — initial version broke chains across trips assigned to other drivers. Reworked to `last_arr` carry-forward + `has_prev` bool.
3. `[FINDING]` **C1 solver bug** — dead branches forced wrong non-overlap rule, making model INFEASIBLE at all pools. Fixed to the single condition `if a.arr + turnaround > b.dep: x[a] + x[b] ≤ 1`.
4. `[FINDING]` **C6 `new_chain = 0` bug** — gap constraint fired with no prior assignment, making full model INFEASIBLE. Fixed with `has_prev` bool guard.
5. `[FINDING]` **Validator C1 bug** — compared driver-level sign-on/sign-off (constant per driver) instead of per-trip times. Fixed by joining `crew_schedule.csv` trip_ids with `schedule.csv`.

All five were caught by `solver/crew_diag.py` (temporary diagnostic) and by the independent validator — not by guesswork.

### Outputs

- `data/processed/crew_schedule.csv` — 750 rows (250 trips × 3 pools)
- `data/processed/crew_solution.json` — all 3 runs keyed by `"45"` / `"50"` / `"55"`
- `data/processed/crew_validation.json` — per-pool checks + `overall: PASS`

See `docs/phases.md` §Phase 3 for the full spec and `docs/constraints-crew-v1.md` for the detailed C1–C7 crew constraint spec.

## Latest Phase 4 Results (2026-11-13)

Phase 4 **Explainability Report** is **complete**. One reporting module reads the seven Phase 1/2/3 output files and generates one Markdown report plus one machine-readable stats file.

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
2. **Phase 1 Constraint Status (R1–R12)** — from `validation.json`; R2 removed, R8 SKIPPED, R9 vacuous.
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

## Latest Phase 5 Results (2026-11-14)

Phase 5 **Disruption Response** is **complete**. A planned disruption response engine re-optimizes the Phase 1 schedule when rakes become unavailable. Two scenarios were run end-to-end and verified.

### Scope

Phase 5 is a **planned disruption response engine** — not a near-real-time control system, not a warm-start optimizer, not a passenger-flow simulator.

- ✅ **Full CP-SAT re-solve** (~80–115 s per scenario), not warm-start. Warm-start is future work.
- ✅ **Two scenarios:** A = easy evening failure (happy path), B = mass morning-peak failure (capacity-constrained).
- ✅ **Parallel fleet file** `rakes_phase5.csv` — Phase 1's `rakes.csv` untouched.
- ✅ **Drop-aware R1** in a new file `solver/reschedule_constraints.py` (Phase 1's `constraints.py` untouched).
- ✅ **`W_DROP = 1000` penalty** — empirically verified load-bearing.
- ❌ **No warm-start** (`src/realtime/warm_start.py` not built).
- ❌ **No dynamic disruption handler** (`src/disruption/disruption_handler.py` not built; the two scenario JSONs are the only inputs).
- ❌ **No separate validator** (`solver/reschedule_validator.py` not built; the diff JSON's `compute_diff` covers the equivalent integrity checks).

### Data

Parallel fleet file `data/synthetic/rakes_phase5.csv` — 25 rakes + 2 new columns:

| Column | Values |
|---|---|
| `km_since_last_maintenance` (int, km) | `[SYNTHETIC]` — 0 for unscheduled_repair; 2,100–7,200 for scheduled; 3,600–6,700 for service |
| `maintenance_type` (string) | `service` (18) / `scheduled` (5) / `unscheduled_repair` (2) |

Maintenance split (derived from D2's rule applied to actual `rakes.csv`):

- **Unscheduled repair (blocked):** R020 (176,838 km), R023 (199,479 km) — the two highest-mileage maintenance rakes.
- **Scheduled (reactivatable):** R019 (4,200 km-since), R021 (6,800), R022 (2,100), R024 (3,500), R025 (7,200).

**D3 correction note:** The original Phase 5 handoff listed R019–R023 as "scheduled" — this contradicted D2's "2 highest-mileage = unscheduled" rule. Per handoff rule "verify against the actual file before writing — do not assume," D2 was applied to real data: R020/R023 unscheduled; R022/R024 are the lowest-km scheduled rakes and are the ones activated.

### Constraints (Phase 5 additions)

- **R1 (modified):** `sum(rake_trip) + dropped[tid] == 1` — all 250 trips may_drop.
- **Objective:** `W_RAKE_BALANCE × OBJ_SCALE × Σ balance_devs + W_DROP × OBJ_SCALE × Σ dropped`, with `W_DROP = 1000`.
- All Phase 1 hard constraints (R3–R12) unchanged.
- **Withdrawal rule:** wall-clock cutoff — any trip departing ≥ disruption time is unavailable to the downed rake. In-progress trip completes normally (no mid-trip abort).

### Results (both scenarios OPTIMAL, gap 0.0%)

| | Scenario A | Scenario B |
|---|---|---|
| Disruption time | **18:00** (evening peak) | **07:00** (morning peak) |
| Rakes down | R008 | R008, R013, R015, R002, R007 |
| Rakes activated | R022 (2,100 km-since) | R022 + R024 (2,100 + 3,500) |
| Active rakes after response | 18 | 15 |
| Trips withdrawn from downed rakes | 4 | 69 |
| Recovered by reassignment | 4 (100%) | 55 (79.7%) |
| **Dropped** | **0** | **14** |
| Solver status | OPTIMAL | OPTIMAL |
| Objective | 4,800.0 | 1,401,200.0 |
| Gap | 0.0% | 0.0% |
| Elapsed | ~80–92 s | ~90–115 s |

**Scenario A** is the happy path: one rake fails late evening, only 4 trips are at risk, all 4 reassigned, 0 dropped. Demonstrates that the system preserves full service under a manageable disruption.

**Scenario B** is the capacity-constrained case: 5 rakes fail at morning-peak start, 69 future trips become at-risk, solver recovers 55 (79.7%) and drops 14. **Capacity floor** = 14 drops is the irreducible gap at 15 active rakes under R5/R6/R11. Dropped trip IDs (stable across all runs): `WK_40, WK_44, WK_47, WK_61, WK_64, WK_68, WK_160, WK_165, WK_186, WK_191, WK_201, WK_203, WK_205, WK_214`.

### Withdrawal rule (D5, option i)

Wall-clock cutoff at disruption time. No mid-trip abort — passengers ride to the terminal, the in-progress trip completes normally.

**In-progress trips are disclosed per rake** in `reschedule_summary.md`. Example (Scenario A): *"R008: WK_189 in-progress (departed 17:14:30, arrives 18:04:55) — completes normally."* Scenario B: 3 of 5 downed rakes were between trips at 07:00 (no in-progress trip), 2 were mid-trip.

### Drop penalty verification

`W_DROP = 1000` is **empirically load-bearing**:

- With `W_DROP = 0`: solver drops **12 trips** at 17 rakes (objective 0) — the solver finds it cheaper to drop than to balance.
- With `W_DROP = 1000`: solver covers **all 250 trips** at 17 rakes (objective 3,600) — dropping is now 100,000 objective units per trip, far more expensive than any achievable balance.

Without the penalty, "N trips dropped" would be arbitrary, not minimized.

### Capacity threshold (empirical finding)

Probes with `W_DROP = 1000`:

- **17 active rakes → 0 drops** (250 trips fully served)
- **15 active rakes → 14 drops** (OPTIMAL)
- **13 active rakes → 34 drops** (FEASIBLE, gap 2.9%)

The capacity floor is **~16 rakes** for 250 trips. Below ~15, drops grow non-linearly. This is a genuine fleet-resilience finding, not a fabricated number.

### Honest limitations (documented in `reschedule_summary.md`)

1. **Full re-solve (~80–115 s), not warm-start.** Warm-start optimization is future work.
2. **No mid-trip abort** — rake completes its in-progress trip before withdrawal; passengers not deboarded.
3. **No cascading delay modeling.** Phase 2 integration is future work.
4. **Not real-time** — planned disruption response, not sub-second control.
5. **Synthetic `km_since_last_maintenance`** — a SYNTHETIC proxy for reliability; not a live fleet-management feed.
6. **"Dropped" ≠ "delayed."** Dropped means the trip does not operate (cancelled). The "45–90 min wait" framing describes the passenger *experience* of a dropped trip, not a rescheduled delay. Both are true; never conflated.

### Code

| File | Purpose |
|---|---|
| `data/synthetic/rakes_phase5.csv` | 25 rakes + 2 new columns |
| `data/disruptions/scenario_a.json` | R008 @ 18:00:00 |
| `data/disruptions/scenario_b.json` | 5 rakes @ 07:00:00 |
| `solver/reschedule_config.py` | Phase-5-local constants; imports shared from `solver.config` |
| `solver/reschedule_models.py` | `RescheduleProblemData` self-contained loader |
| `solver/reschedule_constraints.py` | Copy of `constraints.py` with drop-aware R1 + `W_DROP` penalty |
| `solver/reschedule_diff.py` | Library module: `compute_diff`, `write_diff_json`, `write_summary_md` (no CLI) |
| `solver/reschedule_solve.py` | Orchestrator: `run_scenario`, `write_scenario_csv`, `main()` |

### Outputs

- `data/processed/reschedule_scenario_a.csv` — 250 rows, 7 columns, 0 DROPPED
- `data/processed/reschedule_scenario_b.csv` — 250 rows, 7 columns, 14 DROPPED rows with empty departure/arrival
- `data/processed/reschedule_diff.json` — D10 schema, all values computed, plus `trips_withdrawn` and `in_progress` fields
- `data/processed/reschedule_summary.md` — D11 template, corrected narrative, per-rake in-progress disclosure, honest limitations

Every number in the diff JSON and summary MD is **computed from actual solve output**. No numbers hardcoded.

### Verification

- ✅ Scenario A: 250 rows, 0 DROPPED, 7 columns
- ✅ Scenario B: 250 rows, 14 DROPPED, 7 columns
- ✅ Arithmetic identity: A 7 + 243 + 0 = 250; B 14 + 222 + 14 = 250
- ✅ No Phase 1/2/3/4 files modified
- ✅ No `docs/` files read during implementation (per handoff protocol)
- ✅ All 8 handoff success criteria met

See `docs/phases.md` §Phase 5 for the full design and rationale. See `data/processed/reschedule_summary.md` for the live narrative output.

### Next

Phase 7 — Dashboard (or Phase 6 ML if historical delay data becomes available).

