# MetroPulse — Constraint Specification v2.3

**Status:** Locked for V1 implementation (255-trip model, rebuilt on real GTFS trips)
**Date:** 2026-11-15
**Supersedes:** v2.2 (2026-11-12) — updates trip count (250→255), operating window (06:00–23:00 → 04:40–24:00), fleet split (9/7/2 → 9/9/0), R6 per-pair deadhead, R11 KVTR rule, R8/R12 removed from validator scope, R9 and direction check added, objective 4800 → 900, home-lock removed
**Scope:** Real-data train scheduling (GTFS + Annual Report), train layer only

---

## 1. Source Classification

Every parameter in this specification is tagged with one of:

| Tag | Meaning |
|---|---|
| `[EXTERNAL]` | External authoritative source (GTFS feed, Annual Report, news) |
| `[DERIVED]` | Computed from an external source |
| `[SYNTHETIC]` | Project assumption (no verified source) |
| `[MODEL LIMITATION]` | Deliberate simplification |

**Rule:** No parameter is claimed as `[DPR]` because the DPR document is not in the project. Values previously tagged `[DPR]` are relabeled `[EXTERNAL]` (if verified) or `[SYNTHETIC]` (if assumed).

---

## 2. Scope & Scenario

### 2.1 Baseline Scenario — Current Operations

- Uses **GTFS 2024-25 feed** for weekday service (255 trips: 232 full-route + 23 partial).
- Uses **KMRL Annual Report 2024-25** for route length, fleet, and service hours.
- Uses **news article 2026** for fleet breakdown (18 operating + 7 maintenance).
- Single-line metro (Aluva → Tripunithura).
- Operating window **04:40–24:00** `[EXTERNAL — GTFS 2024-25 WK trips]`. Extended from the earlier 06:00–23:00 Annual Report window to include 5 real positioning/depot movements (WK_4, WK_256, WK_18, WK_12, WK_253).
- Solver uses **real GTFS trip records**, not hourly counts and not synthetic `T0000` trips.
- **Deadhead IS modeled** (see §3.5).
- No crew scheduling in V1.
- No ML in V1.
- Objective minimization: **O6 rake balance active** (see §6).

### 2.2 Out of Scope for V1

- Crew rostering (Phase 3). **Phase 3 is now complete (2026-11-13) — see `docs/phases.md` §Phase 3 for the C1–C7 crew constraint spec. This file covers the train layer only; crew constraints are not duplicated here.**
- XGBoost / ML predictions (optional, Phase 6).
- Stochastic SimPy feedback to CP-SAT.
- Muttom depot finite capacity.
- Depot-to-depot deadhead beyond §3.5.

---

## 3. Inputs

### 3.1 Trip Dataset (Solver Input) `[EXTERNAL — GTFS 2024-25]`

**The solver input is `data/trips_all.csv` (255 real GTFS trips).** It is the merge of:

- `data/trips_full_route.csv` — **232** full-route ALVA↔TPHT trips
- `data/trips_partial.csv` — **23** partial trips (Muttom/KVTR ↔ terminals)

Schema:

```text
trip_id, origin_stop, destination_stop, direction,
departure_time, arrival_time, duration,
stop_count, first_stop, last_stop
```

`trip_id` = original GTFS trip_id (e.g., `WK_160`), not synthetic.
`departure_time` / `arrival_time` = original GTFS strings, may exceed 24:00.
`duration` = integer seconds (arrival − departure), includes intermediate dwell.

Reconciliation only: `data/hourly_service.csv` is kept on disk as an independent check (232 + 23 = 255, verified by `data/verify_gtfs_trips.py`). It is not read by the solver.

### 3.2 Physical Parameters

| Parameter | Value | Source |
|---|---:|---|
| Route length | 28.144 km | `[EXTERNAL — Annual Report 2024-25]` |
| One-way running time (median) | 50.47 min | `[DERIVED — GTFS 412 trips]` — summary statistic only |
| Per-trip running time | Real GTFS duration | `[EXTERNAL — GTFS]` — used by solver |
| Terminal turnaround | 5 min | `[SYNTHETIC]` |
| Stations | 25 | `[EXTERNAL — Annual Report]` |
| Operating window | 04:40 ≤ departure < 24:00 | `[EXTERNAL — GTFS 2024-25 WK trips]` |

The 50.47-min median is not a model input. The solver uses each trip's own GTFS duration.

### 3.3 Fleet

