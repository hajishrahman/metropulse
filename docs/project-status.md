# MetroPulse — Current Project Status

**Last Updated:** 2026-11-13

## Current Project Direction

MetroPulse is an AI-driven train induction planning and scheduling system for Kochi Metro Rail Limited (KMRL).

The project migrated to a verified-data approach on 2026-10-15 and was **rebuilt on real GTFS trip records on 2026-11-12**. The earlier synthetic-trip schedule (250 `T0000` trips, FEASIBLE, ~306 s, 93.4% gap) is superseded.

Sources of truth:
- KMRL GTFS static feed (2024-25) — real trip records
- KMRL Annual Report 2024-25 — route length, operating hours
- 2026 news article — fleet breakdown
- Synthetic assumptions where verified operational data is unavailable (clearly tagged)

## Current Technology Stack

- Python 3.12 (venv)
- pandas
- NetworkX
- SimPy
- Google OR-Tools CP-SAT
- Streamlit

## How to Run

From a fresh PowerShell session:

```powershell
cd Z:\metropulse
.\venv\Scripts\Activate.ps1

# Phase 1 — rebuild trip files (only if needed)
python data\extract_gtfs_trips.py
python data\verify_gtfs_trips.py
python data\merge_trips.py

# Phase 1 — synthetic fleet
python data\generate_synthetic_v2.py

# Phase 1 — solve and validate
python -m solver.solve
python -m solver.validator

# Phase 2 — regenerate outputs (only if needed)
python -m src.simulation.preflight
python -m src.simulation.experiments

# Phase 3 — generate drivers (one-time; deterministic)
python -m data.generate_drivers

# Phase 3 — solve all three pool sizes
python -m solver.crew_solve

# Phase 3 — validate crew assignments
python -m solver.crew_validator

# Tests
pytest tests\ -v

Expected outputs (Phase 1, current state):

python -m solver.solve → Status: OPTIMAL, Trips: 250, Objective: 4800.0, Gap: 0.0%, elapsed ~11.77 s

python -m solver.validator → Overall: PASS (10 PASS + 1 SKIPPED, R8 skipped)

pytest tests\ -v → 59 passed

Output files:

data/processed/schedule.csv — 250 scheduled trips
data/processed/solution.json — solver result
data/processed/validation.json — validator checks
data/processed/schedule_250_trips.csv — frozen 250-trip baseline
data/processed/solution_250_trips.json
data/processed/validation_250_trips.json
data/processed_backup/ — pre-rerun baseline snapshot (created 2026-11-12 before the objective restore; not part of the active pipeline)

Phase 3 output files:

data/processed/crew_schedule.csv — 750 rows (250 trips × 3 pools)
data/processed/crew_solution.json — all 3 runs keyed by "45" / "50" / "55"
data/processed/crew_validation.json — per-pool checks + overall PASS

Note on Phase 2: data/processed/simulation_kpis.json and simulation_timeline.csv were regenerated on 2026-11-12 on the 250-trip real-GTFS schedule.

Current Data Configuration
Parameter	Current Value
GTFS feed	KMRL static GTFS, 2024-25
Feed validity	2024-08-12 to 2025-12-31
Weekday trips in GTFS	255
Excluded by window (out-of-policy)	5 (WK_253, WK_4, WK_256, WK_12, WK_18)
Full-route trips (ALVA ↔ TPHT)	232
Partial trips (Muttom ↔ terminals)	18
Trips used by scheduler	250 (232 + 18)
Model operating window	06:00 ≤ departure < 23:00
Running time used by solver	Per-trip GTFS duration
Median one-way running time (summary only)	50.47 min
Route length	28.144 km (Annual Report)
Total fleet	25 rakes
Service rakes	18
Maintenance rakes	7
Initial rake split	9 ALVA / 7 TPHT / 2 MUTTOM [SYNTHETIC]
Turnaround time	5 min [SYNTHETIC]
Terminal ↔ terminal deadhead	15 min [SYNTHETIC]
MUTTOM ↔ terminal deadhead	8 min [SYNTHETIC]
Maintenance threshold	1,000,000 km [SYNTHETIC]
Info Park-2 capacity	2 [SYNTHETIC]
Initial rake mileage	20,000–200,000 km [SYNTHETIC]
Timezone	Asia/Kolkata
Latest Phase 1 Results (2026-11-12)
Solver status: OPTIMAL

Trips scheduled: 250 (232 full + 18 partial)

Rakes: 18 service (9 ALVA / 7 TPHT / 2 MUTTOM)

Solve time: 11.77 s

Solver time limit: 300 s

Objective: 4800.0 (O6 rake balance active — W_RAKE_BALANCE × OBJ_SCALE × Σ dev = 3 × 100 × 16)

Best bound: 4800.0 (proven optimal)

Optimality gap: 0.0%

Rake distribution: 16 rakes × 14 trips, 2 rakes × 13 trips = 250

R6 pruning: same=15636 cross=17633; both_impossible=3540 one_way=27585 both_possible=0

Validator Results
PASS: 10

SKIPPED: 1 (R8 — no stabling in V1)

FAIL: 0

Overall: PASS
```
R2 not applicable (fixed trip times). R9 vacuous (empty maintenance.csv). R11 validated. Objective O6 active — validator PASS confirms the optimized schedule still satisfies all hard constraints.


