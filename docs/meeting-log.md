# MetroPulse Meeting Log

---

## Meeting 1 — 2026-09-27
**Attendees:** [Names]
**Duration:** 30 min
**Agenda:** Phase 0 setup — project bootstrap

**Decisions:**
- Tool stack finalized (Python 3.11, pandas, networkx, SimPy, OR-Tools, Streamlit)
- Folder structure created (`data/`, `src/`, `docs/`, `notebooks/`)
- Virtual environment set up (`venv`)
- Git initialized, pushed to GitHub

**Action Items:**
- [x] Install Python 3.11
- [x] Install VS Code + Python extension
- [x] Create project folder
- [x] Activate virtual environment
- [x] Install `requirements.txt`
- [x] Create `.gitignore`
- [x] Add `.gitkeep` files
- [x] Initialize Git + push to GitHub

**Next Meeting:** 2026-09-28

---

## Meeting 2 — 2026-09-28
**Attendees:** [Names]
**Duration:** 30 min
**Agenda:** Phase 1 — GTFS ingestion

**Decisions:**
- KMRL GTFS feed is our Phase 1 dataset (real data, not synthetic)
- Feed stored in `data/raw/` (excluded from Git via `.gitignore`)
- Loader module: `src/loaders/gtfs_loader.py`
- All tables loaded as strings to preserve leading zeros in IDs and times

**Action Items:**
- [x] Copy 11 GTFS `.txt` files into `data/raw/`
- [x] Write `docs/data-provenance.md`
- [x] Update `.gitignore`
- [x] Write `data/raw/README.md`
- [x] Write `src/loaders/gtfs_loader.py`

**Notes:**
- Feed has 24 stops, 1 route, 252 trips, ~6300 stop_times *(pre-audit count; superseded — 25 stations per Annual Report and rebuilt GTFS extraction, see Meeting 10)*

**Next Meeting:** 2026-09-28

---

## Meeting 3 — 2026-09-28
**Attendees:** [Names]
**Duration:** 20 min
**Agenda:** Phase 1 — GTFS validation

**Decisions:**
- 7 validation categories: referential integrity, monotonic sequences, time format, temporal ordering, calendar dates, fare coverage, duplicates
- Exit code 1 on any ERROR → enables future CI integration

**Action Items:**
- [x] Write `src/validation/gtfs_checks.py` — 19 checks, all pass
- [x] Update `docs/checklist.md`

**Notes:**
- Feed passed all 19 checks

**Next Meeting:** 2026-10-03

---

## Meeting 4 — 2026-10-03
**Attendees:** [Names]
**Duration:** 45 min
**Agenda:** Phase 1 review — CP-SAT solver complete

**Decisions:**
- Spec v2 locked (DPR-driven, no invented thresholds) — later superseded
- CP-SAT model uses interval variables and AddNoOverlap
- R6 turnaround rewritten with window-based pair pruning
- Validator is the source of truth
- 300s time limit accepted for V1

**Action Items:**
- [x] Full-day solve: 408 trips, FEASIBLE (superseded)
- [x] Validator: all 7 checks PASS (superseded)
- [ ] Next: SimPy simulation

**Notes:**
- Initial solve failed validation on R1 and R6 — fixed both
- Two real bugs found by validator

**Next Meeting:** 2026-10-15

---

## Meeting 5 — 2026-10-15
**Attendees:** [Names]
**Duration:** 40 min
**Agenda:** Critical audit — DPR assumptions found to be unverifiable

**Decisions:**
- The "DPR" document in the project was actually the KMRL Annual Report 2024-25, not the DPR
- Values tagged `[DPR]` were unverified: 10.715 km, 18.91 min, 408 trips, 18-rake fleet, 3-min turnaround
- Pivot: use only verified sources (GTFS + Annual Report + news article)
- All DPR-based values must be removed

