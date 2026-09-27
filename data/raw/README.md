# Raw GTFS Data

GTFS `.txt` files are **not tracked in Git** (see `.gitignore`).
Place them here after downloading.

## Expected files (KMRL feed)

Required:
- agency.txt
- stops.txt
- routes.txt
- trips.txt
- stop_times.txt
- calendar.txt

Optional:
- fare_attributes.txt
- fare_rules.txt
- shapes.txt
- translations.txt
- feed_info.txt

## Source

- **Provider:** Kochi Metro Rail Limited (KMRL)
- **Website:** https://kochimetro.org/
- **Feed version:** 1.0
- **Feed validity:** 2024-08-12 → 2025-12-31
- **Timezone:** Asia/Kolkata

## Setup

Copy the `.txt` files from the KMRL GTFS download into this folder:

```powershell
Copy-Item "Z:\path\to\KMRLGTFS\*.txt" -Destination data\raw\