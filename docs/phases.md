# MetroPulse — Complete Phase Plan

**Project:** AI-Driven Train Induction Planning and Scheduling System for Kochi Metro Rail Limited (KMRL)  
**Scheduling Engine:** OR-Tools CP-SAT  
**Simulation Engine:** SimPy  
**Version:** 2.5
**Last Updated:** 13 November 2026

---

# 1. Project Overview

MetroPulse is an AI-driven train induction planning and scheduling system designed for Kochi Metro Rail Limited (KMRL).

The system aims to generate feasible train schedules, allocate available rakes, simulate operational delays, assign drivers, and eventually support near-real-time rescheduling.

### Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core development |
| Pandas | Data processing |
| NetworkX | Network and route analysis |
| OR-Tools CP-SAT | Train and crew scheduling |
| SimPy | Operational simulation |
| XGBoost | Optional delay prediction |
| Streamlit | Dashboard and visualization |

### Data Sources

| Source | Purpose |
|---|---|
| KMRL Static GTFS 2024–25 | Timetable and trip information |
| KMRL Annual Report 2024–25 | Route length and operating information |
| 2026 news report | Updated fleet information |
| Synthetic data | Missing operational information and assumptions |

**Important:** The GTFS feed is static data valid from 12 August 2024 to 31 December 2025. It is not a live 2026 timetable.

---

# 2. Phase Overview

| Phase | Description | Status |
|---|---|---|
| Phase 0 | Project Setup | Completed |
| Phase 1 | Train Scheduling using CP-SAT | Completed (rebuilt 2026-11-12 on real GTFS trips) |
| Phase 2 | Operational Simulation using SimPy | Completed (rebuilt 2026-11-12 on 250-trip real schedule) |
| Phase 3 | Crew Scheduling | Completed (2026-11-13) |
| Phase 4 | Explainability Report | Completed (2026-11-13) |
| Phase 5 | Near-Real-Time Rescheduling | Pending |
| Phase 6 | Machine Learning Delay Prediction | Optional |
| Phase 7 | Dashboard and Visualization | Pending |

---

# Phase 0 — Project Setup

**Status: Completed**

## Objectives

- Set up the Python development environment.
- Create the project folder structure.
- Install required libraries.
- Configure Git and GitHub.

## Technology Stack

- Python
- Pandas
- NetworkX
- SimPy
- OR-Tools
- Streamlit
- Git and GitHub

## Deliverables

- Python virtual environment.
- GitHub repository.
- Project folder structure.
- `.gitignore`
- `.gitattributes`
- `requirements.txt`

---

# Phase 1 — Train Scheduling using CP-SAT

**Status: Completed (rebuilt on real GTFS trip records, 2026-11-12)**

## 1.1 Objective

Generate a feasible daily train schedule using the KMRL GTFS timetable and available rake information.

The scheduler assigns trips to available rakes while satisfying the configured operational constraints.

**Revision note (2026-11-12):** Phase 1 was rebuilt on **real GTFS trip records**, not hourly counts and not synthetic `T0000` trips. The earlier result (FEASIBLE, 306 s, 93.4% gap on 250 synthetic trips) is superseded.

## 1.2 Data Configuration

### GTFS Data

| Parameter | Value |
|---|---:|
| GTFS feed validity | 12 Aug 2024 – 31 Dec 2025 |
| Weekday trips in GTFS | 255 |
| Full-route trips (ALVA ↔ TPHT) | 232 |
| Partial trips (Muttom ↔ terminals) | 18 |
| Total trips used by solver | 250 |
| Operating window | 06:00 ≤ departure < 23:00 |
| Per-trip running time | Real GTFS duration per trip |
| Median one-way running time (summary only) | 50.47 min |
| Route length | 28.144 km |

Of 255 weekday trips in GTFS, **5 depart outside the model window** (`WK_253`, `WK_4`, `WK_256`, `WK_12`, `WK_18`) and are excluded by policy. The remaining **250 trips** are split into 232 full-route and 18 partial trips. **232 + 18 = 250.**

The **solver uses each trip's own GTFS duration**. The 50.47-minute median is a summary statistic only, not a model input.

### Fleet Data

| Parameter | Value |
|---|---:|
| Total rakes | 25 |
| Service rakes | 18 |
| Maintenance rakes | 7 |
| Separate standby rakes | 0 |
| Terminal turnaround | 5 min `[SYNTHETIC]` |
| Terminal ↔ terminal deadhead | 15 min `[SYNTHETIC]` |
| MUTTOM ↔ terminal deadhead | 8 min `[SYNTHETIC]` |

**Initial position split (fixed, not solver choice):**

| Location | Service rakes |
|---|---:|
| ALVA | 9 |
| TPHT | 7 |
| MUTTOM | 2 |

The fleet counts (25 total, 18 service, 7 maintenance) follow the 2026 news article. The KMRL Annual Report 2024–25 reports **15 operating trains**; this is a different reporting period and should be acknowledged when describing the fleet configuration.

