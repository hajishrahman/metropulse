# MetroPulse — Current Project Status

**Last Updated:** 2026-11-11

## Current Project Direction

MetroPulse is an AI-driven train induction planning and scheduling system for Kochi Metro Rail Limited (KMRL).

The project originally used DPR-based assumptions. Following the October 15, 2026 audit, the project was migrated to a verified-data approach using:

- KMRL GTFS static feed (2024–25)
- KMRL Annual Report 2024–25
- 2026 news article for fleet information
- Synthetic assumptions where verified operational data is unavailable

The original DPR-based specification has been superseded.

## Current Technology Stack

- Python
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

# Phase 1 — schedule
python data\extract_gtfs_hourly.py
python data\generate_synthetic_v2.py
python -m solver.solve
python -m solver.validator

# Phase 2 — simulation
python -m src.simulation.preflight
python -m src.simulation.experiments

# Tests
pytest tests\ -v
```
Expected output after solve: Status: FEASIBLE, Trips: 250.

Expected output after validate: Overall: PASS (9 PASS + 1 SKIPPED).

Expected after preflight: 250 trips, 18 rakes, 232 eligible; slack and headway summary.

Expected after experiments: "Loaded 250 trips, 18 rakes, 232 eligible." followed by headline summary table for E1–E4.

Expected after pytest: 55 passed.

Output files:

- `data/processed/schedule.csv` — 250 scheduled trips
- `data/processed/solution.json` — solver result
- `data/processed/validation.json` — validator checks
- `data/processed/simulation_kpis.json` — Phase 2 KPI results (headline + 100-seed aggregate + metadata)
- `data/processed/simulation_timeline.csv` — Phase 2 per-trip timeline (1000 rows: 4 experiments × 250 trips)

## Current Data Configuration

| Parameter | Current Value |
|---|---|
| GTFS feed | KMRL static GTFS, 2024–25 |
| Feed validity | 2024-08-12 to 2025-12-31 |
| Weekday trips in GTFS | 255 |
| Trips used by scheduler | 250 |
| Model operating window | 06:00–23:00 |
| Hourly buckets | 17 |
| Median one-way running time | 50.47 minutes |
| Model running time | 50 minutes (rounded from 50.47) |
| Route length | 28.144 km (Annual Report) |
| Total fleet | 25 rakes |
| Service rakes | 18 |
| Maintenance rakes | 7 |
| Turnaround time | 5 minutes (synthetic assumption) |
| Timezone | Asia/Kolkata |
| Initial rake mileage | 20,000–200,000 km (synthetic) |
| Info Park-2 capacity | 2 (synthetic assumption) |

## Latest Phase 1 Results

- Solver status: FEASIBLE
- Scheduled trips: 250
- Solve time: approximately 306 seconds
- Solver time limit: 300 seconds
- Objective value: 1,102,800
- Optimality gap: 93.40%
- Consecutive same-rake trip pairs: 232
- All 232 pairs satisfy the 5-minute turnaround requirement

### Validator Results

- PASS: 9
- SKIPPED: 1
- Overall status: PASS
- R8: Skipped because stabling assignments are not implemented in V1
- R9 and R11: Not included in current validation results

The FEASIBLE result does not mean the solution is proven optimal.

## Latest Phase 2 Results

- Simulation entry point: python -m src.simulation.experiments
- Trips: 250; rakes: 18; eligible for propagation: 232
- Delay model: clipped normal, pre-clip mean −48 s, std swept 0 / 60 / 120 / 300 s, clip [0, 300 s] — all [SYNTHETIC]
- Rounding rule: clip-then-round (Python round, half-to-even)
- Common random numbers: one z per trip, seed 42, shared across stds
- Monte Carlo: 100 seeds (42–141) per std, mean + p5–p95 band

### Headline (seed 42)

| Experiment | std (s) | ±5 on-time | Propagation % | Total propagated (min) | Headway violations (actual) |
|---|---:|---:|---:|---:|---:|
| E1 | 0 | 100.00% | 0.00% | 0.0 | 0 |
| E2 | 60 | 100.00% | 3.88% | 2.4 | 12 |
| E3 | 120 | 100.00% | 7.76% | 19.3 | 21 |
| E4 | 300 | 100.00% | 11.64% | 63.2 | 30 |

### 100-seed mean

| Experiment | ±5 on-time | ±3 on-time | ±1 on-time | Propagation % (mean; p5–p95) |
|---|---:|---:|---:|---:|
| E1 | 100.00% | 100.00% | 100.00% | 0.00% (0.00–0.00) |
| E2 | 100.00% | 100.00% | 95.26% | 6.34% (4.31–8.62) |
| E3 | 100.00% | 96.15% | 76.59% | 9.81% (6.90–12.07) |
| E4 | 100.00% | 71.57% | 55.81% | 13.12% (10.34–15.95) |


### Phase 2 key findings

- ±5 on-time = 100% throughout. Structural under the model (own delay capped at 300 s, ±5 inclusive, measured slack distribution). Model property, not operational guarantee.
- ±3 and ±1 show the propagation impact: at E4, 71.57% and 55.81%.
- Scheduled headway violations = 0 at every std (R2a holds). Actual-gap violations rise with std (0 → 33.3 mean at E4).
- All 55 tests passing across tests/test_reference.py, tests/test_schedule_loader.py, tests/test_simpy_matches_reference.py, tests/test_kpis.py.
- SimPy output asserted equal to closed-form reference bit-for-bit, all four stds.

### Phase 2 known limitations

- Terminal continuity not verifiable from Phase 1 outputs. No GTFS↔Txxxx mapping. 127 of 232 pairs show non-alternating UP/DOWN direction. Phase 2 models delay flow, not physical route movement. Deadhead not modeled (R11 not configured).
- All Phase 2 delay values are [SYNTHETIC]. Results describe model behaviour, not real KMRL performance.

## Important Code Locations

- `data/extract_gtfs_hourly.py` — extracts hourly service data from GTFS
- `data/generate_synthetic_v2.py` — generates synthetic rake data
- `solver/config.py` — solver configuration
- `solver/models.py` — project data models
- `solver/solve.py` — CP-SAT scheduling model
- `solver/validator.py` — independent schedule validation
- `data/processed/schedule.csv` — generated schedule
- `data/processed/solution.json` — solver result
- `data/processed/validation.json` — validation result
- `src/simulation/schedule_loader.py` — Phase 2 schedule loader (strict parsing)
- `src/simulation/reference.py` — Phase 2 closed-form recurrence
- `src/simulation/simpy_runner.py` — Phase 2 SimPy per-rake process
- `src/simulation/kpis.py` — Phase 2 KPI functions
- `src/simulation/experiments.py` — Phase 2 E1–E4 + Monte Carlo runner
- `src/simulation/preflight.py` — Phase 2 pre-flight check (read-only)
- `data/processed/simulation_kpis.json` — Phase 2 KPI results
- `data/processed/simulation_timeline.csv` — Phase 2 per-trip timeline

## GIVE THIS TO CHAT 

I am continuing development of MetroPulse, an AI-driven train induction planning and scheduling system for Kochi Metro Rail Limited (KMRL).

I have provided the project documentation, source code, data scripts and latest outputs.

Before suggesting changes or writing code:

1. Read all the provided documentation.
2. Inspect the existing source code.
3. Understand the current architecture and implementation.
4. Understand the completed phases and pending phases.
5. Check the actual implementation against the documentation.
6. Do not assume file paths, variable names or data formats.
7. Do not reintroduce superseded DPR-based assumptions.
8. Preserve existing working functionality.

Current phase status:

- Phase 0 (Setup): COMPLETED
- Phase 1 (CP-SAT train scheduling): COMPLETED
- Phase 2 (SimPy simulation): COMPLETED
- Phase 3 (Crew scheduling): NEXT

Phase 1 and Phase 2 facts — see sections above.

Rules specific to the current data:

- Do not reintroduce DPR values (10.715 km, 18.91 min, 408 trips, 3-min turnaround).

- Distinguish verified data from synthetic assumptions.

- The GTFS feed is 2024–25 static data, not a live 2026 timetable.

- All Phase 2 delay values are [SYNTHETIC]. Phase 2 results describe model behaviour, not real KMRL performance.

- Do not claim R9 and R11 passed validation. Phase 1 validator: 9 PASS + 1 SKIPPED (R8 skipped). R9 and R11 are not in the results.

- ±5 on-time 100% is a model property (own-delay cap 300 s, ±5 inclusive, measured slack), not an operational guarantee.

- Terminal continuity is not verifiable from Phase 1 outputs. Deadhead not modeled.

Use the provided files as the primary source of truth. If something is missing or inconsistent, identify it instead of guessing.

First, summarize your understanding of the project and its current status. Do not modify any files until I give you the next task.