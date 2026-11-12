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

## Phase 3 — Crew Scheduling ✅ COMPLETE (2026-11-13)

### Code (new files only — Phase 1 and Phase 2 untouched)
- [x] `data/generate_drivers.py` — generates 55 synthetic drivers `[SYNTHETIC]`
- [x] `data/synthetic/drivers.csv` — **55 drivers D001–D055**, `driver_id` column only in V1 (qualification / availability / shift_preference / weekly_availability **deferred to V2** — same honesty pattern as C5)
- [x] `solver/crew_config.py` — constants, `POOL_SIZES = [45, 50, 55]`, all `[EXTERNAL]`/`[DERIVED]`/`[SYNTHETIC]` tagged
- [x] `solver/crew_models.py` — `CrewProblemData` loader (reads `schedule.csv` + `drivers.csv`)
- [x] `solver/crew_constraints.py` — C1–C4 hard, C6 state-machine soft, C7 soft
- [x] `solver/crew_solve.py` — CP-SAT, loops over `POOL_SIZES`, writes both outputs
- [x] `solver/crew_validator.py` — independent C1–C4 + C7 checks per pool
- [x] `solver/crew_diag.py` — temporary diagnostic (delete after Phase 3 sign-off)

### Constraints
- [x] C1 no overlap (arrival + 5-min turnaround ≤ next departure)
- [x] C2 max active duty (`last_arr − first_dep ≤ 28,800 s`)
- [x] C3 sign-on / sign-off buffers (≥ 900 s each side)
- [x] C4 full coverage (250/250 trips assigned exactly once)
- [x] C5 min rest 12 h — **DEFERRED, not exercised in single-day V1**; no code, no validator check
- [x] C6 continuous driving ≤ 5 h (soft) — state-machine, spec-compliant, 6 vars per `(d,i)`; break threshold reuses `MIN_TURNAROUND_SEC` `[DERIVED from C1]`
- [x] C7 reserve ≥ 5 drivers (soft) — penalize use > `pool_size − 5` drivers; validator WARNs if exceeded

### Results (all three pool sizes OPTIMAL)
- [x] **pool=45:** OPTIMAL, 57.25 s, **active=40, reserve=5**, objective=0.0, gap=0.0%
- [x] **pool=50:** OPTIMAL, 58.80 s, **active=45, reserve=5**, objective=0.0, gap=0.0%
- [x] **pool=55:** OPTIMAL, 64.34 s, **active=50, reserve=5**, objective=0.0, gap=0.0%
- [x] C6 penalty = 0 across all pools (no driver exceeded 5 h continuous driving)
- [x] C7 penalty = 0 across all pools (reserve held at 5 everywhere)
- [x] CP-SAT non-determinism note: with `num_search_workers = 4`, solve results may vary between runs. Documented, not hidden.

### Validator (independent of solver)
- [x] **pool=45:** C1 PASS, C2 PASS, C3 PASS, C4 PASS, C7 PASS → **pool PASS**
- [x] **pool=50:** C1 PASS, C2 PASS, C3 PASS, C4 PASS, C7 PASS → **pool PASS**
- [x] **pool=55:** C1 PASS, C2 PASS, C3 PASS, C4 PASS, C7 PASS → **pool PASS**
- [x] **Overall: PASS**

### Outputs
- [x] `data/processed/crew_schedule.csv` — 750 rows (250 trips × 3 pools); columns: `trip_id, driver_id, sign_on, sign_off, pool_size`
- [x] `data/processed/crew_solution.json` — all 3 runs keyed by `"45"` / `"50"` / `"55"`
- [x] `data/processed/crew_validation.json` — per-pool checks + `overall: PASS`

### Bugs found and fixed during the build
- `[FINDING]` **C6 first formulation was O(n²)** (~3.4M vars). Caught before writing. Reworked to state-machine (6 vars per `(d,i)` ≈ 82,500 total new vars).
- `[FINDING]` **C6 chain-continuity bug** — initial state machine used `x[d,i−1] AND gap_ok`, which broke chains across trips assigned to other drivers. Reworked to `last_arr` carry-forward + `has_prev` bool.
- `[FINDING]` **C1 solver bug** — dead branches in `add_c1_no_overlap` forced "if first trip assigned, next trip not assigned" for *every* non-overlapping pair. Made model INFEASIBLE at all pools. Fixed to the single condition `if a.arr + turnaround > b.dep: x[a] + x[b] ≤ 1`.
- `[FINDING]` **C6 `new_chain = 0` bug** — gap constraint fired even when driver had no prior assignment, making full model INFEASIBLE. Fixed with `has_prev` bool guard.
- `[FINDING]` **Validator C1 bug** — compared driver-level `sign_on`/`sign_off` (constant per driver) instead of per-trip times, so C1 FAILed on every pair. Fixed by joining `crew_schedule.csv` trip_ids with `schedule.csv` to get per-trip departure/arrival.
- `[FINDING]` **Diagnostic-driven debugging** — `solver/crew_diag.py` isolated each constraint individually (C4-only, C4+C1, etc.) and caught both INFEASIBLE causes without guessing.

### Notes
- Handoff trust rule honored: Phase 1 docs treated as historical context only; actual code (`crew_*.py`) and actual data (`schedule.csv`, `drivers.csv`, `crew_*.json/csv`) are authoritative for this section.
- Do not reintroduce DPR values (10.715 km, 18.91 min, 408 trips, 3-min turnaround) — none present in Phase 3.
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