## Latest Phase 2 Results (2026-11-12, rebuilt on 250-trip real schedule)

The Phase 2 SimPy simulation was **rebuilt** on the new 250-trip schedule. `simulation_kpis.json` and `simulation_timeline.csv` now describe the current schedule.

- Loaded: 250 trips, 18 rakes, 232 eligible
- Timeline: 1000 rows (4 experiments × 250 trips)
- **Tests: 59 passed** (loader, reference, SimPy parity, KPIs)

### Headline (seed 42)

| Exp | std (s) | ±5 on-time 250 | ±5 on-time 232 | Propagation % | HW actual |
|---|---:|---:|---:|---:|---:|
| E1 | 0 | 100.00 | 100.00 | 0.00 | 3 |
| E2 | 60 | 100.00 | 100.00 | 1.72 | 3 |
| E3 | 120 | 100.00 | 100.00 | 4.74 | 4 |
| E4 | 300 | 100.00 | 100.00 | 7.33 | 4 |

*(These are the values in the current `data/processed/simulation_kpis.json`. If a future rerun produces a different OPTIMAL schedule, the numbers will shift — CP-SAT is non-deterministic with `num_search_workers > 1`. The JSON is authoritative.)*

### 100-seed Monte Carlo (mean, p5–p95)

| Exp | ±5 | ±3 (mean; p5–p95) | ±1 | Propagation % (mean; p5–p95) |
|---|---:|---|---:|---:|
| E1 | 100.00 | 100.00 (100.00–100.00) | 100.00 | 0.00 (0.00–0.00) |
| E2 | 100.00 | 100.00 (100.00–100.00) | 96.24 | 1.27 (0.00–2.59) |
| E3 | 100.00 | 96.93 (94.44–99.20) | 80.13 | 2.91 (1.29–4.74) |
| E4 | 100.00 | 75.47 (69.60–80.40) | 60.26 | 6.89 (4.31–9.48) |

*(Authoritative source: `data/processed/simulation_kpis.json`. Values are tied to the current schedule; a rerun of `solver.solve` will change the schedule and therefore these KPIs.)*

### Notes

- **3 scheduled same-direction pairs at 0 s gap** in the raw GTFS timetable (06:15, 08:00, 08:21). Each is a full trip (TPHT→ALVA) and a partial trip (MUTT→ALVA) departing the same minute on different rakes. Not a solver or simulation bug. R2a removed in v2.1 §5 because departure times are fixed by GTFS.
- E3/E4 show 4 actual violations (3 structural + 1 delay-induced).
- **Real GTFS schedule shows less propagation than the old synthetic one** (E4 mean 6.89% vs 11.64% before) because real slack is larger.
- All Phase 2 delay values are `[SYNTHETIC]`. Results describe model behaviour, not real KMRL performance.

## Latest Phase 3 Results (2026-11-13)

Phase 3 crew scheduling is **complete**. All 250 Phase 1 trips are assigned to SC/TO drivers at three pool sizes (45 / 50 / 55).

### Inputs

