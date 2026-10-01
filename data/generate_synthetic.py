"""
Generates synthetic KMRL-like metro data.

Sources:
  - Real KMRL figures where public (fleet size, driver count, depot info)
  - Industry norms where KMRL doesn't disclose
  - Documented assumptions (marked in docs/data-provenance.md)

Run: python data/generate_synthetic.py
"""
import pandas as pd
import numpy as np
from pathlib import Path

np.random.seed(42)

ROOT = Path(__file__).parent
OUT = ROOT / "synthetic"
OUT.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Constants (real KMRL values where public)
# ---------------------------------------------------------------------------
NUM_TRAINS = 25
SERVICE_COUNT = 18
MAINTENANCE_COUNT = 7

NUM_DRIVERS = 60
NUM_WOMEN = 28

DEPOT_LINES = ["L1", "L2", "L3", "L4", "L5", "L6"]
STABLING_LOCATIONS = ["Muttom_Depot", "Aluva_Terminal", "Tripunithura_Terminal"]
STABLING_WEIGHTS = [0.33, 0.34, 0.33]   # ~1/3 each per KMRL "one-third" rule

# ---------------------------------------------------------------------------
# 1. TRAINS (rakes)
# ---------------------------------------------------------------------------
# Stabling: ~1/3 at Muttom depot, ~1/3 each at terminals (KMRL rule)
stabling_location = np.random.choice(
    STABLING_LOCATIONS, NUM_TRAINS, p=STABLING_WEIGHTS
)

# Depot depth is only meaningful for rakes at Muttom
stabling_line = []
stabling_position = []
for loc in stabling_location:
    if loc == "Muttom_Depot":
        stabling_line.append(np.random.choice(DEPOT_LINES))
        stabling_position.append(np.random.randint(1, 5))     # depth 1-4
    else:
        stabling_line.append("")                              # not in depot
        stabling_position.append(0)                           # N/A

trains = pd.DataFrame({
    "train_id": [f"T{i:03d}" for i in range(1, NUM_TRAINS + 1)],
    "cmrs_status": np.random.choice(
        ["valid", "conditional"], NUM_TRAINS, p=[0.8, 0.2]
    ),
    "current_mileage_km": np.random.randint(50_000, 800_000, NUM_TRAINS),
    "last_cleaned_hours_ago": np.random.randint(1, 72, NUM_TRAINS),
    "stabling_location": stabling_location,
    "stabling_line": stabling_line,
    "stabling_position": stabling_position,
})
trains.to_csv(OUT / "trains.csv", index=False)

# ---------------------------------------------------------------------------
# 2. DRIVERS
# ---------------------------------------------------------------------------
drivers = pd.DataFrame({
    "driver_id": [f"D{i:03d}" for i in range(1, NUM_DRIVERS + 1)],
    "last_shift_end_hours_ago": np.random.randint(10, 30, NUM_DRIVERS),
    "min_rest_hours": 12,                    # KMRL policy lower bound
    "available_today": np.random.choice(
        [1, 1, 1, 0], NUM_DRIVERS, p=[0.7, 0.15, 0.1, 0.05]
    ),
})
drivers.to_csv(OUT / "drivers.csv", index=False)

# ---------------------------------------------------------------------------
# 3. ROUTES (real KMRL: 1 Blue Line)
# ---------------------------------------------------------------------------
routes = pd.DataFrame({
    "route_id": ["Blue_Line"],
    "start_station": ["ALVA"],
    "end_station": ["TPHT"],
    "num_stations": [25],
    "length_km": [25.6],
    "round_trip_minutes": [90],
    "required_trains_peak": [18],
    "required_trains_offpeak": [12],
})
routes.to_csv(OUT / "routes.csv", index=False)

# ---------------------------------------------------------------------------
# 4. SHIFTS
# ---------------------------------------------------------------------------
shifts = pd.DataFrame({
    "shift_id": ["M", "A", "N"],
    "shift_name": ["Morning", "Afternoon", "Night"],
    "start_hour": [5, 13, 21],
    "end_hour": [13, 21, 29],            # 29 = 5 AM next day
    "required_drivers": [20, 20, 10],
})
shifts.to_csv(OUT / "shifts.csv", index=False)

# ---------------------------------------------------------------------------
# 5. JOB CARDS (maintenance)
# ---------------------------------------------------------------------------
NUM_JOBS = 15
job_cards = pd.DataFrame({
    "job_id": [f"J{i:03d}" for i in range(1, NUM_JOBS + 1)],
    "train_id": np.random.choice(trains["train_id"], NUM_JOBS, replace=False),
    "priority": np.random.choice(
        ["critical", "high", "medium", "low"],
        NUM_JOBS, p=[0.1, 0.2, 0.4, 0.3],
    ),
    "due_date": pd.date_range("2025-01-05", periods=NUM_JOBS, freq="2D")
                   .strftime("%Y-%m-%d"),
    "estimated_hours": np.random.randint(2, 12, NUM_JOBS),
})
job_cards.to_csv(OUT / "job_cards.csv", index=False)

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
print("Synthetic data generated:")
for f in sorted(OUT.glob("*.csv")):
    print(f"   - {f.name}")