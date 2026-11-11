# MetroPulse — Complete Phase Plan

**Project:** AI-Driven Train Induction Planning and Scheduling System for Kochi Metro Rail Limited (KMRL)  
**Scheduling Engine:** OR-Tools CP-SAT  
**Simulation Engine:** SimPy  
**Version:** 2.3  
**Last Updated:** 11 November 2026

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
| Phase 1 | Train Scheduling using CP-SAT | Completed |
| Phase 2 | Operational Simulation using SimPy | Completed |
| Phase 3 | Crew Scheduling | Next |
| Phase 4 | Explainability and Constraint Analysis | Pending |
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
| `solver/solve.py` | Executes the CP-SAT solver (feasibility probe, no objective) |
| `solver/validator.py` | Independently validates the generated schedule |

The current validator checks: **R1, R3, R4, R5, R6, R7, R10, R11, R12** (9 PASS) + **R8 SKIPPED** (no stabling in V1). That is **9 PASS + 1 SKIPPED**.

`R2` is **not applicable** — trip departure times are fixed by GTFS, so headway is a timetable property, not a scheduling decision. `R9` is **vacuous** — `maintenance.csv` is empty in V1.

**Findings from the rebuild:**

- `[FINDING]` `add_obj6_rake_balance` makes the model **INFEASIBLE** when `build_objective` is not called. The `o6` call must be commented out in feasibility-probe mode. See `constraints-v2.1` §6/§8.
- `[FINDING]` R6 must compute `gap_ab` and `gap_ba` **per order**. The earlier one-gap-per-pair rule allowed cross-terminal switches (ALVA↔MUTT, TPHT↔MUTT) with gaps between 5 and 15 min. See `constraints-v2.1` §5 R6.

## 1.5 Phase 1 Results

| Metric | Result |
|---|---:|
| Trips scheduled | **250** (232 full + 18 partial) |
| Configured service rakes | 18 (9 ALVA / 7 TPHT / 2 MUTTOM) |
| Solver status | **OPTIMAL** |
| Solver wall-clock time | **28.73 s** |
| Solver time limit | 300 s |
| Objective value | 0.0 (feasibility probe — objective disabled) |
| Optimality gap | 0.0% (no objective; not a proven bound on a cost) |
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
- The objective is disabled because of the `add_obj6` bug. V1 is a feasibility probe.
- "All 18 service rakes used" is **confirmed** from `schedule_250_trips.csv`.

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

**Status: Completed**

## 2.1 Objective

Simulate the Phase 1 schedule under different delay conditions.

The purpose is to understand how delays affect:

- Train departure times.
- Train arrival times.
- Rake availability.
- Subsequent trips assigned to the same rake.
- Overall timetable reliability.

The simulation will use the schedule generated by CP-SAT.

## 2.2 Simulation Design

### Input

- `schedule.csv`
- Rake assignments from Phase 1.
- Running time: 50 minutes.
- Turnaround time: 5 minutes.

The 50-minute running time is the integer value used by the solver, rounded from the GTFS-derived median of 50.47 minutes.

### Delay Distribution

**Synthetic assumption:**

```python
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

actual_arr[i] = actual_dep[i] + 50_minutes

propagated_delay[i] = max(
    0,
    propagated_dep[i] - early_dep[i]
)
```

Where:

- `i` = Current trip.
- `p` = Immediately preceding trip assigned to the same rake, ordered by scheduled departure.
- `actual_arr[p]` = Actual arrival time of the preceding trip.
- 5 minutes = Synthetic turnaround time.

For the first trip assigned to a rake:

```python
actual_dep[i] = early_dep[i]
propagated_delay[i] = 0
```

There is no preceding trip for the first trip assigned to a rake.

## 2.4 Simulation KPIs

### Primary KPIs

| KPI | Description |
|---|---|
| Total propagated delay | Sum of additional delay caused by previous trips |
| Propagation percentage | Percentage of eligible trips affected by propagated delay |
| On-time performance | Percentage of trips departing within the defined on-time tolerance |

For propagation percentage:

