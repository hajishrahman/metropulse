

# MetroPulse

AI-driven train scheduling, crew allocation, operational simulation, explainability, and disruption response platform for the Kochi Metro Rail Limited (KMRL) network.

**Project Status:** Complete.

**Core Stack:** Python · OR-Tools CP-SAT · SimPy · NiceGUI · Plotly · Tailwind CSS

**Baseline:** 255 weekday trips · 18 service rakes · 25 total rakes.

---

## Project Structure

```text
metropulse/
├── data/
│   ├── raw/                         # Original KMRL GTFS feed (Git-ignored)
│   ├── processed/                   # Generated outputs from Phases 1–5
│   │   ├── schedule.csv
│   │   ├── solution.json
│   │   ├── validation.json
│   │   ├── simulation_kpis.json
│   │   ├── simulation_timeline.csv
│   │   ├── crew_schedule.csv
│   │   ├── crew_solution.json
│   │   ├── crew_validation.json
│   │   ├── explainability_report.md
│   │   ├── utilization_stats.json
│   │   ├── reschedule_scenario_a.csv
│   │   ├── reschedule_scenario_b.csv
│   │   ├── reschedule_scenario_c.csv
│   │   ├── reschedule_scenario_d.csv
│   │   ├── reschedule_scenario_e.csv
│   │   ├── reschedule_diff.json
│   │   ├── reschedule_summary.md
│   │   └── sensitivity_analysis.json
│   ├── synthetic/                    # Synthetic fleet and driver data
│   └── disruptions/                 # Phase 5 disruption scenarios
├── solver/                          # CP-SAT scheduling and crew engines
├── src/
│   ├── simulation/                  # Phase 2 SimPy simulation
│   └── explainability/              # Phase 4 report generator
├── frontend/
│   ├── main.py
│   ├── pages/
│   ├── components/
│   ├── data/
│   ├── assets/
│   └── tests/
├── docs/                            # Specifications and project documentation
├── tests/                           # Backend tests
├── probes/                          # Read-only diagnostic probes
└── requirements.txt
```

---

## Setup

### 1. Clone and enter the repository

```powershell
git clone <your-repo-url>
cd metropulse
```

### 2. Create and activate a virtual environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

If activation is blocked, run once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Load the GTFS data

The raw GTFS `.txt` files are not tracked in Git. Copy them into `data/raw/`:

```powershell
Copy-Item "Z:\path\to\KMRLGTFS\*.txt" -Destination data\raw\
```

Expected files (11):

```text
agency.txt          fare_rules.txt      stops.txt
calendar.txt        feed_info.txt       translations.txt
fare_attributes.txt routes.txt          trips.txt
shapes.txt          stop_times.txt
```

See `data/raw/README.md` for source details.

---

# Phase 1 — Train Scheduling

Assigns every KMRL weekday trip to a rake using OR-Tools CP-SAT, subject to operational constraints.

### What Phase 1 produces

- **255 trips scheduled:** 232 full-route + 23 partial.
- **18 service rakes** assigned; 7 maintenance rakes excluded.
- **Solver status:** OPTIMAL.
- **Objective:** 900.0 (O6 rake-balance, Σdev = 3).
- **Gap:** 0.0% (proven optimal).
- **Validator:** 10 checks, all PASS.

### What Phase 1 enforces

| Rule | Description |
|---|---|
| R1 | Every trip assigned to exactly one service rake |
| R2 | Departures within `[04:40, 24:00)` |
| R3 | Only service rakes used (no maintenance rakes) |
| R4 | No overlapping trips on the same rake |
| R5 | Per-pair turnaround and deadhead (5 / 8 / 15 min) |
| R6 | Per-trip GTFS duration preserved |
| R7 | No trip assigned to a rake inside a maintenance window |
| R8 | No rake over 1,000,000 km used |
| R9 | First-trip home rule with KVTR-aware predecessor rule |
| D | Direction consistency (recomputed from stop order) |

R2 (headway) is not applicable because departure times are fixed by GTFS. R8 (depot capacity) is not modelled in V1. R12 is subsumed by R3.

### Bugs fixed in Phase 1

- **R6:** Previously enforced 15-minute deadhead for all cross-terminal pairs. Fixed to per-pair requirements: 5 minutes same-stop, 8 minutes MUTT-to-terminal, and 15 minutes ALVA-to-TPHT.
- **R11:** Previously treated KVTR as if it were MUTT. Fixed to require a predecessor ending at KVTR, making WK_256 → WK_12 a mandatory chain on one rake.
- **Home-lock:** An undocumented pruning rule blocked rakes from the earliest opposite-terminal trip. Removed. The resulting 9/9/0 split is OPTIMAL.

---

# Phase 2 — Operational Simulation

Uses SimPy to simulate delay propagation through the 255-trip Phase 1 schedule.

