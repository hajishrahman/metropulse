"""
MetroPulse synthetic data generator — v2.

Generates scenario-A synthetic fleet and operational data.
Hourly service plan is generated separately from GTFS.

Sources:
    hourly_service.csv  — [GTFS] Generated separately by extract_gtfs_hourly.py
    rakes.csv           — 15 service + 3 standby + 7 maintenance rakes
                          + [SYNTHETIC] per-rake state
    terminals.csv       — [ASSUMPTION] Terminal turnaround times
    maintenance.csv     — Empty for Scenario A
    depot.csv           — [DPR] Info Park-2 capacity; Muttom unbounded

Run:
    python data/generate_synthetic_v2.py

Spec:
    docs/constraints-v2.md
"""
from __future__ import annotations

import csv
from pathlib import Path
import random

random.seed(42)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent
SYNTH_DIR = ROOT / "synthetic"

SYNTH_DIR.mkdir(exist_ok=True)

# ===========================================================================
# 2. RAKES  [DPR breakdown + SYNTHETIC per-rake state]
# ===========================================================================
# Fleet: 15 service + 3 standby + 7 maintenance = 25 total

# Terminals available for initial positioning
TERMINALS = ["ALVA", "TPHT"]


def write_rakes() -> None:
    """
    Generate rakes.csv.

    Fields:
        rake_id             — unique identifier (R001..R025)
        status             — 'service', 'standby', or 'maintenance'
        initial_mileage_km  — starting odometer
        cmrs_status         — 'valid' or 'conditional'
        initial_location    — terminal or depot where the rake starts the day
        initial_available_time — earliest time rake can be deployed (HH:MM)
    """
    path = SYNTH_DIR / "rakes.csv"

    rows = []

    # 18 in service rakes 
    for i in range(1, 19): #R001..R018
        rows.append({
            "rake_id": f"R{i:03d}",
            "status": "service",
            "initial_mileage_km": random.randint(20_000, 200_000),
            "cmrs_status": "valid",
            "initial_location": random.choice(TERMINALS),
            "initial_available_time": "06:00",
        })

    # 0 standby rakes — folded into 18 service

    # 7 maintenance rakes at Muttom
    for i in range(19, 26): #R019..R025
        rows.append({
            "rake_id": f"R{i:03d}",
            "status": "maintenance",
            "initial_mileage_km": random.randint(20_000, 200_000),
            "cmrs_status": "valid",
            "initial_location": "MUTTOM",
            "initial_available_time": "00:00",   # technically available but reserved
        })

    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"[OK] {path.relative_to(ROOT.parent)}  ({len(rows)} rows)")


# ===========================================================================
# 3. TERMINALS  [DPR]
# ===========================================================================
def write_terminals() -> None:
    """Write terminals.csv — turnaround times from DPR."""
    path = SYNTH_DIR / "terminals.csv"

    rows = [
        {"terminal_id": "ALVA", "station_id": "ALVA", "turnaround_min": 5},
        {"terminal_id": "TPHT", "station_id": "TPHT", "turnaround_min": 5},
    ]

    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"[OK] {path.relative_to(ROOT.parent)}  ({len(rows)} rows)")


# ===========================================================================
# 4. MAINTENANCE  (empty for Scenario A — headers only)
# ===========================================================================
def write_maintenance() -> None:
    """
    Write maintenance.csv — empty for Scenario A (baseline, no scheduled blocks).

    Populated in later scenarios (e.g., Scenario E — Maintenance stress).
    """
    path = SYNTH_DIR / "maintenance.csv"

    headers = ["rake_id", "maintenance_start", "maintenance_end", "maintenance_type"]

    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        # No rows for Scenario A

    print(f"[OK] {path.relative_to(ROOT.parent)}  (0 rows — Scenario A)")


# ===========================================================================
# 5. DEPOT  [DPR + MODEL LIMITATION]
# ===========================================================================
def write_depot() -> None:
    """Write depot.csv — stabling capacities."""
    path = SYNTH_DIR / "depot.csv"

    rows = [
    {"location": "INFO_PARK_2", "capacity": 2, "note": "DPR-stated 2-train stabling"},
    {"location": "MUTTOM",      "capacity": "", "note": "UNBOUNDED_FOR_V1 - model limitation"},
]

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"[OK] {path.relative_to(ROOT.parent)}  ({len(rows)} rows)")


# ===========================================================================
# MAIN
# ===========================================================================
def main() -> None:
    print("Generating v2 synthetic scenario data...\n")

    write_rakes()
    write_terminals()
    write_maintenance()
    write_depot()

    print("\nDone.")


if __name__ == "__main__":
    main()