```python
propagation_percentage = (
    trips_with_propagated_delay /
    eligible_trips
) * 100
```

Eligible trips exclude the first trip assigned to each rake because those trips have no preceding trip.

### Supplementary KPIs

- On-time performance within ±5 minutes.
- On-time performance within ±3 minutes.
- On-time performance within ±1 minute.
- Maximum departure delay.
- Total trips completed.
- Headway violations.

**Proposed on-time definition:** A trip is on time if its actual departure is within ±5 minutes of its scheduled departure.

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

```powershell
pip install simpy
```

### Run

```
python -m src.simulation.experiments
```

### Deliverables

- SimPy simulation engine.
- Delay propagation model.
- KPI calculation module.
- Simulation results for all four experiments.
- Comparison of timetable performance under different delay conditions.

## 2.7 Phase 2 Results

### Files delivered

| File | Purpose |
|---|---|
| `src/simulation/__init__.py` | Package marker |
| `src/simulation/schedule_loader.py` | Strict CSV loader with parsing guards and count cross-check |
| `src/simulation/reference.py` | Closed-form recurrence; correctness baseline for SimPy |
| `src/simulation/simpy_runner.py` | SimPy per-rake process |
| `src/simulation/kpis.py` | Pure KPI functions (no SimPy import) |
| `src/simulation/experiments.py` | E1–E4 and Monte Carlo runner |
| `src/simulation/preflight.py` | Read-only continuity / slack / headway analysis |
| `src/simulation/check_terminals.py` | Read-only terminal check helper |

### Tests

| File | Count |
|---|---:|
| `tests/test_reference.py` | 8 |
| `tests/test_schedule_loader.py` | 24 |
| `tests/test_simpy_matches_reference.py` | 9 |
| `tests/test_kpis.py` | 14 |
| **Total** | **55** |

All 55 pass. The parity test asserts that SimPy output equals the closed-form reference bit-for-bit across all four std values.

### Headline results (seed 42)

| Experiment | std (s) | On-time ±5 | Propagation % | Total propagated (min) | Headway violations (actual) |
|---|---:|---:|---:|---:|---:|
| E1 | 0 | 100.00% | 0.00% | 0.0 | 0 |
| E2 | 60 | 100.00% | 3.88% | 2.4 | 12 |
| E3 | 120 | 100.00% | 7.76% | 19.3 | 21 |
| E4 | 300 | 100.00% | 11.64% | 63.2 | 30 |

### 100-seed Monte Carlo aggregate

| Experiment | On-time ±5 (mean) | On-time ±3 (mean) | On-time ±1 (mean) | Propagation % (mean; p5–p95) |
|---|---:|---:|---:|---:|
| E1 | 100.00% | 100.00% | 100.00% | 0.00% (0.00–0.00) |
| E2 | 100.00% | 100.00% | 95.26% | 6.34% (4.31–8.62) |
| E3 | 100.00% | 96.15% | 76.59% | 9.81% (6.90–12.07) |
| E4 | 100.00% | 71.57% | 55.81% | 13.12% (10.34–15.95) |

Scheduled same-direction headway violations = **0** at every std (R2a holds across 100 seeds). Actual-gap violations rise with std as departures bunch under delay.

### Key findings

1. **±5 on-time is structurally protected under this model.** Own delay is capped at 300 s (= 5 min inclusive), and the measured slack distribution keeps cumulative delay below the cap. **This is a model property, not an operational guarantee.** Scenarios with a higher delay cap or tighter slack would show ±5 degradation. Do not report "KMRL is 100% reliable at ±5."
2. **±3 and ±1 are where delay impact appears.** At E4: 71.57% and 55.81% on-time respectively. The headline seed sits slightly below the 100-seed mean — treat the mean as the expected value.
3. **Propagation % rises non-linearly with std** (0 → 6.3 → 9.8 → 13.1 mean). Total propagated delay rises faster (0 → 8.6 → 31.1 → 81.4 min mean) because more trips break slack at high std.
4. **Scheduled headway is clean; actual headway degrades.** R2a holds in the schedule (0 scheduled violations). Actual-gap violations grow from 0 (E1) to 33.3 mean (E4) as delays reorder departures.
5. **Max single propagated delay saturates at 300 s at E4** (the own-delay cap). Some trips carry the full cap.