### What Phase 2 produces

- **4 experiments:** E1, E2, E3, E4.
- **100 seeds per experiment:** 400 Monte Carlo runs.
- **Headline results:** Seed 42.
- **Delay model:** Clipped normal distribution with pre-clip mean −48 seconds, clipped to `[0, 300]` seconds.
- **All delays are synthetic**, not real KMRL operational delay data.

### Experiment configuration

| Experiment | Delay standard deviation |
|---|---:|
| E1 | 0 seconds |
| E2 | 60 seconds |
| E3 | 120 seconds |
| E4 | 300 seconds |

### Headline results — Seed 42

| Experiment | ±5 min on-time (255) | ±5 min on-time (237) | Propagation % | Total propagation (min) | Headway actual | Headway scheduled |
|---|---:|---:|---:|---:|---:|---:|
| E1 | 100.00% | 100.00% | 0.00% | 0.0 | 3 | 3 |
| E2 | 100.00% | 100.00% | 0.42% | 1.8 | 4 | 3 |
| E3 | 100.00% | 100.00% | 1.27% | 5.1 | 4 | 3 |
| E4 | 100.00% | 100.00% | 2.53% | 10.9 | 7 | 3 |

### KPIs calculated

- **On-time performance:** ±1, ±3, and ±5 minutes, calculated for all trips and eligible trips.
- **Propagation percentage:** Percentage of eligible trips with `propagated_delay > 0`.
- **Total propagated delay:** Sum of propagated delay across eligible trips.
- **Maximum propagation:** Maximum propagated delay.
- **Headway violations:** Actual and scheduled same-direction pairs with a gap below 120 seconds.

### Simulation rules

| Rule | Description |
|---|---|
| P1 | Own delay sampled from clipped normal distribution `normal(-48, std)`, clipped to `[0, 300]` seconds |
| P2 | Propagation floor = previous actual arrival + 300-second turnaround |
| P3 | Actual departure = maximum of early departure and propagation floor |
| P4 | Common random numbers across experiments, using seeds 42–141 |
| P5 | Headline timeline generated using seed 42 |

### Bugs fixed

- **Time parser:** `check_terminals.py` originally accepted `HH:MM` only, while the schedule uses `HH:MM:SS`. Fixed by importing the parser from `schedule_loader`.
- **Experiment output:** Fixed string formatting in `experiments.py`, including JSON output formatting. No KPI values changed.

### Important interpretation

- The 100% ±5-minute on-time result is a **model property**, not an operational guarantee. Own delay is capped at 300 seconds and the ±5-minute threshold is inclusive.
- The three scheduled headway violations are present in the GTFS-derived schedule. They are not simulation bugs.
- The simulation uses a flat 300-second turnaround for propagation. It does not independently model cross-terminal deadhead time.

---

# Phase 3 — Crew Scheduling

Assigns the 255 Phase 1 trips to SC/TO drivers using OR-Tools CP-SAT.

### What Phase 3 produces

- **255 trips × 3 pool sizes:** 765 assignment rows.
- **55 synthetic drivers:** D001–D055.
- **Three tested pools:** 45, 50, and 55 drivers.
- **All three solver runs:** OPTIMAL.
- **Objective:** 0.0 at all pools.
- **Gap:** 0.0% at all pools.
- **Independent validator:** PASS at all pools.
- **Terminal continuity:** 0 impossible transitions after the fix.

### Inputs

| File | Purpose |
|---|---|
| `data/processed/schedule.csv` | Phase 1 schedule — 255 trips, read-only |
| `data/synthetic/drivers.csv` | 55 synthetic drivers, D001–D055 |

### What Phase 3 enforces

- Every Phase 1 trip is assigned to exactly one driver.
- No driver is assigned overlapping trips.
- Every transition between terminals is physically possible.
- Active duty does not exceed 8 hours.
- Each driver has 15 minutes before their first trip and after their last trip.
- At least 5 drivers remain unused as reserve.
- The Phase 1 schedule is read-only. Phase 3 does not change trip times or rake assignments.

### Crew scheduling rules

| ID | Rule | Type |
|---|---|---|
| C1 | No overlap and physically possible terminal continuity | Hard |
| C2 | Maximum active duty of 28,800 seconds (8 hours) | Hard |
| C3 | Sign-on 900 seconds before first departure and sign-off 900 seconds after last arrival | Hard |
| C4 | Every trip assigned to exactly one driver | Hard |
| C5 | Minimum 12-hour rest between shifts | Future works |
| C6 | Continuous driving of up to 5 hours, with a soft penalty | Soft |
| C7 | At least 5 reserve drivers | Soft |

C1 terminal transition requirements:

- Same stop: 300 seconds.
- MUTT ↔ ALVA/TPHT: 480 seconds.
- Other transitions, including ALVA ↔ TPHT and KVTR: 900 seconds.

