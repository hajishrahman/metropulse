# Data Provenance

Every parameter in MetroPulse is sourced and labeled.

| Tag | Meaning |
|---|---|
| `[EXTERNAL]` | External source (GTFS feed, Annual Report, news article) |
| `[DERIVED]` | Computed from an external source |
| `[SYNTHETIC]` | Project assumption; no verified source |
| `[MODEL LIMITATION]` | Deliberate model simplification |

**Rule:** No parameter is claimed as `[DPR]` because the DPR document is not present in the project. Previously DPR-based values were removed and replaced with values from available sources (see Section 4).

---

## 1. Primary Data Source — GTFS Feed

### Source

- **Provider:** Kochi Metro Rail Limited (KMRL)
- **URL:** https://kochimetro.org/
- **Retrieved:** 2026-09-27
- **Format:** GTFS Static
- **Feed version:** 1.0
- **Feed validity:** 2024-08-12 to 2025-12-31
- **Timezone:** Asia/Kolkata
- **Data vintage:** 2024–25 timetable; not current 2026 operations.

### Files Present (11)

**Required:**
- `agency.txt`
- `calendar.txt`
- `routes.txt`
- `stop_times.txt`
- `stops.txt`
- `trips.txt`

**Optional:**
- `fare_attributes.txt`
- `fare_rules.txt`
- `feed_info.txt`
- `shapes.txt`
- `translations.txt`

### What GTFS Provides to the Model

| Parameter | Value | How Derived |
|---|---:|---|
| Weekday trips used (total) | 250 | Filter `service_id=WK`, `06:00 ≤ departure < 23:00` |
| Full-route trips (ALVA ↔ TPHT) | 232 | First/last stop both are terminals |
| Partial trips (Muttom ↔ terminals) | 18 | First or last stop is MUTT |
| UP/DOWN split | 127 UP / 123 DOWN | Station-index from stop order (ALVA=0 … TPHT=24) |
| Per-trip running time | Real GTFS duration | Arrival − departure, per trip |
| One-way running time (median) | 50.47 min | Median over 412 full-route trips — **summary statistic only** |
| Route distance from GTFS shapes | Approximately 27.87 km | Final distance from `shapes.txt` |
| Model route length | 28.144 km | KMRL Annual Report 2024–25 |
| Stations | 25 | Count of distinct `stop_id` values in `stops.txt` |
| Hourly distribution | `data/hourly_service.csv` | Reconciliation only; not read by solver |

**Route length clarification:**
- GTFS shapes provide approximately 27.87 km.
- The Annual Report provides 28.144 km.
- The model uses 28.144 km from the Annual Report for length reporting. The schedule itself uses per-trip GTFS durations, not a global running-time constant.

### GTFS Handling

- **Extraction script:** `data/extract_gtfs_trips.py`
- **Outputs:**
  - `data/trips_full_route.csv` — 232 full-route trips
  - `data/stop_sequences_full_route.csv` — stop sequences for the 232
  - `data/trips_partial.csv` — 18 partial trips
  - `data/stop_sequences_partial.csv` — stop sequences for the 18
- **Merge script:** `data/merge_trips.py`
- **Solver input:** `data/trips_all.csv` — 250 trips (232 + 18)
- **Audit script:** `data/verify_gtfs_trips.py` — independently verifies the extraction and reconciles 232 + 18 = 250 against the untouched `hourly_service.csv`

**Filtering:** Of 255 weekday trips in `trips.txt`, 5 depart outside the model window:

- `WK_253`, `WK_4`, `WK_256`, `WK_12`, `WK_18`

These 5 trips are excluded by policy as non-passenger movements (times outside `06:00 ≤ departure < 23:00`).

**Direction identification:**

Direction is determined by **station index** from stop order (ALVA = 0 … TPHT = 24):

- `UP` = last station index > first station index
- `DOWN` = last station index < first station index

