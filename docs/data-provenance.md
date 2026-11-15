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
| Weekday trips used (total) | 255 | Filter `service_id=WK`, `04:40 ≤ departure < 24:00` |
| Full-route trips (ALVA ↔ TPHT) | 232 | First/last stop both are terminals |
| Partial trips (Muttom ↔ terminals) | 23 | First or last stop is MUTT, KVTR, or TPHT/MUTT |
| UP/DOWN split | 130 UP / 125 DOWN | Station-index from stop order (ALVA=0 … TPHT=24) |
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
  - `data/trips_partial.csv` — 23 partial trips
  - `data/stop_sequences_partial.csv` — stop sequences for the 23
- **Merge script:** `data/merge_trips.py`
- **Solver input:** `data/trips_all.csv` — 255 trips (232 + 23)
- **Audit script:** `data/verify_gtfs_trips.py` — independently verifies the extraction and reconciles 232 + 23 = 255 against the untouched `hourly_service.csv`

**Filtering:** All 255 weekday trips in `trips.txt` are **included** in the model (operating window (04:40, 24:00)). The 5 trips that would have been excluded under the earlier 06:00–23:00 window are:

- `WK_4` (departs MUTT at 05:00) — pre-service positioning run
- `WK_256` (departs MUTT at 05:20) — pre-service positioning run
- `WK_18` (departs MUTT at 05:45) — pre-service positioning run
- `WK_12` (departs KVTR at 05:57) — pre-service positioning run
- `WK_253` (departs TPHT at 23:22:54, arrives MUTT at 24:03:45) — late-night return-to-depot

These are **real train movements that use rakes**, not passenger-service exclusions. Including them makes the model operationally complete.

**Direction identification:**

Direction is determined by **station index** from stop order (ALVA = 0 … TPHT = 24):

- `UP` = last station index > first station index
- `DOWN` = last station index < first station index

No fallback to `trips.txt direction_id`. Verified by `data/verify_gtfs_trips.py` (all 255 consistent with `direction_id`, but the model uses stop order).

### Known Quirks

- The `transfers` column in `fare_attributes.txt` is empty.
- Fare range: ₹10 (shortest) to ₹60 (Aluva ↔ Tripunithura).
- The feed ends on 2025-12-31 and represents the 2024–25 timetable, not current 2026 operations.
- Some raw `stop_times.txt` entries have times ≥ 24:00:00 (e.g., `24:03:45`). **WK_253 now appears in `trips_all.csv` and has arrival 24:03:45** — this is GTFS-valid and the parser handles `H*3600 + M*60 + S` without a day limit. Verified: 255 trips in `trips_all.csv`, one with arrival past midnight (WK_253), which is normal for late-night returns.

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
| Operating hours | 06:00–23:00 | KMRL published timetable (V1 extends to (04:40, 24:00) to include positioning runs — see §1) |
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
| 408 trips/day | GTFS weekday data | 255 trips (232 full-route + 23 partial) |
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
| TPHT | 9 | `[SYNTHETIC]` |
| MUTTOM | 0 service (7 maintenance only) | `[SYNTHETIC]` |

The 9/9/0 split is **verified feasible** on the 255-trip schedule (OPTIMAL, objective 900.0, ~60 s). Earlier documentation that claimed MUTT-home service rakes were required was based on an **undocumented home-lock pruning rule** in `create_rake_assignment_variables` that has been removed. With the home-lock removed, 9/9/0 is feasible and is the current committed configuration.

### Aggregate Fleet Capacity Estimate

The following is an **aggregate summary only**. It uses the 50.47-min median as a rough per-trip figure. The model itself uses per-trip GTFS durations.

- Required running time (rough estimate): 255 trips × 50.47 min = 12,870 train-minutes.
- Available running time: 18 rakes × 19.3 hours × 60 = 20,844 train-minutes (window (04:40, 24:00)).
- Estimated utilization: approximately 61.7%, rounded to 62%.

This is a planning estimate, not a proof of feasibility. Actual feasibility is determined by the CP-SAT solver and the independent schedule validator. 
The empirical result on the 255-trip case is **OPTIMAL under the O6 rake-balance objective** (objective 900.0, gap 0%, ~60 s; see constraints-v2.2 §6).

---

## 6. Synthetic Data

Synthetic data lives in `data/synthetic/`. All synthetic values are tagged `[SYNTHETIC]`.

### Files

| File | Rows | Content |
|---|---:|---|
| `rakes.csv` | 25 | Fleet status, mileage, and location (Phase 1) |
| `rakes_phase5.csv` | 25 | **Phase 5 parallel fleet file** — same 25 rakes + `km_since_last_maintenance` + `maintenance_type` columns. Phase 1's `rakes.csv` not modified. `[SYNTHETIC]` |
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