The soft objective is:

```text
Minimize(
    OBJ_SCALE × (
        10 × C6_penalty +
        15 × C7_penalty
    )
)

OBJ_SCALE = 100
```

### Solver results

| Pool size | Status | Runtime | Active drivers | Reserve | Objective | Gap |
|---|---|---:|---:|---:|---:|---:|
| 45 | OPTIMAL | 104.28 s | 40 | 5 | 0.0 | 0.0% |
| 50 | OPTIMAL | 58.09 s | 45 | 5 | 0.0 | 0.0% |
| 55 | OPTIMAL | 60.25 s | 50 | 5 | 0.0 | 0.0% |

### Independent validation

All three pools passed:

- C1 — No overlap and terminal continuity.
- C2 — Maximum active duty.
- C3 — Sign-on and sign-off buffers.
- C4 — Full trip coverage.
- C7 — Reserve requirement.

### Terminal continuity verification

| Pool | Impossible transitions before fix | After fix |
|---|---:|---:|
| 45 | 62 | 0 |
| 50 | 53 | 0 |
| 55 | 44 | 0 |

### Bugs fixed

- Reworked the C6 formulation from an O(n²) model to a state machine to reduce the number of Boolean variables.
- Fixed C6 chain continuity using `last_arr` carry-forward and `has_prev`.
- Fixed C1 non-overlap logic that incorrectly made all pools infeasible.
- Added a `has_prev` guard to the C6 new-chain constraint.
- Fixed validator C1 to compare per-trip times by joining `crew_schedule.csv` with `schedule.csv`.
- Added terminal deadhead requirements to C1 using `_need_sec`.

### Limitations

- C5 (12-hour rest between shifts) is deferred to V2.
- C6 is effectively inactive under the current configuration. Objective 0.0 does not prove that no driver exceeded five hours of continuous driving.
- `drivers.csv` contains only `driver_id`. Qualifications, availability, shift preferences, and weekly availability are deferred to V2.
- Single-day planning only; no multi-day rostering.
- No driver-minimization objective.
- CP-SAT may produce different but equally optimal assignments on reruns.
- No per-trip explanation of why a particular driver was assigned.

### Phase 3 output files

| File | Contents |
|---|---|
| `data/processed/crew_schedule.csv` | 765 rows. Columns: `trip_id, driver_id, sign_on, sign_off, pool_size` |
| `data/processed/crew_solution.json` | Per-pool solver results and assignments |
| `data/processed/crew_validation.json` | Per-pool validation checks and overall status |
| `data/synthetic/drivers.csv` | 55 synthetic driver IDs |

**Important:** `sign_on` and `sign_off` are per-driver, per-day values, not per-trip times. To build a driver Gantt chart, join `crew_schedule.csv` with `schedule.csv` using `trip_id`.

---

# Phase 4 — Explainability Report

Generates a human-readable report and machine-readable utilization statistics from the Phase 1, Phase 2, and Phase 3 outputs.

Phase 4 is a read-only reporting layer. It does not modify earlier phase outputs.

### What Phase 4 produces

- One Markdown report: `data/processed/explainability_report.md`.
- One statistics file: `data/processed/utilization_stats.json`.
- Seven report sections.
- Baseline: 255 trips, 18 rakes, and driver pools 45/50/55.
- Runtime: approximately 5 seconds.
- No solver or simulation execution.

### Input files

| File | Source | Used in |
|---|---|---|
| `data/processed/validation.json` | Phase 1 validator | Section 2 |
| `data/processed/solution.json` | Phase 1 solver | Sections 1, 7 |
| `data/processed/schedule.csv` | Phase 1 solver | Sections 1, 4 |
| `data/processed/simulation_kpis.json` | Phase 2 experiments | Section 6 |
| `data/processed/crew_solution.json` | Phase 3 solver | Sections 1, 3, 5, 7 |
| `data/processed/crew_validation.json` | Phase 3 validator | Section 3 |
| `data/processed/crew_schedule.csv` | Phase 3 solver | Section 5 |

All seven input files are read-only.

### The seven report sections

| Section | Contents |
|---|---|
| 1. Executive Summary | Total trips, rakes, and active drivers per pool. Clarifies the scope of Phase 1 optimality. |
| 2. Phase 1 Constraint Status | The 10 checks in `validation.json`: R1, R3, R4, R5, R6, R7, R9, R10, R11, D. |
| 3. Phase 3 Constraint Status | C1–C7 status for pools 45, 50, and 55. C1–C4 and C7 PASS; C5 deferred and C6 soft. |
| 4. Rake Utilization | Per-rake utilization table covering 18 rakes. |
| 5. Driver Utilization | Per-driver utilization tables for all three pools. |
| 6. Simulation Results | Seed 42 headline results and 100-seed Monte Carlo results. |
| 7. Sensitivity Analysis & Honest Limitations | Pool-size comparison and documented limitations. |

