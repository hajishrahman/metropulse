"""Compare DPR-derived operating values with values observed in GTFS."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from solver import config


ROOT = Path(__file__).parent.parent
GTFS_DIR = ROOT / "data" / "raw"
OUT_JSON = ROOT / "data" / "processed" / "gtfs_validation.json"
GTFS_FILES = ("stops.txt", "stop_times.txt", "trips.txt", "routes.txt")


def load_gtfs(data_dir: Path = GTFS_DIR) -> dict[str, pd.DataFrame]:
    """Load the GTFS tables required for validation."""
    missing = [
        data_dir / name
        for name in GTFS_FILES
        if not (data_dir / name).is_file()
    ]
    if missing:
        raise FileNotFoundError(
            "Missing required GTFS files:\n  - "
            + "\n  - ".join(str(path) for path in missing)
        )

    return {
        Path(name).stem: pd.read_csv(
            data_dir / name, dtype=str, keep_default_na=False
        )
        for name in GTFS_FILES
    }


def _time_to_seconds(value: str) -> int:
    """Convert a GTFS HH:MM:SS time, including hours beyond 24, to seconds."""
    hours, minutes, seconds = (int(part) for part in value.split(":"))
    return hours * 3600 + minutes * 60 + seconds


def _status_for_diff(diff_pct: float) -> str:
    if diff_pct <= 10:
        return "PASS"
    if diff_pct <= 25:
        return "WARN"
    return "FAIL"


def _comparison(name: str, gtfs_value: float, dpr_value: float) -> dict:
    diff_pct = abs(gtfs_value - dpr_value) / dpr_value * 100
    return {
        "name": name,
        "gtfs_value": round(gtfs_value, 2),
        "dpr_value": round(dpr_value, 2),
        "diff_pct": round(diff_pct, 2),
        "status": _status_for_diff(diff_pct),
    }


def _trip_endpoints(stop_times: pd.DataFrame) -> pd.DataFrame:
    ordered = stop_times.copy()
    ordered["stop_sequence"] = pd.to_numeric(ordered["stop_sequence"])
    ordered = ordered.sort_values(["trip_id", "stop_sequence"])

    first_stops = ordered.drop_duplicates("trip_id", keep="first")[
        ["trip_id", "stop_id", "departure_time"]
    ].rename(columns={
        "stop_id": "first_stop_id",
        "departure_time": "first_departure",
    })
    last_stops = ordered.drop_duplicates("trip_id", keep="last")[
        ["trip_id", "arrival_time"]
    ].rename(columns={"arrival_time": "last_arrival"})
    endpoints = first_stops.merge(last_stops, on="trip_id")
    endpoints["departure_seconds"] = endpoints["first_departure"].map(
        _time_to_seconds
    )
    endpoints["arrival_seconds"] = endpoints["last_arrival"].map(
        _time_to_seconds
    )
    endpoints["running_time_min"] = (
        endpoints["arrival_seconds"] - endpoints["departure_seconds"]
    ) / 60
    return endpoints


def validate_gtfs(feed: dict[str, pd.DataFrame]) -> dict:
    stop_times = feed["stop_times"]
    endpoints = _trip_endpoints(stop_times)

    running_time_value = float(endpoints["running_time_min"].mean())
    running_time_check = _comparison(
        "running_time", running_time_value, config.ONE_WAY_RUNNING_MIN
    )

    turnaround_check = {
        "name": "turnaround",
        "gtfs_value": None,
        "dpr_value": config.TERMINAL_TURNAROUND_MIN,
        "diff_pct": None,
        "status": "WARN",
        "reason": "GTFS has no block_id or rake assignment",
    }

    peak_dpr_value = min(
        plan_row[2] for plan_row in config.DPR_HOURLY_PLAN_2043_2048
    )
    peak_departures = endpoints.merge(
        feed["trips"][["trip_id", "service_id"]], on="trip_id"
    )
    peak_departures = peak_departures[
        peak_departures["first_stop_id"].isin(["ALVA", "TPHT"])
        & peak_departures["departure_seconds"].between(
            8 * 3600, 9 * 3600, inclusive="left"
        )
    ]
    gaps = []
    for _, direction_trips in peak_departures.groupby(
        ["service_id", "first_stop_id"]
    ):
        departures = direction_trips["departure_seconds"].sort_values()
        if len(departures) >= 2:
            gaps.extend(departures.diff().dropna().tolist())

    if gaps:
        peak_headway_check = _comparison(
            "peak_headway", min(gaps) / 60, peak_dpr_value
        )
    else:
        peak_headway_check = {
            "name": "peak_headway",
            "gtfs_value": None,
            "dpr_value": peak_dpr_value,
            "diff_pct": None,
            "status": "WARN",
            "reason": "insufficient trips to measure headway",
        }

    checks = [running_time_check, turnaround_check, peak_headway_check]
    statuses = [check["status"] for check in checks]
    if "FAIL" in statuses:
        overall_status = "FAIL"
    elif "WARN" in statuses:
        overall_status = "PARTIAL"
    else:
        overall_status = "PASS"

    summary = (
        f"{sum(status == 'PASS' for status in statuses)} of {len(checks)} checks "
        f"PASS, {sum(status == 'WARN' for status in statuses)} WARN, "
        f"{sum(status == 'FAIL' for status in statuses)} FAIL. "
        "Turnaround is unvalidated because GTFS has no rake/block assignments."
    )
    return {
        "status": overall_status,
        "checks": checks,
        "summary": summary,
    }


def main() -> None:
    feed = load_gtfs()
    result = validate_gtfs(feed)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUT_JSON.open("w", encoding="utf-8") as output_file:
        json.dump(result, output_file, indent=2)
    print(json.dumps(result, indent=2))
    print(f"\nWritten: {OUT_JSON}")


if __name__ == "__main__":
    main()