The MUTTOM-home rakes are required because 18 partial trips start or end at Muttom. Without them, the 250-trip case is INFEASIBLE.

### Synthetic Assumptions

| Parameter | Value |
|---|---:|
| Terminal turnaround | 5 min |
| Terminal-to-terminal deadhead | 15 min |
| MUTTOM ↔ terminal deadhead | 8 min |
| Maintenance threshold | 1,000,000 km |
| Info Park-2 capacity | 2 rakes |
| Initial rake mileage | 20,000–200,000 km |
| Initial rake split | 9 ALVA / 7 TPHT / 2 MUTTOM |

All the above are `[SYNTHETIC]` because verified operational data is unavailable.

## 1.3 Data Files

| File | Purpose |
|---|---|
| `data/raw/` | Original GTFS files |
| `data/extract_gtfs_trips.py` | Extracts per-trip GTFS records |
| `data/trips_full_route.csv` | 232 full-route trips |
| `data/trips_partial.csv` | 18 partial trips (Muttom ↔ terminals) |
| `data/stop_sequences_full_route.csv` | Full stop sequences for the 232 |
| `data/stop_sequences_partial.csv` | Full stop sequences for the 18 |
| `data/merge_trips.py` | Merges the two into `trips_all.csv` (250) |
| `data/trips_all.csv` | **Solver input** — 250 real GTFS trips |
| `data/verify_gtfs_trips.py` | Reconciliation audit; verifies 232 + 18 = 250 against `hourly_service.csv` |
| `data/hourly_service.csv` | Legacy — reconciliation only; not read by the solver |
| `data/synthetic/rakes.csv` | Synthetic rake fleet |
| `data/synthetic/terminals.csv` | Terminal configuration |
| `data/synthetic/maintenance.csv` | Empty in V1 |
| `data/synthetic/depot.csv` | Depot capacities |
| `data/generate_synthetic_v2.py` | Generates the synthetic fleet |

## 1.4 Solver Implementation

| File | Responsibility |
|---|---|
| `solver/config.py` | Solver configuration |
| `solver/models.py` | Loads `trips_all.csv`, per-trip durations, seconds parsing (supports `>24:00`) |
| `solver/constraints.py` | Defines constraints R1–R12; R6 per-order gap fix; R11 first-trip home rule with deadhead |
| `solver/solve.py` | Executes the CP-SAT solver (O6 rake balance objective active) |
| `solver/validator.py` | Independently validates the generated schedule |

The current validator checks: **R1, R3, R4, R5, R6, R7, R10, R11, R12** (9 PASS) + **R8 SKIPPED** (no stabling in V1). That is **9 PASS + 1 SKIPPED**. R11 is now validated (PASS) because terminal continuity is checked against `rakes.csv` under the first-trip home rule with deadhead.

`R2` is **not applicable** — trip departure times are fixed by GTFS, so headway is a timetable property, not a scheduling decision. `R9` is **vacuous** — `maintenance.csv` is empty in V1.

**Findings from the rebuild:**

- `[FINDING]` `add_obj6_rake_balance` must be called alongside `build_objective`. When both are called (current configuration), the model is OPTIMAL with objective 4800 in 11.77 s. Earlier attempts to call `o6` without `build_objective` produced mixed results during the 2026-11-12 rebuild; the precise cause was not conclusively diagnosed. See `constraints-v2.2` §6/§10.

- `[FINDING]` R6 must compute `gap_ab` and `gap_ba` **per order**. The earlier one-gap-per-pair rule allowed cross-terminal switches (ALVA↔MUTT, TPHT↔MUTT) with gaps between 5 and 15 min. See `constraints-v2.2` §5 R6.

## 1.5 Phase 1 Results

| Metric | Result |
|---|---:|
| Trips scheduled | **250** (232 full + 18 partial) |
| Configured service rakes | 18 (9 ALVA / 7 TPHT / 2 MUTTOM) |
| Solver status | **OPTIMAL** |
| Solver wall-clock time | **11.77 s** |
| Solver time limit | 300 s |
| Objective value | **4800.0** (O6 rake balance active) |
| Best bound | **4800.0** (proven optimal) |
| Optimality gap | **0.0%** (best bound equals objective) |
| Rake distribution | 16 rakes × 14 trips, 2 rakes × 13 trips = 250 |
| R6 pruning summary | `same=15636 cross=17633; both_impossible=3540 one_way=27585 both_possible=0` |

### Validator Results

| Result | Count |
|---|---:|
| PASS | 10 |
| SKIPPED | 1 (R8) |
| FAIL | 0 |

**Overall validator status: PASS**

Important notes:

