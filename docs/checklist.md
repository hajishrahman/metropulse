# MetroPulse — Development Checklist

Progress tracker for the project. Update as phases complete.

---

## Phase 0 — Setup

- [x] Python 3.11 installed
- [x] VS Code + Python extension installed
- [x] Project folder created (`Z:\metropulse`)
- [x] Virtual environment activated (`venv`)
- [x] `requirements.txt` installed
- [x] `.gitignore` created (Python + GTFS exclusions)
- [x] `.gitkeep` files added for empty data folders
- [x] Git initialized + pushed to GitHub
- [x] GTFS data in `data/raw/` (11 files)
- [x] `docs/meeting-log.md` created

---

## Phase 1 — Data Ingestion & Validation

- [x] KMRL GTFS files copied to `data/raw/`
- [x] `docs/data-provenance.md` written (source, dates, quirks)
- [x] `.gitignore` excludes GTFS `.txt` files
- [x] `data/raw/README.md` documents the source
- [x] Root `README.md` — setup + common commands
- [x] `src/loaders/gtfs_loader.py` — loads all 11 tables
- [x] `src/validation/gtfs_checks.py` — 19 checks, all pass
- [x] `requirements.txt` curated (direct deps only)
- [x] Row counts verified against `docs/data-provenance.md`

**Validation results:** 19 passed, 0 warnings, 0 errors.

---

## Phase 2 — Mapping & Routing (next)

- [ ] `notebooks/01_map.ipynb` — folium map with stops + shapes
- [ ] `src/routing/graph.py` — networkx DiGraph from stop_times
- [ ] `src/routing/planner.py` — journey planner (from, to, time → next trains)
- [ ] `src/routing/fare.py` — fare lookup from fare_rules
- [ ] Headway / frequency analysis notebook

---

## Phase 3 — Simulation

- [ ] `src/simulation/train_sim.py` — SimPy model of train movements
- [ ] Delay propagation experiments
- [ ] OR-Tools optimization (headways, dwell times)

---

## Phase 4 — UI & Deployment

- [ ] Streamlit dashboard (`src/ui/app.py`)
- [ ] Interactive map (folium / pydeck)
- [ ] Multilingual stop names from `translations.txt`
- [ ] Deploy to Streamlit Cloud

---

## Data Summary (reference)

| Item | Value |
|------|-------|
| Route | R1 — Kochi Metro Line 1 |
| Stops | 24 |
| Trips | 252 |
| Stop times | ~6,300 |
| Fare slabs | 6 (₹10 → ₹60) |
| Services | WK (weekday), WE (weekend) |
| Feed validity | 2024-08-12 → 2025-12-31 |

---

## Last Updated

2026-09-28