"""
Data models for the MetroPulse solver.
Loads synthetic KMRL-like data into a single ProblemData object.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data" / "synthetic"


@dataclass
class ProblemData:
    """Everything the CP-SAT model needs."""
    trains: pd.DataFrame
    drivers: pd.DataFrame
    routes: pd.DataFrame
    shifts: pd.DataFrame
    job_cards: pd.DataFrame
    schedule_date: str = "2025-01-15"

    @classmethod
    def load(cls, data_dir: Optional[Path] = None) -> "ProblemData":
        d = Path(data_dir) if data_dir else DATA_DIR
        if not d.exists():
            raise FileNotFoundError(
                f"Synthetic data dir not found: {d}\n"
                f"Run: python data/generate_synthetic.py"
            )
        return cls(
            trains=pd.read_csv(d / "trains.csv", keep_default_na=False),
            drivers=pd.read_csv(d / "drivers.csv"),
            routes=pd.read_csv(d / "routes.csv"),
            shifts=pd.read_csv(d / "shifts.csv"),
            job_cards=pd.read_csv(d / "job_cards.csv"),
        )

    def summary(self) -> str:
        return (
            f"Trains:     {len(self.trains)}\n"
            f"Drivers:    {len(self.drivers)}\n"
            f"Routes:     {len(self.routes)}\n"
            f"Shifts:     {len(self.shifts)}\n"
            f"Job Cards:  {len(self.job_cards)}\n"
            f"Date:       {self.schedule_date}"
        )


if __name__ == "__main__":
    data = ProblemData.load()
    print("=== Loaded Problem Data ===")
    print(data.summary())
    print("\n=== Trains sample ===")
    print(data.trains.head())
    print("\n=== Drivers sample ===")
    print(data.drivers.head())