- R8 is skipped because stabling assignments are not implemented in V1.
- R9 is vacuous (empty `maintenance.csv`).
- R11 is **validated** (PASS) — first-trip home rule with deadhead, checked against `rakes.csv`.
- The objective is **active** (O6 rake balance). See §1.5 results and `constraints-v2.2` §6. V1 is single-objective optimization, not a feasibility probe.
- "All 18 service rakes used" is **confirmed** from `schedule.csv`.

## 1.6 How to Run Phase 1

```powershell
cd Z:\metropulse

.\venv\Scripts\Activate.ps1

# Regenerate real-GTFS trip files from scratch (only if required)
python data\extract_gtfs_trips.py
python data\verify_gtfs_trips.py
python data\merge_trips.py

# Generate synthetic operational data
python data\generate_synthetic_v2.py

# Run the scheduler
python -m solver.solve

# Validate the generated schedule
python -m solver.validator
```
# Phase 2 — Operational Simulation using SimPy

**Status**: Completed (rebuilt 2026-11-12 on 250-trip real schedule)

## 2.1 Objective
Simulate the Phase 1 schedule under different delay conditions.

The purpose is to understand how delays affect:

Train departure times.

Train arrival times.

Rake availability.

Subsequent trips assigned to the same rake.

Overall timetable reliability.

The simulation uses the schedule generated by CP-SAT, using per-trip GTFS durations.

## 2.2 Simulation Design

### Input

- `schedule.csv`
- Rake assignments from Phase 1.
- Running time: per-trip GTFS duration (loaded from `schedule.csv` column `duration_sec`).
- Turnaround time: 5 minutes.

Each trip uses its own GTFS duration; there is no global 50-minute constant. The 50.47-min median is a summary statistic only and is not a simulation input.

### Delay Distribution
Synthetic assumption:
``` python

DELAY_DISTRIBUTION_TYPE = "clipped_normal"

DELAY_DISTRIBUTION_MEAN_SEC = -48  # Pre-clip mean
DELAY_DISTRIBUTION_STD_SEC = 60

DELAY_DISTRIBUTION_MIN_SEC = 0
DELAY_DISTRIBUTION_MAX_SEC = 300
```
The distribution is clipped between 0 and 300 seconds.

The mean of -48 seconds is the pre-clipping mean. It is not the resulting mean delay after clipping.

## 2.3 Delay Propagation Logic

Use the following propagation approach.
```python
early_dep[i] = sched_dep[i] + own_delay[i]

propagated_dep[i] = actual_arr[p] + 5_minutes

actual_dep[i] = max(
    early_dep[i],
    propagated_dep[i]
)

actual_arr[i] = actual_dep[i] + duration_sec[i]

propagated_delay[i] = max(
    0,
    propagated_dep[i] - early_dep[i]
)
```
Where:

i = Current trip.

p = Immediately preceding trip assigned to the same rake, ordered by scheduled departure.

actual_arr[p] = Actual arrival time of the preceding trip.

duration_sec[i] = Per-trip GTFS duration from the schedule (not a fixed constant).

5 minutes = Synthetic turnaround time.

Running time is per-trip from GTFS, not a fixed 50-minute constant.

For the first trip assigned to a rake:

```
actual_dep[i] = early_dep[i]
propagated_delay[i] = 0
```

There is no preceding trip for the first trip assigned to a rake.

## 2.4 Simulation KPIs

### Primary KPIs
| KPI | Description |
|---|---|
| Total propagated delay | Sum of additional delay caused by previous trips |

For propagation percentage:
```python
propagation_percentage = (
    trips_with_propagated_delay /
    eligible_trips
) * 100
```

Eligible trips exclude the first trip assigned to each rake because those trips have no preceding trip.

### Supplementary KPIs

On-time performance within ±5 minutes.

On-time performance within ±3 minutes.

On-time performance within ±1 minute.

Maximum departure delay.

Total trips completed.

Headway violations.

Proposed on-time definition: A trip is on time if its actual departure is within ±5 minutes of its scheduled departure.

Use this definition consistently in the simulation and reporting.

## 2.5 Experiment Design

Run the simulation with different standard deviation values.

| Experiment | Standard Deviation |
|---|---:|
| E1 | 0 seconds |
| E2 | 60 seconds |
| E3 | 120 seconds |
| E4 | 300 seconds |

Keep the pre-clipping mean fixed at -48 seconds.

Compare the resulting KPIs to understand how increasing delay variability affects the timetable.

The zero-standard-deviation experiment is the baseline scenario. With no additional disruptions, it is expected to show no delay variability, subject to the implemented simulation logic.

## 2.6 Files to Create
```text 
src/
└── simulation/
    ├── __init__.py
    ├── schedule_loader.py
    ├── reference.py
    ├── simpy_runner.py
    ├── kpis.py
    ├── experiments.py
    ├── preflight.py
    └── check_terminals.py
```
### Output Files
```text
data/
└── processed/
    ├── simulation_kpis.json
    └── simulation_timeline.csv
```

### Installation
```
pip install simpy
```
### Run
```
python -m src.simulation.experiments
```