**Action Items:**
- [x] Grep "DPR file" for `10.715` — not found
- [x] Grep for `28.125` — not found
- [x] Confirmed `KMRLGTFS2.md` is Annual Report, not DPR
- [x] Locate GTFS-derived running time via analysis

**Next Meeting:** 2026-10-20

---

## Meeting 6 — 2026-10-20
**Attendees:** [Names]
**Duration:** 35 min
**Agenda:** GTFS analysis — real running time and trip count

**Decisions:**
- Real one-way running time: **50.47 min** (median over 412 GTFS trips)
- Real weekday trips: **250** (255 in GTFS, 5 excluded because their departures are outside the selected 06:00–23:00 model window)
- Real route length: **28.144 km** (Annual Report)
- Real service window: **06:00–23:00** (Annual Report)

**Action Items:**
- [x] Write `data/extract_gtfs_hourly.py`
- [x] Generate `data/hourly_service.csv` (250 trips, 17 hours)
- [x] Document GTFS filtering

**Next Meeting:** 2026-10-25

---

## Meeting 7 — 2026-10-25
**Attendees:** [Names]
**Duration:** 30 min
**Agenda:** Fleet and configuration update

**Decisions:**
- Fleet: **25 total** (news 2026: 18 operating + 7 maintenance)
- V1 uses 18 service rakes (aggregate fleet-capacity utilization estimate: 250 × 50.47 / (18 × 17 × 60) ≈ 69%)
- Turnaround: **5 min** `[SYNTHETIC]`
- Maintenance threshold: **1,000,000 km** `[SYNTHETIC]`

**Action Items:**
- [x] Update `solver/config.py` (SERVICE_RAKES=18, ONE_WAY_RUNNING_MIN=50.47, window 06:00–23:00)
- [x] Update `data/generate_synthetic_v2.py` (25 rakes: 18 service + 7 maintenance)
- [x] Update `solver/models.py` (new CSV format, status column)
- [x] Update `solver/validator.py` (R1/R3/R4/R12)

**Next Meeting:** 2026-11-08

---

## Meeting 8 — 2026-11-08
**Attendees:** [Names]
**Duration:** 50 min
**Agenda:** Phase 1 complete on verified data

**Decisions:**
- Phase 1 complete: 250 trips with 18 service rakes using 50.47 min GTFS median running time
- Current validator result: 9 PASS + 1 SKIPPED, Overall PASS
- R8 is skipped because V1 does not include stabling assignments
- R9 and R11 are not included in the current validation results
- Ready for Phase 2 (SimPy)

**Action Items:**
- [x] Solve: FEASIBLE, 250 trips, ~306s, objective 1,102,800, gap 93.40%
- [x] Validate: all 232 consecutive same-rake trip pairs have ≥5 min turnaround
- [x] Rewrite docs (checklist, constraints-v2, data-provenance, project-status)
- [ ] Next: Phase 2 — SimPy simulation

**Notes:**
- Solve time approximately 306s with R6 pruning; solver time limit is 300s
- Optimality gap 93.40% (FEASIBLE, not proven optimal)
- Validator: 9 PASS + 1 SKIPPED; R8 skipped, R9/R11 not included in current validation
- No DPR-based values remain
- GTFS feed is static and represents the 2024–25 data vintage, not a live 2026 timetable.

**Next Meeting:** 2026-11-11

---

## Meeting 9 — 2026-11-11
**Attendees:** [Names]
**Duration:** ~90 min (across two sessions)
**Agenda:** Phase 2 — SimPy operational simulation complete

