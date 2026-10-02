"""
MetroPulse synthetic data generator — v2.

Generates DPR-sourced hourly service plan and scenario-A synthetic fleet data.

Sources:
    hourly_service.csv  — [DPR] KMRL Phase-II DPR hourly operation table
    rakes.csv           — [DPR] 15+1+2 fleet breakdown + [SYNTHETIC] per-rake state
    terminals.csv       — [DPR] terminal turnaround times
    maintenance.csv     — empty for Scenario A
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
DPR_DIR = ROOT / "dpr"
SYNTH_DIR = ROOT / "synthetic"

DPR_DIR.mkdir(exist_ok=True)
SYNTH_DIR.mkdir(exist_ok=True)


# ===========================================================================
# 1. DPR HOURLY SERVICE PLAN  [DPR]
# ===========================================================================
# Format: (hour_start, hour_end, target_headway_min, up_departures, down_departures)
# 19:00–20:00 row preserved as-is per spec §4.1 (5 min target, 15 count).

DPR_HOURLY_PLAN = [
    (5,  6,  10.0,  6,  6),
    (6,  7,   7.5,  8,  8),
    (7,  8,   5.0, 12, 12),
    (8,  9,   3.0, 20, 20),
    (9,  10,  3.0, 20, 20),
    (10, 11,  5.0, 12, 12),
    (11, 12,  7.5,  8,  8),
    (12, 13, 10.0,  6,  6),
    (13, 14, 12.0,  5,  5),
    (14, 15, 12.0,  5,  5),
    (15, 16, 10.0,  6,  6),
    (16, 17,  5.0, 12, 12),
    (17, 18,  3.0, 20, 20),
    (18, 19,  3.0, 20, 20),
    (19, 20,  5.0, 15, 15),   # see spec §4.1 — internally inconsistent
    (20, 21,  6.0, 10, 10),
    (21, 22,  7.5,  8,  8),
    (22, 23, 10.0,  6,  6),
    (23, 24, 12.0,  5,  5),
]


def write_hourly_service() -> None:
    """Write DPR hourly service plan as long-format CSV (one row per hour×direction)."""
    path = DPR_DIR / "hourly_service.csv"
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "hour_start", "hour_end", "direction",
            "required_departures", "target_headway_min",
        ])
        for h_start, h_end, hw, up, down in DPR_HOURLY_PLAN:
            w.writerow([h_start, h_end, "UP",   up,   hw])
            w.writerow([h_start, h_end, "DOWN", down, hw])
    print(f"[OK] {path.relative_to(ROOT.parent)}  ({len(DPR_HOURLY_PLAN) * 2} rows)")


# ===========================================================================
# 2. RAKES  [DPR breakdown + SYNTHETIC per-rake state]
# ===========================================================================
# Fleet: 15 bare + 1 traffic spare + 2 maintenance spare = 18 total

# Terminals available for initial positioning
TERMINALS = ["ALVA", "TPHT"]


def write_rakes() -> None:
    """
    Generate rakes.csv.

    Fields:
        rake_id             — unique identifier (R001..R018)
        initial_mileage_km  — starting odometer
        cmrs_status         — 'valid' or 'conditional'
        traffic_spare       — 1 for the traffic reserve rake, else 0
        maintenance_spare   — 1 for the 2 maintenance reserves, else 0
        initial_location    — terminal or depot where the rake starts the day
        initial_available_time — earliest time rake can be deployed (HH:MM)
    """
    path = SYNTH_DIR / "rakes.csv"

    rows = []

    # 15 bare rakes — all valid, well below 1M km threshold
    for i in range(1, 16):
        rows.append({
            "rake_id": f"R{i:03d}",
            "initial_mileage_km": random.randint(20_000, 200_000),
            "cmrs_status": "valid",
            "traffic_spare": 0,
            "maintenance_spare": 0,
            "initial_location": random.choice(TERMINALS),
            "initial_available_time": "05:00",
        })

    # 1 traffic spare
    rows.append({
        "rake_id": "R016",
        "initial_mileage_km": random.randint(20_000, 200_000),
        "cmrs_status": "valid",
        "traffic_spare": 1,
        "maintenance_spare": 0,
        "initial_location": "MUTTOM",
        "initial_available_time": "05:00",
    })

    # 2 maintenance spares — blocked, at Muttom
    for i in (17, 18):
        rows.append({
            "rake_id": f"R{i:03d}",
            "initial_mileage_km": random.randint(20_000, 200_000),
            "cmrs_status": "valid",
            "traffic_spare": 0,
            "maintenance_spare": 1,
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
        {"terminal_id": "ALVA", "station_id": "ALVA", "turnaround_min": 3},
        {"terminal_id": "TPHT", "station_id": "TPHT", "turnaround_min": 3},
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
    print("Generating v2 synthetic + DPR data...\n")

    write_hourly_service()
    write_rakes()
    write_terminals()
    write_maintenance()
    write_depot()

    print("\nDone.")


if __name__ == "__main__":
    main()