### Utilization formulas

Rake utilization:

```text
utilization_pct = busy_sec / span_sec × 100
```

Driver total depot time:

```text
total_depot_hours =
    (max sign_off − min sign_on) / 3600
```

Driver total depot time includes both 900-second buffers. It is not the same as the C2 active-duty variable.

### What Phase 4 deliberately does not do

- No conflict analyzer: all solver phases have valid solutions; there is no infeasibility to analyze.
- No per-trip "why" explanations: assignments are presented as context and consistency, not as individual solver reasons.
- No SHAP or LIME: this is a reporting and audit layer, not an ML explainability layer.
- No additional modularization into separate rule-tracing or trip-explainer modules.

### Output files

| File | Contents |
|---|---|
| `data/processed/explainability_report.md` | Seven-section report with source files cited below its tables |
| `data/processed/utilization_stats.json` | Machine-readable rake and driver utilization statistics, including derivation formulas |

`utilization_stats.json` is the canonical source for frontend utilization displays. The frontend should render its tables rather than independently recomputing utilization from the schedule files.

### Data format guarantees

- All seven inputs must be valid UTF-8.
- `schedule.csv` requires `trip_id, rake_id, direction, first_stop, last_stop, departure, arrival`.
- `crew_schedule.csv` requires `trip_id, driver_id, sign_on, sign_off, pool_size`.
- Time parsing supports `HH:MM:SS` values beyond 24:00.
- Missing files raise `FileNotFoundError`.
- Missing required CSV columns raise `ValueError`.

### Run Phase 4

From the project root:

```powershell
python -m src.explainability.report_generator
```

Expected runtime: approximately 5 seconds.

Expected output:

```text
[report] reading inputs ...
[report] wrote data/processed/explainability_report.md
[report] wrote data/processed/utilization_stats.json
[report] done
```

---

# Phase 5 — Disruption Response

A planned disruption response engine that re-optimizes the Phase 1 schedule when rakes become unavailable.

Uses CP-SAT to minimize dropped trips while respecting the scheduling constraints.

### What Phase 5 produces

- Five disruption scenarios tested.
- One to five rakes taken out of service.
- Five scenario CSV files.
- A machine-readable diff and human-readable summary for Scenarios A and B.
- A sensitivity analysis output for Scenarios C, D, and E.

### Scenario results

| Scenario | Rakes down | Active rakes | Dropped trips | Recovery | Status | Gap | Runtime |
|---|---|---:|---:|---:|---|---:|---:|
| A | 1 (R008) | 18 | 0 | 100% | OPTIMAL | 0.0% | 189 s |
| C | 2 (R008, R013) | 18 | 0 | 100% | OPTIMAL | 0.0% | 187 s |
| D | 3 (R008, R013, R015) | 17 | 0 | 100% | OPTIMAL | 0.0% | 142 s |
| B | 4 (+R002) | 16 | 7 | 86.8% | FEASIBLE | 21.92% | 300 s |
| E | 5 (+R007) | 15 | 16 | 75.8% | FEASIBLE | 18.75% | 300 s |

Disruption times:

- Scenario A: 18:00, evening peak.
- Scenarios B, C, D, and E: 07:00, morning peak.

### What Phase 5 enforces

| Rule | Description |
|---|---|
| R1 (modified) | Every trip is served exactly once or explicitly dropped |
| R3 | Departures within `[04:40, 24:00)` |
| R5 | No overlapping trips on the same rake |
| R6 | Per-pair turnaround and deadhead: 5 / 8 / 15 minutes |
| R10 | No rake over 1,000,000 km used |
| R11 | First-trip home rule with KVTR-aware predecessor rule |
| R12 | Subsumed by R3 |
| `W_DROP = 1000` | Drop penalty: 100,000 objective units per dropped trip, multiplied by `OBJ_SCALE = 100` |
| `add_balance_bound_phase5` | Hard trips-per-rake bound used as a pruning hint; does not change the objective |

R4, R7, R8, and R9 are no-ops in the Phase 5 model because they are enforced by construction or load-time checks.

### Withdrawal rule

A downed rake is unavailable for any trip whose departure is greater than or equal to the disruption time.

- Trips that have already departed complete normally.
- No mid-trip abort is performed.
- No passenger deboarding is modelled.
- The in-progress trip at the disruption instant is disclosed in `reschedule_summary.md`.

### Inputs

| File | Purpose |
|---|---|
| `data/processed/schedule.csv` | Phase 1 baseline — 255 trips, read-only |
| `data/synthetic/rakes_phase5.csv` | Parallel fleet containing 25 rakes and Phase 5 maintenance fields |
| `data/disruptions/scenario_a.json` | Scenario A configuration |
| `data/disruptions/scenario_b.json` | Scenario B configuration |
| `data/disruptions/scenario_c.json` | Scenario C configuration |
| `data/disruptions/scenario_d.json` | Scenario D configuration |
| `data/disruptions/scenario_e.json` | Scenario E configuration |
| `solver/config.py` | Phase 1 constants, imported but not modified |

