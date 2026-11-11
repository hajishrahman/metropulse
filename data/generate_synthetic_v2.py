"""
MetroPulse synthetic data generator — v2.

Generates synthetic fleet and operational data.
Hourly service plan is generated separately from GTFS.

Sources:
    rakes.csv       — 18 service + 7 maintenance  [EXTERNAL fleet, SYNTHETIC per-rake state]
    terminals.csv   — [SYNTHETIC] 5-min turnaround
    maintenance.csv — empty for V1
    depot.csv       — [SYNTHETIC] Info Park-2 cap 2; Muttom unbounded

Initial locations (fixed, no randomness):
    9 service rakes at ALVA
    9 service rakes at TPHT
    7 maintenance rakes at MUTTOM

Run:
    python data/generate_synthetic_v2.py
"""
from __future__ import annotations

import csv
from pathlib import Path
import random

ROOT = Path(__file__).parent
SYNTH_DIR = ROOT / "synthetic"


# ===========================================================================
# RAKES
# ===========================================================================
def write_rakes() -> None:
    """
    18 service rakes, 7 maintenance. Initial split:
      9 at ALVA    (R001..R009)
      7 at TPHT    (R010..R016)
      2 at MUTTOM  (R017..R018)   [SYNTHETIC — Muttom depot has operating rakes]
    7 maintenance at MUTTOM (R019..R025)
    """
    path = SYNTH_DIR / "rakes.csv"
    rows = []

    # 9 at ALVA
    for i in range(1, 10):
        rows.append({
            "rake_id": f"R{i:03d}",
            "status": "service",
            "initial_mileage_km": random.randint(20_000, 200_000),
            "cmrs_status": "valid",
            "initial_location": "ALVA",
            "initial_available_time": "06:00",
        })

    # 7 at TPHT
    for i in range(10, 17):
        rows.append({
            "rake_id": f"R{i:03d}",
            "status": "service",
            "initial_mileage_km": random.randint(20_000, 200_000),
            "cmrs_status": "valid",
            "initial_location": "TPHT",
            "initial_available_time": "06:00",
        })

    # 2 at MUTTOM (service)
    for i in range(17, 19):
        rows.append({
            "rake_id": f"R{i:03d}",
            "status": "service",
            "initial_mileage_km": random.randint(20_000, 200_000),
            "cmrs_status": "valid",
            "initial_location": "MUTTOM",
            "initial_available_time": "06:00",
        })

    # 7 maintenance at MUTTOM
    for i in range(19, 26):
        rows.append({
            "rake_id": f"R{i:03d}",
            "status": "maintenance",
            "initial_mileage_km": random.randint(20_000, 200_000),
            "cmrs_status": "valid",
            "initial_location": "MUTTOM",
            "initial_available_time": "00:00",
        })

    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"[OK] {path.relative_to(ROOT.parent)}  ({len(rows)} rows)")

# ===========================================================================
# TERMINALS  [SYNTHETIC]
# ===========================================================================
def write_terminals() -> None:
    path = SYNTH_DIR / "terminals.csv"
    rows = [
        {"terminal_id": "ALVA", "station_id": "ALVA", "turnaround_min": 5},
        {"terminal_id": "TPHT", "station_id": "TPHT", "turnaround_min": 5},
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    print(f"[OK] {path.relative_to(ROOT.parent)}  ({len(rows)} rows)")


# ===========================================================================
# MAINTENANCE (empty for V1)
# ===========================================================================
def write_maintenance() -> None:
    path = SYNTH_DIR / "maintenance.csv"
    headers = ["rake_id", "maintenance_start", "maintenance_end", "maintenance_type"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
    print(f"[OK] {path.relative_to(ROOT.parent)}  (0 rows — V1)")


# ===========================================================================
# DEPOT
# ===========================================================================
def write_depot() -> None:
    path = SYNTH_DIR / "depot.csv"
    rows = [
        {"location": "INFO_PARK_2", "capacity": 2, "note": "SYNTHETIC — 2-train stabling"},
        {"location": "MUTTOM", "capacity": "", "note": "UNBOUNDED_FOR_V1"},
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    print(f"[OK] {path.relative_to(ROOT.parent)}  ({len(rows)} rows)")


# ===========================================================================
# MAIN
# ===========================================================================
def main() -> None:
    print("Generating v2 synthetic scenario data...\n")
    SYNTH_DIR.mkdir(exist_ok=True)
    write_rakes()
    write_terminals()
    write_maintenance()
    write_depot()
    print("\nDone.")


if __name__ == "__main__":
    main()
