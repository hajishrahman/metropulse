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
- Feed has 24 stops, 1 route, 252 trips, ~6300 stop_times

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
- Scheduled headway violations = 0 at every std (R2a holds). Actual-gap violations rise with std (E1: 0 → E4: 33.3 mean), reflecting departure bunching under delay.
- R9 and R11 remain outside the Phase 1 validator results — unchanged from Meeting 8. Phase 2 does not touch R1–R12.
- Terminal continuity: 127 of 232 pairs broken by direction alternation. Cannot distinguish real gap from labeling artifact — no GTFS↔`Txxxx` map exists in Phase 1 outputs. Deferred to Phase 4/5 where terminal awareness matters.
- `solver/` stays at project root (Phase 1 legacy); `src/simulation/` sits under `src/` as planned. Asymmetry is historical, harmless, noted here.
- All Phase 2 work is committed and pushed to GitHub.

**Next Meeting:** Phase 3 kickoff


---

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
- **Phase 2 (SimPy) outputs are STALE.** `simulation_kpis.json` and `simulation_timeline.csv` were computed on the pre-rebuild synthetic schedule. They must be regenerated on the new 250-trip real-GTFS schedule.

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
- [ ] Next: regenerate Phase 2 (SimPy) on the new 250-trip schedule
- [ ] Next: `project-status.md` update

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
  - The 250-trip result on disk: `data/processed/schedule_250_trips.csv`, `solution_250_trips.json`, `validation_250_trips.json` (need to be saved from the current run before the next rebuild).
  - The 232-trip result is also proven OPTIMAL and can be regenerated any time.
  - `hourly_service.csv` is kept on disk for reconciliation only; not read by the solver.

- **GTFS data vintage.** Feed is 2024-08-12 to 2025-12-31. It represents the 2024–25 timetable, not current 2026 operations. The 2026 news article provides only the fleet breakdown; it does not update the timetable.

- **No DPR-based values remain.** The 2026-10-15 pivot (Meeting 5) fully removed them. All tags are now EXTERNAL / DERIVED / SYNTHETIC / MODEL LIMITATION.

- **Committed and pushed to GitHub.** All source code, data scripts, and doc updates from this meeting.

**Next Meeting:** Phase 2 rebuild kickoff (SimPy on the new 250-trip schedule).