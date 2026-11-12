# MetroPulse — Constraint Specification v2.2

**Status:** Locked for V1 implementation (rebuilt on real GTFS trips)
**Date:** 2026-11-12
**Supersedes:** v2 (2026-11-08) — updates R6, R11, trip input, per-trip durations, validator coverage
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

- Uses **GTFS 2024-25 feed** for weekday service (250 trips: 232 full-route + 18 partial).
- Uses **KMRL Annual Report 2024-25** for route length, fleet, and service hours.
- Uses **news article 2026** for fleet breakdown (18 operating + 7 maintenance).
- Single-line metro (Aluva → Tripunithura).
- 17-hour operating window (06:00–23:00) `[EXTERNAL — Annual Report]`.
- Solver uses **real GTFS trip records**, not hourly counts and not synthetic `T0000` trips.
- **Deadhead IS modeled** (see §3.5).
- No crew scheduling in V1.
- No ML in V1.
- Objective minimization: **O6 rake balance active** (see §6).

### 2.2 Out of Scope for V1

- Crew rostering (Phase 3).
- XGBoost / ML predictions (optional, Phase 6).
- Stochastic SimPy feedback to CP-SAT.
- Muttom depot finite capacity.
- Depot-to-depot deadhead beyond §3.5.

---

## 3. Inputs

### 3.1 Trip Dataset (Solver Input) `[EXTERNAL — GTFS 2024-25]`

**The solver input is `data/trips_all.csv` (250 real GTFS trips).** It is the merge of:

- `data/trips_full_route.csv` — **232** full-route ALVA↔TPHT trips
- `data/trips_partial.csv` — **18** partial trips (Muttom ↔ terminals)

Schema:

```text
trip_id, origin_stop, destination_stop, direction,
departure_time, arrival_time, duration,
stop_count, first_stop, last_stop
```

`trip_id` = original GTFS trip_id (e.g., `WK_160`), not synthetic.
`departure_time` / `arrival_time` = original GTFS strings, may exceed 24:00.
`duration` = integer seconds (arrival − departure), includes intermediate dwell.

Reconciliation only: `data/hourly_service.csv` is kept on disk as an independent check (232 + 18 = 250, verified by `data/verify_gtfs_trips.py`). It is not read by the solver.

### 3.2 Physical Parameters

| Parameter | Value | Source |
|---|---:|---|
| Route length | 28.144 km | `[EXTERNAL — Annual Report 2024-25]` |
| One-way running time (median) | 50.47 min | `[DERIVED — GTFS 412 trips]` — summary statistic only |
| Per-trip running time | Real GTFS duration | `[EXTERNAL — GTFS]` — used by solver |
| Terminal turnaround | 5 min | `[SYNTHETIC]` |
| Stations | 25 | `[EXTERNAL — Annual Report]` |
| Operating window | 06:00 ≤ departure < 23:00 | `[EXTERNAL — Annual Report]` |

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
| TPHT | 7 | `[SYNTHETIC]` |
| MUTTOM | 2 | `[SYNTHETIC]` |

### 3.4 Depot / Stabling

| Location | Capacity | Source |
|---|---:|---|
| Info Park-2 | 2 | `[SYNTHETIC]` |
| Muttom Depot | UNBOUNDED_FOR_V1 | `[MODEL LIMITATION]` |

R8 (depot capacity) is SKIPPED in V1 — no stabling assignment exists.

### 3.5 Deadhead `[SYNTHETIC]`

Two values, both used by R6 and R11:

| Parameter | Value | Meaning |
|---|---:|---|
| `TERMINAL_TO_TERMINAL_DEADHEAD_MIN` | 15 min | ALVA ↔ TPHT switching |
| `MUTTOM_TO_TERMINAL_DEADHEAD_MIN` | 8 min | MUTTOM ↔ ALVA, MUTTOM ↔ TPHT |

Both tagged `[SYNTHETIC]`. No verified KMRL source.

### 3.6 Maintenance Threshold

| Parameter | Value | Source |
|---|---:|---|
| Rake maintenance threshold | 1,000,000 km | `[SYNTHETIC]` |

