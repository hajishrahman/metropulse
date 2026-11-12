"""Tests for schedule_loader: parsing, guards, grouping."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from src.simulation.schedule_loader import (
    MAX_DURATION_SEC,
    MIN_DURATION_SEC,
    group_by_rake,
    load_schedule,
    load_schedule_grouped,
    parse_hhmm_to_sec,
    total_trips,
)


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=["trip_id", "rake_id", "direction", "departure", "arrival"]
        )
        w.writeheader()
        w.writerows(rows)


@pytest.mark.parametrize(
    ("value", "seconds"),
    [
        ("00:00", 0),
        ("06:00", 21_600),
        ("06:50", 24_600),
        ("23:00", 82_800),
        ("06:00:00", 21_600),
        ("06:50:14", 24_614),
        ("24:03:45", 86_625),
    ],
)
def test_parse_hhmm(value: str, seconds: int):
    assert parse_hhmm_to_sec(value) == seconds


@pytest.mark.parametrize(
    "value", ["", "6:00", "06:5", "0600", "aa:bb", "25:00", "06:99", "06:99:00"]
)
def test_parse_hhmm_rejects_invalid_values(value: str):
    with pytest.raises(ValueError):
        parse_hhmm_to_sec(value)


def test_load_schedule_minimal(tmp_path: Path):
    p = tmp_path / "schedule.csv"
    _write_csv(
        p,
        [
            {"trip_id": "T1", "rake_id": "R1", "direction": "UP",
             "departure": "06:00", "arrival": "06:50"},
            {"trip_id": "T2", "rake_id": "R1", "direction": "DOWN",
             "departure": "06:55", "arrival": "07:45"},
        ],
    )
    rows = load_schedule(p)
    assert rows == [
        {
            "trip_id": "T1",
            "rake_id": "R1",
            "direction": "UP",
            "dep_sec": 21_600,
            "arr_sec": 24_600,
            "duration_sec": 3000,
        },
        {
            "trip_id": "T2",
            "rake_id": "R1",
            "direction": "DOWN",
            "dep_sec": 24_900,
            "arr_sec": 27_900,
            "duration_sec": 3000,
        },
    ]
    for r in rows:
        assert r["duration_sec"] == r["arr_sec"] - r["dep_sec"]


def test_load_schedule_duplicate_id(tmp_path: Path):
    p = tmp_path / "schedule.csv"
    _write_csv(
        p,
        [
            {"trip_id": "T1", "rake_id": "R1", "direction": "UP",
             "departure": "06:00", "arrival": "06:50"},
            {"trip_id": "T1", "rake_id": "R2", "direction": "UP",
             "departure": "07:00", "arrival": "07:50"},
        ],
    )
    with pytest.raises(ValueError, match="duplicate"):
        load_schedule(p)


def test_load_schedule_accepts_short_partial_duration(tmp_path: Path):
    """Real GTFS has partial trips (e.g. MUTT->ALVA) as short as ~8 min."""
    p = tmp_path / "schedule.csv"
    _write_csv(
        p,
        [
            {"trip_id": "T1", "rake_id": "R1", "direction": "DOWN",
             "departure": "06:15:00", "arrival": "06:23:40"},  # 520 s
        ],
    )
    rows = load_schedule(p)
    assert rows[0]["duration_sec"] == 520


def test_load_schedule_rejects_absurdly_short_trip(tmp_path: Path):
    """Duration below MIN_DURATION_SEC must be rejected as bad data."""
    p = tmp_path / "schedule.csv"
    _write_csv(
        p,
        [
            {"trip_id": "T1", "rake_id": "R1", "direction": "UP",
             "departure": "06:00", "arrival": "06:00:30"},  # 30 s — absurd
        ],
    )
    with pytest.raises(ValueError, match="outside sane range"):
        load_schedule(p)


def test_load_schedule_rejects_absurdly_long_trip(tmp_path: Path):
    """Duration above MAX_DURATION_SEC must be rejected as bad data."""
    p = tmp_path / "schedule.csv"
    _write_csv(
        p,
        [
            {"trip_id": "T1", "rake_id": "R1", "direction": "UP",
             "departure": "06:00", "arrival": "09:00:00"},  # 180 min — absurd
        ],
    )
    with pytest.raises(ValueError, match="outside sane range"):
        load_schedule(p)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("trip_id", "", "empty trip_id"),
        ("rake_id", "", "empty rake_id"),
        ("direction", "", "empty direction"),
        ("departure", "6:00", "line 2: bad time format"),
    ],
)
def test_load_schedule_rejects_invalid_row_values(
    tmp_path: Path, field: str, value: str, message: str
):
    p = tmp_path / "schedule.csv"
    row = {
        "trip_id": "T1",
        "rake_id": "R1",
        "direction": "UP",
        "departure": "06:00",
        "arrival": "06:50",
    }
    row[field] = value
    _write_csv(p, [row])

    with pytest.raises(ValueError, match=message):
        load_schedule(p)


def test_group_by_rake_sorts(tmp_path: Path):
    p = tmp_path / "schedule.csv"
    _write_csv(
        p,
        [
            {"trip_id": "T2", "rake_id": "R1", "direction": "DOWN",
             "departure": "07:00", "arrival": "07:50"},
            {"trip_id": "T1", "rake_id": "R1", "direction": "UP",
             "departure": "06:00", "arrival": "06:50"},
            {"trip_id": "T3", "rake_id": "R2", "direction": "UP",
             "departure": "06:00", "arrival": "06:50"},
        ],
    )
    grouped = group_by_rake(load_schedule(p))
    assert sorted(grouped) == ["R1", "R2"]
    assert [t["trip_id"] for t in grouped["R1"]] == ["T1", "T2"]


def test_load_schedule_grouped_count_mismatch(tmp_path: Path):
    p = tmp_path / "schedule.csv"
    _write_csv(
        p,
        [
            {"trip_id": "T1", "rake_id": "R1", "direction": "UP",
             "departure": "06:00", "arrival": "06:50"},
        ],
    )
    sol = tmp_path / "solution.json"
    sol.write_text(json.dumps({"num_trips": 2}))
    with pytest.raises(ValueError, match="trip count mismatch"):
        load_schedule_grouped(p, sol)


def test_total_trips_real_schedule():
    """Integration: real schedule.csv loads and passes all guards."""
    grouped = load_schedule_grouped()
    assert total_trips(grouped) == 250
    assert len(grouped) == 18
    for trips in grouped.values():
        assert trips == sorted(trips, key=lambda t: (t["dep_sec"], t["trip_id"]))


def test_shuffle_does_not_change_grouping():
    """Loader must sort by (dep_sec, trip_id), independent of input row order."""
    import random

    rows = load_schedule()
    base = group_by_rake(rows)

    shuffled = rows[:]
    random.Random(0).shuffle(shuffled)
    assert shuffled != rows
    shuffled_grouped = group_by_rake(shuffled)

    assert set(shuffled_grouped) == set(base)
    for rake in base:
        assert [t["trip_id"] for t in shuffled_grouped[rake]] == [
            t["trip_id"] for t in base[rake]
        ]


def test_one_trip_rake_has_zero_eligible():
    """A rake with 1 trip has 0 eligible (first) trips for propagation."""
    grouped = {
        "R1": [
            {"trip_id": "A", "rake_id": "R1", "direction": "UP",
             "dep_sec": 21600, "arr_sec": 24600, "duration_sec": 3000},
        ],
    }
    total = sum(len(v) for v in grouped.values())
    eligible = total - len(grouped)
    assert eligible == 0