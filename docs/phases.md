# MetroPulse — Complete Phase Plan

**Project:** DPR-driven train scheduling & optimization for Kochi Metro Rail Limited (KMRL) Phase-II
**Method:** Google OR-Tools CP-SAT
**Version:** 2 (V1 complete, Phase 2 next)
**Last updated:** 2026-11-06

---

## Phase Overview

| Phase | Name | Status | Deliverable |
|-------|------|--------|-------------|
| **0** | Setup | ✅ Complete | Venv, Git, folder structure |
| **1** | Train Scheduling (CP-SAT) | ✅ Complete | 408-trip valid schedule, 10/10 validator checks |
| **1.5** | Model Refinements | 🟡 Optional | R13 cleaning, R14 stabling, traffic spare activation |
| **2** | SimPy Validation | ⏳ Next | Robustness KPIs under stochastic delays |
| **3** | Crew Scheduling | ⏳ Later | 60 drivers assigned to 408 fixed trips |
| **4** | Explainability | ⏳ Later | Human-readable decision rationale |
| **5** | Near-Real-Time Re-Optimization | ⏳ Later | Warm-start re-solve in 1–2 min |
| **6** | ML Layer (optional) | ⏳ If data | XGBoost running-time prediction |
| **7** | UI + Demo | ⏳ Later | Streamlit dashboard |

---

## Phase 0 — Setup ✅

**Deliverables:**
- Virtual environment (`venv/`)
- Git repository on GitHub
- Folder structure (`data/`, `solver/`, `src/`, `docs/`, `notebooks/`, `tests/`)
- `.gitignore` for GTFS and generated outputs
- `.gitattributes` for line-ending consistency
- `requirements.txt` (ortools, pandas, numpy)

---

## Phase 1 — Train Scheduling (CP-SAT) ✅

**Purpose:** Given DPR hourly service plan + 18-rake fleet, produce a valid 408-trip daily schedule satisfying 12 hard constraints and minimizing 7 soft objectives.

### Delivered

**Data:**
- `data/raw/` — GTFS feed (11 tables, 24 stops, 252 trips) `[DPR-adjacent real data]` — used for validation only, not V1 scheduler input
- `data/dpr/hourly_service.csv` — DPR hourly plan (38 rows)
- `data/synthetic/rakes.csv` — 18 rakes (15 bare + 1 traffic + 2 maintenance)
- `data/synthetic/terminals.csv` — 2 terminals, 3-min turnaround
- `data/synthetic/maintenance.csv` — empty (Scenario A)
- `data/synthetic/depot.csv` — Info Park-2 = 2, Muttom unbounded
- `data/generate_synthetic_v2.py` — deterministic generator

**Solver:**
- `solver/config.py` — all constants, source-tagged
- `solver/models.py` — `ProblemData` loader
- `solver/constraints.py` — R1–R12 + O1–O7
- `solver/solve.py` — orchestrator with optimality gap printout
- `solver/validator.py` — independent verification (10 of 12 constraints)

**Results:**
- 408 trips scheduled (204 UP + 204 DOWN)
- 16 rakes used (R001–R016)
- Solve time: ~317s (FEASIBLE, gap varies)
- Validator: 9 PASS + 1 SKIPPED, Overall PASS
- 15-rake test: FEASIBLE (proves traffic spare not required)

### How to Run

```powershell
cd Z:\metropulse
.\venv\Scripts\Activate.ps1
python data\generate_synthetic_v2.py
python -m solver.solve        # ~5 min
python -m solver.validator    # 10 checks
```

---

## Phase 1.5 — Model Refinements (Optional) 🟡

**Purpose:** Close gaps in V1's coverage of the original six constraints. Both additions are [SYNTHETIC].

### R13 — Cleaning Interval

    Every rake cleaned ≤ every 24h (interior) or 72h (exterior) [SYNTHETIC]

    Cleaning bay capacity = 3 [SYNTHETIC]

    Requires last_cleaned_hours_ago field in rakes.csv

    Effort: ~1 day

