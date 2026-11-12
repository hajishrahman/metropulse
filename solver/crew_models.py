"""
MetroPulse Phase 3 crew problem data loader.

Reads:
    data/processed/schedule.csv       (Phase 1 output — 250 trips; READ-ONLY input)
    data/synthetic/drivers.csv        (55 synthetic drivers, driver_id only in V1)

Mirrors solver/models.py style:
    @dataclass + @classmethod load(); validates columns, duplicates, non-empty;
    raises ValueError / FileNotFoundError; summary(); .num_* properties.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd


DEFAULT_ROOT = Path(__file__).parent.parent / "data"


# ==== helpers ====
def _read(path: Path, **kwargs) -> pd.DataFrame:
    try:
        return pd.read_csv(path, encoding="utf-8", **kwargs)
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin-1", **kwargs)


def _time_to_sec(t: str) -> int:
    """HH:MM:SS -> seconds. Local copy (mirrors solver/models._time_to_sec)."""
    try:
        h, m, s = (int(part) for part in str(t).split(":"))
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"Invalid time: {t!r}") from exc
    if h < 0 or not 0 <= m < 60 or not 0 <= s < 60:
        raise ValueError(f"Invalid time: {t!r}")
    return h * 3600 + m * 60 + s


# ==== data class ====
@dataclass
class CrewProblemData:
    trips: pd.DataFrame
    drivers: pd.DataFrame
    scenario: str = "V1_crew_250"

    @property
    def num_trips(self) -> int:
        return len(self.trips)

    @property
    def num_drivers(self) -> int:
        return len(self.drivers)

    @property
    def trip_ids(self) -> list[str]:
        return self.trips["trip_id"].tolist()

    @property
    def driver_ids(self) -> list[str]:
        return self.drivers["driver_id"].tolist()

    @classmethod
    def load(cls, root: Optional[Path] = None,
             scenario: str = "V1_crew_250") -> "CrewProblemData":
        base = Path(root) if root else DEFAULT_ROOT
        synth = base / "synthetic"

        files = {
            "schedule": base / "processed" / "schedule.csv",
            "drivers":  synth / "drivers.csv",
        }
        missing = [str(p) for p in files.values() if not p.is_file()]
        if missing:
            raise FileNotFoundError(
                "Missing data files:\n  - " + "\n  - ".join(missing)
            )

        # ---- schedule.csv ----
        trips = _read(files["schedule"])
        req = {"trip_id", "rake_id", "direction", "first_stop", "last_stop",
               "departure", "arrival"}
        missing_cols = req - set(trips.columns)
        if missing_cols:
            raise ValueError(f"schedule.csv missing columns: {sorted(missing_cols)}")
        if trips["trip_id"].isna().any() or trips["trip_id"].astype(str).eq("").any():
            raise ValueError("schedule.csv contains empty trip_id")
        if trips["trip_id"].duplicated().any():
            raise ValueError("schedule.csv contains duplicate trip_id")

        trips["dep_sec"] = trips["departure"].apply(_time_to_sec)
        trips["arr_sec"] = trips["arrival"].apply(_time_to_sec)
        if (trips["arr_sec"] <= trips["dep_sec"]).any():
            raise ValueError("schedule.csv contains non-positive trip durations")

        # ---- drivers.csv ----
        drivers = _read(files["drivers"])
        if "driver_id" not in drivers.columns:
            raise ValueError("drivers.csv missing column: driver_id")
        if drivers["driver_id"].isna().any() or drivers["driver_id"].astype(str).eq("").any():
            raise ValueError("drivers.csv contains empty driver_id")
        if drivers["driver_id"].duplicated().any():
            raise ValueError("drivers.csv contains duplicate driver_id")

        return cls(trips=trips, drivers=drivers, scenario=scenario)

    def summary(self) -> str:
        return (
            f"Scenario:    {self.scenario}\n"
            f"Trips:       {self.num_trips}\n"
            f"Drivers:     {self.num_drivers}\n"
            f"First dep:   {self.trips['dep_sec'].min()}s\n"
            f"Last arr:    {self.trips['arr_sec'].max()}s"
        )