### Phase 5 fleet data

`rakes_phase5.csv` includes:

```text
rake_id,status,initial_mileage_km,cmrs_status,initial_location,initial_available_time,km_since_last_maintenance,maintenance_type
```

Fleet composition:

- 18 service rakes: R001–R018.
- 5 scheduled maintenance rakes: R019, R021, R022, R024, R025. These are reactivatable.
- 2 unscheduled repair rakes: R020 and R023. These are permanently blocked.

`km_since_last_maintenance` is a synthetic reliability proxy, not a live fleet measurement.

### Output files

| File | Contents |
|---|---|
| `data/processed/reschedule_scenario_a.csv` | 255 rows, 0 dropped trips |
| `data/processed/reschedule_scenario_b.csv` | 255 rows, 7 dropped trips |
| `data/processed/reschedule_scenario_c.csv` | 255 rows, 0 dropped trips |
| `data/processed/reschedule_scenario_d.csv` | 255 rows, 0 dropped trips |
| `data/processed/reschedule_scenario_e.csv` | 255 rows, 16 dropped trips |
| `data/processed/reschedule_diff.json` | Scenario A and B diff |
| `data/processed/reschedule_summary.md` | Scenario A and B narrative summary |
| `data/processed/sensitivity_analysis.json` | Scenario C, D, and E metrics |

The scenario CSVs use the same schema as `schedule.csv`:

```text
trip_id,rake_id,direction,first_stop,last_stop,departure,arrival
```

Dropped trips have `rake_id = "DROPPED"` and empty `departure` and `arrival` fields. Their original direction and stop information is preserved.

### Key facts

- **Scenario A objective (900.0):** Matches the Phase 1 objective because no trips are dropped and the balance term remains active.
- **Scenario B objective (702,400):** 7 dropped trips × 100,000 + 2,400 balance penalty.
- **Scenarios B and E are FEASIBLE, not OPTIMAL.** Valid solutions were found, but minimality was not proven within the 300-second time limit.
- **Scenario B can vary between 7 and 8 dropped trips** across runs because CP-SAT search is truncated at 300 seconds. The current committed result has 7 drops.
- **Dropped does not mean delayed.** A dropped trip is cancelled; it is not a rescheduled trip.
- Scenario A activates one rescue rake. Scenarios B–E activate two by design.

### Bugs fixed during Phase 5

- **Constraint drift:** Rebuilt the Phase 5 constraints from the corrected Phase 1 constraints, including R6 and KVTR-aware R11.
- **MUTT/MUTTOM mismatch:** Standardized the terminal name to `MUTT` across the Phase 5 fleet and deadhead logic.
- **Dead code:** Removed unreachable lines in `_first_trip_deadhead`.

### Honest limitations

1. Scenarios B and E are FEASIBLE, not OPTIMAL.
2. Scenario B can produce 7–8 dropped trips across runs.
3. No independent Phase 5 validator re-checks all R1–R12 constraints from the output.
4. Crew is not rescheduled. Phase 3 crew assignments still correspond to the original Phase 1 schedule.
5. The 45–90-minute passenger wait framing is illustrative, not calculated.
6. No mid-trip abort is modelled.
7. Maintenance mileage is synthetic, not a live fleet feed.
8. Each scenario uses a full re-solve rather than warm-start optimization.
9. This is planned disruption response, not real-time control.
10. Dropped trips are cancellations, not delays.

### Run Phase 5

From the project root:

```powershell
python -m solver.reschedule_solve
```

Writes five scenario CSVs, `reschedule_diff.json`, `reschedule_summary.md`, and `sensitivity_analysis.json`.

Expected total runtime: approximately 20–25 minutes.

To verify the sensitivity output:

```powershell
python -c "import json; d = json.load(open('data/processed/sensitivity_analysis.json')); [print(s['id'], '| drops:', s['drops'], '| status:', s['status'], '| gap:', s['gap_pct'], '%') for s in d['scenarios']]"
```

Expected: three lines for scenarios C, D, and E.

---

# Frontend — MetroPulse Dashboard

Read-only NiceGUI dashboard displaying outputs from all five phases.

**Stack:** NiceGUI 4.0 · Python · Tailwind CSS · Plotly

**Location:** `frontend/`

### Run the frontend

```powershell
cd frontend
python main.py
```

Open:

```text
http://127.0.0.1:8080/
```

### Pages and routes