### Known limitations

- **Terminal continuity is not verifiable from Phase 1 outputs.** The schedule stores internal trip IDs (`Txxxx`) with no mapping back to GTFS trip IDs. 127 of 232 pairs show non-alternating UP/DOWN direction. Cannot distinguish real modeling gap from labeling artifact. Phase 2 models delay flow, not physical route movement. Deadhead is not modeled (R11 not configured). Deferred to Phase 4/5 where terminal awareness matters.
- **Delay model is `[SYNTHETIC]`.** All numbers describe model behaviour under a synthetic delay assumption, not real KMRL performance.
- **R9 and R11 remain outside Phase 1 validator results.** Unchanged by Phase 2.

---

# Phase 3 — Crew Scheduling

**Status: Pending**

## 3.1 Objective

Assign drivers to the trips generated in Phase 1 while satisfying crew duty and rest requirements.

The Phase 1 train schedule will remain fixed initially.

## 3.2 Crew Data

Create synthetic driver information.

```text
data/
└── synthetic/
    └── drivers.csv
```

Suggested fields:

- `driver_id`
- `qualification`
- `availability`
- `shift_preference`
- `weekly_availability`

All synthetic driver information must be clearly identified as assumed data.

## 3.3 Crew Constraints

| Constraint | Description |
|---|---|
| C1 | Driver must be qualified for the Blue Line |
| C2 | Maximum duty time of 8 hours per day |
| C3 | Minimum rest period of 12 hours |
| C4 | Maximum continuous driving time of 4 hours |
| C5 | Maximum 6 consecutive working days before weekly rest |
| C6 | A driver cannot be assigned overlapping trips |

These are initial model constraints. They must be checked against verified KMRL crew rules before being presented as official operating rules.

## 3.4 Driver Pool

An initial estimate of approximately 13 drivers can be obtained by dividing 250 trips by an assumed 20 trips per driver.

However, 20 trips per driver is only a planning assumption. It does not establish the minimum number of drivers required.

Use a synthetic driver pool of approximately 20–30 drivers for initial experiments.

Actual feasibility depends on:

- Trip timing.
- Duty duration.
- Rest requirements.
- Driver availability.
- Trip overlap.
- Shift allocation.

## 3.5 Scheduling Approach

Use OR-Tools CP-SAT to assign drivers to the fixed train schedule.

The model should:

1. Load the Phase 1 schedule.
2. Load synthetic driver information.
3. Create driver assignment variables.
4. Apply crew constraints.
5. Solve the assignment problem.
6. Validate the generated assignments.

## 3.6 Files to Create

```text
solver/
├── crew_models.py
├── crew_constraints.py
├── crew_solve.py
└── crew_validator.py

data/
└── synthetic/
    └── drivers.csv
```

### Deliverables

- Synthetic driver dataset.
- Crew scheduling model.
- Crew constraint implementation.
- Driver assignment output.
- Independent crew schedule validator.
- Driver utilization report.

---

# Phase 4 — Explainability and Constraint Analysis

**Status: Pending**

## 4.1 Objective

Make the scheduling results understandable and explain why the solver generated a particular schedule.

The system should provide useful explanations rather than only showing the final timetable.

## 4.2 Features

### Constraint Status

Show the status of each implemented constraint.

Example:

| Constraint | Description | Status |
|---|---|---|
| R1 | Service coverage | PASS |
| R2a | Minimum headway | PASS |
| R3 | Operating window | PASS |
| R4 | Fleet availability | PASS |
| R5 | Rake non-overlap | PASS |
| R6 | Turnaround time | PASS |
| R7 | Running time | PASS |
| R8 | Depot capacity | SKIPPED |

The displayed results must come from the actual validator output. Do not display unvalidated constraints as PASS.

### Scheduling Explanation

For each trip, show:

