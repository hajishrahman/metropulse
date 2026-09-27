# MetroPulse Meeting Log

## Meeting 1 — [Date]
**Attendees:** [Names]
**Duration:** 30 min
**Agenda:** Phase 0 setup
**Decisions:**
- Tool stack finalized
- Folder structure created
- Virtual env set up
**Action Items:**
- [x] Install dependencies
- [x] GTFS data acquired
- [x] Git repo initialized

---

## Meeting 2 — 2026-09-28
**Attendees:** [Names]
**Duration:** 30 min
**Agenda:** Phase 1 — GTFS ingestion
**Decisions:**
- KMRL GTFS feed is Phase 1 dataset
- Feed stored in `data/raw/` (excluded from Git)
- Loader loads all tables as strings (preserves IDs, times)
**Action Items:**
- [x] `src/loaders/gtfs_loader.py` written and verified
- [x] `docs/data-provenance.md` written
- [ ] `src/validation/gtfs_checks.py` ← done in Meeting 3
**Next Meeting:** 2026-09-28

---

## Meeting 3 — 2026-09-28
**Attendees:** [Names]
**Duration:** 20 min
**Agenda:** Phase 1 — GTFS validation
**Decisions:**
- 7 validation categories: referential integrity, monotonic sequences,
  time format, temporal ordering, calendar dates, fare coverage, duplicates
- Exit code 1 on error → CI-ready
- Warnings don't fail the build
**Action Items:**
- [x] `src/validation/gtfs_checks.py` — 19/19 checks pass
- [ ] Next: folium map of the network
- [ ] Then: journey planner
**Next Meeting:** [Date]