### Deliverables
SimPy simulation engine.

Delay propagation model.

KPI calculation module.

Simulation results for all four experiments.

Comparison of timetable performance under different delay conditions.

## 2.7 Phase 2 Results (rebuilt 2026-11-12)
See docs/project-status.md §Latest Phase 2 Results for the current E1–E4 headline and 100-seed Monte Carlo numbers.

Key facts:

250-trip real-GTFS schedule, 232 eligible.

Per-trip GTFS durations throughout.

59 tests passing.

- E4 (std 300) headline numbers are in the table below and in `data/processed/simulation_kpis.json` (authoritative source; if this doc disagrees with the JSON, the JSON is correct).
- 100-seed mean at E4: ±5 100.00%, ±3 75.95%, ±1 60.84%, propagation 5.88% (per the current `simulation_kpis.json`).

3 scheduled headway violations are a GTFS data fact (R2 removed in v2.1 §5).

### Files delivered

#### File Purpose
```
src/simulation/__init__.py	Package marker
src/simulation/schedule_loader.py	Strict CSV loader with parsing guards and count cross-check
src/simulation/reference.py	Closed-form recurrence; correctness baseline for SimPy
src/simulation/simpy_runner.py	SimPy per-rake process
src/simulation/kpis.py	Pure KPI functions (no SimPy import)
src/simulation/experiments.py	E1–E4 and Monte Carlo runner
src/simulation/preflight.py	Read-only continuity / slack / headway analysis
src/simulation/check_terminals.py	Read-only terminal check helper
```

### Tests

File	Count
tests/test_reference.py	7
tests/test_schedule_loader.py	29
tests/test_simpy_matches_reference.py	9
tests/test_kpis.py	14
Total	59

All 59 pass. The parity test asserts that SimPy output equals the closed-form reference bit-for-bit across all four std values.

### Headline results (seed 42, 250-trip real schedule)

| Experiment | std (s) | ±5 on-time (250) | ±5 on-time (232) | Propagation % | HW actual |
|---|---:|---:|---:|---:|---:|
| E1 | 0 | 100.00% | 100.00% | 0.00% | 3 |
| E2 | 60 | 100.00% | 100.00% | 0.86% | 3 |
| E3 | 120 | 100.00% | 100.00% | 3.02% | 4 |
| E4 | 300 | 100.00% | 100.00% | 6.47% | 4 |

### 100-seed Monte Carlo aggregate

Experiment	±5 mean	±3 mean (p5–p95)	±1 mean	Propagation % mean (p5–p95)
E1	100.00%	100.00% (100.00–100.00)	100.00%	0.00% (0.00–0.00)
E2	100.00%	100.00% (100.00–100.00)	96.29%	1.10% (0.00–2.16)
E3	100.00%	97.00% (94.80–98.80)	80.45%	2.43% (1.27–3.88)
E4	100.00%	75.95% (70.40–80.40)	60.84%	5.88% (3.88–8.19)

### Key findings

±5 on-time is 100% throughout — model property (own-delay cap 300 s, inclusive), not an operational guarantee. Do not report "KMRL is 100% reliable at ±5."

±3 and ±1 show the propagation impact: at E4, 75.95% and 60.84% mean.

Propagation % rises non-linearly with std: 0 → 1.10 → 2.43 → 5.88 mean.

3 scheduled same-direction pairs at 0 s gap in raw GTFS (06:15, 08:00, 08:21). Each is a full trip (TPHT→ALVA) plus a partial trip (MUTT→ALVA) departing the same minute on different rakes. Data fact, not a solver bug. R2 removed in v2.1 §5.

Real GTFS schedule has less propagation than the old synthetic schedule (E4 mean 5.88% vs 11.64%) because real slack is larger.

±3/±1 on-time degrade under higher std as expected.

### Known limitations

Terminal continuity's first-trip home rule is validated by R11 PASS on the 250-trip schedule; cross-terminal gap consistency is separately confirmed by R6. The old "Txxxx not verifiable" limitation applied to the pre-rebuild synthetic schedule and is removed.

Delay model is [SYNTHETIC] — all numbers describe model behaviour, not real KMRL performance.

Preflight reported 67 non-alternating rake pairs — MUTT/partial-trip artefact, not an error. Documented in the preflight output.

hw_act = 3 at E1–E2, 4 at E3–E4. The 3 structural violations are the GTFS data fact; the extra one at higher std is delay-induced.


# Phase 3 — Crew Scheduling

**Status: Completed (2026-11-13)**

## 3.1 Objective

Assign SC/TO drivers to the 250 trips in the Phase 1 schedule, while satisfying crew duty and rest constraints. The Phase 1 train schedule is read-only input; the crew solver does not modify trip times or rake assignments.

## 3.2 Crew Data

### `data/synthetic/drivers.csv` `[SYNTHETIC]`

**V1 schema (locked 2026-11-13):**

```text
driver_id
D001
D002
...
D055
```

