# MetroPulse — Development Checklist

Progress tracker for the project. Update as phases complete.

---

## Phase 0 — Setup

- [x] Python installed (venv currently Python 3.12; earlier checklist said 3.11 — update if reinstalling)
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

## Phase 1 — Train Scheduling (CP-SAT) ✅ COMPLETE (rebuilt on real GTFS trips)

### Source of Truth
- Real data from **GTFS** (2024-25 feed) + **KMRL Annual Report 2024-25** + **news article 2026**
- DPR values removed (10.715 km, 18.91 min, 408 trips, 3-min turnaround) — replaced with verified sources
- Solver now uses **real GTFS trip records**, not hourly counts and not synthetic `T0000` trips

### Data pipeline
- [x] `data/raw/` GTFS feed in place (validity 2024-08-12 → 2025-12-31)
- [x] `data/extract_gtfs_trips.py` — extracts per-trip records from GTFS
  - [x] `data/trips_full_route.csv` — **232** full-route ALVA↔TPHT trips
  - [x] `data/stop_sequences_full_route.csv` — full stop sequences for those 232
  - [x] `data/trips_partial.csv` — **18** partial trips (Muttom ↔ terminals)
  - [x] `data/stop_sequences_partial.csv` — stop sequences for the 18
- [x] `data/verify_gtfs_trips.py` — independent audit; reconciles 232 + 18 = 250 against `hourly_service.csv` (reconciliation reference only; not read by the solver)
- [x] `data/merge_trips.py` — merges the two into `data/trips_all.csv` (**250** trips)
- [x] Route length: **28.144 km** (Annual Report)
- [x] Synthetic generator (`data/generate_synthetic_v2.py`) → 25 rakes
  - [x] **18 service** rakes: **9 at ALVA, 7 at TPHT, 2 at MUTTOM** `[SYNTHETIC]`
  - [x] **7 maintenance** rakes at MUTTOM
- [x] Per-trip GTFS duration used directly by the solver (no fixed 50.47-min constant)
- [x] `python -m src.simulation.preflight` — 250 trips, 18 rakes, 232 eligible; 67 non-alternating rake pairs (MUTT/partial-trip artefact, not an error); 3 scheduled headway violations (GTFS fact)

### Model
- [x] Config with verified sources and synthetic tags (`solver/config.py`)
- [x] ProblemData loader for `trips_all.csv` (`solver/models.py`)
- [x] CP-SAT constraints R1–R12 (`solver/constraints.py`)
  - [x] R1 service coverage
  - [x] R3 operating window (06:00 ≤ departure < 23:00)
  - [x] R4 fleet availability (service rakes only)
  - [x] R5 rake non-overlap
  - [x] R6 turnaround + deadhead — **per-order gap** (same-terminal 5 min; cross-terminal 15 min; **order-aware**, see Findings)
  - [x] R7 running time — real per-trip GTFS duration
  - [x] R8 depot capacity — SKIPPED (no stabling in V1)
  - [x] R9 maintenance exclusivity — vacuous (`maintenance.csv` empty)
  - [x] R10 maintenance threshold
  - [x] R11 terminal continuity — first-trip home rule with deadhead allowance
  - [x] R12 non-service window
- [x] CP-SAT solve pipeline (`solver/solve.py`) — O6 rake-balance objective active
- [x] Independent validator (`solver/validator.py`) — 10 PASS + 1 SKIPPED (R8)

### Results (Phase 1, objective active)

- [x] Full-day solve: **250 trips, OPTIMAL, 11.77 s**
- [x] **Objective = 4800.0** (O6 rake balance, `W_RAKE_BALANCE × OBJ_SCALE × sum(dev) = 3 × 100 × 16`)
- [x] **Best bound = 4800.0** (proven optimal)
- [x] **Gap = 0.0%**
- [x] Rake distribution: 16 rakes × 14 trips, 2 rakes × 13 trips = 250 (sum of |count−13| = 16)
- [x] `[r6]` pruning: `same=15636 cross=17633 | both_impossible=3540 one_way=27585 both_possible=0`
- [x] Validator: **10 PASS + 1 SKIPPED (R8), Overall PASS**
- [x] Both baselines proven OPTIMAL:
  - [x] **232 full-route only** — OPTIMAL, ~28.7 s (feasibility probe, no objective)
  - [x] **250 full + partial** — OPTIMAL, 11.77 s with O6 objective active (current baseline)
- [x] Outputs written:
  - [x] `data/processed/schedule.csv`
  - [x] `data/processed/solution.json`
  - [x] `data/processed/validation.json`

### Findings (Phase 1 rebuild)

- `[FINDING]` **`add_obj6_rake_balance` must be called alongside `build_objective`.** When both are present, the model is OPTIMAL with objective 4800 in 11.77 s. Earlier attempts to call `add_obj6_rake_balance` without `build_objective` produced mixed results in the prior code state; the exact cause was not conclusively diagnosed. **Current committed code calls both together; this is the correct configuration.**