---

## 4. Data Quality Notes

### 4.1 GTFS Filtering

GTFS has 255 weekday trips in `trips.txt` (WK service). Of those:

- 232 trips are full-route (ALVA↔TPHT).
- 18 trips are partial (Muttom ↔ terminals).
- 5 trips depart outside 06:00–23:00 (WK_253, WK_4, WK_256, WK_12, WK_18) — excluded by policy as non-passenger movements.

232 + 18 = 250 trips in the V1 model.

### 4.2 Direction Determination

Direction is determined by station index from stop order (ALVA = 0 … TPHT = 24):

- `UP` = last station index > first station index
- `DOWN` = last station index < first station index

No fallback to `trips.txt direction_id`. Verified by `data/verify_gtfs_trips.py` (232 + 18 all consistent with `direction_id`, but the model uses stop order).

### 4.3 Window Boundary

Departure must satisfy `06:00:00 ≤ departure < 23:00:00`. A departure at exactly `23:00:00` is excluded (locked decision).

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

```python
06:00:00 <= departure < 23:00:00
```

Arrivals may extend past 23:00.

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

### R8 — Depot Capacity `[SYNTHETIC]`

Info Park-2 capacity = 2. Muttom = unbounded.

Not enforced in V1 (no stabling assignment exists). Validator: SKIPPED.

### R9 — Maintenance Exclusivity `[SYNTHETIC]`

A rake in maintenance cannot serve passenger trips. `maintenance.csv` is empty in V1, so R9 is vacuous — no scheduled maintenance windows exist.

### R10 — Maintenance Threshold `[SYNTHETIC]`

A rake with `initial_mileage_km >= 1,000,000` is blocked from trips.

Validator check: No trip in `schedule.csv` is assigned to a rake over the threshold.

### R11 — Terminal Continuity `[SYNTHETIC — first-trip home rule with deadhead]`

A rake whose home terminal is `H` may take a trip starting at `S` as its first trip of the day if:

- `S == H`, or
- the trip's departure is no earlier than `earliest_departure_of_day_from_H + deadhead(H, S)`.

This models a rake leaving its depot and deadheading to a terminal before the first trip. It is `[SYNTHETIC]` because no verified KMRL depot-dispatch data exists.

Pair gaps between consecutive trips are enforced by R6, not R11.

Validator check:

- First trip of each rake must satisfy the deadhead condition above.
- Cross-terminal switches between consecutive trips are counted (informational).

### R12 — Non-Service Window `[EXTERNAL]`

No departure before 06:00. Arrivals may extend past 23:00 (covered by R3).

Validator check: Every departure is ≥ 06:00.

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

- Target per rake: `floor(num_trips / num_rakes) = floor(250 / 18) = 13`.
- For each rake, `dev[r] = |trips_assigned[r] − 13|`.
- Objective: `Minimize(W_RAKE_BALANCE × OBJ_SCALE × Σ dev[r]) = Minimize(3 × 100 × Σ dev)`.

**Result (2026-11-12):** OPTIMAL, objective = 4800 (Σ dev = 16), best bound = 4800, gap = 0.0%, solve time 11.77s. Rake distribution: 16 rakes × 14 trips, 2 rakes × 13 trips = 250.

The minimum achievable deviation under floor-target 13 is 16 (since `250 − 13×18 = 16`). The solver achieves this minimum, which is why gap = 0%.

