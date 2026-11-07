# MetroPulse — Development Checklist

Progress tracker for the project. Update as phases complete.

---

## Phase 0 — Setup

- [x] Python 3.11 installed
- [x] VS Code + Python extension installed
- [x] Project folder created
- [x] Virtual environment activated
- [x] `requirements.txt` installed
- [x] `.gitignore` created
- [x] `.gitkeep` files added
- [x] Git initialized + pushed to GitHub
- [x] GTFS data in `data/raw/`
- [x] `docs/meeting-log.md` created

---

## Phase 1 — Train Scheduling (CP-SAT) ✅ COMPLETE

### Source of Truth
- Real data from **GTFS** (2024-25 feed) + **KMRL Annual Report 2024-25** + **news article 2026**
- DPR values removed (10.715 km, 18.91 min, 408 trips) — replaced with verified sources

### Data pipeline
- [x] GTFS hourly extraction (`data/extract_gtfs_hourly.py`) → 250 weekday trips, 06:00–23:00
- [x] GTFS-derived running time: **50.47 min** (median of 412 trips)
- [x] Route length: **28.144 km** (Annual Report)
- [x] Synthetic generator (`data/generate_synthetic_v2.py`) → 25 rakes (18 service + 7 maintenance)

### Model
- [x] Config with verified sources (`solver/config.py`)
- [x] ProblemData loader (`solver/models.py`)
- [x] CP-SAT constraints R1–R12 (`solver/constraints.py`)
- [x] CP-SAT solve pipeline with optimality gap printout (`solver/solve.py`)
- [x] Independent validator (`solver/validator.py`) — 10 checks

### Results
- [x] Full-day solve: **250 trips, FEASIBLE, ~306s**
- [x] Validator: **9 PASS + 1 SKIPPED, Overall PASS**
- [x] Optimality gap reported
- [x] 15-rake feasibility test: **FEASIBLE** (proved traffic spare not required — now folded into 18 service rakes)
- [x] R8/R10/R12 validator checks added (10 of 12 constraints covered)

### Cleanup
- [x] Removed DPR hourly CSV (`data/dpr/hourly_service.csv`)
- [x] GTFS validator module (`src/gtfs_validation.py`) — validates DPR-adjacent values against real GTFS
- [x] Committed 250-trip schedule for Phase 2

---

## Phase 2 — SimPy Validation (NEXT)

- [ ] `src/simulation/__init__.py`
- [ ] `src/simulation/simpy_runner.py`
- [ ] `src/simulation/kpis.py`
- [ ] Install simpy
- [ ] Delay distribution: clipped normal (mean -48s pre-clip, std 60s, clipped [0, 300s])
- [ ] Propagation: Option A (waits for previous trip + 5-min turnaround)
- [ ] KPIs: propagated delay minutes, share delayed by propagation, on-time % at ±1/±3/±5, headway violations
- [ ] Scenario sweep: std = 0, 60, 120, 300 s
- [ ] Outputs: `simulation_kpis.json`, `simulation_timeline.csv`

---

## Phase 3 — Crew Scheduling

- [ ] `data/synthetic/drivers.csv` (60 drivers `[SYNTHETIC]`)
- [ ] `solver/crew_constraints.py` (C1–C6)
- [ ] `solver/crew_solve.py`
- [ ] Fairness objective

---

## Phase 4 — Explainability

- [ ] `src/explainability/rule_tracer.py`
- [ ] Per-trip rationale report

---

## Phase 5 — Near-Real-Time Re-Optimization

- [ ] `src/realtime/warm_start.py`
- [ ] Target: 1–2 min re-solve

---

## Phase 6 — ML Layer (Optional)

- [ ] `src/ml/train.py` (only if historical data available)

---

## Phase 7 — UI

- [ ] `src/ui/app.py` (Streamlit dashboard)