- Assigned rake.
- Scheduled departure.
- Scheduled arrival.
- Previous trip assigned to the same rake.
- Available turnaround time.
- Reason for the assignment, where supported by the solver data.

### Conflict Explanation

When the solver cannot find a feasible solution, identify:

- Conflicting constraints, where diagnosable.
- Trips involved in the conflict.
- Rake availability issues.
- Timing conflicts.
- Resource shortages.

Use solver diagnostics and controlled relaxation tests. Do not claim that a particular constraint caused infeasibility unless the analysis supports it.

## 4.3 Deliverables

- Constraint status report.
- Trip-level assignment explanation.
- Rake utilization report.
- Conflict analysis.
- Human-readable scheduling summary.

---

# Phase 5 — Near-Real-Time Rescheduling

**Status: Pending**

## 5.1 Objective

Allow MetroPulse to regenerate or adjust schedules when operational conditions change.

Instead of rebuilding the entire schedule from scratch, the system should attempt to preserve existing assignments wherever possible.

## 5.2 Possible Inputs

- Train delays.
- Rake breakdowns.
- Rake unavailability.
- Temporary service disruptions.
- Changes in operating conditions.
- Updated trip requirements.

These inputs will initially be simulated unless verified operational data becomes available.

## 5.3 Rescheduling Approach

Use OR-Tools CP-SAT with the current schedule as the starting reference.

The rescheduling process should:

1. Load the existing schedule.
2. Receive an operational disruption.
3. Update affected trip and rake availability information.
4. Recalculate the affected scheduling decisions.
5. Generate a revised schedule.
6. Validate the revised schedule.
7. Compare the revised schedule with the original.

### Important Considerations

- Preserve unaffected assignments where possible.
- Avoid unnecessary changes to the existing schedule.
- Respect all active hard constraints.
- Minimize schedule disruption.
- Record the reason for each rescheduling decision.

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

- Disruption input handler.
- Rescheduling model.
- Previous-schedule comparison.
- Revised schedule output.
- Rescheduling validation.
- Schedule change report.

---

# Phase 6 — Machine Learning Delay Prediction

**Status: Optional / Pending**

## 6.1 Objective

Predict possible train delays using historical operational data.

The prediction model can provide delay estimates to the scheduling system.

**Important:** This phase depends on obtaining suitable historical delay data. Synthetic data can be used for experimentation, but it must not be presented as real KMRL prediction performance.

## 6.2 Proposed Model

**Algorithm:** XGBoost Regressor

### Possible Input Features

- Hour of the day.
- Day of the week.
- Month.
- Previous trip delay.
- Previous trip running time.
- Historical average delay.
- Route direction.
- Weather information, if reliable data is available.
- Operational disruption indicators.

### Target

Predicted delay in minutes or seconds.

The final target definition must be established from the available dataset.

## 6.3 Training Process

1. Collect and inspect historical delay data.
2. Clean and preprocess the data.
3. Create time-based features.
4. Create training and testing datasets.
5. Train the XGBoost model.
6. Evaluate prediction performance.
7. Generate delay predictions.
8. Pass predictions to the scheduling system.

Use a time-based train/test split to avoid data leakage.

## 6.4 Evaluation Metrics

- MAE
- RMSE
- R²
- Actual vs predicted delay chart.

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

### Deliverables

- Historical delay dataset.
- Data preprocessing pipeline.
- XGBoost model.
- Model evaluation report.
- Prediction output.
- Integration with the scheduling system.

---

# Phase 7 — Dashboard and Visualization

**Status: Pending**

## 7.1 Objective

Build a dashboard to display scheduling, simulation, crew allocation, and rescheduling results.

**Technology:** Streamlit

## 7.2 Dashboard Sections

### 1. Overview

Display:

- Total trips.
- Available rakes.
- Scheduled trips.
- Solver status.
- Validation status.
- Overall schedule utilization.

### 2. Train Schedule

Display:

- Trip ID.
- Direction.
- Departure time.
- Arrival time.
- Assigned rake.
- Trip status.

### 3. Rake Utilization

Display:

- Rake-wise trip assignments.
- Total operating time.
- Idle time.
- Turnaround time.
- Utilization percentage.

