# MetroPulse — Complete Phase Plan

**Project:** AI-Driven Train Induction Planning and Scheduling System for Kochi Metro Rail Limited (KMRL)  
**Scheduling Engine:** OR-Tools CP-SAT  
**Simulation Engine:** SimPy  
**Version:** 2.2  
**Last Updated:** 08 November 2026

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
| Phase 2 | Operational Simulation using SimPy | Next |
| Phase 3 | Crew Scheduling | Pending |
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

**Status: Completed**

## 1.1 Objective

Generate a feasible daily train schedule using the KMRL GTFS timetable and available rake information.

The scheduler assigns trips to available rakes while satisfying the configured operational constraints.

## 1.2 Data Configuration

### GTFS Data

| Parameter | Value |
|---|---:|
| GTFS feed validity | 12 Aug 2024 – 31 Dec 2025 |
| Weekday trips in GTFS | 255 |
| Trips selected for the model | 250 |
| Operating window | 06:00–23:00 |
| Hourly buckets | 17 |
| Median one-way running time | 50.47 minutes |
| Integer running time used by solver | 50 minutes |
| Route length | 28.144 km |

Five GTFS trips were excluded because their departures fall outside the selected 06:00–23:00 model window.

The 250 trips represent the selected model trips, not the total number of weekday trips in GTFS.

### Fleet Data

| Parameter | Value |
|---|---:|
| Total rakes | 25 |
| Service rakes | 18 |
| Maintenance rakes | 7 |
| Separate standby rakes | 0 |
| Turnaround time | 5 minutes |

The fleet information is based on a 2026 news report.

The KMRL Annual Report 2024–25 reports 15 operating trains. This difference in reporting periods must be acknowledged when describing the fleet configuration.

### Synthetic Assumptions

| Parameter | Value |
|---|---:|
| Turnaround time | 5 minutes |
| Maintenance threshold | 1,000,000 km |
| Info Park-2 capacity | 2 rakes |
| Initial rake mileage | 20,000–200,000 km |

These values are synthetic assumptions because verified operational data is unavailable.

## 1.3 Data Files

| File | Purpose |
|---|---|
| `data/raw/` | Original GTFS files |
| `data/hourly_service.csv` | Extracted hourly service information |
| `data/synthetic/rakes.csv` | Synthetic rake information |
| `data/synthetic/terminals.csv` | Terminal configuration |
| `data/synthetic/maintenance.csv` | Maintenance information |
| `data/synthetic/depot.csv` | Depot capacity information |
| `data/extract_gtfs_hourly.py` | Extracts hourly GTFS information |
| `data/generate_synthetic_v2.py` | Generates synthetic operational data |

Confirm synthetic file paths against the actual loader configuration before running the project.

## 1.4 Solver Implementation

| File | Responsibility |
|---|---|
| `solver/config.py` | Solver configuration |
| `solver/models.py` | Loads and prepares problem data |
| `solver/constraints.py` | Defines scheduling constraints and objectives |
| `solver/solve.py` | Executes the CP-SAT solver |
| `solver/validator.py` | Independently validates the generated schedule |

The solver uses the R1–R12 constraint framework.

The current validator checks R1, R2a, R3, R4, R5, R6, R7, R10, and R12 (9 PASS).

R8 is present in the validator but SKIPPED because V1 does not contain stabling assignments. R9 and R11 are not included in the current validation results.



## 1.5 Phase 1 Results

| Metric | Result |
|---|---:|
| Selected trips | 250 |
| Configured service rakes | 18 |
| Solver status | FEASIBLE |
| Solver wall-clock time | Approximately 306 seconds |
| Solver time limit | 300 seconds |
| Objective value | 1,102,800 |
| Optimality gap | 93.40% |
| Consecutive same-rake trip pairs checked | 232 |
| Minimum turnaround requirement | 5 minutes |

All 232 checked consecutive same-rake trip pairs satisfy the 5-minute turnaround requirement.

### Validator Results

| Result | Count |
|---|---:|
| PASS | 9 |
| SKIPPED | 1 |
| FAIL | 0 |

**Overall validator status: PASS**

Important limitations:

- R8 is skipped because stabling assignments are not implemented in V1.
- R9 and R11 are not included in the current validation results.
- FEASIBLE does not mean OPTIMAL.
- Eighteen is the configured number of service rakes. Do not claim all 18 were used unless confirmed from the generated schedule.

