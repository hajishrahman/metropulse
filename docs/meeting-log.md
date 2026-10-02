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
- `README.md` and `.gitkeep` explicitly un-ignored in `data/raw/`

**Action Items:**
- [x] Copy 11 GTFS `.txt` files into `data/raw/`
- [x] Write `docs/data-provenance.md`
- [x] Update `.gitignore` (`data/raw/*.txt` ignored, README tracked)
- [x] Write `data/raw/README.md` documenting the source
- [x] Write `src/loaders/gtfs_loader.py` — loads all 11 tables

**Notes:**
- Initial `.gitignore` had a too-broad rule (`data/raw/*`) that ignored `README.md`
- Fixed by narrowing to `data/raw/*.txt` and adding `!data/raw/README.md`
- Row counts: 24 stops, 1 route, 252 trips, ~6300 stop_times

**Next Meeting:** 2026-09-28

---

## Meeting 3 — 2026-09-28
**Attendees:** [Names]
**Duration:** 20 min
**Agenda:** Phase 1 — GTFS validation

**Decisions:**
- 7 validation categories: referential integrity, monotonic sequences, time format, temporal ordering, calendar dates, fare coverage, duplicates
- Exit code 1 on any ERROR → enables future CI integration
- Warnings don't fail the build (e.g., fare coverage gaps are non-critical)

**Action Items:**
- [x] Write `src/validation/gtfs_checks.py` — 19 checks, all pass
- [x] Update `docs/checklist.md` with Phase 1 progress
- [ ] Next: build first map (folium) → `notebooks/01_map.ipynb`
- [ ] Then: graph builder → `src/routing/graph.py`
- [ ] Then: journey planner → `src/routing/planner.py`

**Notes:**
- Feed passed all 19 checks — Phase 1 complete
- Feed is clean and ready for Phase 2

**Next Meeting:** [Date]

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
- `README.md` and `.gitkeep` explicitly un-ignored in `data/raw/`

**Action Items:**
- [x] Copy 11 GTFS `.txt` files into `data/raw/`
- [x] Write `docs/data-provenance.md`
- [x] Update `.gitignore` (`data/raw/*.txt` ignored, README tracked)
- [x] Write `data/raw/README.md` documenting the source
- [x] Write `src/loaders/gtfs_loader.py` — loads all 11 tables

**Notes:**
- Initial `.gitignore` had a too-broad rule (`data/raw/*`) that ignored `README.md`
- Fixed by narrowing to `data/raw/*.txt` and adding `!data/raw/README.md`
- Row counts: 24 stops, 1 route, 252 trips, ~6300 stop_times

**Next Meeting:** 2026-09-28

---

## Meeting 3 — 2026-09-28
**Attendees:** [Names]
**Duration:** 20 min
**Agenda:** Phase 1 — GTFS validation

**Decisions:**
- 7 validation categories: referential integrity, monotonic sequences, time format, temporal ordering, calendar dates, fare coverage, duplicates
- Exit code 1 on any ERROR → enables future CI integration
- Warnings don't fail the build (e.g., fare coverage gaps are non-critical)

**Action Items:**
- [x] Write `src/validation/gtfs_checks.py` — 19 checks, all pass
- [x] Update `docs/checklist.md` with Phase 1 progress
- [ ] Next: build first map (folium) → `notebooks/01_map.ipynb`
- [ ] Then: graph builder → `src/routing/graph.py`
- [ ] Then: journey planner → `src/routing/planner.py`

**Notes:**
- Feed passed all 19 checks — Phase 1 complete
- Feed is clean and ready for Phase 2

**Next Meeting:** [Date]

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
## Meeting 4 — 2026-10-03

**Attendees:** [Names]
**Duration:** 45 min
**Agenda:** Phase 1 review — CP-SAT solver complete

### Decisions

- Spec v2 locked (DPR-driven, no invented thresholds)
- CP-SAT model uses interval variables and AddNoOverlap
- R6 turnaround rewritten with window-based pair pruning
- Validator is the source of truth for schedule correctness
- 300s time limit accepted for V1 (not chasing optimality)

### Action Items

- [x] Full-day solve: 408 trips, FEASIBLE
- [x] Validator: all 7 checks PASS
- [ ] Next: SimPy simulation for Scenario A
- [ ] Later: objective tuning, faster solve

### Notes

- Initial solve failed validation on R1 and R6 — fixed both
- R1: trip latest start now strictly before hour_end (was allowing overlap)
- R6: extended to cross-direction pairs with window pruning (15,624 pairs vs 83,028)
- Objective after fix: 1,159,000 (was 1,303,700)

**Next Meeting:** TBD

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
