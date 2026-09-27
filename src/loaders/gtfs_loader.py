"""Load and validate KMRL GTFS data."""
from pathlib import Path
import pandas as pd

REQUIRED = [
    "agency", "stops", "routes", "trips", "stop_times", "calendar",
]
OPTIONAL = [
    "calendar_dates", "fare_attributes", "fare_rules",
    "shapes", "translations", "feed_info",
]


def load_gtfs(data_dir: str | Path = "data/raw") -> dict[str, pd.DataFrame]:
    """Load all GTFS .txt files into a dict of DataFrames.

    All columns are loaded as strings to preserve IDs with leading zeros
    and to avoid accidental numeric coercion of time fields.
    """
    data_dir = Path(data_dir)
    if not data_dir.exists():
        raise FileNotFoundError(f"GTFS dir not found: {data_dir}")

    feed: dict[str, pd.DataFrame] = {}

    for name in REQUIRED:
        path = data_dir / f"{name}.txt"
        if not path.exists():
            raise FileNotFoundError(f"Missing required GTFS file: {path}")
        feed[name] = pd.read_csv(path, dtype=str, keep_default_na=False)
        print(f"[OK]  {name}.txt  ({len(feed[name])} rows)")

    for name in OPTIONAL:
        path = data_dir / f"{name}.txt"
        if path.exists():
            feed[name] = pd.read_csv(path, dtype=str, keep_default_na=False)
            print(f"[OK]  {name}.txt  ({len(feed[name])} rows)  [optional]")

    return feed


if __name__ == "__main__":
    feed = load_gtfs()
    print("\nLoaded tables:", list(feed.keys()))
    print("\nSample stops:")
    print(feed["stops"].head(3).to_string(index=False))