### R14 — Muttom Stabling Depth

    Assume 4 lines × 4 depth = 16 slots [SYNTHETIC]

    Depth-d rakes only leave when shallower ones go

    Requires stabling_line, stabling_position in rakes.csv

    Effort: ~1 day

### Traffic Spare Activation (R4a refinement)

    Add explicit activated_traffic_reserve[h] BoolVar per hour

    Constraint: active_rakes[h] ≤ 15 + activated[h]

    Penalize in O7

    15-rake test confirms this will remain feasible

    Effort: ~2 hours

Result after 1.5: 5/6 original constraints partially covered (job cards + branding still deferred).

Decision: Skip if timeline tight. Do if 3–5 extra days and stronger defensibility needed.

---

## Phase 2 — SimPy Validation ⏳ NEXT

**Purpose:** Replay the Phase 1 schedule under stochastic delays. Measure how the schedule holds up. This is the "digital twin" differentiator.

### Design (from constraints-v2.md)

Delay model [SYNTHETIC]:

```python
DELAY_DISTRIBUTION_TYPE = "clipped_normal"
DELAY_DISTRIBUTION_MEAN_SEC = -48
DELAY_DISTRIBUTION_STD_SEC = 60
DELAY_DISTRIBUTION_MIN_SEC = 0
DELAY_DISTRIBUTION_MAX_SEC = 300
```

Propagation rule (Option A):

```python
early_dep[i]      = sched_dep[i] + own_delay[i]
propagated_dep[i] = actual_arr[p] + 3 min
actual_dep[i]     = max(early_dep[i], propagated_dep[i])
actual_arr[i]     = actual_dep[i] + 19 min
propagated_delay[i] = max(0, propagated_dep[i] - early_dep[i])
```

First-of-rake trips have no predecessor: actual_dep = early_dep, propagated_delay = 0.

Headline KPIs (schedule-dependent):

    Propagated delay minutes = sum(propagated_delay[i])

    Share delayed by propagation = count(propagated_delay[i] > 0) / (408 − first-of-rake trips)

Supplementary KPIs:

    On-time ±5 min (headline among on-time metrics)

    On-time ±3 min

    On-time ±1 min (distribution readout)

    Headway violations

    Max delay propagated

    Trips completed

Sweep: Std = 0, 60, 120, 300 s. Mean fixed at -48 s.

### Files to Create

src/simulation/
├── __init__.py
├── simpy_runner.py       ← loads schedule.csv, runs simulation
└── kpis.py               ← KPI computation

data/processed/
├── simulation_kpis.json
└── simulation_timeline.csv

### Dependencies

pip install simpy

### How to Run (after Phase 2 built)

python -m src.simulation.simpy_runner

Runtime: ~30 sec (much faster than solve).

### Deliverable

"The schedule produced by CP-SAT maintains X% on-time (±5 min) up to Y minutes of std delay, and degrades to Z% at W minutes."

---

## Phase 3 — Crew Scheduling ⏳

**Purpose:** Given fixed 408-trip schedule, assign 60 drivers to trips respecting duty-hour, rest, and weekly rest rules.

### Data

    data/synthetic/drivers.csv — 60 drivers [SYNTHETIC]

### Constraints (C1–C6, all [SYNTHETIC])

ID	Rule
C1	All Blue Line qualified
C2	Max duty 8 hours/day
C3	Min rest 12 hours
C4	Max continuous driving 4 hours
C5	Weekly rest ≤ 6 working days
C6	No driver overlap

### Approach

Once trips are fixed, crew assignment is a smaller subproblem. ~21 drivers minimum (408 trips / 20 trips per driver), 60 available gives slack.

### Files

solver/crew_models.py
solver/crew_constraints.py
solver/crew_solve.py
solver/crew_validator.py
data/synthetic/drivers.csv

