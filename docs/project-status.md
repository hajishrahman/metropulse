# MetroPulse — Current Project Status

**Last Updated:** 2026-11-08

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

## How to Run Phase 1

From a fresh PowerShell session:

```powershell

cd Z:\metropulse
.\venv\Scripts\Activate.ps1

python data\extract_gtfs_hourly.py
python data\generate_synthetic_v2.py
python -m solver.solve
python -m solver.validator

```
Expected output after solve: Status: FEASIBLE, Trips: 250.

Expected output after validate: Overall: PASS (9 PASS + 1 SKIPPED).

Output files:

    data/processed/schedule.csv — 250 scheduled trips

    data/processed/solution.json — solver result

    data/processed/validation.json — validator checks

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

Use the provided files as the primary source of truth. If something is missing or inconsistent, identify it instead of guessing.

First, summarize your understanding of the project and its current status. Do not modify any files until I give you the next task.