**Note on target choice:** the floor target (13) produces a minimum deviation of 16. A ceiling target (14) would produce a different, lower deviation (2). The current V1 uses the floor target consistently; this is a design choice, not an error, and is documented so the objective value 4800 is interpretable.

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
  "elapsed_sec": 11.77,
  "objective": 4800.0,
  "best_bound": 4800.0,
  "gap_pct": 0.0,
  "num_trips": 250,
  "schedule": [ ... ]
}
```

`status = OPTIMAL` because CP-SAT proved no feasible schedule can have objective value below 4800 (best bound = objective = 4800). The objective value 4800 corresponds to Σ dev = 16 under floor-target 13 (see §6).

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

Current coverage (10 PASS + 1 SKIPPED of 11 applicable):

| Rule | Status |
|---|---|
| R1 service coverage | PASS |
| R3 operating window | PASS |
| R4 fleet availability | PASS |
| R5 rake non-overlap | PASS |
| R6 turnaround + deadhead | PASS |
| R7 per-trip running time | PASS |
| R8 depot capacity | SKIPPED (no stabling in V1) |
| R10 maintenance threshold | PASS |
| R11 terminal continuity | PASS |
| R12 non-service window | PASS |

R2 is not applicable (fixed trip times). R9 is vacuous (empty `maintenance.csv`).

Overall result (Phase 1, 250 trips): PASS, 10 PASS + 1 SKIPPED.

---

## 10. Model Limitations (V1)

- Muttom depot capacity — unbounded in V1.
- Deadhead values — synthetic (15 min terminal, 8 min MUTT).
- Objective — single-term O6 rake balance only (see §6). Multi-objective extension (O1–O5, O7) deferred.
- Optimality gap — reported as 0.0% because the O6 objective is proven optimal (best bound = objective = 4800).
- Crew scheduling — deferred to Phase 3.
- ML / XGBoost — deferred.
- Passenger demand — no demand model.
- Maintenance windows — `maintenance.csv` empty; R9 vacuous.
- Turnaround — synthetic (5 min).
- Initial rake split — synthetic (9 ALVA / 7 TPHT / 2 MUTTOM).
- DPR — removed from project; no DPR-based claims remain.
- GTFS validity — 2024-08-12 to 2025-12-31 (2024-25 timetable, not current 2026).
- Fleet — 18 service + 7 maintenance = 25 (from news 2026).

### Findings from v2.1 rebuild (2026-11-12)

- **[FINDING]** `add_obj6_rake_balance` must be called alongside `build_objective`. When both are called, the model is OPTIMAL with objective 4800 in 11.77 s (2026-11-12). Earlier attempts to call `add_obj6_rake_balance` without `build_objective` during the 2026-11-12 rebuild produced mixed results (INFEASIBLE in some runs, but the code state was different). The precise cause was not conclusively diagnosed. The current committed configuration calls both together; this is the working configuration.

-**[FINDING]** R6 must compute per-order gap values. The v2 wording used one gap per pair (5 min if either order was same-terminal). This allowed cross-terminal switches (ALVA↔MUTT, TPHT↔MUTT) with gaps between 5 and 15 min. Validator caught 4 such violations on 250 trips. Fixed by computing `gap_ab` and `gap_ba` independently and enforcing each in the correct order.

-**[FINDING]** Fleet-size behaviour: 232 trips, 18 rakes, 9/9 split → OPTIMAL; 250 trips, 18 rakes, 9/9 split → INFEASIBLE (insufficient MUTT coverage); 250 trips, 18 rakes, 9/7/2 split → OPTIMAL. Adding more rakes (20, 22) does not fix the 250 case if the split does not include MUTTOM-origin rakes.

---

## 11. Scenario Roadmap

| Scenario | Status | Focus |
|---|---|---|
| A — 232-trip feasibility baseline | OPTIMAL (feasibility only, 2026-11-12) | 232 trips, 18 rakes, 9/9 split — pre-objective debugging baseline |
| A' — Full GTFS service (250) | Proven OPTIMAL (2026-11-12) | 250 trips, 18 rakes, 9/7/2 split |
| B — Peak-stress | Planned | Higher hourly demand |
| C — Maintenance-stress | Planned | Non-empty maintenance windows |
| D — Delay stress | **Rebuilt 2026-11-12** | SimPy sweep on 250-trip real schedule (E1–E4 + 100 seeds) |

---

## 12. Sign-Off

This specification is v2.1, dated 2026-11-12. It supersedes v2 (2026-11-08).

Any change to constraints, parameters, or architecture requires:

1. Update to this document.
2. Version bump (v2.1 → v2.2 → v3).
3. Explicit re-approval.
