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
- [x] `data/verify_gtfs_trips.py` — independent audit; all checks pass (232 + 18 = 250 reconcile against old hourly CSV)
- [x] `data/merge_trips.py` — merges the two into `data/trips_all.csv` (**250** trips)
- [x] Route length: **28.144 km** (Annual Report)
- [x] Synthetic generator (`data/generate_synthetic_v2.py`) → 25 rakes
  - [x] **18 service** rakes: **9 at ALVA, 7 at TPHT, 2 at MUTTOM** `[SYNTHETIC]`
  - [x] **7 maintenance** rakes at MUTTOM
- [x] Per-trip GTFS duration used directly by the solver (no fixed 50.47-min constant)

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
  - [x] R9 maintenance exclusivity — vacuous (maintenance.csv empty)
  - [x] R10 maintenance threshold
  - [x] R11 terminal continuity — first-trip home rule with deadhead allowance
  - [x] R12 non-service window
- [x] CP-SAT solve pipeline (`solver/solve.py`) — feasibility probe (objective disabled)
- [x] Independent validator (`solver/validator.py`) — 10 checks + 1 SKIPPED (R8)

### Results (Phase 1 baseline)
- [x] Full-day solve: **250 trips, OPTIMAL, 28.73 s**
- [x] `[r6]` pruning: `same=15636 cross=17633 | both_impossible=3540 one_way=27585 both_possible=0`
- [x] Validator: **10 PASS + 1 SKIPPED (R8), Overall PASS**
- [x] Both baselines proven OPTIMAL:
  - [x] **232 full-route only** — OPTIMAL ~29 s
  - [x] **250 full + partial** — OPTIMAL ~28.7 s (current baseline)
- [x] Outputs written:
  - [x] `data/processed/schedule_250_trips.csv`
  - [x] `data/processed/solution_250_trips.json`
  - [x] `data/processed/validation_250_trips.json`

### Tagged synthetic values
- `[SYNTHETIC]` Terminal turnaround: **5 min**
- `[SYNTHETIC]` Terminal-to-terminal deadhead: **15 min**
- `[SYNTHETIC]` MUTTOM ↔ terminal deadhead: **8 min**
- `[SYNTHETIC]` Initial split: **9 ALVA / 7 TPHT / 2 MUTTOM**
- `[SYNTHETIC]` Maintenance threshold: **1,000,000 km**
- `[SYNTHETIC]` Info Park-2 capacity: **2**
- `[SYNTHETIC]` Initial rake mileage: 20,000–200,000 km

### Findings (Phase 1 rebuild)
- `[FINDING]` **`add_obj6_rake_balance` can make the model INFEASIBLE when the objective is disabled.** With `build_objective` commented out but `add_obj6_rake_balance` still called, the 250-trip case returns INFEASIBLE in ~10–17 s. Commenting out the `o6` call entirely → OPTIMAL in 28 s. Cause: free auxiliary `dev` variables without an objective. **Never call `add_obj6_rake_balance` without `build_objective`.**
- `[FINDING]` **R6 requires per-order gap values.** Prior R6 chose one gap per pair (5 min if either order was same-terminal). For the 250-trip case, this allowed cross-terminal switches (ALVA↔MUTT, TPHT↔MUTT) with gaps between 5 and 15 min. The validator caught 4 such violations (R6 FAIL). Fixed by computing `gap_ab` and `gap_ba` independently and enforcing each in the correct order.
- `[FINDING]` **Fleet-size behaviour:**
  - 232 trips with 18 rakes, 9 ALVA / 9 TPHT, hard continuity + 15-min terminal deadhead → OPTIMAL
  - 250 trips with 18 rakes, 9/9 split → INFEASIBLE (needs MUTT-origin coverage)
  - 250 trips with 18 rakes, **9/7/2 split** → OPTIMAL
  - Adding more rakes (20, 22) does **not** fix the 250-trip case if the split does not include MUTTOM-origin rakes.
- `[FINDING]` **DPR-based values fully removed.** Old 250-trip result (~306 s, FEASIBLE, 93.4% gap) is superseded.

---

## Phase 2 — SimPy Validation ⚠ STALE (needs rebuild on new schedule)

The **code** is complete and its **55 tests pass**. The **outputs** were computed on the OLD synthetic 250-trip schedule (trip IDs `T0000…`), not the rebuilt real-GTFS schedule (`WK_*`). They must be regenerated.

### Code (unchanged, still correct)
- [x] `src/simulation/__init__.py`
- [x] `src/simulation/schedule_loader.py`
- [x] `src/simulation/reference.py`
- [x] `src/simulation/simpy_runner.py`
- [x] `src/simulation/kpis.py`
- [x] `src/simulation/experiments.py`
- [x] `src/simulation/preflight.py`
- [x] SimPy 4.1.1 installed

### Model (unchanged)
- [x] Delay distribution: clipped normal (pre-clip mean −48 s, std swept, clip [0, 300 s]) `[SYNTHETIC]`
- [x] Clip-then-round (half-to-even)
- [x] Propagation: wait for previous trip + 5-min turnaround
- [x] Common random numbers: one `z` per trip, seed 42
- [x] Monte Carlo: 100 seeds (42–141)
- [x] KPIs: on-time ±1/±3/±5 (dual denominator), propagation %, total propagated delay, headway violations

### Tests (unchanged)
- [x] `tests/test_reference.py` — 8
- [x] `tests/test_schedule_loader.py` — 24
- [x] `tests/test_simpy_matches_reference.py` — 9
- [x] `tests/test_kpis.py` — 14
- [x] **Total: 55 tests passing**

### STALE outputs (must be regenerated)
- [ ] `data/processed/simulation_kpis.json` — currently from old 250 synthetic trips; **regenerate**
- [ ] `data/processed/simulation_timeline.csv` — currently from old synthetic schedule; **regenerate**
- [ ] Pre-flight limitation "terminal continuity not verifiable" — **no longer true**; real `WK_*` IDs used; R11 validated PASS in Phase 1; update this section after rebuild

### Rebuild steps (next)
- [ ] Run `python -m src.simulation.preflight` against `data/processed/schedule.csv` (new 250-trip real-GTFS schedule)
- [ ] Run `python -m src.simulation.experiments` to regenerate KPIs and timeline
- [ ] Verify output row count: 4 experiments × 250 trips = 1000 rows
- [ ] Update results section with new numbers (do not reuse old seed-42 figures)

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