- `[FINDING]` **R6 requires per-order gap values.** Prior R6 chose one gap per pair (5 min if either order was same-terminal). For the 250-trip case, this allowed cross-terminal switches (ALVA↔MUTT, TPHT↔MUTT) with gaps between 5 and 15 min. The validator caught 4 such violations (R6 FAIL). Fixed by computing `gap_ab` and `gap_ba` independently and enforcing each in the correct order.
- `[FINDING]` **Fleet-size behaviour:**
  - 232 trips with 18 rakes, 9 ALVA / 9 TPHT, hard continuity + 15-min terminal deadhead → OPTIMAL
  - 250 trips with 18 rakes, 9/9 split → INFEASIBLE (needs MUTT-origin coverage)
  - 250 trips with 18 rakes, **9/7/2 split** → OPTIMAL
  - Adding more rakes (20, 22) does **not** fix the 250-trip case if the split does not include MUTTOM-origin rakes.
- `[FINDING]` **DPR-based values fully removed.** The old (pre-rebuild) 250-trip result (~306 s, FEASIBLE, 93.4% gap) is superseded and no longer applies.

---

## Phase 2 — SimPy Validation ✅ COMPLETE (rebuilt 2026-11-12)

### Code
- [x] `src/simulation/__init__.py`
- [x] `src/simulation/schedule_loader.py` — strict loader, per-trip `duration_sec`, sane range guard `[300, 4500]` s
- [x] `src/simulation/reference.py` — closed-form recurrence; per-trip duration; `RUNNING_SEC` kept as deprecated legacy
- [x] `src/simulation/simpy_runner.py` — SimPy per-rake process, per-trip `duration_sec`
- [x] `src/simulation/kpis.py` — pure KPI functions
- [x] `src/simulation/experiments.py` — E1–E4 + Monte Carlo runner; metadata reflects per-trip durations
- [x] `src/simulation/preflight.py` — read-only continuity/slack/headway analysis
- [x] `src/simulation/check_terminals.py` — read-only helper
- [x] SimPy 4.1.1

### Model
- [x] Delay: clipped normal, pre-clip mean −48 s, std 0/60/120/300 s, clip [0, 300] s `[SYNTHETIC]`
- [x] Clip-then-round (half-to-even)
- [x] Propagation: wait for previous trip + 5-min turnaround
- [x] Common random numbers: one `z` per trip, seed 42
- [x] Monte Carlo: 100 seeds (42–141)
- [x] KPIs: on-time ±5/±3/±1 (dual denominator 250 / 232), propagation %, total propagated delay, headway violations (actual + scheduled)

### Tests (59 total, all pass in 0.69 s)
- [x] `test_reference.py` — 7
- [x] `test_schedule_loader.py` — 29
- [x] `test_simpy_matches_reference.py` — 9
- [x] `test_kpis.py` — 14
- [x] **Total: 59 passed**

### Headline results (seed 42, 250-trip real schedule)
- E1: 100% ±5, 0.00% propagation, 3 scheduled headway violations
- E2: 100% ±5, 0.86% propagation, 3 scheduled headway violations
- E3: 100% ±5, 3.02% propagation, 4 actual headway violations
- E4: 100% ±5, 6.47% propagation, 4 actual headway violations

### 100-seed Monte Carlo (mean)
- E1: ±5=100.00, ±3=100.00, ±1=100.00, prop=0.00%
- E2: ±5=100.00, ±3=100.00, ±1=96.29, prop=1.10%
- E3: ±5=100.00, ±3=97.00, ±1=80.45, prop=2.43%
- E4: ±5=100.00, ±3=75.95, ±1=60.84, prop=5.88%

### Outputs
- [x] `data/processed/simulation_kpis.json` — regenerated 2026-11-12
- [x] `data/processed/simulation_timeline.csv` — **1000 rows** (250 trips × 4 experiments), regenerated 2026-11-12

### Notes
- **3 scheduled same-direction pairs at 0 s gap** in raw GTFS (data fact, not bug). R2 removed in v2.1.
- Real GTFS schedule has **less** propagation than the old synthetic one.
- ±5 on-time 100% is a **model property** (own-delay cap 300 s, inclusive), not an operational guarantee.
- All Phase 2 delay values are `[SYNTHETIC]`.

---

## Phase 3 — Crew Scheduling
- [ ] `data/synthetic/drivers.csv` (55 drivers D001–D055 `[SYNTHETIC]`; solver tests pool sizes 45/50/55)
- [ ] `solver/crew_config.py` (constants, POOL_SIZES = [45, 50, 55])
- [ ] `solver/crew_models.py` (crew ProblemData loader)
- [ ] `solver/crew_constraints.py` (C1–C7)
- [ ] `solver/crew_solve.py`
- [ ] `solver/crew_validator.py`
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