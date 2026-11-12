# MetroPulse — Crew Constraint Specification v1 (Phase 3)

**Status:** Locked for V1 implementation  
**Date:** 2026-11-13  
**Scope:** Crew scheduling layer only (SC/TO driver assignment to 250 Phase 1 trips).  
**Relationship to `constraints-v2.2.md`:** that file covers the **train layer**. This file covers the **crew layer**. Neither supersedes the other.

---

## 1. Source Classification

Every parameter is tagged with one of:

| Tag | Meaning |
|---|---|
| `[EXTERNAL]` | External authoritative source (KMRL rules, Metro Railways General Rules) |
| `[DERIVED]` | Computed from an external source |
| `[SYNTHETIC]` | Project assumption |
| `[MODEL LIMITATION]` | Deliberate simplification |

---

## 2. Scope & Scenario

- Reads `data/processed/schedule.csv` (Phase 1 output — 250 trips, read-only) and `data/synthetic/drivers.csv`.
- Assigns each of the 250 trips to exactly one driver.
- Single-day planning. No rostering across days in V1.
- Pool sizes tested: **45, 50, 55** `[SYNTHETIC]`.
- Solver: OR-Tools CP-SAT.
- `num_search_workers = 4` → may be **non-deterministic between runs**. Documented, not hidden.

### 2.1 Out of Scope for V1

- Multi-day rostering (C5 rest rule). **Deferred to V2.**
- Per-driver qualifications / availability / shift preferences / weekly availability. **Deferred to V2.**
- Real-time crew re-rostering.

---

## 3. Inputs

### 3.1 `data/processed/schedule.csv` `[EXTERNAL — Phase 1 output]`

Schema (7 columns, unchanged from Phase 1):

```text
trip_id, rake_id, direction, first_stop, last_stop, departure, arrival
```

- `trip_id` = real GTFS ID (e.g. `WK_1`).
- `departure` / `arrival` = `HH:MM:SS`, may exceed 24:00.
- `rake_id` is carried but **not used by the crew solver** — a driver can take trips from different rakes.

### 3.2 `data/synthetic/drivers.csv` `[SYNTHETIC]`

Schema (V1):

```text
driver_id
```

55 rows: `D001` … `D055`. Driver qualifications, availability, shift preferences, and weekly availability are **deferred to V2** — same honesty pattern as C5.

### 3.3 Operational Parameters

| Parameter | Value | Tag / Source |
|---|---:|---|
| Total SC/TO operators (KMRL) | 60 | `[EXTERNAL]` — cited in handoff §1 |
| Daily-active pool sizes tested | 45, 50, 55 | `[SYNTHETIC]` |
| Max active duty | 28,800 s (8 h) | `[EXTERNAL]` — Metro Railways General Rules / KMRL |
| Sign-on buffer | 900 s | `[EXTERNAL]` — pre-departure checks |
| Sign-off buffer | 900 s | `[EXTERNAL]` — post-departure checks |
| Total depot time ceiling | 30,600 s (8 h 30 m) | `[DERIVED]` (8 h + 15 m + 15 m) |
| Min rest between shifts | 43,200 s (12 h) | `[EXTERNAL]` — deferred to V2 (C5) |
| Continuous driving limit (preferred) | 18,000 s (5 h) | `[SYNTHETIC]` |
| Continuous driving limit (relaxed) | 21,600 s (6 h) | `[SYNTHETIC]` |
| Continuous-driving break threshold | 300 s (5 min) = `MIN_TURNAROUND_SEC` | `[DERIVED]` from C1 turnaround |
| Sick-leave reserve (preferred) | ≥ 5 drivers unused | `[SYNTHETIC]` |
| Min turnaround between trips | 300 s (5 min) | `[SYNTHETIC]` |

---

## 4. Hard Constraints (C1–C4)

### C1 — No Overlap `[EXTERNAL — KMRL]`

For each driver, no two assigned trips may overlap:

```text
arr(a) + 300 s ≤ dep(b)   for any two trips a, b assigned to same driver, a before b
```

Validator: for each driver, sort assigned trips by departure; check `arr(prev) + 300 ≤ dep(next)`. Any violation → FAIL.

### C2 — Max Active Duty `[EXTERNAL — 8 h rule]`

For each active driver:

```text
last_arr(d) − first_dep(d) ≤ 28,800 s
```

Validator: for each driver with ≥ 1 trip, compute `last_arr − first_dep`; any > 28,800 s → FAIL.

### C3 — Sign-On / Sign-Off Buffers `[EXTERNAL]`

```text
sign_on(d)  = first_dep(d) − 900 s
sign_off(d) = last_arr(d)  + 900 s
```

Both must be ≥ 900 s from the nearest trip edge (guaranteed by construction; validator checks explicitly).

