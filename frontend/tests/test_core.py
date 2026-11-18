# tests/test_core.py
"""Spec-rule tests. No file I/O, no framework imports.
Run: python tests/test_core.py   (or: pytest -q)
"""
import sys
from pathlib import Path

# Make `from components...` and `from pages...` resolve when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from components.time_utils import hhmmss_to_sec, sec_to_hhmmss
from components.trip_category import derive_trip_category


def test_hhmmss_post_midnight():
    assert hhmmss_to_sec('24:03:45') == 86625


def test_sec_to_hhmmss_post_midnight():
    assert sec_to_hhmmss(86625) == '24:03:45'


def test_hhmmss_gantt_bounds():
    assert hhmmss_to_sec('04:40:00') == 16800
    assert hhmmss_to_sec('24:30:00') == 88200


def test_category_positioning():
    row = {'trip_id': 'WK_4', 'first_stop': 'X', 'last_stop': 'Y'}
    assert derive_trip_category(row) == 'positioning'


def test_category_full_route():
    row = {'trip_id': 'WK_1', 'first_stop': 'ALVA', 'last_stop': 'TPHT'}
    assert derive_trip_category(row) == 'full_route'


def test_category_partial():
    row = {'trip_id': 'WK_2', 'first_stop': 'KVTR', 'last_stop': 'ALVA'}
    assert derive_trip_category(row) == 'partial'


def test_category_positioning_beats_full_route():
    row = {'trip_id': 'WK_4', 'first_stop': 'ALVA', 'last_stop': 'TPHT'}
    assert derive_trip_category(row) == 'positioning'


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in tests:
        t()
        print(f'PASS {t.__name__}')
    print(f'\n{len(tests)} passed')