**Decisions:**
- Delay model: clipped normal, pre-clip mean **−48 s**, std swept **0 / 60 / 120 / 300 s**, clip **[0, 300 s]** `[SYNTHETIC]`
- Rounding rule: **clip-then-round** (Python `round`, half-to-even). One shared function used in experiments and tests.
- Propagation: Option A — next trip waits for previous arrival + 5-min turnaround
- Common random numbers: one `z` per trip, drawn once with seed 42 in sorted `trip_id` order, shared across all stds
- Monte Carlo: 100 seeds (42–141), same seed list for every std. Report mean + p5–p95.
- On-time metric: dual denominator — 250 (headline, operational) and 232 eligible (secondary, isolates propagation). One-sided: "late by at most N", since delays are never negative.
- Headway violations: same-direction gaps strictly < 120 s. Report actual-gap violations separately from scheduled-gap violations.
- Run entry point: `python -m src.simulation.experiments` (not `simpy_runner.py` as originally planned)
- Pre-flight limitation accepted: terminal continuity cannot be verified from Phase 1 outputs (no GTFS↔`Txxxx` map). Phase 2 models delay flow, not physical route movement. Documented as a known limitation.

**Action Items:**
- [x] `src/simulation/schedule_loader.py` — strict loader with parsing guards, count cross-check
- [x] `src/simulation/reference.py` — closed-form recurrence (correctness baseline)
- [x] `src/simulation/simpy_runner.py` — SimPy per-rake process, output matches reference bit-for-bit
- [x] `src/simulation/kpis.py` — pure KPI functions, no SimPy import
- [x] `src/simulation/experiments.py` — E1–E4 + Monte Carlo runner
- [x] `src/simulation/preflight.py` — read-only continuity/slack/headway analysis
- [x] 55 tests passing across 4 test files
- [x] Outputs written: `data/processed/simulation_kpis.json`, `simulation_timeline.csv`
- [ ] Next: Phase 3 — Crew Scheduling

**Notes:**
- Headline (seed 42) results: E1 0% propagation; E2 3.88%; E3 7.76%; E4 11.64%. Total propagated delay at E4 = 63.2 min.
- 100-seed Monte Carlo at E4: propagation mean **13.12%** (p5–p95: 10.3–15.9%). Seed 42 sits below the mean — treat the mean as the expected value.
- **±5 on-time = 100% across all experiments and all 100 seeds.** Structural, not lucky: own delay is capped at 300 s, ±5 is inclusive, and measured slack keeps cumulative delay below the cap. **Model property, not operational guarantee.** Scenarios with a higher delay cap or tighter slack would show ±5 degradation.
- Scheduled headway violations = 0 at every std (R2 holds — R2 was later removed from V1 in constraints-v2.1/2.2; this line records the pre-removal state). Actual-gap violations rise with std (E1: 0 → E4: 33.3 mean), reflecting departure bunching under delay.

- R9 and R11 remain outside the Phase 1 validator results — unchanged from Meeting 8. Phase 2 does not touch R1–R12.
- Terminal continuity: 127 of 232 pairs broken by direction alternation. Cannot distinguish real gap from labeling artifact — no GTFS↔`Txxxx` map exists in Phase 1 outputs. Deferred to Phase 4/5 where terminal awareness matters. *(This predates the Phase 1 rebuild on real GTFS trips in Meeting 10.)*
- `solver/` stays at project root (Phase 1 legacy); `src/simulation/` sits under `src/` as planned. Asymmetry is historical, harmless, noted here.
- All Phase 2 work is committed and pushed to GitHub.

**Next Meeting:** Phase 3 kickoff

---

## Meeting 10 — 2026-11-12
**Attendees:** [Names]
**Duration:** ~6 hours (across many sessions)
**Agenda:** Phase 1 rebuild on real GTFS trip records — 232 + 18 partial = 250