No fallback to `trips.txt direction_id`. Verified by `data/verify_gtfs_trips.py` (all 250 consistent with `direction_id`, but the model uses stop order).

### Known Quirks

- The `transfers` column in `fare_attributes.txt` is empty.
- Fare range: ₹10 (shortest) to ₹60 (Aluva ↔ Tripunithura).
- The feed ends on 2025-12-31 and represents the 2024–25 timetable, not current 2026 operations.
- Some raw `stop_times.txt` entries have times ≥ 24:00:00 (e.g., `24:03:45`), because they belong to the 5 excluded trips. These are parsed as `H*3600 + M*60 + S` without a day limit. Verified: none of the 250 trips in `trips_all.csv` have departure or arrival ≥ 24:00 (checked 2026-11-12).

### Git Strategy

- GTFS `.txt` files are excluded from Git through `.gitignore`.
- Source and setup instructions are stored in `data/raw/README.md`.
- Rationale: The feed is static, re-downloadable, and externally maintained by KMRL.

---

## 2. Secondary Data Source — KMRL Annual Report 2024–25

**Local copy:**

- `Z:\Hajish College\Major_project\KMRLGTFS2.md` (1.1 MB)
- Corresponding PDF: `KMRLGTFS2.pdf` (38.9 MB)

The file is named `KMRLGTFS2`, but it contains the **KMRL Annual Report 2024–25**, not GTFS data or a DPR.

### What It Provides

| Parameter | Value | Context |
|---|---:|---|
| Route length | 28.144 km | Annual Report corridor description |
| Trains operating | 15 | Report states 15 trains operating |
| Peak headway | 7 min 30 sec | Same source |
| Stations | 25 | Same source |
| Operating hours | 06:00–23:00 | KMRL published timetable |
| Punctuality rate | 99.98% | Annual Report KPIs |
| Ridership | 35.6 million passengers/year | Annual Report KPIs; reporting period should be confirmed |

**Important fleet discrepancy:**

The Annual Report says 15 trains are operating. The 18-operating figure comes from a separate 2026 news article (see Section 3).

These figures refer to different reporting periods and should not be treated as identical source data.

---

## 3. Tertiary Data Source — News Article (2026)

A 2026 news article reports the following fleet breakdown:

- **Total fleet:** 25 trains
- **Operating:** 18 trains
- **Maintenance rotation:** 7 trains

