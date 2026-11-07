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
| Weekday trips used | 250 | Filter `service_id=WK`, departure 06:00–23:00 |
| UP/DOWN split | Approximately 125 each | First and last stop IDs in `stop_times.txt` |
| One-way running time | 50.47 min | Median over 412 trips (ALVA ↔ TPHT) |
| Route distance from GTFS shapes | Approximately 27.87 km | Final distance from `shapes.txt` |
| Model route length | 28.144 km | KMRL Annual Report 2024–25 |
| Stations | 25 | Count of distinct `stop_id` values in `stops.txt` |
| Hourly distribution | `data/hourly_service.csv` | Grouped by departure hour |

**Route length clarification:**
- GTFS shapes provide approximately 27.87 km.
- The Annual Report provides 28.144 km.
- The model uses 28.144 km from the Annual Report.

### GTFS Handling

- **Output:** `data/hourly_service.csv`
- **Extraction script:** `data/extract_gtfs_hourly.py`
- **Filtering:** Of 255 weekday trips in `trips.txt`, 5 depart outside the 06:00–23:00 model window.
- **Trips used:** 250 passenger trips.

The five excluded departures are:

- 05:00
- 05:20
- 05:45
- 05:57
- 23:22

These trips fall outside the selected model operating window.

**Direction identification:**

- UP: ALVA → TPHT
- DOWN: TPHT → ALVA

Direction is identified using the first and last stops in `stop_times.txt`, with `trips.txt` `direction_id` as a fallback.

### Known Quirks

- The `transfers` column in `fare_attributes.txt` is empty.
- Fare range: ₹10 (shortest) to ₹60 (Aluva ↔ Tripunithura).
- The feed ends on 2025-12-31 and represents the 2024–25 timetable, not current 2026 operations.

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
| 408 trips/day | GTFS weekday data | 250 trips |
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

**Model configuration:** The model uses 18 service rakes. The 7 maintenance rakes are not available for passenger service.

### Aggregate Fleet Capacity Estimate

- Required running time: 250 trips × 50.47 min = 12,617.5 train-minutes.
- Available running time: 18 rakes × 17 hours × 60 = 18,360 train-minutes.
- Estimated utilization: approximately 68.72%, rounded to 69%.

This is an aggregate capacity estimate. It does not independently prove that all trips can be assigned to rakes while satisfying direction, trip sequence, turnaround, and availability constraints.

Actual schedule feasibility is determined by the CP-SAT solver and the independent schedule validator.

---

## 6. Synthetic Data

Synthetic data lives in `data/synthetic/`. All synthetic values are tagged `[SYNTHETIC]`.

### Files

| File | Rows | Content |
|---|---:|---|
| `rakes.csv` | 25 | Fleet status, mileage, and location |
| `terminals.csv` | 2 | ALVA and TPHT with 5-minute turnaround |
| `maintenance.csv` | 0 | Empty; no scheduled maintenance records |
| `depot.csv` | 2 | Info Park-2 (capacity 2), Muttom (unbounded) |

### Generated By

`data/generate_synthetic_v2.py`

- Deterministic generation.
- Random seed: `42`.

### Rake Schema

```csv
rake_id,status,initial_mileage_km,cmrs_status,initial_location,initial_available_time
R001,service,187621,valid,ALVA,06:00
...
R019,maintenance,45321,valid,MUTTOM,00:00
```

### Rake Distribution

- **18 rakes:** `status = "service"`
- **7 rakes:** `status = "maintenance"`
- **Total:** 25 rakes.
- **Initial mileage:** Randomized between 20,000 and 200,000 km.

### Synthetic Assumptions

| Field | Assumed Value | Rationale |
|---|---:|---|
| Terminal turnaround | 5 min | No verified source; project assumption |
| Maintenance threshold | 1,000,000 km | No verified source |
| Info Park-2 capacity | 2 rakes | No verified source |
| Initial mileage | 20,000–200,000 km | Randomized for simulation realism |

