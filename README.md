# MetroPulse

Transit analytics, routing, and simulation platform for the Kochi Metro Rail Limited (KMRL) network.

**Status:** Phase 1 — GTFS ingestion complete.

---

## Project Structure

```
metropulse/
├── data/
│   ├── raw/             # GTFS feed (git-ignored, see data/raw/README.md)
│   ├── processed/       # Cleaned/derived data (git-ignored)
│   └── synthetic/       # Generated data (git-ignored)
├── src/
│   ├── loaders/         # GTFS loading
│   ├── validation/      # Data quality checks
│   ├── routing/         # Journey planner, graph algorithms
│   ├── simulation/      # SimPy models
│   └── ui/              # Streamlit / folium visualizations
├── notebooks/           # Exploration & prototyping
├── docs/                # Provenance, meeting log, checklist
├── tests/               # Unit tests
└── requirements.txt
```

---

## Setup

### 1. Clone and enter the repo

```powershell
git clone <your-repo-url>
cd metropulse
```

### 2. Create and activate a virtual environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

> If activation is blocked, run once:
> `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Load the GTFS data

The raw GTFS `.txt` files are **not tracked in Git**. Copy them into `data/raw/`:

```powershell
Copy-Item "Z:\path\to\KMRLGTFS\*.txt" -Destination data\raw\
```

Expected files (11):

```
agency.txt          fare_rules.txt      stops.txt
calendar.txt        feed_info.txt       translations.txt
fare_attributes.txt routes.txt          trips.txt
shapes.txt          stop_times.txt
```

See `data/raw/README.md` for source details.

---

## Common Commands

### Load GTFS into memory

```powershell
python -m src.loaders.gtfs_loader
```

Prints row counts for all 11 tables. Run this to verify the feed is intact.

### Run data-quality checks

```powershell
python -m src.validation.gtfs_checks
```

Referential integrity, monotonic stop sequences, time-format validation, fare coverage.

### Generate the network map

```powershell
python -m src.ui.map_stops
```

Produces `kmrl_map.html` — opens in any browser.

### Clean Python caches

```powershell
Get-ChildItem -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force
Get-ChildItem -Recurse -File -Filter *.pyc | Remove-Item -Force
```

---

## Data

| Item | Detail |
|------|--------|
| Source | Kochi Metro Rail Limited |
| Format | GTFS (static) |
| Feed version | 1.0 |
| Feed validity | 2024-08-12 → 2025-12-31 |
| Timezone | Asia/Kolkata |
| Route | R1 (Kochi Metro Line 1) |
| Stops | 24 |
| Services | WK (weekday), WE (weekend) |
| Fares | ₹10 – ₹60 across 6 slabs |

Full provenance: `docs/data-provenance.md`

---

## Development

### Git strategy

- **Code, docs, configs** → tracked
- **GTFS `.txt` files** → ignored (see `.gitignore`), documented in `data/raw/README.md`
- **Virtual environment, caches, databases** → ignored

### Adding a dependency

```powershell
pip install <package>
pip freeze > requirements.txt
```

### Project docs

- `docs/data-provenance.md` — where the data came from
- `docs/meeting-log.md` — decisions log
- `docs/checklist.md` — phase-by-phase task tracking

---

## Roadmap

- [x] **Phase 0** — Project setup, Git, venv
- [x] **Phase 1** — GTFS ingestion, loader, provenance
- [ ] **Phase 1.5** — Validation, first map
- [ ] **Phase 2** — Journey planner, graph, headway analysis
- [ ] **Phase 3** — SimPy simulation, delay propagation
- [ ] **Phase 4** — Streamlit dashboard, multilingual UI

---

## License

See `LICENSE` (TBD).