**Source:** [The New Indian Express — KMRL fleet and maintenance rotation, August 2026](https://www.newindianexpress.com/amp/story/cities/kochi/2026/Aug/23/kochi-metro-will-need-eight-more-trains-after-pink-line-completion-says-md-loknath-behera)

### Discrepancy Note

- Annual Report 2024–25: 15 trains operating.
- News article 2026: 18 trains operating and 7 in maintenance.

Both figures may reflect different operating periods.

**V1 model configuration:**

The model uses 18 service rakes and 7 maintenance rakes, following the 2026 news article's fleet breakdown.

The model also supports testing with a reduced service fleet, such as 15 rakes, to examine scheduling feasibility. Results must be taken from the corresponding solver run.

---

## 4. Removed from Scope — DPR Values

The project initially used values attributed to a DPR (Detailed Project Report). These values were removed because:

1. The DPR document was not actually present in the project.
2. Several values could not be independently verified.
3. GTFS and the KMRL Annual Report provide the available data for the current model.

### Removed DPR Values

| Old Value | Replacement Source | New Value |
|---|---|---|
| 10.715 km route length | Annual Report | 28.144 km |
| 18.91 min running time | GTFS median | 50.47 min |
| 408 trips/day | GTFS weekday data | 250 trips (232 full-route + 18 partial) |
| 18 rakes (15 + 1 + 2) | News article 2026 | 25 total (18 service + 7 maintenance) |
| 05:00–24:00 operating window | KMRL timetable | 06:00–23:00 |
| 3-min turnaround | Project assumption | 5 min `[SYNTHETIC]` |
| 420,000 km IOH threshold | Unverified | Removed |
| 1,000,000 km bogie threshold | Unverified | Retained as `[SYNTHETIC]` |
| Info Park-2 capacity = 2 | Unverified | Retained as `[SYNTHETIC]` |

**No DPR-based claims are intended to remain in the current project configuration.**

---

## 5. Fleet Sizing

### Fleet Distribution

| Metric | Value | Source |
|---|---:|---|
| Total fleet | 25 rakes | `[EXTERNAL — News 2026]` |
| Service rakes | 18 | `[EXTERNAL — News 2026]` |
| Maintenance rakes | 7 | `[EXTERNAL — News 2026]` |
| Separate standby rakes | 0 | No separate standby category in the synthetic fleet |

**Initial position split (fixed, not solver choice):**

| Location | Service rakes | Source |
|---|---:|---|
| ALVA | 9 | `[SYNTHETIC]` |
| TPHT | 7 | `[SYNTHETIC]` |
| MUTTOM | 2 | `[SYNTHETIC]` |

The MUTTOM assignment is required because 18 partial trips start or end at Muttom; without MUTTOM-origin rakes, the 250-trip case is INFEASIBLE (see `constraints-v2.1` Findings).

### Aggregate Fleet Capacity Estimate

The following is an **aggregate summary only**. It uses the 50.47-min median as a rough per-trip figure. The model itself uses per-trip GTFS durations.

- Required running time (rough estimate): 250 trips × 50.47 min = 12,617.5 train-minutes.
- Available running time: 18 rakes × 17 hours × 60 = 18,360 train-minutes.
- Estimated utilization: approximately 68.72%, rounded to 69%.

This is a planning estimate, not a proof of feasibility. Actual feasibility is determined by the CP-SAT solver and the independent schedule validator. 
The empirical result on the 250-trip case is **OPTIMAL under the O6 rake-balance objective** (objective 4800, gap 0%, 11.77 s; see constraints-v2.2 §6 and §11 Scenario A').

---

## 6. Synthetic Data

Synthetic data lives in `data/synthetic/`. All synthetic values are tagged `[SYNTHETIC]`.

### Files

| File | Rows | Content |
|---|---:|---|
| `rakes.csv` | 25 | Fleet status, mileage, and location (Phase 1) |
| `terminals.csv` | 2 | ALVA and TPHT with 5-minute turnaround (Phase 1) |
| `maintenance.csv` | 0 | Empty; no scheduled maintenance records (Phase 1) |
| `depot.csv` | 2 | Info Park-2 (capacity 2), Muttom (unbounded) (Phase 1) |
| `drivers.csv` | 55 | Crew IDs `D001`–`D055`, `driver_id` only (Phase 3) `[SYNTHETIC]` |

### Generated By — Phase 1 (train layer)

`data/generate_synthetic_v2.py`

- Deterministic generation.
- Random seed: `42`.

### Generated By — Phase 3 (crew layer)

`data/generate_drivers.py`

- Deterministic generation.
- No random seed — driver IDs are simply `D001` … `D055`.
- Output: `data/synthetic/drivers.csv` (55 rows, `driver_id` column only).

**Phase 3 driver schema (V1):**

```csv
driver_id
D001
D002
...
D055
```

Driver qualifications, availability, shift preferences, and weekly availability are **deferred to V2** — same honesty pattern as C5 (min rest). The V1 crew model uses `driver_id` only because C1–C4 need nothing else.

**Why 55, not 60?** KMRL has 60 SC/TO operators `[EXTERNAL — cited in handoff §1]`. The V1 model uses a synthetic 55-driver roster to test three daily-active pool sizes (45/50/55) against a controlled driver set. This is **not** a claim that KMRL has 55 drivers — it is a project assumption for testing. The 55 count is `[SYNTHETIC]`.

### Rake Schema

```csv
rake_id,status,initial_mileage_km,cmrs_status,initial_location,initial_available_time
R001,service,187621,valid,ALVA,06:00
...
R017,service,<mileage>,valid,MUTTOM,06:00
R018,service,<mileage>,valid,MUTTOM,06:00
R019,maintenance,<mileage>,valid,MUTTOM,00:00
...
R025,maintenance,<mileage>,valid,MUTTOM,00:00
```
### Rake Distribution

- **9 rakes:** service, home ALVA
- **7 rakes:** service, home TPHT
- **2 rakes:** service, home MUTTOM
- **7 rakes:** maintenance, at MUTTOM
- **Total:** 25 rakes
- **Initial mileage:** Randomized between 20,000 and 200,000 km

### Synthetic Assumptions

| Field | Assumed Value | Rationale |
|---|---|---|
| Terminal turnaround | 5 min | No verified source; project assumption |
| Terminal-to-terminal deadhead (ALVA ↔ TPHT) | 15 min | No verified source; project assumption |
| MUTTOM ↔ terminal deadhead | 8 min | No verified source; project assumption; used for R11 first-trip deadhead |
| Maintenance threshold | 1,000,000 km | No verified source |
| Info Park-2 capacity | 2 rakes | No verified source |
| Initial mileage | 20,000–200,000 km | Randomized for realism |
| Initial rake split | 9 ALVA / 7 TPHT / 2 MUTTOM | Fixed; required for 250-trip feasibility |
| Simulation delay model | clipped normal, mean −48 s pre-clip, clip [0, 300 s] | No verified source; Phase 2 assumption |

These values are project assumptions, not confirmed KMRL operational data.

The Phase 2 delay model is documented in full in docs/phases.md (Phase 2) and in data/processed/simulation_kpis.json (metadata section). Phase 2 outputs were regenerated on 2026-11-12 on the new 250-trip real-GTFS schedule.

## 7. GTFS Consistency Check (optional module)

**File:** `src/gtfs_validation.py`

An optional, non-pipeline consistency check. It is not part of the scheduling pipeline. It compares selected GTFS-derived values with model values for sanity.

| Check | GTFS-Derived Value | Model Value | Status |
|---|---|---|---|
| Running time | Approximately 50.47 min (median) | Per-trip GTFS duration | INFO — model uses per-trip values |
| Turnaround | Not measurable (no block_id) | 5 min | WARN — unvalidated |
| Peak headway | Varies (5–10 min) | No direct GTFS-matched value | WARN |

### Purpose
The module exists to spot obvious inconsistencies. It is not required for the solver or validator. The main scheduling pipeline is:

extract_gtfs_trips.py → trips_full_route.csv + trips_partial.csv → merge_trips.py → trips_all.csv → solver → validator.

## 8. Data Flow Summary

### Main Scheduling Pipeline
``` text 

GTFS (data/raw/)
       |
       v
data/extract_gtfs_trips.py
       |
       +---> data/trips_full_route.csv      (232)
       +---> data/trips_partial.csv         (18)
       +---> data/stop_sequences_*.csv      (audit)
       |
       v
data/merge_trips.py
       |
       v
data/trips_all.csv  (250 = 232 + 18)
       |
       v
solver/models.py  (ProblemData)
       |
       v
solver/solve.py  (CP-SAT, O6 rake balance active)
       |
       v
data/processed/schedule.csv  (250 scheduled trips)
       |
       v
solver/validator.py  (Independent verification)
       |
       v
data/processed/validation.json
(10 PASS + 1 SKIPPED, Overall PASS)

## Supporting Data Flow

KMRL Annual Report
       |
       v
solver/config.py
(Route length, operating hours)

2026 News Article
       |
       v
solver/config.py
(Fleet: 18 service + 7 maintenance)

GTFS running-time analysis
       |
       v
Summary statistic only (50.47 min median).
The solver uses per-trip GTFS durations, not this constant.

Initial rake split (9 / 7 / 2)
       |
       v
data/generate_synthetic_v2.py → rakes.csv

## Reconciliation Check

data/hourly_service.csv  (legacy, 250 counts)
       |
       v
data/verify_gtfs_trips.py
       |
       v
Verifies: hourly(250) == hourly(232) + hourly(18)
Kept on disk for reconciliation only.
Not read by the solver.

```

## 9. Limitations

**GTFS data vintage:** The feed covers 2024–25 and may not represent current 2026 operations.
- **Fleet discrepancy:** Annual Report 2024–25 says 15 trains operating; 2026 news says 18 operating + 7 maintenance. V1 uses 18 service + 7 maintenance (News 2026). The two figures reflect different reporting periods.
- **Turnaround:** The 5-minute turnaround is `[SYNTHETIC]`; no verified source is available.

Deadhead: Both 15 min (terminal) and 8 min (MUTT) deadhead values are [SYNTHETIC]. No verified KMRL source.

Maintenance threshold: The 1,000,000 km threshold is [SYNTHETIC].

Depot capacity: Info Park-2 capacity of 2 is [SYNTHETIC]. R8 not enforced in V1.

Initial rake split: 9 ALVA / 7 TPHT / 2 MUTTOM is [SYNTHETIC].

Crew scheduling: **Phase 3 complete (2026-11-13).** Crew solver reads `data/processed/schedule.csv` (Phase 1 output, read-only) and `data/synthetic/drivers.csv` (55 synthetic drivers). Assigns all 250 trips to SC/TO drivers at pool sizes 45/50/55; all three pools OPTIMAL with independent validator PASS. See `docs/constraints-crew-v1.md` for C1–C7 crew spec and `docs/phases.md` §Phase 3 for results. C5 (12 h rest) deferred to V2; driver qualifications / availability / shift preferences / weekly availability deferred to V2.

GTFS limitations: GTFS provides scheduled timetable information, not real-time train positions or actual operating delays.

Objective: O6 rake balance is active (§6 of constraints-v2.2). O1–O5 and O7 remain declared but disabled. Result: OPTIMAL, objective 4800 (Σ dev = 16), gap 0%, 11.77 s. V1 is optimization (single-objective), not a feasibility probe.

DPR: DPR-based values have been removed from the current project configuration.

Terminal continuity: The Phase 1 schedule uses real GTFS trip IDs (WK_*). Terminal continuity is validated (R11 PASS). It is not "unverifiable" — that was true of the earlier synthetic-Txxxx schedule and no longer applies.

- **Constraint classification:** R1, R5, R6, R10, R11 are solver-enforced. R3, R7, R12 are guaranteed by `trips_all.csv` being pre-filtered to the operating window and matching GTFS durations — the solver's constraint functions for these are effectively constant checks. R2 is removed from V1 (headway is a property of the fixed GTFS timetable, not a solver decision). R8 is skipped (no stabling). R9 is vacuous (no maintenance windows).

Phase 2 outputs: data/processed/simulation_kpis.json and simulation_timeline.csv were regenerated on 2026-11-12 on the 250-trip real-GTFS schedule.

## 10. Source References



### GTFS Feed

- Provider: Kochi Metro Rail Limited.
- Website: https://kochimetro.org/
- Validity: 2024-08-12 to 2025-12-31.
- Local location: `data/raw/`

### KMRL Annual Report 2024–25

- Local Markdown copy: `Z:\Hajish College\Major_project\KMRLGTFS2.md`
- Local PDF copy: `Z:\Hajish College\Major_project\KMRLGTFS2.pdf`

### News Article — 2026

- Publisher: The New Indian Express.
- Date: August 23, 2026.
- Article: Kochi Metro will need eight more trains after Pink Line completion, says MD Loknath Behera

### KMRL Official Timetable

- URL: https://kochimetro.org/train-time-table/
- Operating hours used: 06:00–23:00.
- Reported peak headway: 7 minutes 30 seconds.