| Page | Route | Module | Data sources |
|---|---|---|---|
| Home | `/` | Overview | 9 files |
| Train Scheduling | `/phase1` | Phase 1 | `schedule.csv`, `solution.json`, `validation.json` |
| Operational Simulation | `/phase2` | Phase 2 | `simulation_kpis.json`, `simulation_timeline.csv` |
| Crew Scheduling | `/phase3` | Phase 3 | `crew_solution.json`, `crew_validation.json`, `crew_schedule.csv`, `drivers.csv` |
| Explainability | `/phase4` | Phase 4 | `explainability_report.md`, `utilization_stats.json` |
| Disruption Response | `/phase5` | Phase 5 | `reschedule_diff.json`, `sensitivity_analysis.json`, five scenario CSVs, five scenario JSONs |

### Frontend structure

```text
frontend/
├── main.py                      # App entry, routes, font/background
├── pages/
│   ├── home.py                  # Overview dashboard
│   ├── phase1.py                # Train Scheduling
│   ├── phase2.py                # Operational Simulation
│   ├── phase3.py                # Crew Scheduling
│   ├── phase4.py                # Explainability
│   └── phase5.py                # Disruption Response
├── components/
│   ├── tokens.py                # Central design system
│   ├── ui_elements.py           # Reusable cards, badges, tables, charts
│   ├── navigation.py            # Collapsible sidebar
│   ├── time_utils.py            # Time conversion utilities
│   └── trip_category.py         # Trip classifier
├── data/
│   └── registry.py              # File loaders and caching
├── assets/
│   └── kochi_metro.jpg          # Home hero image
└── tests/
    ├── test_core.py
    └── test_ui_rules.py
```

### Design system

All visual tokens are centralized in `components/tokens.py`.

- **Fonts:** IBM Plex Sans for body text; Roboto Mono for code and technical hover details.
- **Colors:** Navy `#1E3A5F`, blue `#2563EB`, grey `#94A3B8`, plus status colors.
- **Cards:** White backgrounds, light borders, 6px rounded corners, and no heavy shadows.
- **Typography:** KPI values 28px semibold, card titles 16px, body text 12–14px.
- **Badges:** Centralized status-to-color mapping.

| Status | Badge color |
|---|---|
| OPTIMAL / PASS | Green |
| FEASIBLE / WARNING | Amber |
| FAIL / CANCELLED | Red |
| DEFERRED | Grey |

Pages cannot independently choose badge colors.

A frontend test enforces that hex color literals exist only in `tokens.py`.

### Data loading

`frontend/data/registry.py` provides file loaders used by every page.

Each loader returns:

```python
{
    "data": ...,
    "status": "ok" | "not_generated" | "invalid",
    "message": str,
    "path": str,
    "mtime": float
}
```

**Caching:**

- Uses `functools.lru_cache` on a private `(path, mtime)` function.
- The public loader retrieves the file modification time on every call.
- Changing a source file's modification time invalidates its cached result.

**Error handling:**

- If a required file is not `ok`, the page displays a `state_card`.
- The page stops rendering rather than displaying partial data.

**Provenance:**

Each page ends with `provenance_footer(path, mtime)`, showing the source file and its last modification time.

### What each page displays

**Home (`/`)**

- Four KPIs: Trips, Rakes, Crew Pools, Delay Tolerance.
- Split hero banner with Kochi Metro image and five-step pipeline.
- Five phase cards with navigation buttons.
- Compact footer showing system boundaries and data files.

**Train Scheduling (`/phase1`)**

- Four KPIs: Trips, Rakes, Status, Objective.
- Rake Gantt chart.
- Schedule table using aggrid.
- Validation checks accordion (R1–D).
- Limitations.

**Operational Simulation (`/phase2`)**

- Three KPIs: ±1-minute on-time, ±3-minute on-time, total delay.
- Experiment selector (E1–E4).
- Four charts: on-time performance, propagation, headway, and delay with p5–p95 bands.
- Gantt overlay showing scheduled and actual times.
- Methodology.

**Crew Scheduling (`/phase3`)**

- Pool tabs: 45, 50, and 55.
- Three KPIs: Active Drivers, Solver Status, Solve Time.
- Fleet crew Gantt with two columns and all drivers.
- Validator panel (C1–C7).
- Methodology.

**Explainability (`/phase4`)**

- Seven Markdown report sections from `explainability_report.md`.
- Tables rendered as HTML.
- Collapsed utilization-formula expansion at the bottom.

**Disruption Response (`/phase5`)**

- Observed output summary.
- Sensitivity bar chart.
- Five-scenario comparison table.
- Scenario cards: A/B side by side and C/D/E in a three-column grid.
- Rescheduled Gantt with four-color coding.

### Chart rules

- All Gantt charts use HH:MM time formatting.
- Hover tooltips use ASCII hyphens to avoid encoding issues.
- No dual-Y axes.
- Plotly modebar is hidden in the UI.

### Frontend tests

