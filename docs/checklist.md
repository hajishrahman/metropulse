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

## Phase 1 — DPR-Driven Train Scheduling

- [x] Lock spec (`docs/constraints-v2.md`)
- [x] DPR-sourced `solver/config.py`
- [x] Clean-slate generator (`data/generate_synthetic_v2.py`)
- [x] DPR hourly plan (`data/dpr/hourly_service.csv`)
- [x] `ProblemData` loader (`solver/models.py`)
- [x] CP-SAT constraints R1–R12 (`solver/constraints.py`)
- [x] CP-SAT solve pipeline (`solver/solve.py`)
- [x] Full-day solve: 408 trips, FEASIBLE in ~317s
- [x] Independent validator (`solver/validator.py`)
- [x] All 7 validator checks PASS
- [x] DPR reference labels revised (`[DPR reference — unverified]`)
- [ ] Optimality gap printout in `solve.py` (Step 3)
- [ ] 15-rake feasibility test (Step 4)
- [ ] R8/R10/R12 validator checks (Step 5)

---

## Phase 2 — SimPy Validation (Next)

- [ ] `src/simulation/simpy_runner.py`
- [ ] `src/simulation/kpis.py`
- [ ] Delay distribution config in `config.py`
- [ ] Scenario sweep: std = 0, 60, 120, 300 s
- [ ] KPI report (`simulation_kpis.json`)

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