### Generated By — Phase 5 (disruption layer)

`data/synthetic/rakes_phase5.csv` is written by hand (no generator script) as a **parallel file** alongside Phase 1's `rakes.csv` — Phase 1's `rakes.csv` is read-only.

Two new columns added to the same 25 rakes:

| Column | Type | Values |
|---|---|---|
| `km_since_last_maintenance` | int (km) | 0 for unscheduled_repair rakes; 2,100–7,200 for scheduled maintenance rakes; 3,600–6,700 for service rakes `[SYNTHETIC]` |
| `maintenance_type` | string | `service` (18 rakes) / `scheduled` (5 rakes) / `unscheduled_repair` (2 rakes) |

**Maintenance split (derived from D2's rule applied to Phase 1 `rakes.csv`):**

- **Unscheduled repair (blocked):** R020 (176,838 km), R023 (199,479 km) — the two highest-`initial_mileage_km` maintenance rakes.
- **Scheduled (reactivatable):** R019 (4,200 km-since), R021 (6,800), R022 (2,100), R024 (3,500), R025 (7,200).
- **Service rakes (18):** R001–R018, values 3,600–6,700 km-since `[SYNTHETIC]`.

**255-trip baseline update:** R017 and R018 moved from MUTTOM to TPHT to match the 255-trip Phase 1 baseline. Split is now **9 ALVA / 9 TPHT / 0 service MUTTOM** (7 maintenance at MUTTOM). The MUTTOM-home rakes (R017, R018) no longer exist in service — all 18 service rakes now start from ALVA or TPHT.

**Note — D3 correction:** The Phase 5 handoff's original D3 table listed R019, R020, R021, R022, R023 as "scheduled" maintenance rakes. This contradicts D2's "2 highest-mileage maintenance rakes become unscheduled" rule. The actual split follows D2 on real data: **R020/R023 are unscheduled_repair (blocked); R019/R021/R022/R024/R025 are scheduled (reactivatable).** The heuristic therefore activates **R022** first (lowest km-since) and **R024** second.

**Why a parallel file, not a modified `rakes.csv`:** Phase 1's `rakes.csv` is verified and locked. Phase 5 preserves Phase 1 integrity by adding a parallel file with the same 25 rakes plus the two new columns.

**Defense (viva):** `km_since_last_maintenance` is a snapshot at start of service day. In a real deployment, a fleet management system would update it after every shift. Phase 5 uses the snapshot as input — it does not update it during execution. This is a SYNTHETIC input, not a live feed.

**Disruption scenario configs:**

- `data/disruptions/scenario_a.json` — R008 fails @ 18:00:00 (single-rake happy path, evening peak)
- `data/disruptions/scenario_b.json` — 4 rakes (R008, R013, R015, R002) fail @ 07:00:00 (mass failure, morning peak)

Both JSONs are hand-authored per handoff D8 (with the corrected scenario timings from the peak-hour analysis — see `docs/phases.md` §Phase 5).

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
R017,service,<mileage>,valid,TPHT,06:00
R018,service,<mileage>,valid,TPHT,06:00
R019,maintenance,<mileage>,valid,MUTTOM,00:00
...
R025,maintenance,<mileage>,valid,MUTTOM,00:00
```
```
### Rake Distribution

- **9 rakes:** service, home ALVA
- **9 rakes:** service, home TPHT
- **0 rakes:** service, home MUTTOM (no service MUTT-home rakes in 255-trip V1)
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
| Initial rake split | 9 ALVA / 9 TPHT / 0 MUTTOM | Fixed; verified feasible on 255-trip schedule |
| Simulation delay model | clipped normal, mean −48 s pre-clip, clip [0, 300 s] | No verified source; Phase 2 assumption |
| `km_since_last_maintenance` (Phase 5) | 0 / 2,100–7,200 / 3,600–6,700 (see §6) | `[SYNTHETIC]` — snapshot at start of service day; real deployment updates per shift. Used as reliability proxy for reactivation heuristic. |
| Phase 5 drop penalty (`W_DROP`) | 1000 (before `OBJ_SCALE`) | `[SYNTHETIC]` — large weight so drops are minimized; empirically verified load-bearing (diagnostic with `W_DROP = 0` produced 12 drops at 17 rakes; real run produced 0 drops) |

These values are project assumptions, not confirmed KMRL operational data.

The Phase 2 delay model is documented in full in docs/phases.md (Phase 2) and in data/processed/simulation_kpis.json (metadata section). Phase 2 outputs were regenerated on 2026-11-15 on the 255-trip real-GTFS schedule. A CP1252/UTF-8 encoding bug in src/simulation/experiments.py's JSON writer was found and fixed during Phase 4 regeneration (encoding="utf-8" added to both CSV and JSON writers) — no KPI values were affected.

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
       +---> data/trips_partial.csv         (23)
       +---> data/stop_sequences_*.csv      (audit)
       |
       v
data/merge_trips.py
       |
       v
data/trips_all.csv  (255 = 232 + 23)
       |
       v
solver/models.py  (ProblemData)
       |
       v
solver/solve.py  (CP-SAT, O6 rake balance active)
       |
       v
data/processed/schedule.csv  (255 scheduled trips)
       |
       v
solver/validator.py  (Independent verification)
       |
       v
data/processed/validation.json
(10 PASS, 0 SKIPPED, Overall PASS)

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

Initial rake split (9 / 9 / 0)
       |
       v
data/generate_synthetic_v2.py → rakes.csv

## Reconciliation Check

data/hourly_service.csv  (legacy, 255 counts)
       |
       v
data/verify_gtfs_trips.py
       |
       v
Verifies: hourly(255) == hourly(232) + hourly(23)
Kept on disk for reconciliation only.
Not read by the solver.

## Phase 4 — Explainability (reads Phase 1/2/3 outputs, writes two new files)

Phase 1 outputs                     Phase 2 output         Phase 3 outputs
-----------------                   ---------------        ---------------
validation.json                     simulation_kpis.json   crew_solution.json
solution.json                                              crew_validation.json
schedule.csv                                               crew_schedule.csv
       \                                   |                    /
        \                                  |                   /
         \                                 v                  /
          +-----> src/explainability/report_generator.py <----+
                              |
                              +---> data/processed/explainability_report.md
                              +---> data/processed/utilization_stats.json

Read-only: Phase 4 does not modify any Phase 1/2/3 output.

## Phase 5 — Disruption Response (reads Phase 1 outputs + Phase 5 parallel fleet, writes four new files)

Phase 1 outputs                Phase 5 parallel fleet + disruption configs
---------------                -----------------------------------------
schedule.csv  (255 trips)      rakes_phase5.csv   (25 rakes + 2 columns)
                               scenario_a.json    (R008 @ 18:00)
                               scenario_b.json    (4 rakes @ 07:00: R008, R013, R015, R002)
       \                                   |
        \                                  |
         \                                 v
          +------> solver/reschedule_models.py (RescheduleProblemData)
                               |
                               v
                    solver/reschedule_solve.py
                    (per scenario: build active fleet, apply wall-clock
                     withdrawal, CP-SAT re-solve, in-memory diff)
                               |
                               +---> data/processed/reschedule_scenario_a.csv
                               +---> data/processed/reschedule_scenario_b.csv
                               |
                               v
                    solver/reschedule_diff.py (library module)
                    (compute_diff → write_diff_json → write_summary_md)
                               |
                               +---> data/processed/reschedule_diff.json
                               +---> data/processed/reschedule_summary.md

Read-only: Phase 5 does not modify schedule.csv, rakes.csv, or any Phase 1/2/3/4 output.
Phase 1's solver/constraints.py is unchanged — Phase 5's drop-aware R1 lives
in solver/reschedule_constraints.py (new file, parallel to constraints.py).

```

## 9. Limitations

**GTFS data vintage:** The feed covers 2024–25 and may not represent current 2026 operations.
- **Fleet discrepancy:** Annual Report 2024–25 says 15 trains operating; 2026 news says 18 operating + 7 maintenance. V1 uses 18 service + 7 maintenance (News 2026). The two figures reflect different reporting periods.
- **Turnaround:** The 5-minute turnaround is `[SYNTHETIC]`; no verified source is available.

Deadhead: Both 15 min (terminal) and 8 min (MUTT) deadhead values are [SYNTHETIC]. No verified KMRL source.

Maintenance threshold: The 1,000,000 km threshold is [SYNTHETIC].

Depot capacity: Info Park-2 capacity of 2 is [SYNTHETIC]. R8 (depot capacity) is not modelled in V1 and has been removed from the validator scope.

Initial rake split: 9 ALVA / 9 TPHT / 0 MUTTOM is [SYNTHETIC].(7 maintenance rakes at MUTTOM).

Crew scheduling: **Phase 3 complete (2026-11-13, regenerated 2026-11-15 on 255-trip Phase 1 baseline).** Crew solver reads `data/processed/schedule.csv` (Phase 1 output, read-only, 255 trips) and `data/synthetic/drivers.csv` (55 synthetic drivers). Assigns all 255 trips to SC/TO drivers at pool sizes 45/50/55; all three pools OPTIMAL with independent validator PASS. Regenerated 2026-11-15 without code changes — 255-trip solver output: pool 45 = 40 active / 5 reserve / 59.61 s; pool 50 = 45 active / 5 reserve / 62.10 s; pool 55 = 50 active / 5 reserve / 70.10 s. Objective 0.0 and gap 0.0% at all pools. Old 250-trip outputs preserved as `*_250_before_255.*` for before/after comparison. See `docs/constraints-crew-v1.md` for C1–C7 crew spec and `docs/phases.md` §Phase 3 for results. C5 (12 h rest) deferred to V2; driver qualifications / availability / shift preferences / weekly availability deferred to V2.

Explainability: **Phase 4 complete (2026-11-13).** Phase 4 is a reporting layer only — it reads the seven Phase 1/2/3 output files (`validation.json`, `solution.json`, `schedule.csv`, `simulation_kpis.json`, `crew_solution.json`, `crew_validation.json`, `crew_schedule.csv`) and writes two new files (`explainability_report.md`, `utilization_stats.json`). Phase 4 introduces **no new data sources** and modifies **no Phase 1/2/3 outputs**. See `docs/phases.md` §Phase 4 for the report structure and `src/explainability/report_generator.py` for the implementation.

Disruption response: **Phase 5 complete (2026-11-15, regenerated on 255-trip Phase 1 baseline).** Phase 5 reads Phase 1's `schedule.csv` (255 trips, read-only) plus a new parallel fleet file `data/synthetic/rakes_phase5.csv` (25 rakes + 2 new columns). Phase 1's `rakes.csv`, `constraints.py`, `models.py`, `solve.py`, `config.py` are **not modified**. Phase 5 adds a drop-aware R1 in a **new** file `solver/reschedule_constraints.py`; the drop penalty `W_DROP = 1000` is a new `[SYNTHETIC]` weight added to the O6 rake-balance objective. Two scenarios: A = R008 fails @ 18:00 (evening peak, single-rake happy path, 4 withdrawn → 4 recovered → 0 dropped, OPTIMAL, obj 900.0); B = 4 rakes (R008, R013, R015, R002) fail @ 07:00 (morning-peak mass failure, 53 withdrawn → 46 recovered (86.8%) → 7 dropped, OPTIMAL, obj 702,400.0, 16 active rakes). Withdrawal rule: **wall-clock cutoff** (any trip departing ≥ disruption time unavailable to the downed rake; trips already departed complete normally — no mid-trip abort). **Optimality-gap acceleration:** `add_balance_bound_phase5` in `reschedule_constraints.py` adds a redundant constraint `trips_per_rake ≤ ceil(255/active_rakes)` (logically implied by the balance objective) that closed a 14.19% FEASIBLE gap to 0.0% OPTIMAL in 93.8s — objective and optimum unchanged. Full re-solve (A ~270 s, B ~94 s on 255 trips), not warm-start; warm-start optimization is future work. See `docs/phases.md` §Phase 5 for the full design and `data/processed/reschedule_summary.md` for the live narrative output. **"Dropped" ≠ "delayed"** — dropped means the trip does not operate (cancelled); the "45–90 min wait" framing describes the passenger experience of a dropped trip, not a rescheduled delay.

GTFS limitations: GTFS provides scheduled timetable information, not real-time train positions or actual operating delays.

Objective: O6 rake balance is active (§6 of constraints-v2.2). O1–O5 and O7 remain declared but disabled. Result: OPTIMAL, objective 900.0 (Σ dev = 3, target 14), gap 0%, ~60 s. V1 is optimization (single-objective), not a feasibility probe.

DPR: DPR-based values have been removed from the current project configuration.

Terminal continuity: The Phase 1 schedule uses real GTFS trip IDs (WK_*). Terminal continuity is validated (R11 PASS). It is not "unverifiable" — that was true of the earlier synthetic-Txxxx schedule and no longer applies.

- **Constraint classification:** R1, R5, R6, R10, R11 are solver-enforced. R3 is guaranteed by trips_all.csv being pre-filtered to the operating window. R7 is guaranteed by models.py::ProblemData.load() (rejects duration mismatches). R4 is enforced by construction (only service_rakes iterated). R2 is removed from V1. R8, R9, R12 have no solver function (R8 removed from scope, R9 vacuous, R12 subsumed by R3). All of R1, R3, R4, R5, R6, R7, R9, R10, R11, D are checked by solver/validator.py.

Phase 2 outputs: data/processed/simulation_kpis.json and simulation_timeline.csv were regenerated on 2026-11-15 on the 255-trip real-GTFS schedule.

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