**55 drivers, `D001`–`D055`, `driver_id` column only.**

Fields `qualification`, `availability`, `shift_preference`, `weekly_availability` were originally suggested for this file. **They are deferred to V2** — same honesty pattern as C5 (min rest). The V1 crew model uses `driver_id` only because C1–C4 need nothing else.

**Why 55, not 60?** KMRL has 60 SC/TO operators `[EXTERNAL — cited in handoff §1]`. The 55-driver roster is a synthetic test pool to exercise three daily-active pool sizes (45 / 50 / 55). It is **not** a claim that KMRL has 55 drivers.

Generated by `data/generate_drivers.py` (deterministic).

## 3.3 Crew Constraints (C1–C7)

**Locked for V1** (2026-11-13). Full spec in `docs/constraints-crew-v1.md`. Summary:

### Hard Constraints

| ID | Rule | Tag |
|---|---|---|
| C1 | No overlap — `arr(a) + 300 s ≤ dep(b)` for any two trips assigned to same driver | `[EXTERNAL]` |
| C2 | Max active duty — `last_arr − first_dep ≤ 28,800 s` (8 h) | `[EXTERNAL]` |
| C3 | Sign-on / sign-off — ≥ 900 s buffer each side | `[EXTERNAL]` |
| C4 | Full coverage — 250 / 250 trips assigned exactly once | `[EXTERNAL]` |

### Deferred

| ID | Rule | Status |
|---|---|---|
| C5 | Min rest between shifts — 12 h | **DEFERRED to V2.** No solver constraint, no validator check. Same honesty pattern as R8 (SKIPPED). |

### Soft Constraints

| ID | Rule | Weight | Tag |
|---|---|---:|---|
| C6 | Continuous driving ≤ 5 h. Break threshold = `MIN_TURNAROUND_SEC` (300 s) `[DERIVED from C1]`. | 10 | `[SYNTHETIC]` |
| C7 | Reserve ≥ 5 drivers unused. Penalize `active > pool_size − 5`. | 15 | `[SYNTHETIC]` |

**C6 implementation note:** implemented as a **state machine** in CP-SAT (6 vars per driver-trip pair, ~82,500 new vars total). An earlier O(n²) run-enumeration approach was rejected at ~3.4M vars. C6 is soft — the validator does not check it.

**No invented thresholds.** The C6 break threshold is the C1 turnaround reused, not a new number.

## 3.4 Driver Pool

Pool sizes tested: **45, 50, 55** `[SYNTHETIC]`.

**Why these sizes?** The 55-driver roster lets us measure feasibility under three daily-active assumptions. The 45-pool is tight; the 55-pool gives 10 spare on top of the 5-reserve. This is a controlled sensitivity sweep, not a claim about real KMRL shift patterns.

C7 (`reserve ≥ 5`) is checked at the validator level. C7 also drives the solver toward `active ≤ pool_size − 5`. At all three pools, the solver used exactly `pool_size − 5` active drivers.

## 3.5 Scheduling Approach

- **Solver:** OR-Tools CP-SAT
- **Inputs:** `data/processed/schedule.csv` (Phase 1 output, read-only) + `data/synthetic/drivers.csv`
- **Parameters:** `num_search_workers = 4`, `max_time_in_seconds = 300`, `random_seed = 42`
- **Non-determinism:** with `num_search_workers > 1`, results may vary between runs. Documented, not hidden.

## 3.6 Files

| File | Purpose |
|---|---|
| `data/generate_drivers.py` | Generates 55 synthetic drivers |
| `data/synthetic/drivers.csv` | 55 drivers, `driver_id` only |
| `solver/crew_config.py` | Constants, `POOL_SIZES = [45, 50, 55]`, all tagged |
| `solver/crew_models.py` | `CrewProblemData` loader |
| `solver/crew_constraints.py` | C1–C4 hard, C6 state-machine soft, C7 soft |
| `solver/crew_solve.py` | Loops over 45/50/55, writes both output files |
| `solver/crew_validator.py` | Independent C1–C4 + C7 checks per pool |
| `solver/crew_diag.py` | **Temporary** diagnostic (delete after Phase 3 sign-off) |
| `data/processed/crew_schedule.csv` | Output — 750 rows (250 trips × 3 pools) |
| `data/processed/crew_solution.json` | Output — keyed by `"45"` / `"50"` / `"55"` |
| `data/processed/crew_validation.json` | Output — per-pool checks + `overall` |

## 3.7 Phase 3 Results (2026-11-13)

| Pool | Status | Time | Active | Reserve | Objective | Gap |
|---|---|---:|---:|---:|---:|---:|
| 45 | **OPTIMAL** | 57.25 s | 40 | 5 | 0.0 | 0.0% |
| 50 | **OPTIMAL** | 58.80 s | 45 | 5 | 0.0 | 0.0% |
| 55 | **OPTIMAL** | 64.34 s | 50 | 5 | 0.0 | 0.0% |