`tests/test_core.py` — 7 tests covering time parsing and trip categories.

`tests/test_ui_rules.py` — 5 tests covering:

- Forbidden wording in error contexts.
- Protected strings in code.
- Hex colors restricted to `tokens.py`.
- FEASIBLE badge remaining amber and distinct from OPTIMAL.
- Plotly gridline and hover settings.

Run tests:

```powershell
pytest tests/ -v
```

### Frontend limitations

- Read-only: no writes to backend files.
- Single-day scope: no multi-day crew or maintenance modelling.
- Assumes backend output is correct; no independent frontend validation beyond registry status checks.
- Some technical hover tooltips still use a monospaced font.

---

## Common Commands

Run commands from the project root unless otherwise stated.

### Phase 1 — Build solver input

Only required if GTFS or source inputs change:

```powershell
python data/extract_gtfs_trips.py
python data/verify_gtfs_trips.py
python data/merge_trips.py
python data/generate_synthetic_v2.py
```

Produces `data/trips_all.csv` and `data/synthetic/rakes.csv`.

### Phase 1 — Run scheduler

```powershell
python -m solver.solve
```

Writes `schedule.csv` and `solution.json`.

### Phase 1 — Validate schedule

```powershell
python -m solver.validator
```

Writes `validation.json`.

### Phase 2 — Preflight checks

Read-only:

```powershell
python -m src.simulation.preflight
```

Expected:

- 255 trips.
- 18 rakes.
- 237 eligible trips.
- 3 scheduled zero-second headway pairs.

### Phase 2 — Run experiments

```powershell
python -m src.simulation.experiments
```

Writes:

- `simulation_kpis.json`
- `simulation_timeline.csv`

Expected runtime: approximately 2–3 minutes.

### Phase 2 — Check terminal continuity

Read-only:

```powershell
python -m src.simulation.check_terminals
```

Expected:

- 237 pairs.
- 164 matched pairs.
- 73 cross-terminal deadheads.
- 0 missing GTFS information.

### Phase 3 — Generate drivers

```powershell
python -m data.generate_drivers
```

Generates 55 deterministic synthetic drivers.

### Phase 3 — Solve crew scheduling

```powershell
python -m solver.crew_solve
```

Solves pools 45, 50, and 55.

### Phase 3 — Validate crew schedule

```powershell
python -m solver.crew_validator
```

Writes `crew_validation.json`.

### Phase 4 — Generate explainability report

```powershell
python -m src.explainability.report_generator
```

Writes `explainability_report.md` and `utilization_stats.json`.

### Phase 5 — Run disruption scenarios

```powershell
python -m solver.reschedule_solve
```

Writes five scenario outputs and the associated reports.

### Frontend — Run dashboard

```powershell
cd frontend
python main.py
```

### Run tests

From the appropriate project directory:

```powershell
pytest tests/ -v
```

### Clean Python caches

```powershell
Get-ChildItem -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force
Get-ChildItem -Recurse -File -Filter *.pyc | Remove-Item -Force
```

---

## Output Files Summary

| Phase | Output | Purpose |
|---|---|---|
| Phase 1 | `schedule.csv` | 255-trip rake schedule |
| Phase 1 | `solution.json` | Solver results |
| Phase 1 | `validation.json` | Independent constraint validation |
| Phase 2 | `simulation_kpis.json` | Headline and Monte Carlo KPIs |
| Phase 2 | `simulation_timeline.csv` | Seed 42 trip-level timeline |
| Phase 3 | `crew_schedule.csv` | Driver assignments for three pools |
| Phase 3 | `crew_solution.json` | Per-pool solver results |
| Phase 3 | `crew_validation.json` | Independent crew validation |
| Phase 4 | `explainability_report.md` | Human-readable explainability report |
| Phase 4 | `utilization_stats.json` | Canonical utilization statistics |
| Phase 5 | `reschedule_scenario_*.csv` | Five disruption scenario schedules |
| Phase 5 | `reschedule_diff.json` | Scenario A/B changes |
| Phase 5 | `reschedule_summary.md` | Scenario A/B narrative summary |
| Phase 5 | `sensitivity_analysis.json` | Scenario C/D/E sensitivity metrics |

---

## Data

| Item | Detail |
|---|---|
| Source | Kochi Metro Rail Limited |
| Format | GTFS static feed |
| Feed version | 1.0 |
| Feed validity | 2024-08-12 → 2025-12-31 |
| Timezone | Asia/Kolkata (IST) |
| Route | R1 (Kochi Metro Line 1) |
| Stations | 25 |
| Services | WK (weekday), WE (weekend) |
| Weekday trips used | 255 |
| Full-route trips | 232 (ALVA ↔ TPHT) |
| Partial trips | 23 |
| Fares | ₹10–₹60 across 6 slabs |