### 4. Simulation Results

Display:

- Delay distribution.
- Total propagated delay.
- On-time performance.
- Maximum delay.
- Headway violations.
- Comparison of simulation experiments.

### 5. Crew Schedule

Display:

- Driver assignments.
- Duty hours.
- Rest periods.
- Weekly working days.
- Driver utilization.

### 6. Rescheduling

Display:

- Original schedule.
- Disruption details.
- Updated schedule.
- Changed assignments.
- Reason for changes.

### 7. Constraint Validation

Display:

- Constraint name.
- Description.
- PASS / FAIL / SKIPPED status.
- Validation details.

## 7.3 Deliverables

- Streamlit dashboard.
- Schedule visualization.
- Rake utilization charts.
- Simulation KPI charts.
- Crew allocation view.
- Rescheduling comparison.
- Constraint validation report.

---

# 3. Critical Development Order

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

---

# 4. Final Expected Project Structure

The following is the intended structure. Existing files should be retained, and new files should be added as their phases are implemented.

```text
MetroPulse/
│
├── data/
│   ├── raw/
│   ├── synthetic/
│   ├── processed/
│   ├── extract_gtfs_hourly.py
│   ├── generate_synthetic_v2.py
│   └── hourly_service.csv
│
├── solver/
│   ├── config.py
│   ├── models.py
│   ├── constraints.py
│   ├── solve.py
│   ├── validator.py
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

---

# 5. Estimated Timeline

These are planning estimates, not confirmed completion dates.

| Phase | Estimated Duration |
|---|---|
| Phase 0 | Completed |
| Phase 1 | Completed |
| Phase 2 | 1–2 weeks |
| Phase 3 | 1–2 weeks |
| Phase 4 | 3–5 days |
| Phase 5 | 1–2 weeks |
| Phase 6 | Depends on historical data availability |
| Phase 7 | 1–2 weeks |

**MVP target:** Phase 1 + Phase 2, approximately 3 weeks of development.

The complete implementation may take approximately 2 months, depending on testing, data availability, and integration complexity.

---

# 6. Current Project Status

As of 11 November 2026:

### Completed

- Project setup.
- GTFS ingestion and analysis.
- GTFS validation.
- Data provenance review.
- Synthetic rake data generation.
- CP-SAT train scheduling.
- Rake allocation.
- Independent schedule validation.
- Phase 1 documentation.
- SimPy operational simulation (Phase 2).
- Simulation KPIs, Monte Carlo, and outputs.
- 55 tests passing across four test files.

### Phase 1 Result (unchanged)

- 250 selected trips.
- 18 configured service rakes (all 18 used — confirmed from `schedule.csv`).
- 50.47-minute GTFS median running time.
- 50-minute integer running time used by solver.
- 5-minute synthetic turnaround.
- Solver status: FEASIBLE.
- Solver wall-clock time: approximately 306 seconds.
- Objective value: 1,102,800.
- Optimality gap: 93.40%.
- Validator: 9 PASS + 1 SKIPPED.
- Overall validator status: PASS.
- R8 skipped; R9 and R11 not included in current validation results.

### Phase 2 Result

- 250 trips, 18 rakes, 232 eligible trips.
- 4 experiments (std 0/60/120/300 s) + 100-seed Monte Carlo per std.
- Headline (seed 42): ±5 on-time 100% throughout; propagation 0 → 3.88 → 7.76 → 11.64%.
- 100-seed mean at E4: propagation 13.12% (p5–p95: 10.3–15.9%); ±3 on-time 71.57%; ±1 on-time 55.81%.
- Scheduled headway violations 0 at all stds; actual-gap violations rise 0 → 33.3 mean.
- ±5 on-time structurally protected under the model — model property, not operational guarantee.
- Terminal continuity not verifiable from Phase 1 outputs; documented limitation.

### Next Immediate Task

Start **Phase 3 — Crew Scheduling**.

The first step is to design the synthetic driver dataset and the C1–C6 crew constraints against the fixed Phase 1 schedule.

---

**End of Phase Plan — Version 2.3**