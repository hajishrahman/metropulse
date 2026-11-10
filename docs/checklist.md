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

## Phase 2 — SimPy Validation ✅ COMPLETE

### Pre-flight
- [x] Schedule inspected: 250 trips, 18 rakes, 232 eligible trips
- [x] Preflight check (`src/simulation/preflight.py`) — continuity, slack, headways
- [x] Known limitation: terminal continuity not verifiable (no GTFS↔`Txxxx` map); Phase 2 models delay flow, not physical route movement

### Code
- [x] `src/simulation/__init__.py`
- [x] `src/simulation/schedule_loader.py` — strict CSV loader (parsing guards, count cross-check)
- [x] `src/simulation/reference.py` — closed-form recurrence (correctness baseline)
- [x] `src/simulation/simpy_runner.py` — SimPy per-rake process
- [x] `src/simulation/kpis.py` — pure KPI functions (no SimPy import)
- [x] `src/simulation/experiments.py` — E1–E4 + Monte Carlo runner
- [x] Install simpy (4.1.1)

### Model
- [x] Delay distribution: clipped normal (mean −48s pre-clip, std swept, clip [0, 300s])
- [x] Rounding rule: clip-then-round (documented, one shared function)
- [x] Propagation: Option A (wait for previous + 5-min turnaround)
- [x] Common random numbers: one `z` per trip, seed 42, same draws across stds
- [x] Monte Carlo: 100 seeds (42–141), mean + p5–p95 band
- [x] KPIs: on-time % at ±1/±3/±5 (dual denominator 250 / 232), propagation %, total propagated delay, headway violations (actual + scheduled)

### Tests
- [x] `tests/test_reference.py` — 8 tests
- [x] `tests/test_schedule_loader.py` — 24 tests
- [x] `tests/test_simpy_matches_reference.py` — 9 tests (parity proof, all 4 stds)
- [x] `tests/test_kpis.py` — 14 tests
- [x] **Total: 55 tests passing**

### Results (headline seed 42)
- [x] E1: 100% on-time, 0% propagation
- [x] E2: 100% on-time ±5, 3.88% propagation, 2.4 min total propagated
- [x] E3: 100% on-time ±5, 7.76% propagation, 19.3 min total propagated
- [x] E4: 100% on-time ±5, 11.64% propagation, 63.2 min total propagated
- [x] 100-seed Monte Carlo: E4 mean propagation 13.12% (p5–p95: 10.3–15.9%)
- [x] Scheduled headway violations = 0 at every std (R2a holds)
- [x] ±5 on-time structurally protected under the model (own-delay cap + slack); **not** an operational guarantee

### Outputs
- [x] `data/processed/simulation_kpis.json` (headline + 100-seed aggregate + metadata)
- [x] `data/processed/simulation_timeline.csv` (1000 rows: 4 experiments × 250 trips)
- [x] All delay values tagged `[SYNTHETIC]` in metadata
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