**Validator (independent of solver):**
- pool=45: C1 PASS, C2 PASS, C3 PASS, C4 PASS, C7 PASS → **pool PASS**
- pool=50: C1 PASS, C2 PASS, C3 PASS, C4 PASS, C7 PASS → **pool PASS**
- pool=55: C1 PASS, C2 PASS, C3 PASS, C4 PASS, C7 PASS → **pool PASS**
- **Overall: PASS**

**Objective = 0 at all pools.** The solver found schedules with zero C6 and C7 penalty. This proves the penalty term is zero; it does not prove no driver neared the 5-h chain limit. Individual chain lengths are in `crew_solution.json`.

**Success criteria (handoff §8) — all met:**
1. ✅ ≥ 1 pool FEASIBLE with 250 trips — all three OPTIMAL
2. ✅ All hard constraints (C1–C4) PASS independent validation
3. ✅ Sensitivity table across pool sizes reported
4. ✅ Docs updated (this file, `checklist.md`, `meeting-log.md` Meeting 13, `project-status.md`)

## 3.8 How to Run Phase 3

```powershell
cd Z:\metropulse
.\venv\Scripts\Activate.ps1

# Generate drivers (one-time; deterministic)
python -m data.generate_drivers

# Solve all three pool sizes
python -m solver.crew_solve

# Validate outputs
python -m solver.crew_validator
```

**Expected wall clock:** ~3–5 minutes (60 s per pool, plus validation).

# Phase 4 — Explainability Report

**Status: Completed (2026-11-13)**

> **Revision note (2026-11-13):** Phase 4 was rebuilt as a **reporting layer only**. It reads the seven Phase 1/2/3 output files and generates one Markdown report and one machine-readable stats file. The original plan (per-trip assignment explanation, conflict analysis) was **not built** because CP-SAT returns a global solution (no per-trip reasons) and the solver returns OPTIMAL in every phase (no infeasibility to analyze). See §4.2 for the actual scope.

 ## 4.1 Objective

Generate a single human-readable report that documents the Phase 1/2/3 outputs, the constraint status at each phase, and the utilization statistics of the schedule — **without claiming per-trip solver reasoning**.

Phase 4 is a **reporting layer**, not an analyzer. Every number in the report traces to a source file in `data/processed/`; no numbers are hardcoded. CP-SAT returns a global solution, not per-assignment reasons, so explanations are framed as **context + consistency** ("R008 was assigned 14 trips, consistent with the balance objective"), not **reason** ("R008 was chosen because…").

The solver returns **OPTIMAL in every phase** (Phase 1 objective 4800 gap 0.0%; Phase 3 all pools objective 0.0 gap 0.0%). There is no infeasibility to analyze, so Phase 4 does **not** include a conflict analyzer.

## 4.2 Features (as built)

Phase 4 produced **one module** (`src/explainability/report_generator.py`) that generates **one report** (`data/processed/explainability_report.md`) with seven sections, plus **one stats file** (`data/processed/utilization_stats.json`).

**Report sections:**

1. **Executive Summary** — total trips scheduled, total rakes used, active drivers per pool, and a plain-English statement. Explicitly states that Phase 1 OPTIMAL is under the O6 rake-balance objective only; other objectives are declared but disabled in V1.
2. **Phase 1 Constraint Status (R1–R12)** — from `validation.json`; R2 removed, R8 SKIPPED, R9 vacuous.
3. **Phase 3 Constraint Status (C1–C7, per pool)** — from `crew_validation.json`; C5 deferred, C6 soft-objective.
4. **Rake Utilization** — from `schedule.csv`; `utilization_pct = busy_sec / span_sec × 100`, defined before the table.
5. **Driver Utilization** — from `crew_schedule.csv` + `crew_solution.json`; `total_depot_hours = (max sign_off − min sign_on)/3600` per driver per pool, documented as **total depot time including 900 s buffers**, not the C2 `duty` variable.
6. **Simulation Results** — from `simulation_kpis.json`; headline + 100-seed Monte Carlo; ±5 = 100% stated as a **model property** (300 s own-delay cap + inclusive ±5), not an operational guarantee.
7. **Sensitivity Analysis & Honest Limitations** — pool-size table (45/50/55) presented as-is; no recommendation drawn.

**What Phase 4 does NOT do:**

- ❌ **No conflict analyzer.** The solver returns OPTIMAL in every phase; there is no infeasibility to analyze. The original plan's "Conflict Explanation" feature is dropped because it would be ~300 lines of dead code.
- ❌ **No per-trip "why" explanations.** CP-SAT does not produce per-trip reasoning. The report frames assignments as "context + consistency," not "reason."
- ❌ **No hardcoded numbers.** Every value in the report traces to one of the seven source files, cited below each table.
- ❌ **No modularization.** One module, one report — not `rule_tracer.py`, `conflict_analyzer.py`, `trip_explainer.py`, `utilization_analyzer.py`, or `constraint_reporter.py`.