| Parameter | Value | Source |
|---|---:|---|
| Total fleet | 25 | `[EXTERNAL — news 2026]` |
| Service rakes | 18 | `[EXTERNAL — news 2026]` |
| Maintenance rakes | 7 | `[EXTERNAL — news 2026]` |
| Standby rakes | 0 | Folded into 18 service |

Initial position split (fixed, not solver choice):

| Location | Service rakes | Source |
|---|---:|---|
| ALVA | 9 | `[SYNTHETIC]` |
| TPHT | 9 | `[SYNTHETIC]` |
| MUTTOM | 0 service (7 maintenance only) | `[SYNTHETIC]` |

The 9/9/0 split is **verified feasible** on the 255-trip schedule (OPTIMAL, objective 900.0, ~60 s). Earlier versions claimed MUTT-home service rakes were required; that was an artifact of a home-lock pruning rule (see §10) that has been removed.
### 3.4 Depot / Stabling

| Location | Capacity | Source |
|---|---:|---|
| Info Park-2 | 2 | `[SYNTHETIC]` |
| Muttom Depot | UNBOUNDED_FOR_V1 | `[MODEL LIMITATION]` |

**R8 (depot capacity) is removed from validator scope in V1** — no stabling assignment exists. The implicit capacity is enforced by the 9/9/0 split in `rakes.csv`.

### 3.5 Deadhead `[SYNTHETIC]`

Two values, both used by R6 and R11:

| Parameter | Value | Meaning |
|---|---:|---|
| `TERMINAL_TO_TERMINAL_DEADHEAD_MIN` | 15 min | ALVA ↔ TPHT switching |
| `MUTTOM_TO_TERMINAL_DEADHEAD_MIN` | 8 min | MUTTOM ↔ ALVA, MUTTOM ↔ TPHT |

Both tagged `[SYNTHETIC]`. No verified KMRL source.

**KVTR rule:** deadhead is **undefined** for any pair where one endpoint is a non-terminal, non-MUTT stop (e.g., KVTR, EMKM). A trip starting at KVTR can only be taken by a rake whose **previous trip ends at KVTR**. With the current 255-trip schedule, WK_12 (KVTR → ALVA) is the only such trip; WK_256 (MUTT → KVTR) is its only valid predecessor. The solver enforces the WK_256 → WK_12 chain on a single rake.

### 3.6 Maintenance Threshold

| Parameter | Value | Source |
|---|---:|---|
| Rake maintenance threshold | 1,000,000 km | `[SYNTHETIC]` |

---

## 4. Data Quality Notes

### 4.1 GTFS Filtering

GTFS has 255 weekday trips in `trips.txt` (WK service). **All 255 are included in the model** under the [04:40, 24:00) window:

- **232** trips are full-route (ALVA↔TPHT).
- **23** trips are partial (Muttom/KVTR ↔ terminals).
- **5** of the partial trips are real positioning/depot movements that would have been excluded under the earlier 06:00–23:00 window:
  - WK_4 (departs MUTT at 05:00) — pre-service positioning
  - WK_256 (departs MUTT at 05:20) — pre-service positioning
  - WK_18 (departs MUTT at 05:45) — pre-service positioning
  - WK_12 (departs KVTR at 05:57) — pre-service positioning
  - WK_253 (departs TPHT at 23:22:54, arrives MUTT at 24:03:45) — late-night return-to-depot

**232 + 23 = 255 trips in the V1 model.** None excluded by policy. All 5 are real train movements that use rakes.

### 4.2 Direction Determination

Direction is determined by station index from stop order (ALVA = 0 … TPHT = 24):

- `UP` = last station index > first station index
- `DOWN` = last station index < first station index

No fallback to `trips.txt direction_id`. Verified by `data/verify_gtfs_trips.py` (all 255 consistent with `direction_id`, but the model uses stop order).

### 4.3 Window Boundary

Departure must satisfy `04:40:00 ≤ departure < 24:00:00`. A departure at exactly `24:00:00` is excluded (locked decision). Arrivals may exceed 24:00 (WK_253 arrives at 24:03:45 — GTFS-valid).

---

## 5. Hard Constraints (R1–R12)

### R1 — Service Coverage `[EXTERNAL]`

Every trip in `trips_all.csv` must be assigned to exactly one service rake.

```python
for each trip i:
    sum(rake_trip[rake, i] for service rakes) == 1
```

Validator check: Every required trip appears exactly once in `schedule.csv`; no duplicates, no missing, no extra.

### R2 — Headway (removed from V1)