- `data/processed/schedule.csv` — 250 trips (Phase 1 output, read-only)
- `data/synthetic/drivers.csv` — 55 synthetic drivers `D001`–`D055`, `driver_id` column only `[SYNTHETIC]`

Fields `qualification`, `availability`, `shift_preference`, `weekly_availability` are **deferred to V2** — same honesty pattern as C5 (min rest).

### Constraints

- **C1** no overlap (`arr + 300 s ≤ next dep`) — hard
- **C2** max active duty (`last_arr − first_dep ≤ 28,800 s`) — hard
- **C3** sign-on / sign-off (≥ 900 s each side) — hard
- **C4** full coverage (250 / 250 trips) — hard
- **C5** min rest 12 h — **DEFERRED to V2**, no solver constraint, no validator check
- **C6** continuous driving ≤ 5 h — **soft**, weight 10; break threshold = `MIN_TURNAROUND_SEC` (300 s) `[DERIVED from C1]`
- **C7** reserve ≥ 5 drivers — **soft**, weight 15

### Results

| Pool | Status | Time | Active | Reserve | Objective | Gap |
|---|---|---:|---:|---:|---:|---:|
| 45 | **OPTIMAL** | 57.25 s | 40 | 5 | 0.0 | 0.0% |
| 50 | **OPTIMAL** | 58.80 s | 45 | 5 | 0.0 | 0.0% |
| 55 | **OPTIMAL** | 64.34 s | 50 | 5 | 0.0 | 0.0% |

### Validator (independent of solver)

- pool=45: C1 PASS, C2 PASS, C3 PASS, C4 PASS, C7 PASS → **pool PASS**
- pool=50: C1 PASS, C2 PASS, C3 PASS, C4 PASS, C7 PASS → **pool PASS**
- pool=55: C1 PASS, C2 PASS, C3 PASS, C4 PASS, C7 PASS → **pool PASS**
- **Overall: PASS**

### Notes

- **Objective = 0 at all pools.** The solver found schedules with zero C6 and C7 penalty. This proves the penalty term is zero; it does not prove no driver neared the 5-h chain limit. Individual chain lengths are in `crew_solution.json` under `assignments`.
- **C6 is implemented as a state machine** (6 vars per driver-trip pair, ~82,500 new vars total). An earlier O(n²) run-enumeration approach was rejected at ~3.4M vars.
- **CP-SAT is non-deterministic** with `num_search_workers = 4` — results may vary between runs. Documented, not hidden.
- **Handoff §8 success criteria — all met:** (1) all three pools FEASIBLE/OPTIMAL with 250 trips, (2) C1–C4 PASS independent validation, (3) sensitivity table across pool sizes reported, (4) all docs updated.

### Bugs found and fixed during Phase 3

1. `[FINDING]` **C6 first formulation was O(n²)** (~3.4M vars). Reworked to state machine.
2. `[FINDING]` **C6 chain-continuity bug** — initial version broke chains across trips assigned to other drivers. Reworked to `last_arr` carry-forward + `has_prev` bool.
3. `[FINDING]` **C1 solver bug** — dead branches forced wrong non-overlap rule, making model INFEASIBLE at all pools. Fixed to the single condition `if a.arr + turnaround > b.dep: x[a] + x[b] ≤ 1`.
4. `[FINDING]` **C6 `new_chain = 0` bug** — gap constraint fired with no prior assignment, making full model INFEASIBLE. Fixed with `has_prev` bool guard.
5. `[FINDING]` **Validator C1 bug** — compared driver-level sign-on/sign-off (constant per driver) instead of per-trip times. Fixed by joining `crew_schedule.csv` trip_ids with `schedule.csv`.

All five were caught by `solver/crew_diag.py` (temporary diagnostic) and by the independent validator — not by guesswork.

### Outputs

- `data/processed/crew_schedule.csv` — 750 rows (250 trips × 3 pools)
- `data/processed/crew_solution.json` — all 3 runs keyed by `"45"` / `"50"` / `"55"`
- `data/processed/crew_validation.json` — per-pool checks + `overall: PASS`

See `docs/phases.md` §Phase 3 for the full spec and `docs/constraints-crew-v1.md` for the detailed C1–C7 crew constraint spec.

### Next

Phase 4 — Explainability and Constraint Analysis.