## 4.3 Deliverables (as built)

- ✅ `src/explainability/__init__.py` — one-line package docstring
- ✅ `src/explainability/report_generator.py` — ~27.7 KB, runs clean
- ✅ `data/processed/explainability_report.md` — seven sections, all sources cited
- ✅ `data/processed/utilization_stats.json` — machine-readable stats, derivation formulas restated for reproducibility

**Not built (and why):**

- ❌ **Trip-level assignment explanation** — CP-SAT produces no per-trip reasons. Explanations are "context + consistency."
- ❌ **Conflict analysis** — solver returns OPTIMAL in every phase; no infeasibility to analyze.
- ❌ **Standalone rake utilization report** — utilization is Section 4 of the main report, not a separate file.

**Verification:** every number in the report traced to `validation.json`, `solution.json`, `schedule.csv`, `simulation_kpis.json`, `crew_solution.json`, `crew_validation.json`, or `crew_schedule.csv`. Audit clean — no hardcoded numbers, no per-trip "why" claims.

# Phase 5 — Near-Real-Time Rescheduling
Status: Pending

## 5.1 Objective
Allow MetroPulse to regenerate or adjust schedules when operational conditions change.

Instead of rebuilding the entire schedule from scratch, the system should attempt to preserve existing assignments wherever possible.

## 5.2 Possible Inputs
Train delays.

Rake breakdowns.

Rake unavailability.

Temporary service disruptions.

Changes in operating conditions.

Updated trip requirements.

These inputs will initially be simulated unless verified operational data becomes available.

## 5.3 Rescheduling Approach
Use OR-Tools CP-SAT with the current schedule as the starting reference.

The rescheduling process should:

Load the existing schedule.

Receive an operational disruption.

Update affected trip and rake availability information.

Recalculate the affected scheduling decisions.

Generate a revised schedule.

Validate the revised schedule.

Compare the revised schedule with the original.

### Important Considerations
Preserve unaffected assignments where possible.

Avoid unnecessary changes to the existing schedule.

Respect all active hard constraints.

Minimize schedule disruption.

Record the reason for each rescheduling decision.

A warm-start or solution-hint approach can be explored to help the solver reuse the previous solution.

## 5.4 Files to Create
Possible implementation structure:

```text
solver/
├── reschedule.py
└── reschedule_validator.py

src/
└── disruption/
    ├── __init__.py
    └── disruption_handler.py
```
Confirm the final structure when implementing the phase.

### Deliverables
Disruption input handler.

Rescheduling model.

Previous-schedule comparison.

Revised schedule output.

Rescheduling validation.

Schedule change report.

# Phase 6 — Machine Learning Delay Prediction
Status: Optional / Pending

## 6.1 Objective
Predict possible train delays using historical operational data.

The prediction model can provide delay estimates to the scheduling system.

Important: This phase depends on obtaining suitable historical delay data. Synthetic data can be used for experimentation, but it must not be presented as real KMRL prediction performance.

## 6.2 Proposed Model
Algorithm: XGBoost Regressor

Possible Input Features
Hour of the day.

Day of the week.

Month.

Previous trip delay.

Previous trip running time.

Historical average delay.

Route direction.

Weather information, if reliable data is available.

Operational disruption indicators.

Target
Predicted delay in minutes or seconds.

The final target definition must be established from the available dataset.

## 6.3 Training Process
Collect and inspect historical delay data.

Clean and preprocess the data.

Create time-based features.

Create training and testing datasets.

Train the XGBoost model.

Evaluate prediction performance.

Generate delay predictions.

Pass predictions to the scheduling system.

Use a time-based train/test split to avoid data leakage.

## 6.4 Evaluation Metrics
MAE

RMSE

R²

Actual vs predicted delay chart.

## 6.5 Integration
The proposed integration flow is:

```text
Historical Data
      |
      v
Data Preprocessing
      |
      v
XGBoost Delay Prediction
      |
      v
Predicted Delay Values
      |
      v
OR-Tools CP-SAT
      |
      v
Updated Train Schedule
      |
      v
SimPy Validation
```
The predicted delays may be used as scheduling inputs or objective weights, depending on the final model design.

Deliverables
Historical delay dataset.

Data preprocessing pipeline.

XGBoost model.

Model evaluation report.

Prediction output.

Integration with the scheduling system.

# Phase 7 — Dashboard and Visualization
Status: Pending

## 7.1 Objective
Build a dashboard to display scheduling, simulation, crew allocation, and rescheduling results.

Technology: Streamlit

## 7.2 Dashboard Sections

### 1. Overview
Display:

Total trips.

Available rakes.

Scheduled trips.

Solver status.

Validation status.

Overall schedule utilization.

### 2. Train Schedule
Display:

Trip ID.

Direction.

Departure time.

Arrival time.

Assigned rake.

Trip status.

