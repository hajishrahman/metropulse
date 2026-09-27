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