**Decisions:**
- **Phase 1 is rebuilt on real GTFS trip records**, not hourly counts and not synthetic `T0000` trips.
- Trip input is now `data/trips_all.csv` (232 full-route + 18 partial = 250). Built by `data/extract_gtfs_trips.py` + `data/merge_trips.py`, verified by `data/verify_gtfs_trips.py`.
- **Per-trip GTFS durations** are used by the solver. The 50.47-min median is now only a summary statistic, not a model input.
- **Window boundary locked:** `06:00:00 ≤ departure < 23:00:00`. A departure at exactly 23:00:00 is excluded.
- **Direction rule locked:** UP if last station index > first station index; DOWN otherwise. Station index from stop order (ALVA=0 … TPHT=24). No fallback to `direction_id`.
- **Initial rake split changed:** 9 ALVA / 7 TPHT / 2 MUTTOM (was 9 / 9 / 0). `[SYNTHETIC]`.
- **Deadhead modeled:** 15 min terminal↔terminal `[SYNTHETIC]`, 8 min MUTTOM↔terminal `[SYNTHETIC]`.
- **R11 updated:** first-trip home rule with deadhead allowance. R11 no longer duplicates pair gaps — those are R6's job.
- **Objective disabled in V1** because `add_obj6_rake_balance` makes the model INFEASIBLE when `build_objective` is not called. V1 is a feasibility probe.
- **`constraints-v2.1` supersedes `constraints-v2`** (v2 date 2026-11-08, v2.1 date 2026-11-12).
- **Phase 2 (SimPy) outputs are STALE.** `simulation_kpis.json` and `simulation_timeline.csv` were computed on the pre-rebuild synthetic schedule. They must be regenerated on the new 250-trip real-GTFS schedule. *(Resolved in Meeting 11.)*

**Action Items:**
- [x] `data/extract_gtfs_trips.py` — extracts per-trip GTFS records
- [x] `data/trips_full_route.csv` (232) and `data/trips_partial.csv` (18)
- [x] `data/stop_sequences_*` — full stop sequences for audit
- [x] `data/verify_gtfs_trips.py` — reconciliation: 232 + 18 = 250, all direction and window checks pass
- [x] `data/merge_trips.py` → `data/trips_all.csv` (250 rows)
- [x] `solver/models.py` — loads `trips_all.csv`, per-trip durations, seconds parsing supports `>24:00`
- [x] `solver/constraints.py` — real trip intervals, R6 per-order gap fix, R11 first-trip home rule with deadhead, `add_obj6` disabled
- [x] `solver/config.py` — new paths, `CP_SAT_NUM_WORKERS=4` (laptop memory), deadhead constants, initial split
- [x] `solver/solve.py` — feasibility probe, no `o6` call
- [x] `solver/validator.py` — 10 applicable checks including R6 per-order and R11 first-trip home rule
- [x] 250-trip solve: **OPTIMAL, 28.73 s**
- [x] 250-trip validator: **10 PASS + 1 SKIPPED (R8), Overall PASS**
- [x] Doc pass in progress: `checklist.md`, `constraints-v2.md` (v2.1), `data-provenance.md`
- [x] Next: regenerate Phase 2 (SimPy) on the new 250-trip schedule — done in Meeting 11
- [x] Next: `project-status.md` update — done in Meeting 11

**Notes:**

- **Diagnosis trail.** 250-trip case initially returned `INFEASIBLE` in 9–17 s repeatedly. Probes isolated two distinct bugs:
  1. `add_obj6_rake_balance` was called with `build_objective` commented out. The function adds `dev` auxiliary variables that make the model INFEASIBLE when there is no objective to minimize. Fix: do not call `o6` when `build_objective` is off. `[FINDING]`
  2. R6 used one gap value per pair, chosen by whichever direction was same-terminal. For the 250-trip case, this allowed cross-terminal switches (ALVA↔MUTT, TPHT↔MUTT) with gaps between 5 and 15 min. The validator caught 4 such violations. Fix: compute `gap_ab` and `gap_ba` independently and enforce each in the correct order. `[FINDING]`

- **Fleet-size behaviour observed during diagnosis:**
  - 232 trips, 18 rakes, 9/9 split → OPTIMAL (~29 s)
  - 250 trips, 18 rakes, 9/9 split → INFEASIBLE (insufficient MUTT coverage)
  - 250 trips, 18 rakes, 9/7/2 split → OPTIMAL (~28.7 s)
  - Adding more rakes (20, 22) does not fix the 250 case if the split does not include MUTTOM-origin rakes.

