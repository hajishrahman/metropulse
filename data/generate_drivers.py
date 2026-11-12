"""
Generate synthetic KMRL drivers for MetroPulse Phase 3.

Writes:
    data/synthetic/drivers.csv      # 55 drivers D001-D055

V1 design (locked, see handoff + user decision 2026-11-13):
    drivers.csv contains ONLY driver_id.
    Fields qualification / availability / shift_preference / weekly_availability
    are DEFERRED TO V2 (same honesty pattern as C5 rest rule).

Tags:
    [SYNTHETIC]  all 55 driver IDs are synthetic placeholders, not real KMRL staff.
"""
from __future__ import annotations

from pathlib import Path

import csv

# ==== PARAMETERS  [SYNTHETIC] ====
NUM_DRIVERS = 55                 # [SYNTHETIC] handoff: 55 drivers in drivers.csv
DRIVER_ID_PREFIX = "D"           # [SYNTHETIC]
DRIVER_ID_WIDTH = 3              # D001 ... D055

# ==== PATHS ====
ROOT = Path(__file__).parent.parent
OUT_CSV = ROOT / "data" / "synthetic" / "drivers.csv"


def make_driver_ids(n: int) -> list[str]:
    if n <= 0:
        raise ValueError("NUM_DRIVERS must be positive")
    return [f"{DRIVER_ID_PREFIX}{i:0{DRIVER_ID_WIDTH}d}" for i in range(1, n + 1)]


def write_drivers(path: Path, driver_ids: list[str]) -> None:
    if not driver_ids:
        raise ValueError("No driver IDs to write")
    if len(set(driver_ids)) != len(driver_ids):
        raise ValueError("Duplicate driver IDs generated")

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["driver_id"])
        writer.writeheader()
        for did in driver_ids:
            writer.writerow({"driver_id": did})
    print(f"[generate_drivers] wrote {path} ({len(driver_ids)} drivers)")


def main() -> None:
    driver_ids = make_driver_ids(NUM_DRIVERS)
    write_drivers(OUT_CSV, driver_ids)


if __name__ == "__main__":
    main()