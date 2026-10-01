# Data Provenance

## KMRL GTFS Feed

- **Source:** Kochi Metro Rail Limited (KMRL)
- **URL:** https://kochimetro.org/
- **Retrieved:** 2026-09-27
- **Format:** GTFS (static)
- **Feed version:** 1.0
- **Feed start:** 2024-08-12
- **Feed end:** 2025-12-31
- **Timezone:** Asia/Kolkata

### Files present (11)

Required:
- agency.txt
- calendar.txt
- routes.txt
- stop_times.txt
- stops.txt
- trips.txt

Optional:
- fare_attributes.txt
- fare_rules.txt
- feed_info.txt
- shapes.txt
- translations.txt

### Known quirks

- Times may exceed 24:00:00 (e.g., trip `WK_253` arrives at `24:03:45`)
- `transfers` column in `fare_attributes.txt` is empty
- Only 1 route (`R1`), 24 stops, 2 service patterns (`WK` = weekday, `WE` = weekend)
- `fare_rules.txt` uses `origin_id`/`destination_id` pairs mapping to fare slabs `F1`–`F6`
- Fare range: ₹10 (shortest) → ₹60 (Aluva ↔ Tripunithura)

### Git strategy

- GTFS `.txt` files are **excluded from Git** (see `.gitignore`)
- Source and setup instructions live in `data/raw/README.md`
- Rationale: feed is static, re-downloadable, and versioned externally by KMRL
## Synthetic Data Calibration

Synthetic operations data (`data/synthetic/`) is calibrated to publicly
available KMRL information. Where KMRL does not disclose numbers, we use
industry norms and mark them as assumptions.

### Sourced from public KMRL information

| Field | Value | Source |
|-------|-------|--------|
| Fleet size | 25 rakes | KMRL Phase I procurement |
| Rakes in service | 18 | KMRL operations |
| Rakes in maintenance | 7 | KMRL operations |
| Manufacturer | Alstom Metropolis | KMRL rolling stock |
| Coaches per rake | 3 (DM-TC-DM) | KMRL fleet spec |
| Driver workforce | 60 | KMRL HR |
| Women loco pilots | 28 (47%) | KMRL diversity reports |
| Net duty hours | 8 | KMRL roster policy |
| Total duty hours | 9 | 8h net + 1h briefing |
| Continuous driving limit | 3–4 h | KMRL fatigue rules |
| Inter-shift rest | 12–16 h | KMRL policy |
| Weekly rest | ≥30 continuous hours | KMRL policy |
| Roster pattern | 6 on / 1 off | KMRL HR |
| Relief point | Muttom Yard | KMRL ops docs |
| Depot area | 15.12 ha | KMRL infra reports |
| Depot cranes | 15-ton Demag | KMRL maintenance infra |
| Operating hours (Mon-Sat) | 06:00 – 23:00 | KMRL timetable |
| Operating hours (Sun) | 08:00 – 23:00 | KMRL timetable |
| Route | Blue Line (Aluva → Tripunithura) | KMRL network |
| Stations | 25 | KMRL network |
| Route length | ~25.6 km | KMRL network |
| Terminal stabling | ~2/3 of fleet | KMRL "one-third depot rule" |
| Fitness clearance | CMRS conditional | CMRS regulation (no fixed 90-day rule) |
| Intermediate overhaul | 420,000 km / 3–4 yrs | KMRL IOH |
| Periodical overhaul | 840,000 km / 7–8 yrs | KMRL POH |

### Modeled assumptions (not publicly disclosed)

| Field | Assumed Value | Rationale |
|-------|---------------|-----------|
| Depot stabling lines | 6 | Calibrated to 15.12 ha depot |
| Rakes per line | 4 | Realistic stack depth |
| Stack depth | 4 | Metro depot norm |
| Job cards per day | 15 | Fleet size × rotation rate |
| Maintenance bays | 2 | Typical for this depot size |
| Cleaning bays | 3 | Typical for 25-rake fleet |
| Cost per km | ₹50 | Indian metro average |
| Cost per shunt | ₹500 | Depot ops estimate |
| Delay cost | ₹100/min | Industry estimate |
| Cancel penalty | ₹5,000/trip | Industry estimate |

### Removed from scope

- **Advertising / branding** — out of scope for Phase 1 optimization.
  `advertisers.csv` deleted. Can be reintroduced in a later phase.

### Schema changes (post-calibration)

- `trains.csv`: added `cmrs_status`, `stabling_location`; removed
  `target_mileage_km`, `cleaning_interval_hours`, `branded`
- `drivers.csv`: reduced from 40 to 4 meaningful columns; kept
  `last_shift_end_hours_ago` (driver state) alongside `min_rest_hours` (rule)
- `routes.csv`: replaced 3 fake routes with 1 real Blue Line
- `advertisers.csv`: **deleted**
- Static constants moved to `solver/config.py`