Validator: for each row in `crew_schedule.csv`, `dep − sign_on ≥ 900` and `sign_off − arr ≥ 900` for that trip.

### C4 — Full Coverage `[EXTERNAL]`

Each of the 250 trips is assigned to **exactly one** driver.

Validator: `crew_schedule.csv` per pool has exactly 250 rows, each `trip_id` once.

### C5 — Min Rest (12 h) — **DEFERRED**

Defined but **not enforced** in single-day V1. No solver constraint. No validator check. Enforced in V2 multi-day model. Same honesty pattern as Phase 1 R8 (SKIPPED).

---

## 5. Soft Constraints / Objectives (C6–C7)

### C6 — Continuous Driving ≤ 5 h `[SYNTHETIC]`

A **chain** = maximal sequence of consecutive trips assigned to the same driver where each inter-trip gap ≤ `MIN_TURNAROUND_SEC` (300 s).

Penalize `Σ over chains of max(0, chain_drive_time − 18,000 s)`.

Implemented as a **state machine** in CP-SAT: per (driver, trip index) carry `last_arr`, `run_drive`, `has_prev`, `new_chain`, `end_of_chain`, `over` (6 vars per pair). Weight: 10.

Validator: **not checked** — C6 is soft / informational only.

### C7 — Reserve Buffer ≥ 5 `[SYNTHETIC]`

Penalize using more than `(pool_size − 5)` drivers.

- PASS: active ≤ `pool_size − 5`
- WARN: active in `[pool_size − 4, pool_size]`
- FAIL: active > `pool_size`

Weight: 15.

---

## 6. Decision Variables

| Variable | Domain | Meaning |
|---|---|---|
| `x[d, t]` | bool | Driver d assigned to trip t |
| `active[d]` | bool | 1 iff driver d has ≥ 1 trip |
| `first_dep[d]` | int (s) | departure of d's first trip (0 if inactive) |
| `last_arr[d]` | int (s) | arrival of d's last trip (0 if inactive) |

`first_dep` and `last_arr` are **derived** from trip assignments, not free — so C2 is meaningful.

---

## 7. Outputs

### 7.1 `data/processed/crew_schedule.csv`

```text
trip_id, driver_id, sign_on, sign_off, pool_size
```

One row per (trip, pool). **750 rows total** (250 trips × 3 pools).

### 7.2 `data/processed/crew_solution.json`

Keyed by `"45"`, `"50"`, `"55"`. Each entry:

```json
{
  "status": "OPTIMAL",
  "pool_size": 45,
  "elapsed_sec": 57.25,
  "objective": 0.0,
  "best_bound": 0.0,
  "gap_pct": 0.0,
  "num_trips": 250,
  "num_active_drivers": 40,
  "reserve": 5,
  "assignments": []
}
```

### 7.3 `data/processed/crew_validation.json`

```json
{
  "overall": "PASS",
  "pools": {
    "45": {"checks": [], "pool_status": "PASS"},
    "50": {"checks": [], "pool_status": "PASS"},
    "55": {"checks": [], "pool_status": "PASS"}
  }
}
```

---

## 8. Results (2026-11-13)

| Pool | Status | Time | Active | Reserve | Objective | Gap |
|---|---|---:|---:|---:|---:|---:|
| 45 | OPTIMAL | 57.25 s | 40 | 5 | 0.0 | 0.0% |
| 50 | OPTIMAL | 58.80 s | 45 | 5 | 0.0 | 0.0% |
| 55 | OPTIMAL | 64.34 s | 50 | 5 | 0.0 | 0.0% |

All hard constraints PASS independent validation at all pools. C7 PASS at all pools. Overall: **PASS**.

---

## 9. Model Limitations (V1)

- Single-day only. **C5 (12 h rest) not enforced.**
- Driver qualifications / availability / shift preferences / weekly availability — **deferred to V2.**
- CP-SAT non-determinism with `num_search_workers = 4` — results may vary between runs.
- C6 break threshold is **300 s (5 min)**, derived from C1 turnaround, not an independent operational constant.
- Objective = 0 at all pools → the solver found schedules with **zero C6 and C7 penalty**. This does not prove that no driver was near the 5 h chain limit — it proves the penalty term is zero. Individual chain lengths are in `crew_solution.json` under `assignments` if inspected.

---

## 10. Sign-Off

This is crew constraint specification **v1**, dated 2026-11-13. It complements (does not replace) `constraints-v2.2.md` (train layer).

Any change requires:

1. Update to this document.
2. Version bump (v1 → v2).
3. Explicit re-approval.

**Deviation note:** this file was created at user's request on 2026-11-13. The handoff `6/10` did not list a separate crew-constraint spec; C1–C7 detail was intended for `phases.md` `Phase 3`. This file is a **stylistic companion**, not a replacement for the `phases.md` `Phase 3` update. Both are kept; `phases.md` is the canonical summary.