- **`[FINDING]` for future work:** When the objective is re-enabled, verify that O6 does not have the same side effect. Either restructure `add_obj6_rake_balance` so its auxiliary variables are tied to a minimized objective, or remove the function entirely and implement rake-balance through a different mechanism.

- **Verification commands and file state.**
  - The 250-trip result on disk: `data/processed/schedule.csv`, `solution.json`, `validation.json` (saved after the Meeting 10 run).
  - The 232-trip result is also proven OPTIMAL and can be regenerated any time.
  - `hourly_service.csv` is kept on disk for reconciliation only; not read by the solver.

- **GTFS data vintage.** Feed is 2024-08-12 to 2025-12-31. It represents the 2024–25 timetable, not current 2026 operations. The 2026 news article provides only the fleet breakdown; it does not update the timetable.

- **No DPR-based values remain.** The 2026-10-15 pivot (Meeting 5) fully removed them. All tags are now EXTERNAL / DERIVED / SYNTHETIC / MODEL LIMITATION.

- **Committed and pushed to GitHub.** All source code, data scripts, and doc updates from this meeting.

**Next Meeting:** 2026-11-12 (Phase 2 rebuild)

---

## Meeting 11 — 2026-11-12
**Attendees:** [Names]
**Duration:** ~3 hours
**Agenda:** Phase 2 rebuild on 250-trip real-GTFS schedule

**Decisions:**
- Phase 2 SimPy was rebuilt on the new 250-trip schedule (232 full + 18 partial).
- Per-trip GTFS durations replace the old fixed 3000 s constant across loader, reference, SimPy runner, and experiments.
- `RUNNING_SEC = 3000` is kept in `reference.py` as a **deprecated legacy constant** so old test fixtures still import it. Not used in the recurrence.
- `schedule_loader` sanity range `[300, 4500]` s allows short partial trips (MUTT→ALVA ~8 min) while rejecting garbage.
- Old `simulation_kpis.json` and `simulation_timeline.csv` are superseded; regenerated 2026-11-12.

**Action Items:**
- [x] `schedule_loader.py` — per-trip `duration_sec`, sane range guard
- [x] `reference.py` — per-trip duration in `propagate()`; `RUNNING_SEC` deprecated
- [x] `simpy_runner.py` — per-trip `trip_running`; guard updated
- [x] `experiments.py` — metadata now reflects per-trip durations; docstring corrected (terminal continuity and deadhead now validated)
- [x] `tests/test_simpy_matches_reference.py` — fixtures now include `duration_sec`; real-schedule test uses real `WK_*` IDs
- [x] `tests/test_reference.py` — fixtures now include `duration_sec`
- [x] `tests/test_schedule_loader.py` — refreshed for new loader API; added `HH:MM:SS` and `24:03:45` parsing tests; replaced 3000-s fixed-duration test with three tests: accepts short partial, rejects too-short, rejects too-long
- [x] **59 tests passing** (up from 55)
- [x] `simulation_kpis.json` and `simulation_timeline.csv` regenerated
- [ ] Next: Phase 3 kickoff (Crew Scheduling)

**Notes:**

- **Authoritative source for current KPI values:** `data/processed/simulation_kpis.json`. Numbers quoted below are snapshots; if that JSON disagrees with this log, the JSON is correct.

- **Real schedule KPIs (seed 42, 250 trips, current `schedule.csv`):**
  - E1 (std 0): 100% ±5, 0.00% propagation, 3 scheduled headway violations
  - E2 (std 60): 100% ±5, 1.72% propagation
  - E3 (std 120): 100% ±5, 4.74% propagation
  - E4 (std 300): 100% ±5, 7.33% propagation
