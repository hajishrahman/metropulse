"""
MetroPulse Phase 5 — Reschedule problem data loader.

Self-contained parallel loader for Phase 5. It does NOT wrap ProblemData.

Reads:
    data/processed/schedule.csv      (Phase 1 baseline — 250 trips)
    data/synthetic/rakes_phase5.csv  (25 rakes + 2 Phase-5 columns)

Mirrors the shape of solver.models.ProblemData (dataclass, .load(), .summary(),
.service_rakes, .maintenance_rakes) so reschedule_constraints.py consumes it
the same way constraints.py consumes ProblemData.

Differences from ProblemData:
    - trips are read from schedule.csv (columns: departure, arrival) and
      renamed to departure_time / arrival_time, with dep_sec, arr_sec,
      duration computed.
    - rakes are read from rakes_phase5.csv (extra columns:
      km_since_last_maintenance, maintenance_type).
    - additional properties: scheduled_maintenance_rakes,
      unscheduled_maintenance_rakes.

Phase 1 files (rakes.csv, trips_all.csv, ProblemData) are NOT touched.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd

from solver import reschedule_config as R5


DEFAULT_ROOT = Path(__file__).parent.parent


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
class RescheduleProblemData:
    trips: pd.DataFrame          # trip_id, direction, first_stop, last_stop,
                                 # departure_time, arrival_time, duration,
                                 # dep_sec, arr_sec
    rakes: pd.DataFrame          # 25 rows, incl. km_since_last_maintenance,
                                 # maintenance_type
    scenario: str = "Phase5_disruption"

    @property
    def num_trips(self) -> int:
        return len(self.trips)

    @property
    def service_rakes(self) -> pd.DataFrame:
        return self.rakes[self.rakes["status"] == "service"]

    @property
    def maintenance_rakes(self) -> pd.DataFrame:
        return self.rakes[self.rakes["status"] == "maintenance"]

    @property
    def scheduled_maintenance_rakes(self) -> pd.DataFrame:
        return self.rakes[
            (self.rakes["status"] == "maintenance")
            & (self.rakes["maintenance_type"] == R5.MAINTENANCE_TYPE_SCHEDULED)
        ]

    @property
    def unscheduled_maintenance_rakes(self) -> pd.DataFrame:
        return self.rakes[
            (self.rakes["status"] == "maintenance")
            & (self.rakes["maintenance_type"] == R5.MAINTENANCE_TYPE_UNSCHEDULED)
        ]

    @classmethod
    def load(cls, root: Optional[Path] = None,
             scenario: str = "Phase5_disruption") -> "RescheduleProblemData":
        base = Path(root) if root else DEFAULT_ROOT

        schedule_path = base / R5.BASELINE_SCHEDULE_CSV
        rakes_path = base / R5.RAKES_PHASE5_CSV

        missing = [str(p) for p in (schedule_path, rakes_path) if not p.is_file()]
        if missing:
            raise FileNotFoundError(
                "Missing Phase 5 data files:\n  - " + "\n  - ".join(missing)
            )

        # --- Trips (from schedule.csv, renamed + sec-computed) ---------------
        trips_raw = _read(schedule_path)
        required = {
            "trip_id", "rake_id", "direction", "first_stop", "last_stop",
            "departure", "arrival",
        }
        missing_cols = required - set(trips_raw.columns)
        if missing_cols:
            raise ValueError(
                f"schedule.csv missing columns: {sorted(missing_cols)}"
            )
        if trips_raw["trip_id"].isna().any() or trips_raw["trip_id"].eq("").any():
            raise ValueError("schedule.csv contains an empty trip_id")
        if trips_raw["trip_id"].duplicated().any():
            raise ValueError("schedule.csv contains duplicate trip_id values")

        trips = trips_raw.rename(
            columns={"departure": "departure_time", "arrival": "arrival_time"}
        ).copy()

        trips["dep_sec"] = trips["departure_time"].apply(_time_to_sec)
        trips["arr_sec"] = trips["arrival_time"].apply(_time_to_sec)
        if (trips["arr_sec"] <= trips["dep_sec"]).any():
            raise ValueError("schedule.csv contains non-positive trip durations")
        trips["duration"] = trips["arr_sec"] - trips["dep_sec"]

        # --- Rakes (from rakes_phase5.csv) ----------------------------------
        rakes = _read(rakes_path)
        required_rake_cols = {
            "rake_id", "status", "initial_mileage_km", "initial_location",
            "km_since_last_maintenance", "maintenance_type",
        }
        missing_rake_cols = required_rake_cols - set(rakes.columns)
        if missing_rake_cols:
            raise ValueError(
                f"rakes_phase5.csv missing columns: {sorted(missing_rake_cols)}"
            )
        if rakes["rake_id"].isna().any() or rakes["rake_id"].eq("").any():
            raise ValueError("rakes_phase5.csv contains an empty rake_id")
        if rakes["rake_id"].duplicated().any():
            raise ValueError("rakes_phase5.csv contains duplicate rake_id values")

        allowed_mt = {
            R5.MAINTENANCE_TYPE_SERVICE,
            R5.MAINTENANCE_TYPE_SCHEDULED,
            R5.MAINTENANCE_TYPE_UNSCHEDULED,
        }
        bad_mt = set(rakes["maintenance_type"]) - allowed_mt
        if bad_mt:
            raise ValueError(
                f"rakes_phase5.csv has invalid maintenance_type values: {sorted(bad_mt)}"
            )

        # --- Integrity guard: baseline schedule must use ONLY service rakes
        service_ids = set(rakes.loc[rakes["status"] == "service", "rake_id"])
        baseline_ids = set(trips_raw["rake_id"])
        non_service = baseline_ids - service_ids
        if non_service:
            raise ValueError(
                "schedule.csv references non-service rakes: "
                f"{sorted(non_service)}"
            )

        return cls(trips=trips, rakes=rakes, scenario=scenario)

    def summary(self) -> str:
        return (
            f"Scenario:               {self.scenario}\n"
            f"Trips:                  {self.num_trips}\n"
            f"Rakes total:            {len(self.rakes)} "
            f"({len(self.service_rakes)} service + "
            f"{len(self.maintenance_rakes)} maintenance)\n"
            f"Scheduled maintenance:  {len(self.scheduled_maintenance_rakes)}\n"
            f"Unscheduled repair:     {len(self.unscheduled_maintenance_rakes)}"
        )