"""GTFS validation checks for the KMRL feed.

Runs referential-integrity and format checks against the loaded feed and
prints a report. Exits with code 1 if any ERROR-level check fails.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

from src.loaders.gtfs_loader import load_gtfs

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TIME_RE = re.compile(r"^(\d{1,2}):(\d{2}):(\d{2})$")


class Report:
    """Collects check results and prints a summary."""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.passes: list[str] = []

    def ok(self, msg: str) -> None:
        self.passes.append(msg)
        print(f"  [PASS] {msg}")

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)
        print(f"  [WARN] {msg}")

    def fail(self, msg: str) -> None:
        self.errors.append(msg)
        print(f"  [FAIL] {msg}")

    def summary(self) -> None:
        print("\n" + "=" * 60)
        print("VALIDATION SUMMARY")
        print("=" * 60)
        print(f"  Passed:   {len(self.passes)}")
        print(f"  Warnings: {len(self.warnings)}")
        print(f"  Errors:   {len(self.errors)}")
        if self.errors:
            print("\nErrors:")
            for e in self.errors:
                print(f"  - {e}")


def _set_diff(df_a: pd.DataFrame, col_a: str, df_b: pd.DataFrame, col_b: str) -> set[str]:
    """Return values in col_a that are not in col_b."""
    a = set(df_a[col_a].dropna().astype(str))
    b = set(df_b[col_b].dropna().astype(str))
    return a - b


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_referential_integrity(feed: dict[str, pd.DataFrame], r: Report) -> None:
    print("\n[1] Referential integrity")

    missing = _set_diff(feed["stop_times"], "stop_id", feed["stops"], "stop_id")
    if missing:
        r.fail(f"{len(missing)} stop_id in stop_times not in stops: {sorted(missing)[:5]}...")
    else:
        r.ok("All stop_times.stop_id exist in stops.txt")

    missing = _set_diff(feed["trips"], "route_id", feed["routes"], "route_id")
    if missing:
        r.fail(f"trips.route_id not in routes: {sorted(missing)}")
    else:
        r.ok("All trips.route_id exist in routes.txt")

    missing = _set_diff(feed["trips"], "service_id", feed["calendar"], "service_id")
    if missing:
        r.fail(f"trips.service_id not in calendar: {sorted(missing)}")
    else:
        r.ok("All trips.service_id exist in calendar.txt")

    if "shapes" in feed:
        missing = _set_diff(feed["trips"], "shape_id", feed["shapes"], "shape_id")
        if missing:
            r.warn(f"trips.shape_id not in shapes: {sorted(missing)}")
        else:
            r.ok("All trips.shape_id exist in shapes.txt")

    if "fare_rules" in feed and "fare_attributes" in feed:
        missing = _set_diff(feed["fare_rules"], "fare_id", feed["fare_attributes"], "fare_id")
        if missing:
            r.fail(f"fare_rules.fare_id not in fare_attributes: {sorted(missing)}")
        else:
            r.ok("All fare_rules.fare_id exist in fare_attributes.txt")


def check_stop_sequences(feed: dict[str, pd.DataFrame], r: Report) -> None:
    print("\n[2] stop_sequence monotonic per trip")

    st = feed["stop_times"].copy()
    st["stop_sequence"] = st["stop_sequence"].astype(int)
    st = st.sort_values(["trip_id", "stop_sequence"])

    bad = st.groupby("trip_id")["stop_sequence"].apply(
        lambda s: not s.is_monotonic_increasing
    )
    bad_trips = bad[bad].index.tolist()

    if bad_trips:
        r.fail(f"{len(bad_trips)} trips have non-monotonic stop_sequence: {bad_trips[:5]}")
    else:
        r.ok(f"All {st.trip_id.nunique()} trips have monotonic stop_sequence")


def check_time_format(feed: dict[str, pd.DataFrame], r: Report) -> None:
    print("\n[3] Time format (HH:MM:SS, allow >= 24:00)")

    st = feed["stop_times"]
    bad_arr = [t for t in st["arrival_time"] if not TIME_RE.match(str(t))]
    bad_dep = [t for t in st["departure_time"] if not TIME_RE.match(str(t))]

    if bad_arr:
        r.fail(f"{len(bad_arr)} invalid arrival_time values, e.g. {bad_arr[:3]}")
    else:
        r.ok("All arrival_time values match HH:MM:SS")

    if bad_dep:
        r.fail(f"{len(bad_dep)} invalid departure_time values, e.g. {bad_dep[:3]}")
    else:
        r.ok("All departure_time values match HH:MM:SS")

    # Confirm times >= 24:00 are acceptable
    over24 = [t for t in st["arrival_time"] if TIME_RE.match(str(t)) and int(str(t).split(":")[0]) >= 24]
    if over24:
        r.ok(f"{len(over24)} times >= 24:00:00 present (valid GTFS, e.g. {over24[0]})")


def check_arrival_before_departure(feed: dict[str, pd.DataFrame], r: Report) -> None:
    print("\n[4] arrival_time <= departure_time per stop_time row")

    st = feed["stop_times"].copy()

    def _to_sec(t: str) -> int:
        h, m, s = t.split(":")
        return int(h) * 3600 + int(m) * 60 + int(s)

    st["arr_s"] = st["arrival_time"].map(_to_sec)
    st["dep_s"] = st["departure_time"].map(_to_sec)

    bad = st[st["arr_s"] > st["dep_s"]]
    if len(bad):
        r.fail(f"{len(bad)} rows have arrival_time > departure_time")
    else:
        r.ok("All rows have arrival_time <= departure_time")


def check_calendar_dates(feed: dict[str, pd.DataFrame], r: Report) -> None:
    print("\n[5] Calendar date ranges")

    cal = feed["calendar"]
    for _, row in cal.iterrows():
        start = row["start_date"]
        end = row["end_date"]
        if start > end:
            r.fail(f"service {row['service_id']}: start_date {start} > end_date {end}")
        else:
            r.ok(f"service {row['service_id']}: {start} → {end}")


def check_fare_coverage(feed: dict[str, pd.DataFrame], r: Report) -> None:
    print("\n[6] Fare coverage & consistency")

    if "fare_rules" not in feed or "fare_attributes" not in feed:
        r.warn("fare_rules.txt or fare_attributes.txt missing — skipping fare checks")
        return

    fr = feed["fare_rules"]
    fa = feed["fare_attributes"]

    # Every stop should be reachable by at least one fare rule (as origin)
    stops = set(feed["stops"]["stop_id"])
    origins = set(fr["origin_id"])
    dests = set(fr["destination_id"])

    unreachable_origin = stops - origins
    unreachable_dest = stops - dests

    if unreachable_origin:
        r.warn(f"{len(unreachable_origin)} stops never appear as origin: {sorted(unreachable_origin)[:5]}")
    else:
        r.ok("Every stop appears as origin in fare_rules")

    if unreachable_dest:
        r.warn(f"{len(unreachable_dest)} stops never appear as destination: {sorted(unreachable_dest)[:5]}")
    else:
        r.ok("Every stop appears as destination in fare_rules")

    # Price sanity
    prices = fa["price"].astype(float)
    if (prices <= 0).any():
        r.fail("Non-positive fares found")
    else:
        r.ok(f"All {len(prices)} fares are positive (min ₹{prices.min():.0f}, max ₹{prices.max():.0f})")


def check_duplicates(feed: dict[str, pd.DataFrame], r: Report) -> None:
    print("\n[7] Duplicate primary keys")

    for table, key in [
        ("stops", "stop_id"),
        ("routes", "route_id"),
        ("trips", "trip_id"),
        ("agency", "agency_id"),
    ]:
        df = feed.get(table)
        if df is None:
            continue
        dup = df[df.duplicated(subset=[key], keep=False)]
        if len(dup):
            r.fail(f"{table}: {len(dup)} duplicate {key} values")
        else:
            r.ok(f"{table}.{key} is unique ({len(df)} rows)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 60)
    print("KMRL GTFS VALIDATION")
    print("=" * 60)

    feed = load_gtfs("data/raw")

    r = Report()
    check_referential_integrity(feed, r)
    check_stop_sequences(feed, r)
    check_time_format(feed, r)
    check_arrival_before_departure(feed, r)
    check_calendar_dates(feed, r)
    check_fare_coverage(feed, r)
    check_duplicates(feed, r)

    r.summary()

    return 1 if r.errors else 0


if __name__ == "__main__":
    sys.exit(main())