- The KPI numbers above are from the current `schedule.csv`. A prior run on a different but valid OPTIMAL schedule showed propagation E2 0.86%, E3 3.02%, E4 6.47%. Both are correct for their respective schedules — CP-SAT non-determinism (documented below).
- ±3/±1 on-time degrade under higher std as expected: E4 mean ±3 75.95%, ±1 60.84%.
- **3 scheduled same-direction pairs at 0 s gap** in the raw GTFS timetable. Identified as data fact during Phase 2 preflight: each pair is a full trip (TPHT→ALVA) plus a partial trip (MUTT→ALVA) departing the same minute on **different rakes**. Not a solver or simulation error. R2 was removed from V1 in `constraints-v2.1` §5.
- `metadata.running_time_sec` in the KPI JSON is `"per-trip (GTFS duration_sec)"` (string), not a number. Consumers should not parse it as int.
- ±5 on-time 100% remains a **structural model property** (own-delay cap 300 s = ±5 inclusive), not an operational guarantee.
- All Phase 2 delay values are `[SYNTHETIC]`. Model behaviour, not real KMRL performance.
- All work committed. Repo state clean.
- `[FINDING]` Phase 1 solver is **non-deterministic** when the objective is disabled (feasibility probe mode). A fresh run may produce a different valid rake assignment than `schedule_250_trips.csv`. Both are OPTIMAL under the empty objective and PASS the independent validator. This is normal CP-SAT behaviour with `num_search_workers > 1` and no objective. The frozen baseline is one valid reference solution, not the unique solution.

**Next Meeting:** Phase 3 kickoff (Crew Scheduling).

---

## Meeting 12 — 2026-11-12
**Attendees:** [Names]
**Duration:** ~1 hour
**Agenda:** Phase 1 objective restored — O6 rake balance active

**Decisions:**
- `solver/solve.py` now calls `add_obj6_rake_balance` + `build_objective`. The objective is active.
- Phase 1 is **real optimization**, not a feasibility probe.
- `constraints-v2.1` → `constraints-v2.2` (objective status updated, `add_obj6` finding corrected).

**Action Items:**
- [x] `solver/solve.py` — insert `o6 = C.add_obj6_rake_balance(...)` + `C.build_objective(model, o6)` before solver construction
- [x] Re-run `python -m solver.solve` — OPTIMAL, 11.77 s
- [x] Re-run `python -m solver.validator` — 10 PASS + 1 SKIPPED, Overall PASS
- [x] Verify rake distribution matches objective math
- [x] Update `constraints-v2.2`, `project-status.md`, `checklist.md`, `data-provenance.md`

**Notes:**
- **Result:** status = OPTIMAL, objective = 4800.0, best_bound = 4800.0, gap = 0.0%, elapsed = 11.77 s.
- **Objective interpretation:** O6 rake balance only (`W_RAKE_BALANCE × OBJ_SCALE × Σ dev` = 3 × 100 × 16). Target per rake = floor(250/18) = 13. Sum of absolute deviations = 16. Rake distribution: 16 rakes × 14 trips, 2 rakes × 13 trips = 250.
- **Corrected [FINDING]:** The Meeting 10 claim that `add_obj6_rake_balance` alone (without `build_objective`) causes INFEASIBLE is **not proven**. The cause of the earlier INFEASIBLE was not conclusively diagnosed. The current committed configuration calls both together, and this works reliably across reruns.
- Validator output identical to Meeting 10 (same 10 PASS + 1 SKIP, Overall PASS) — objective change does not affect constraint satisfaction.
- `constraints-v2.2` §6 documents the active objective; §8.1 shows the updated `solution.json` shape; §10 carries the corrected finding.

**Next Meeting:** Phase 3 kickoff (Crew Scheduling).

---

## Meeting 13 — 2026-11-13
**Attendees:** [Names]
**Duration:** ~5 hours (across many sessions)
**Agenda:** Phase 3 — Crew Scheduling (CP-SAT)

