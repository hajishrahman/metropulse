
"""
MetroPulse solver — problem data loader.

Loads GTFS hourly service and synthetic scenario data into a single
ProblemData object. Reads from:
    data/hourly_service.csv
    data/synthetic/rakes.csv
    data/synthetic/terminals.csv
    data/synthetic/maintenance.csv
    data/synthetic/depot.csv

Spec: docs/constraints-v2.md
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd


# Default root — overridable for testing
DEFAULT_ROOT = Path(__file__).parent.parent / "data"


def _read(path: Path, **kwargs) -> pd.DataFrame:
    """Read CSV as UTF-8; fall back to latin-1 for legacy files."""
    try:
        return pd.read_csv(path, encoding="utf-8", **kwargs)
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin-1", **kwargs)


@dataclass
class ProblemData:
    """All inputs required by the CP-SAT model."""

    hourly_service: pd.DataFrame
    rakes: pd.DataFrame
    terminals: pd.DataFrame
    maintenance: pd.DataFrame
    depot: pd.DataFrame
    scenario: str = "DPR_2043_2048"

    # -----------------------------------------------------------------------
    # Convenience accessors
    # -----------------------------------------------------------------------
    @property
    def num_hours(self) -> int:
        """Number of hourly periods."""
        return len(self.hourly_service)

    @property
    def total_required_departures(self) -> int:
        """Total UP + DOWN departures across all hours."""
        return int(self.hourly_service["total_trips"].sum())

    @property
    def service_rakes(self) -> pd.DataFrame:
        """Rakes with status='service' (available for trips)."""
        return self.rakes[self.rakes["status"] == "service"]

    @property
    def standby_rakes(self) -> pd.DataFrame:
        """Rakes with status='standby' (reserved for disruptions)."""
        return self.rakes[self.rakes["status"] == "standby"]

    @property
    def maintenance_rakes(self) -> pd.DataFrame:
        """Rakes with status='maintenance' (under maintenance)."""
        return self.rakes[self.rakes["status"] == "maintenance"]

    # Backwards compatibility alias
    @property
    def bare_rakes(self) -> pd.DataFrame:
        """DEPRECATED: use service_rakes."""
        return self.service_rakes

    # -----------------------------------------------------------------------
    # Loading
    # -----------------------------------------------------------------------
    @classmethod
    def load(
        cls,
        root: Optional[Path] = None,
        scenario: str = "DPR_2043_2048",
    ) -> "ProblemData":
        base = Path(root) if root else DEFAULT_ROOT
        synth_dir = base / "synthetic"

        files = {
            "hourly_service": base / "hourly_service.csv",
            "rakes": synth_dir / "rakes.csv",
            "terminals": synth_dir / "terminals.csv",
            "maintenance": synth_dir / "maintenance.csv",
            "depot": synth_dir / "depot.csv",
        }

        missing = [str(p) for p in files.values() if not p.exists()]
        if missing:
            raise FileNotFoundError(
                "Missing data files:\n  - " + "\n  - ".join(missing)
                + "\n\nRun: python data/generate_synthetic_v2.py"
            )

        hourly_service = _read(files["hourly_service"])
        rakes = _read(files["rakes"])
        terminals = _read(files["terminals"])
        maintenance = _read(files["maintenance"])
        depot = _read(files["depot"], keep_default_na=False)

        return cls(
            hourly_service=hourly_service,
            rakes=rakes,
            terminals=terminals,
            maintenance=maintenance,
            depot=depot,
            scenario=scenario,
        )

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    def summary(self) -> str:
        return (
            f"Scenario:           {self.scenario}\n"
            f"Hours:              {self.num_hours}\n"
            f"Total departures:   {self.total_required_departures} "
            f"(UP+DOWN)\n"
            f"Rakes (total):      {len(self.rakes)} "
            f"({len(self.service_rakes)} service + "
            f"{len(self.standby_rakes)} standby + "
            f"{len(self.maintenance_rakes)} maintenance)\n"
            f"Terminals:          {len(self.terminals)}\n"
            f"Maintenance blocks: {len(self.maintenance)}\n"
            f"Depot locations:    {len(self.depot)}"
        )


# ---------------------------------------------------------------------------
# CLI test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Loading ProblemData from data/...\n")
    data = ProblemData.load()
    print("=== Summary ===")
    print(data.summary())

    print("\n=== Hourly service (first 5 rows) ===")
    print(data.hourly_service.head().to_string(index=False))

    print("\n=== Rakes (first 5 rows) ===")
    print(data.rakes.head().to_string(index=False))

    print("\n=== Terminals ===")
    print(data.terminals.to_string(index=False))

    print("\n=== Depot ===")
    print(data.depot.to_string(index=False))