## 1.6 How to Run Phase 1

```powershell
cd Z:\metropulse

.\venv\Scripts\Activate.ps1

# Regenerate hourly service data only when required
python data\extract_gtfs_hourly.py

# Generate synthetic operational data
python data\generate_synthetic_v2.py

# Run the scheduler
python -m solver.solve

# Validate the generated schedule
python -m solver.validator
```

The GTFS extraction step requires the original GTFS files in `data/raw/`. Skip it if `data/hourly_service.csv` is already generated and up to date.

### Expected Outputs

- `schedule.csv`
- `solution.json`
- `validation.json`

---

# Phase 2 — Operational Simulation using SimPy

**Status: Next**

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
    ├── simpy_runner.py
    └── kpis.py
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

```powershell
python -m src.simulation.simpy_runner
```

### Deliverables

- SimPy simulation engine.
- Delay propagation model.
- KPI calculation module.
- Simulation results for all four experiments.
- Comparison of timetable performance under different delay conditions.

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
│   │   ├── simpy_runner.py
│   │   └── kpis.py
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

As of 08 November 2026:

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

### Current Phase 1 Result

- 250 selected trips.
- 18 configured service rakes.
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

### Next Immediate Task

Start **Phase 2 — Operational Simulation using SimPy**.

The first step is to inspect the existing project structure, generated schedule, rake assignments, and output schema before writing simulation code.

---

# 7. Handoff Prompt for the Next Development Session

Use the following prompt when continuing development:

```text
We are continuing development of MetroPulse, an AI-driven train
induction planning and scheduling system for Kochi Metro Rail Limited.

Current project status:

PHASE 1 — COMPLETED

- Static KMRL GTFS 2024–25 is used.
- The GTFS contains 255 weekday trips.
- 250 trips are selected within the 06:00–23:00 model window.
- Median one-way running time is 50.47 minutes.
- The CP-SAT model uses 50 minutes as its integer running time.
- Route length is 28.144 km from the KMRL Annual Report 2024–25.
- Fleet configuration: 25 total rakes, 18 service and 7 maintenance.
- Turnaround time: 5 minutes (synthetic assumption).
- Solver status: FEASIBLE.
- Solver wall-clock time: approximately 306 seconds.
- Solver time limit: 300 seconds.
- Objective value: 1,102,800.
- Optimality gap: 93.40%.
- 232 consecutive same-rake trip pairs were checked.
- All 232 satisfy the 5-minute turnaround requirement.
- Validator: 9 PASS + 1 SKIPPED.
- Overall validator status: PASS.
- R8 is skipped because V1 has no stabling assignments.
- R9 and R11 are not included in the current validation results.

IMPORTANT DATA RULES:

- Do not reintroduce the old DPR-based assumptions.
- Distinguish verified data from synthetic assumptions.
- The GTFS feed is static 2024–25 data, not a live 2026 timetable.
- Do not claim all 18 configured service rakes were used unless
  confirmed from the generated schedule.
- Do not describe the validator as 10/10 PASS.
- Do not claim R9 and R11 passed validation.

DOCUMENTATION TO READ:

1. docs/constraints-v2.md
2. docs/project-status.md
3. docs/data-provenance.md
4. docs/meeting-log.md
5. docs/phases.md

NEXT TASK:

Start Phase 2 — Operational Simulation using SimPy.

Before writing code:

1. Inspect the existing project folder structure.
2. Inspect the Phase 1 schedule output.
3. Inspect the rake assignment format.
4. Check the existing Python modules and dependencies.
5. Confirm how trip times and rake assignments are represented.
6. Identify any missing information required by the simulation.

Then design the simulation implementation.

The simulation must:

- Read the CP-SAT-generated schedule.
- Replay trips assigned to each rake.
- Model stochastic departure delays.
- Model delay propagation between consecutive trips assigned
  to the same rake.
- Respect the 5-minute synthetic turnaround time.
- Use the 50-minute solver running time.
- Calculate the planned simulation KPIs.
- Run experiments with standard deviations of 0, 60, 120,
  and 300 seconds.
- Save simulation results to the planned output files.

Do not assume file paths or column names without inspecting
the existing project.

Review the implementation plan before making changes.
Ask for clarification if essential information is missing.
```

---

**End of Phase Plan — Version 2.2**