**Decisions:**
- **Phase 3 is complete.** Crew scheduling assigns all 250 Phase 1 trips to SC/TO drivers.
- **Solver:** OR-Tools CP-SAT, looping over `POOL_SIZES = [45, 50, 55]`.
- **Inputs:** `data/processed/schedule.csv` (Phase 1 output, read-only) and `data/synthetic/drivers.csv` (55 synthetic drivers, `driver_id` only in V1). The 55 count is `[SYNTHETIC]` — KMRL has 60 SC/TO operators `[EXTERNAL]`, and the 55-driver roster is a controlled test pool, not a claim about real KMRL staffing.
- **`drivers.csv` schema (V1):** `driver_id` only. **Driver qualifications, availability, shift preferences, and weekly availability are deferred to V2** — same honesty pattern as C5.
- **Constraints:**
  - **C1** no overlap (`arr + 300 s ≤ next dep`) — hard
  - **C2** max active duty (`last_arr − first_dep ≤ 28,800 s`) — hard
  - **C3** sign-on / sign-off buffers (≥ 900 s each side) — hard
  - **C4** full coverage (250 / 250 trips) — hard
  - **C5** min rest 12 h — **DEFERRED, not exercised in single-day V1.** No solver constraint, no validator check.
  - **C6** continuous driving ≤ 5 h — **soft**, weight 10. Break threshold = `MIN_TURNAROUND_SEC` (300 s) `[DERIVED from C1]`. Implemented as a **state machine** (6 vars per `(d, i)`, ~82,500 new vars) because the earlier O(n²) run-enumeration approach was rejected at ~3.4M vars.
  - **C7** reserve buffer ≥ 5 drivers — **soft**, weight 15. Validator WARNs if `active > pool_size − 5`; FAILs if `active > pool_size`.
- **C5 is documented as deferred**, not silently dropped. Same honesty pattern as Phase 1 R8 (SKIPPED).
- **No DPR values reintroduced.** No invented thresholds. The C6 break threshold is the C1 turnaround reused, not an invented 30 min.
- **CP-SAT non-determinism with `num_search_workers = 4`** is expected and documented, not hidden.

**Action Items:**
- [x] `data/generate_drivers.py` — generates 55 drivers `D001`–`D055`
- [x] `data/synthetic/drivers.csv` — 55 rows, `driver_id` only
- [x] `solver/crew_config.py` — constants, all tagged
- [x] `solver/crew_models.py` — `CrewProblemData` loader (reads `schedule.csv` + `drivers.csv`)
- [x] `solver/crew_constraints.py` — C1–C4 hard, C6 state-machine soft, C7 soft
- [x] `solver/crew_solve.py` — loops over 45/50/55, writes both output files
- [x] `solver/crew_validator.py` — independent C1–C4 + C7 checks per pool
- [x] `solver/crew_diag.py` — temporary diagnostic (to delete after Phase 3 sign-off)
- [x] 250-trip solve at pool=45: **OPTIMAL, 57.25 s**, active=40, reserve=5, objective=0.0, gap=0.0%
- [x] 250-trip solve at pool=50: **OPTIMAL, 58.80 s**, active=45, reserve=5, objective=0.0, gap=0.0%
- [x] 250-trip solve at pool=55: **OPTIMAL, 64.34 s**, active=50, reserve=5, objective=0.0, gap=0.0%
- [x] Validator at all 3 pools: **C1 PASS, C2 PASS, C3 PASS, C4 PASS, C7 PASS → Overall PASS**
- [x] Outputs written: `data/processed/crew_schedule.csv` (750 rows), `crew_solution.json`, `crew_validation.json`
- [x] Docs updated: `checklist.md` §Phase 3, `constraints-v2.2` §12 (internal version label fix), `constraints-crew-v1.md` (new file), `data-provenance.md` §6/§9, `meeting-log.md` (this meeting)
- [ ] Delete `solver/crew_diag.py` after all docs are signed off
- [ ] Update `phases.md` §Phase 3 (pending)

