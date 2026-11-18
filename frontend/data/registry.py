# data/registry.py
"""File registry — Phase 1 only.

Rule 1: every number is read from disk. Rule 2: missing file -> 'not_generated',
missing column -> 'invalid' with the specific field named.
Rule 3: time parsing lives in components/time_utils.py, not here.

Caching: the public loader fetches mtime FRESH on every call and forwards
(path, mtime) to a private @lru_cache'd function. Decorating the *public* loader
would freeze results forever and break the reload button — that was a bug in the
Streamlit prototype. The private function's mtime argument is the cache key, so
touching the file busts the cache automatically.
"""

from __future__ import annotations

import functools
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

# Project root = parent of data/
_ROOT = Path(__file__).resolve().parent.parent.parent
_PROCESSED = _ROOT / 'data' / 'processed'


def _rel(path: str) -> str:
    """Return a path relative to project root for display."""
    try:
        return str(Path(path).resolve().relative_to(_ROOT))
    except ValueError:
        return path


def _result(data: Any, status: str, message: str, path: str, mtime: float) -> dict:
    return {
        'data': data,
        'status': status,
        'message': message,
        'path': _rel(path),
        'mtime': mtime,
    }


# ----------------------------------------------------------------------------
# CSV loader
# ----------------------------------------------------------------------------
@functools.lru_cache(maxsize=None)
def _load_csv_cached(path: str, mtime: float, required_columns: tuple[str, ...]) -> dict:
    if not os.path.exists(path):
        return _result(None, 'not_generated', 'File not generated yet.', path, mtime)
    try:
        df = pd.read_csv(path)
    except Exception as exc:  # noqa: BLE001 - surface parse error verbatim
        return _result(None, 'invalid', f'Parse error: {exc}', path, mtime)
    if df.empty:
        # An empty CSV parses but is not useful — surface as invalid.
        return _result(None, 'invalid', 'File parsed but contains no rows.', path, mtime)
    for col in required_columns:
        if col not in df.columns:
            return _result(None, 'invalid', f'Missing column: {col}', path, mtime)
    return _result(df, 'ok', '', path, mtime)


def _load_csv(path: Path, required_columns: tuple[str, ...]) -> dict:
    path_str = str(path)
    mtime = os.path.getmtime(path_str) if os.path.exists(path_str) else 0.0
    return _load_csv_cached(path_str, mtime, required_columns)


# ----------------------------------------------------------------------------
# JSON loader
# ----------------------------------------------------------------------------
@functools.lru_cache(maxsize=None)
def _load_json_cached(path: str, mtime: float, required_keys: tuple[str, ...]) -> dict:
    if not os.path.exists(path):
        return _result(None, 'not_generated', 'File not generated yet.', path, mtime)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            obj = json.load(f)
    except Exception as exc:  # noqa: BLE001
        return _result(None, 'invalid', f'Parse error: {exc}', path, mtime)
    for key in required_keys:
        if key not in obj:
            return _result(None, 'invalid', f'Missing field: {key}', path, mtime)
    return _result(obj, 'ok', '', path, mtime)


def _load_json(path: Path, required_keys: tuple[str, ...]) -> dict:
    path_str = str(path)
    mtime = os.path.getmtime(path_str) if os.path.exists(path_str) else 0.0
    return _load_json_cached(path_str, mtime, required_keys)


# ----------------------------------------------------------------------------
# Public Phase-1 loaders
# ----------------------------------------------------------------------------
def load_schedule() -> dict:
    return _load_csv(
        _PROCESSED / 'schedule.csv',
        required_columns=(
            'trip_id', 'rake_id', 'direction',
            'first_stop', 'last_stop', 'departure', 'arrival',
        ),
    )


def load_solution() -> dict:
    return _load_json(
        _PROCESSED / 'solution.json',
        required_keys=('status', 'objective', 'gap_pct'),
    )


def load_validation() -> dict:
    return _load_json(
        _PROCESSED / 'validation.json',
        required_keys=('checks',),
    )


def load_utilization_stats() -> dict:
    # Deliberately permissive: Phase 1 uses this opportunistically, so we only
    # require that the file parses as JSON. No key checks — a missing key here
    # must not stop the page.
    return _load_json(_PROCESSED / 'utilization_stats.json', required_keys=())