### 3. Rake Utilization
Display:

Rake-wise trip assignments.

Total operating time.

Idle time.

Turnaround time.

Utilization percentage.

### 4. Simulation Results
Display:

Delay distribution.

Total propagated delay.

On-time performance.

Maximum delay.

Headway violations.

Comparison of simulation experiments.

### 5. Crew Schedule
Display:

Driver assignments.

Duty hours.

Rest periods.

Weekly working days.

Driver utilization.

### 6. Rescheduling
Display:

Original schedule.

Disruption details.

Updated schedule.

Changed assignments.

Reason for changes.

### 7. Constraint Validation
Display:

Constraint name.

Description.

PASS / FAIL / SKIPPED status.

Validation details.

## 7.3 Deliverables
Streamlit dashboard.

Schedule visualization.

Rake utilization charts.

Simulation KPI charts.

Crew allocation view.

Rescheduling comparison.

Constraint validation report.

### 3. Critical Development Order
The main implementation sequence is:

```text
Phase 0: Project Setup
        |
        v
Phase 1: CP-SAT Train Scheduling
        |
        v
Phase 2: SimPy Operational Simulation
        |
        v
Phase 3: Crew Scheduling
        |
        v
Phase 4: Explainability
        |
        v
Phase 5: Near-Real-Time Rescheduling
        |
        v
Phase 7: Dashboard
```
Phase 6 (Machine Learning) is optional and can be developed separately once suitable historical delay data is available.

The dashboard can also be developed incrementally alongside the other phases.

#### 4. Final Expected Project Structure
The following is the intended structure. Existing files should be retained, and new files should be added as their phases are implemented.

```text
MetroPulse/
│
├── data/
│   ├── raw/
│   ├── synthetic/
│   ├── processed/
│   ├── extract_gtfs_trips.py
│   ├── merge_trips.py
│   ├── verify_gtfs_trips.py
│   ├── extract_gtfs_hourly.py     # legacy; reconciliation only
│   ├── generate_synthetic_v2.py
|   |── generate_drivers.py
│   └── hourly_service.csv
│
├── solver/
│   ├── config.py
│   ├── models.py
│   ├── constraints.py
│   ├── solve.py
│   ├── validator.py
│   ├── crew_config.py
│   ├── crew_models.py
│   ├── crew_constraints.py
│   ├── crew_solve.py
│   ├── crew_validator.py
│   ├── reschedule.py
│   └── reschedule_validator.py
│
├── src/
│   ├── simulation/
│   │   ├── __init__.py
│   │   ├── schedule_loader.py
│   │   ├── reference.py
│   │   ├── simpy_runner.py
│   │   ├── kpis.py
│   │   ├── experiments.py
│   │   ├── preflight.py
│   │   └── check_terminals.py
│   │
│   └── disruption/
│       ├── __init__.py
│       └── disruption_handler.py
│
├── dashboard/
│   └── app.py
│
├── docs/
│   ├── phases.md
│   ├── project-status.md
│   ├── meeting-log.md
│   ├── data-provenance.md
│   └── constraints-v2.md
│
├── tests/
│   ├── test_reference.py
│   ├── test_schedule_loader.py
│   ├── test_simpy_matches_reference.py
│   └── test_kpis.py
│
├── requirements.txt
├── .gitignore
└── README.md
```
5. Estimated Timeline
These are planning estimates, not confirmed completion dates.

Phase	Estimated Duration
Phase 0	Completed
Phase 1	Completed
Phase 2	Completed
Phase 3	Completed (2026-11-13; ~5 hours across sessions)
Phase 4 Completed (2026-11-13; ~4 hours across sessions)
Phase 5	1–2 weeks
Phase 6	Depends on historical data availability
Phase 7	1–2 weeks
MVP target: Phase 1 + Phase 2, completed 2026-11-12.

The complete implementation may take approximately 2 months, depending on testing, data availability, and integration complexity.

6. Current Project Status
See docs/project-status.md for the current project state.

phases.md is a phase-planning document — it describes what each phase is and in what order. Current state (last updated, current results, known issues, next task) is kept in project-status.md to avoid duplication.

Last phase completed: **Phase 4 (Explainability Report), 2026-11-13.** One reporting module (`src/explainability/report_generator.py`) reads Phase 1/2/3 outputs and generates `data/processed/explainability_report.md` (7 sections) + `data/processed/utilization_stats.json`. Audit clean — every number traces to a source file, no per-trip reasoning, no conflict analyzer. Phase 3 (Crew Scheduling): all three pool sizes OPTIMAL; independent validator PASS at all pools (C1–C4 + C7). Phase 1 (O6 rake balance active): OPTIMAL, objective 4800, gap 0.0%, 11.77 s. Phase 2 (SimPy): 59 tests passing, 100-seed Monte Carlo complete.

Next: Phase 5 — Near-Real-Time Rescheduling.

---

**End of Phase Plan — Version 2.5**