These values are project assumptions, not confirmed KMRL operational data.

---

## 7. GTFS Validation Module

**File:** `src/gtfs_validation.py`

The module compares selected GTFS-derived values with the corresponding model values.

| Check | GTFS-Derived Value | Model Value | Status |
|---|---|---|---|
| Running time | Approximately 50.47 min (median) | 50 min | PASS |
| Turnaround | Not measurable (no `block_id`) | 5 min | WARN — unvalidated |
| Peak headway | Varies (5–10 min) | No direct GTFS-matched value | WARN |

### Purpose

The module checks whether selected model parameters are consistent with available GTFS information.

The GTFS feed itself is used as a scheduling input through `data/hourly_service.csv`. The validation module is a separate consistency check; it does not replace the GTFS extraction or scheduling pipeline.

---

## 8. Data Flow Summary

### Main Scheduling Pipeline

```text
GTFS (data/raw/)
       |
       v
data/extract_gtfs_hourly.py
       |
       v
data/hourly_service.csv
(250 trips, 06:00–23:00)
       |
       v
solver/models.py
(ProblemData)
       |
       v
solver/solve.py
(CP-SAT)
       |
       v
data/processed/schedule.csv
(250 scheduled trips)
       |
       v
solver/validator.py
(Independent verification)
       |
       v
data/processed/validation.json
(10 checks: 9 PASS + 1 SKIPPED)
```

### Supporting Data Flow

```text
KMRL Annual Report
       |
       v
config.py
(Route length, operating hours)

2026 News Article
       |
       v
config.py
(Fleet: 18 service + 7 maintenance)

GTFS Running-Time Analysis
       |
       v
config.py
(Running time: 50.47 min)
```

---

## 9. Limitations

1. **GTFS data vintage:** The feed covers 2024–25 and may not represent current 2026 operations.
2. **Fleet discrepancy:** The Annual Report says 15 operating trains, while the 2026 news article reports 18 operating trains. V1 uses the 18-service-rake configuration.
3. **Turnaround:** The 5-minute turnaround is `[SYNTHETIC]`; no verified source is available.
4. **Maintenance threshold:** The 1,000,000 km threshold is `[SYNTHETIC]`.
5. **Depot capacity:** Info Park-2 capacity of 2 is `[SYNTHETIC]`.
6. **Crew scheduling:** Crew scheduling data and constraints are not included in the current train-scheduling phase. Crew scheduling is planned for Phase 3.
7. **GTFS limitations:** GTFS provides scheduled timetable information, not real-time train positions or actual operating delays.
8. **Schedule optimization:** A feasible CP-SAT result does not necessarily mean an optimal result. Solver status, objective value, best bound, and optimality gap must be reported separately.
9. **DPR:** DPR-based values have been removed from the current project configuration.

---

## 10. Source References

### GTFS Feed

- **Provider:** Kochi Metro Rail Limited.
- **Website:** https://kochimetro.org/
- **Validity:** 2024-08-12 to 2025-12-31.
- **Local location:** `data/raw/`

### KMRL Annual Report 2024–25

- **Local Markdown copy:** `Z:\Hajish College\Major_project\KMRLGTFS2.md`
- **Local PDF copy:** `Z:\Hajish College\Major_project\KMRLGTFS2.pdf`

### News Article — 2026

- **Publisher:** The New Indian Express.
- **Date:** August 23, 2026.
- **Article:** [Kochi Metro will need eight more trains after Pink Line completion, says MD Loknath Behera](https://www.newindianexpress.com/amp/story/cities/kochi/2026/Aug/23/kochi-metro-will-need-eight-more-trains-after-pink-line-completion-says-md-loknath-behera)

### KMRL Official Timetable

- **URL:** https://kochimetro.org/train-time-table/
- **Operating hours used:** 06:00–23:00.
- **Reported peak headway:** 7 minutes 30 seconds.

---

**End of Data Provenance Document**