Note: 60 drivers is ~3× the minimum. Phase 3 becomes fairness optimization, not feasibility. Consider reducing pool to ~30 for a more interesting problem.

---

## Phase 4 — Explainability ⏳

**Purpose:** Translate CP-SAT decisions into human-readable rationale. Why did the solver choose rake R007 for trip T0012?

### Approach

For each assignment, identify binding constraints (which would be violated if changed) and emit rationale.

### Files

src/explainability/
├── rule_tracer.py
└── report.py

### Deliverable

Per-trip rationale report showing which constraint drove each assignment.

---

## Phase 5 — Near-Real-Time Re-Optimization ⏳

**Purpose:** Re-solve in 1–2 min (not 5) when disruption occurs.

### Honest Scope

Real-time (< 30s) requires decomposition beyond project scope. Near-real-time (1–2 min) is achievable via warm-start.

### Approach

    Feed previous FEASIBLE solution as hint

    Add constraint: minimize deviation from previous schedule

    Compare new vs old

### Files

src/realtime/
├── event_bus.py
├── warm_start.py
└── compare.py

### Deliverable

"Given a mid-day disruption, produce a new schedule in ≤2 min that completes remaining trips with minimal deviation."

---

## Phase 6 — ML Layer (Optional) ⏳

**Purpose:** Predict running times from historical data, feed into CP-SAT. NOT mandatory.

### Scope

Only if historical KMRL delay data available. Predicts running time / delay, not demand.

### Files

src/ml/
├── train.py
└── predict.py

Per requirement doc: "ML forecasting is NOT a prerequisite." CP-SAT works without it. XGBoost is a refinement.

---

## Phase 7 — UI + Demo ⏳

**Purpose:** Streamlit dashboard for demo.

### Files

src/ui/
└── app.py

### Screens

    Schedule view (408 trips)

    KPI cards (on-time %, violations)

    Robustness chart (delay sweep)

    Rake utilization bar chart

### Dependencies

pip install streamlit

### Run

streamlit run src/ui/app.py

---

## Dependencies Between Phases

Phase 0 (setup) ✅
    ↓
Phase 1 (train scheduling) ✅
    ↓
    ├── Phase 1.5 (refinements) [optional]
    ↓
Phase 2 (SimPy validation) ← NEXT
    ↓
Phase 3 (crew scheduling)
    ↓
Phase 4 (explainability)
    ↓
Phase 5 (near-real-time)
    ↓
Phase 6 (ML, optional)
    ↓
Phase 7 (UI)

Critical path: 1 → 2 → 3 → 4 → 5. Phases 6 and 7 are parallel branches.

## Summary Table

| Phase | Content | Duration | Key Deliverable |
|-------|---------|----------|-----------------|
| 0 | Setup | 2 days | Venv, Git, folder structure |
| 1 | Train scheduling | 2 weeks | 408-trip valid schedule |
| 1.5 | Refinements | 3–5 days | R13, R14, traffic spare activation |
| 2 | SimPy validation | 1 week | Robustness KPIs |
| 3 | Crew scheduling | 1 week | 60 drivers on 408 trips |
| 4 | Explainability | 1 week | Per-trip rationale |
| 5 | Near-real-time | 1 week | Warm-start re-optimize |
| 6 | ML (optional) | 1 week | XGBoost predictions |
| 7 | UI | 3–5 days | Streamlit dashboard |

**Full project:** ~2 months. **Minimum viable (1+2):** ~3 weeks.

## Handoff Prompt (for new chat)

> *"I'm working on MetroPulse, a DPR-driven CP-SAT scheduler for KMRL Phase-II. Phase 1 is complete — 408-trip valid schedule with 10/10 validator checks. See docs/constraints-v2.md for the spec and docs/phases.md for the roadmap. I want to work on Phase 2 (SimPy validation). Read constraints-v2.md §11 for the full Phase 2 design. The src/simulation/ folder is empty — that's where Phase 2 goes. Ask me clarifying questions before writing code."*