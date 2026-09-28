"""
Generates synthetic KMRL-like metro data.
Run: python data/generate_synthetic.py
"""
import pandas as pd
import numpy as np
from pathlib import Path

np.random.seed(42)

ROOT = Path(__file__).parent
OUT = ROOT / "synthetic"
OUT.mkdir(exist_ok=True)

# ---------- 1. TRAINSETS ----------
NUM_TRAINS = 25
trains = pd.DataFrame({
    "train_id": [f"T{i:03d}" for i in range(1, NUM_TRAINS + 1)],
    "fitness_valid_until": pd.date_range("2025-01-01", periods=NUM_TRAINS, freq="30D").strftime("%Y-%m-%d"),
    "current_mileage_km": np.random.randint(50000, 200000, NUM_TRAINS),
    "target_mileage_km": 120000,
    "last_cleaned_hours_ago": np.random.randint(1, 72, NUM_TRAINS),
    "cleaning_interval_hours": 24,
    "stabling_line": np.random.choice(["L1", "L2", "L3", "L4"], NUM_TRAINS),
    "stabling_position": np.random.randint(1, 6, NUM_TRAINS),
    "branded": np.random.choice([0, 1], NUM_TRAINS, p=[0.7, 0.3]),
})
trains.to_csv(OUT / "trains.csv", index=False)

# ---------- 2. DRIVERS ----------
NUM_DRIVERS = 40
drivers = pd.DataFrame({
    "driver_id": [f"D{i:03d}" for i in range(1, NUM_DRIVERS + 1)],
    "last_shift_end_hours_ago": np.random.randint(6, 30, NUM_DRIVERS),
    "min_rest_hours": 11,
    "max_shift_hours": 8,
    "qualified_routes": np.random.choice(["Red", "Blue", "Green", "All"], NUM_DRIVERS),
    "available": np.random.choice([1, 1, 1, 0], NUM_DRIVERS, p=[0.7, 0.15, 0.1, 0.05]),
})
drivers.to_csv(OUT / "drivers.csv", index=False)

# ---------- 3. ROUTES ----------
routes = pd.DataFrame({
    "route_id": ["Red", "Blue", "Green"],
    "start_station": ["S1", "S10", "S20"],
    "end_station": ["S9", "S19", "S29"],
    "num_stations": [9, 10, 10],
    "round_trip_minutes": [90, 100, 110],
    "required_trains_peak": [12, 10, 8],
    "required_trains_offpeak": [8, 6, 5],
})
routes.to_csv(OUT / "routes.csv", index=False)

# ---------- 4. SHIFTS (Time windows) ----------
shifts = pd.DataFrame({
    "shift_id": ["S1", "S2", "S3"],
    "start_hour": [5, 13, 21],
    "end_hour": [13, 21, 29],  # 29 = 5 AM next day
    "required_drivers": [20, 20, 10],
})
shifts.to_csv(OUT / "shifts.csv", index=False)

# ---------- 5. JOB CARDS (Maintenance) ----------
NUM_JOBS = 15
job_cards = pd.DataFrame({
    "job_id": [f"J{i:03d}" for i in range(1, NUM_JOBS + 1)],
    "train_id": np.random.choice(trains["train_id"], NUM_JOBS, replace=False),
    "priority": np.random.choice(["critical", "high", "medium", "low"], NUM_JOBS, p=[0.1, 0.2, 0.4, 0.3]),
    "due_date": pd.date_range("2025-01-05", periods=NUM_JOBS, freq="2D").strftime("%Y-%m-%d"),
    "estimated_hours": np.random.randint(2, 12, NUM_JOBS),
})
job_cards.to_csv(OUT / "job_cards.csv", index=False)

# ---------- 6. ADVERTISERS (Branding) ----------
NUM_ADV = 5
advertisers = pd.DataFrame({
    "advertiser_id": [f"A{i:02d}" for i in range(1, NUM_ADV + 1)],
    "branded_train_ids": ["T001;T002", "T003", "T004;T005", "T006", "T007;T008"],
    "required_hours_per_week": [40, 30, 50, 25, 35],
    "current_exposure_hours": [10, 20, 15, 5, 25],
})
advertisers.to_csv(OUT / "advertisers.csv", index=False)

print("✅ Synthetic data generated:")
for f in OUT.glob("*.csv"):
    print(f"   - {f.name}")