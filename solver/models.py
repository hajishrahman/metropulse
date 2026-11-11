"""
MetroPulse problem data loader.

Reads:
    data/trips_all.csv               (solver input — 232 full + 18 partial = 250 trips)
    data/synthetic/rakes.csv         (fleet)
    data/synthetic/terminals.csv
    data/synthetic/maintenance.csv
    data/synthetic/depot.csv

hourly_service.csv is kept on disk for reconciliation only, not loaded here.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd


DEFAULT_ROOT = Path(__file__).parent.parent / "data"


def _read(path: Path, **kwargs) -> pd.DataFrame:
    try:
        return pd.read_csv(path, encoding="utf-8", **kwargs)
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin-1", **kwargs)


def _time_to_sec(t: str) -> int:
    try:
        h, m, s = (int(part) for part in t.split(":"))
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"Invalid GTFS time: {t!r}") from exc
    if h < 0 or not 0 <= m < 60 or not 0 <= s < 60:
        raise ValueError(f"Invalid GTFS time: {t!r}")
    return h * 3600 + m * 60 + s


@dataclass
class ProblemData:
    trips: pd.DataFrame
    rakes: pd.DataFrame
    terminals: pd.DataFrame
    maintenance: pd.DataFrame
    depot: pd.DataFrame
    scenario: str = "V1_baseline_250_merged"

    @property
    def num_trips(self) -> int:
        return len(self.trips)

    @property
    def service_rakes(self) -> pd.DataFrame:
        return self.rakes[self.rakes["status"] == "service"]

    @property
    def maintenance_rakes(self) -> pd.DataFrame:
        return self.rakes[self.rakes["status"] == "maintenance"]

    @classmethod
    def load(cls, root: Optional[Path] = None,
             scenario: str = "V1_baseline_250_merged") -> "ProblemData":
        base = Path(root) if root else DEFAULT_ROOT
        synth = base / "synthetic"

        files = {
            "trips": base / "trips_all.csv",
            "rakes": synth / "rakes.csv",
            "terminals": synth / "terminals.csv",
            "maintenance": synth / "maintenance.csv",
            "depot": synth / "depot.csv",
        }

        missing = [str(p) for p in files.values() if not p.exists()]
        if missing:
            raise FileNotFoundError(
                "Missing data files:\n  - " + "\n  - ".join(missing)
            )

        trips = _read(files["trips"])
        missing_columns = {"trip_id", "departure_time", "arrival_time"} - set(trips.columns)
        if missing_columns:
            raise ValueError(f"trips_all.csv missing columns: {sorted(missing_columns)}")
        if trips["trip_id"].isna().any() or trips["trip_id"].eq("").any():
            raise ValueError("trips_all.csv contains an empty trip_id")
        if trips["trip_id"].duplicated().any():
            raise ValueError("trips_all.csv contains duplicate trip_id values")

        # Precompute seconds for convenience
        trips["dep_sec"] = trips["departure_time"].apply(_time_to_sec)
        trips["arr_sec"] = trips["arrival_time"].apply(_time_to_sec)
        if (trips["arr_sec"] <= trips["dep_sec"]).any():
            raise ValueError("trips_all.csv contains non-positive trip durations")

        return cls(
            trips=trips,
            rakes=_read(files["rakes"]),
            terminals=_read(files["terminals"]),
            maintenance=_read(files["maintenance"]),
            depot=_read(files["depot"], keep_default_na=False),
            scenario=scenario,
        )

    def summary(self) -> str:
        return (
            f"Scenario:        {self.scenario}\n"
            f"Trips:           {self.num_trips}\n"
            f"Rakes total:     {len(self.rakes)} "
            f"({len(self.service_rakes)} service + "
            f"{len(self.maintenance_rakes)} maintenance)\n"
            f"Terminals:       {len(self.terminals)}\n"
            f"Maintenance:     {len(self.maintenance)}\n"
            f"Depot:           {len(self.depot)}"
        )