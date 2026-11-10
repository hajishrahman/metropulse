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

**Next Meeting:** YYYY-MM-DD