R2 is not enforced in the V1 solver, because trip departure times are fixed by GTFS. Headway is a property of the timetable, not a scheduling decision. If two GTFS trips in the same direction are too close, that is a GTFS fact, not a solver choice.

The earlier R2 (moving departure times to fit a headway target) was only meaningful when trip times were synthetic. With real GTFS times, it does not apply.

### R3 — Operating Window `[EXTERNAL]`

04:40:00 <= departure < 24:00:00
Arrivals may extend past 24:00. WK_253 (arrival 24:03:45) is GTFS-valid.

Validator check: Every departure is in `[OPERATING_START_SEC, OPERATING_END_SEC)`.

### R4 — Fleet Availability `[EXTERNAL]`

Only rakes with `status = "service"` can be assigned trips. Maintenance rakes are blocked (they never appear in the model's rake set).

Validator check: No `rake_id` in `schedule.csv` has `status = "maintenance"` in `rakes.csv`.

### R5 — Rake Non-Overlap `[EXTERNAL]`

For each service rake, no two assigned trips overlap in time.

```python
model.AddNoOverlap(optional_intervals[rake_id])
```

Validator check: No rake's consecutive trips overlap in `schedule.csv`.

### R6 — Turnaround + Deadhead `[SYNTHETIC — per-order]`

For each pair of trips `(a, b)` that a rake might do, the required gap depends on the order:

```text
gap_ab  = turnaround  if a.last_stop == b.first_stop  else deadhead(a.last_stop -> b.first_stop)
gap_ba  = turnaround  if b.last_stop == a.first_stop  else deadhead(b.last_stop -> a.first_stop)
```

Where `deadhead(x, y)` = `TERMINAL_TO_TERMINAL_DEADHEAD_MIN` if both are terminals, `MUTTOM_TO_TERMINAL_DEADHEAD_MIN` if one is MUTTOM.

Enforced per-order (see 10 [FINDING] — the earlier v2 wording that used one gap per pair was buggy and rejected by the validator).

Validator check:

- If `a.last_stop == b.first_stop`: gap ≥ 5 min (same_terminal_pairs)
- If `a.last_stop != b.first_stop`: gap ≥ 15 min or 8 min depending on terminals (cross_terminal_pairs)

### R7 — Running Time `[EXTERNAL — GTFS]`

Each trip's duration is its own GTFS duration, taken from `trips_all.csv` column `duration`.

No 50-min constant. No 50.47-min constant.

Validator check: For each row in `schedule.csv`, `arrival − departure` equals the `duration` of that `trip_id` in `trips_all.csv`.

### R8 — Depot Capacity (removed from V1)

Info Park-2 capacity = 2. Muttom = unbounded.

R8 is not modelled in V1 and not in the validator scope. There is no stabling assignment decision for the model to constrain. The implicit capacity is enforced by the 9/9/0 split in rakes.csv.



### R9 — Maintenance Exclusivity `[SYNTHETIC]`

A rake in maintenance cannot serve passenger trips. `maintenance.csv` is empty in V1, so R9 is vacuous — no scheduled maintenance windows exist.

### R10 — Maintenance Threshold `[SYNTHETIC]`

A rake with `initial_mileage_km >= 1,000,000` is blocked from trips.

Validator check: No trip in `schedule.csv` is assigned to a rake over the threshold.

### R11 — Terminal Continuity `[SYNTHETIC — first-trip home rule with deadhead + KVTR rule]`

A rake whose home terminal is H may take a trip starting at S as its first trip of the day if:

- `S == H`, or
- `deadhead(H, S)` is defined AND the trip's departure is no earlier than `OPERATING_START_SEC + deadhead(H, S)`.

KVTR rule: if deadhead(H, S) is undefined (any pair where one stop is a non-terminal, non-MUTT stop such as KVTR), the trip can only be taken as a first trip if a previous trip ends at S. With the current 255-trip schedule, WK_12 (KVTR → ALVA) requires a predecessor ending at KVTR; only WK_256 (MUTT → KVTR) qualifies. The solver enforces the WK_256 → WK_12 chain on a single rake.

Pair gaps between consecutive trips are enforced by R6, not R11.

Validator check:

- First trip of each rake must satisfy the deadhead condition above.
- Cross-terminal switches between consecutive trips are counted (informational).

### R12 — Non-Service Window `[EXTERNAL]`

R12 is subsumed by R3 (R3 already enforces 04:40 ≤ departure < 24:00). R12 is removed from the validator scope as a redundant check.

---

## 6. Soft Objectives (O1–O7) — O6 ACTIVE, OTHERS DISABLED

All weights are `[SYNTHETIC — INITIAL TUNING PARAMETERS]`.

| ID | Objective | Weight | V1 status |
|---|---|---:|---|
| O1 | Minimize passenger waiting time (headway proxy) | 10 | Disabled |
| O2 | Minimize headway deviation | 5 | Disabled |
| O3 | Minimize operational delay | 5 | Disabled |
| O4 | Minimize empty running | 2 | Disabled |
| O5 | Minimize depot movements | 2 | Disabled |
| O6 | Balance rake utilization | 3 | **ACTIVE** |
| O7 | Minimize reserve activation | 1 | Disabled |
| O8 | Crew overtime | — | Phase 3 |

**V1 objective:** O6 rake balance only, via `add_obj6_rake_balance` + `build_objective`.

**Formulation:**

- Target per rake: `floor(num_trips / num_rakes) = floor(255 / 18) = 14`.
- For each rake, `dev[r] = |trips_assigned[r] − 14|`.
- Objective: `Minimize(W_RAKE_BALANCE × OBJ_SCALE × Σ dev[r]) = Minimize(3 × 100 × Σ dev)`.

**Result (2026-11-15):** OPTIMAL, objective = 900.0
 (Σ dev = 3), best bound = 900.0, gap = 0.0%, solve time ~60 s. Rake distribution: 3 rakes × 15 trips, 15 rakes × 14 trips = 255.

The minimum achievable deviation under floor-target 14 is 3 (since 255 − 14×18 = 3). The solver achieves this minimum, which is why gap = 0%.

**Note on target choice:** the floor target (14) produces a minimum deviation of 3 (since 255 − 14×18 = 3). A ceiling target (ceil(255/18) = 15) would require 3 rakes × 14 + 15 rakes × 15 = 255, giving Σ dev = 15 × 0 + 3 × 1 = 3 as well, but with a different distribution. The current V1 uses the floor target consistently; this is a design choice, not an error, and is documented ...so the objective value 900 is interpretable...

**Multi-objective extension:** O1–O5 and O7 are declared in `config.py` as `W_*` constants but not active in the current objective. Restoring the full multi-term objective is future work.

## 7. Decision Variables

With real GTFS trips, trip times are fixed. The only real decision is rake assignment.

| Variable | Domain | Meaning |
|---|---|---|
| `trip[i].start` | constant | Trip i departure (from GTFS) |
| `trip[i].end` | constant | Trip i arrival (from GTFS) |
| `trip[i].duration` | constant | Arrival − departure (from GTFS) |
| `rake_trip[rake, i]` | bool | 1 iff rake does trip i |

There is no free `trip.start` variable. There are no synthetic trip IDs.

---

## 8. Output Format

Three files are written to `data/processed/`.

### 8.1 `solution.json`

Current shape (O6 rake balance active):

```json
{
  "status": "OPTIMAL",
  "elapsed_sec": 60.0,
  "objective": 900.0,
  "best_bound": 900.0,
  "gap_pct": 0.0,
  "num_trips": 255,
  "schedule": [ ... ]
}
```

`status = OPTIMAL` because CP-SAT proved no feasible schedule can have objective value below 900 under floor-target 14.

### 8.2 `schedule.csv`

```csv
trip_id,rake_id,direction,first_stop,last_stop,departure,arrival
WK_160,R001,UP,ALVA,TPHT,16:07:55,16:58:42
WK_49,R007,UP,MUTT,TPHT,07:48:00,08:30:44
```

`trip_id` = real GTFS ID (`WK_*`)
`departure` / `arrival` = `HH:MM:SS`, may exceed 24:00

### 8.3 `validation.json`

Per-check PASS / FAIL / SKIPPED with details.

---

## 9. Validation Layer

Independent of CP-SAT's own status. Every applicable hard constraint is rechecked from `schedule.csv`.

Current coverage (**10 PASS, 0 SKIPPED**):

| Rule | Status |
|---|---|
| R1 service coverage | PASS |
| R3 operating window | PASS |
| R4 fleet availability | PASS |
| R5 rake non-overlap | PASS |
| R6 turnaround + deadhead (per-pair 5/8/15) | PASS |
| R7 per-trip running time | PASS |
| R9 maintenance exclusivity | PASS (trivially while `maintenance.csv` empty) |
| R10 maintenance threshold | PASS |
| R11 terminal continuity (KVTR-aware) | PASS |
| D direction consistency | PASS |

R2 is not applicable (fixed trip times). **R8 (depot capacity) and R12 (non-service window) are removed from validator scope.** R9 and D are added.

Overall result (Phase 1, 255 trips): PASS, 10 PASS, 0 SKIPPED.

---

## 10. Model Limitations (V1)

- Muttom depot capacity — unbounded in V1.
- Deadhead values — synthetic (15 min terminal, 8 min MUTT).
- Objective — single-term O6 rake balance only (see §6). Multi-objective extension (O1–O5, O7) deferred.
- Optimality gap — reported as 0.0% because the O6 objective is proven optimal (best bound = objective = 900).
- Crew scheduling — out of scope for this train-layer file. **Phase 3 complete (2026-11-13); see `docs/phases.md` §Phase 3 and `docs/constraints-crew-v1.md`.**
- ML / XGBoost — deferred.
- Passenger demand — no demand model.
- Maintenance windows — `maintenance.csv` empty; R9 vacuous.
- Turnaround — synthetic (5 min).
- Initial rake split — synthetic (9 ALVA / 9 TPHT / 0 MUTTOM).
- DPR — removed from project; no DPR-based claims remain.
- GTFS validity — 2024-08-12 to 2025-12-31 (2024-25 timetable, not current 2026).
- Fleet — 18 service + 7 maintenance = 25 (from news 2026).

### Findings from v2.1 rebuild (2026-11-12)

- **[FINDING]** `add_obj6_rake_balance` must be called alongside `build_objective`. When both are called, the model is OPTIMAL with objective 900 in 60 s (2026-11-15). Earlier attempts to call `add_obj6_rake_balance` without `build_objective` during the 2026-11-12 rebuild produced mixed results (INFEASIBLE in some runs, but the code state was different). The precise cause was not conclusively diagnosed. The current committed configuration calls both together; this is the working configuration.

-**[FINDING]** R6 must compute per-order gap values. The v2 wording used one gap per pair (5 min if either order was same-terminal). This allowed cross-terminal switches (ALVA↔MUTT, TPHT↔MUTT) with gaps between 5 and 15 min. Validator caught 4 such violations on 250 trips. Fixed by computing `gap_ab` and `gap_ba` independently and enforcing each in the correct order.

-**[FINDING — corrected 2026-11-15]** Fleet-size behaviour revisited. Earlier versions of this document claimed that 250 trips with 18 rakes in a 9/9 split was INFEASIBLE, and that MUTTOM-origin rakes were required. That claim was an artifact of an **undocumented home-lock pruning rule** in `create_rake_assignment_variables` that blocked all 18 rakes from the earliest opposite-terminal trip of the day. With the home-lock removed, the **255-trip case is OPTIMAL at 9/9/0** (no MUTT-home service rakes) — objective 900.0, gap 0.0%, ~60 s. Verified by `probes/probe_9_9.py` and by the current committed solve. MUTT-home service rakes are **not required**; the current split is 9 ALVA / 9 TPHT / 0 service MUTTOM (7 maintenance rakes at MUTTOM).

---

## 11. Scenario Roadmap

| **Scenario** | **Status** | **Focus** |
| :--- | :--- | :--- |
| A — 232-trip feasibility baseline | OPTIMAL (feasibility only, 2026-11-12) | 232 trips, 18 rakes, 9/9 split — pre-objective debugging baseline |
| A' — Full GTFS service (255) | Proven OPTIMAL (2026-11-15) | 255 trips, 18 rakes, 9/9/0 split, objective 900.0, ~60 s |
| B — Peak-stress | Planned | Higher hourly demand |
| C — Maintenance-stress | Planned | Non-empty maintenance windows |
| D — Delay stress | Regenerated 2026-11-15 | SimPy sweep on 255-trip real schedule (E1–E4 + 100 seeds) |

---

## 12. Sign-Off

This specification is v2.3, dated 2026-11-15 (rebuilt on 255-trip GTFS model). It supersedes v2.2 (2026-11-12).

Changes from v2.2: trip count 250 → 255 (all WK trips now included, window extended to 04:40–24:00), fleet split 9/7/2 → 9/9/0, R6 per-pair deadhead (5/8/15 min), R11 KVTR rule, home-lock removal, R8 and R12 removed from validator scope, R9 and direction check added, objective 4800 → 900, validator 10 PASS + 0 SKIPPED.

Any change to constraints, parameters, or architecture requires:

- Update to this document.

- Version bump (v2.3 → v2.4 → v3).

- Explicit re-approval.