**Notes:**

- **Diagnostic-driven debugging.** `solver/crew_diag.py` was created as a temporary file to isolate constraint infeasibility. It ran C4-only, C4+C1, C4+C2, C4+C3, C4+C1+C2, and C4+C1+C2+C3 in sequence. This caught two distinct INFEASIBLE bugs without guessing. All hard constraints C1–C4 are jointly satisfiable at pools 45/50/55.

- **Bugs found and fixed during Phase 3:**
  1. `[FINDING]` **C6 first formulation was O(n²)** — enumerated every run over the 250-trip global list, ~3.4M booleans. Caught before writing. Reworked to a state machine (6 vars per `(d, i)`).
  2. `[FINDING]` **C6 chain-continuity bug** — initial state machine defined "continue chain" as `x[d, i−1] AND gap_ok[i−1]`, which broke chains across trips assigned to other drivers. Reworked to `last_arr` carry-forward + `has_prev` bool.
  3. `[FINDING]` **C1 solver bug** — dead branches in `add_c1_no_overlap` forced "if first trip assigned, next trip not assigned" for **every** non-overlapping pair. This made the model INFEASIBLE at all pools. Fixed to the single condition `if a.arr + turnaround > b.dep: x[a] + x[b] ≤ 1`.
  4. `[FINDING]` **C6 `new_chain = 0` bug** — gap constraint fired even when driver had no prior assignment, making the full model INFEASIBLE. Fixed with `has_prev` bool guard.
  5. `[FINDING]` **Validator C1 bug** — compared driver-level `sign_on`/`sign_off` (constant per driver) instead of per-trip times, so C1 FAILed on every pair. Fixed by joining `crew_schedule.csv` trip_ids with `schedule.csv` to get per-trip departure/arrival.

- **Objective = 0 at all pools.** The solver found schedules with **zero C6 and C7 penalty**. This does not prove that no driver neared the 5 h chain limit — it proves the penalty term is zero. Individual chain lengths are in `crew_solution.json` under `assignments` if inspected.

- **Pool-size observation.** At each pool, exactly `pool_size − 5` drivers are active (reserve held at 5 everywhere). So pool=45 uses 40 drivers, pool=50 uses 45, pool=55 uses 50. This is the C7 optimum — no more drivers than needed after preserving 5-reserve. It does not mean pool=55 is strictly "better"; it means more slack, more reserve, at higher pool sizes.

- **Handoff deviation noted.** The new `docs/constraints-crew-v1.md` was created at user request and is a **stylistic companion** to `phases.md §Phase 3`, not a replacement. The handoff §6/§10 intended C1–C7 detail for `phases.md §Phase 3`. Both are kept; `phases.md` is the canonical summary. This deviation is flagged in `constraints-crew-v1.md` §10 and recorded here.

- **Doc trust rule honored.** Per handoff: "Do not read [project docs] unless the user tells you to." The user did not instruct reading during coding; the docs were only opened after validation PASS and with explicit permission, and treated as historical context where relevant. Code and data files were the source of truth during Phase 3 build.

- **No DPR-based values.** 10.715 km, 18.91 min, 408 trips, 3-min turnaround — none present anywhere in Phase 3 code or docs.

- **Temporary diagnostic file.** `solver/crew_diag.py` is not part of the Phase 3 deliverable. Delete it after all docs are signed off.

**Next Meeting:** Phase 4 — Explainability (or Phase 3 retrospective, if requested).

## Meeting Template (for future meetings)

```markdown
## Meeting N — YYYY-MM-DD
**Attendees:** [Names]
**Duration:** XX min
**Agenda:** [Topic]

**Decisions:**
- [Decision 1]
- [Decision 2]

**Action Items:**
- [ ] Person: Task
- [ ] Person: Task

**Notes:**
- [Anything worth remembering]

**Next Meeting:** YYYY-MM-DD