Full provenance: `docs/data-provenance.md`

Full constraint specification: `docs/constraints-v2.2.md`

---

## Data Format Guarantees

### Time format

- Times use `HH:MM:SS`.
- Some values exceed 24:00:00.
- Example: WK_253 arrives at `24:03:45`.
- Driver `sign_off` can also exceed 24:00:00, for example `24:18:45`.
- Use a custom parser:

```text
seconds = H × 3600 + M × 60 + S
```

Do not impose a 24-hour limit.

### IDs

- `trip_id`, `rake_id`, and `driver_id` values are zero-padded strings.
- Examples: `WK_4`, `R001`, `D001`.
- Do not convert these IDs into integers.

### Direction

`UP` and `DOWN` are station-index based, not terminal-pair based.

For example, KVTR → ALVA is labelled `UP` because the KVTR station index is greater than the ALVA index.

Do not assume `UP` always means ALVA → TPHT.

### Phase 5 dropped trips

Dropped trips use:

- `rake_id = "DROPPED"`.
- Empty `departure` and `arrival`.
- Original `direction`, `first_stop`, and `last_stop` preserved.

---

## Key Facts

### Phase 1

- **Objective 900.0 is not a score.** It represents the O6 rake-balance penalty: `3 × 100 × Σdev`, where Σdev = 3.
- The theoretical minimum distribution is 3 rakes with 15 trips and 15 rakes with 14 trips.
- Five trips are labelled "positioning": WK_4, WK_256, WK_18, WK_12, and WK_253. This is a project label, not a GTFS field.
- The 18-service-rake fleet figure comes from the 2026 news article. The Annual Report 2024–25 reports 15 operating trains, a different reporting period.

### Phase 2

- **100% ±5-minute on-time is a model property**, not an operational guarantee. Own delay is capped at 300 seconds and the threshold is inclusive.
- The three scheduled headway violations originate in the GTFS-derived schedule.
- The 73 cross-terminal deadheads are legal R6 repositioning movements, not violations.
- Phase 2 uses a flat 300-second turnaround for propagation rather than independently modelling terminal deadhead.

### Phase 3

- `crew_schedule.csv` contains 765 rows: 255 trips × 3 pools.
- `sign_on` and `sign_off` are per-driver, per-day values, not per-trip times.
- Active drivers are distinct driver IDs present in the selected pool's schedule.
- The objective 0.0 is a penalty sum, not a quality score.
- The solver uses exactly `pool_size − 5` active drivers at each pool.
- Active duty and total depot time differ by 1,800 seconds because of the two 15-minute buffers.

### Phase 4

- Every number in the report traces to one of its seven input files.
- Phase 1 `OPTIMAL` means optimal under the active O6 objective, not optimal under every possible scheduling objective.
- `utilization_stats.json` is the canonical source for frontend utilization displays.
- The pool-size comparison is presented without drawing a recommendation.

### Phase 5

- Scenarios B and E are FEASIBLE, not OPTIMAL.
- Scenario B can vary between 7 and 8 dropped trips across runs.
- A dropped trip is cancelled, not delayed.
- The Phase 3 crew schedule is not recomputed after a disruption.
- Phase 5 is planned disruption response, not real-time control.

### Frontend

- The dashboard is read-only.
- Backend files are loaded through `data/registry.py`.
- Pages display source-file provenance and modification times.
- The frontend does not import backend solver modules to calculate results.

---

## Development

### Git strategy

- **Code, documentation, and configurations:** tracked.
- **Raw GTFS `.txt` files:** ignored and documented in `data/raw/README.md`.
- **Processed and synthetic data:** ignored where regenerable.
- **Virtual environment and Python caches:** ignored.

### Adding a dependency

```powershell
pip install <package>
pip freeze > requirements.txt
```

### Project documentation

| File | Purpose |
|---|---|
| `docs/constraints-v2.2.md` | Phase 1 constraint specification |
| `docs/data-provenance.md` | Data sources and provenance |
| `docs/meeting-log.md` | Project decisions and meeting notes |
| `docs/checklist.md` | Phase-by-phase task tracking |
| `docs/phases.md` | Full project phase plan |
| `docs/project-status.md` | Project state, results, and known issues |

---

## Roadmap

- [x] **Phase 0** — Project setup, Git, virtual environment
- [x] **Phase 1** — GTFS ingestion, CP-SAT train scheduling, validator
- [x] **Phase 2** — SimPy operational simulation and delay propagation
- [x] **Phase 3** — Crew scheduling
- [x] **Phase 4** — Explainability report
- [x] **Phase 5** — Disruption response
- [ ] **Phase 6** — ML delay prediction (optional; not implemented)
- [x] **Phase 7** — NiceGUI frontend dashboard

**Project completion:** All implemented project phases and the frontend are complete. Phase 6 remains optional and was not implemented.

---

