# components/trip_category.py
"""Pure trip-classification logic. No NiceGUI, no plotly, no file I/O.
Extracted from phase1.py so tests/test_core.py can import it without
pulling in the framework."""

from __future__ import annotations

POSITIONING_TRIPS = {'WK_4', 'WK_256', 'WK_18', 'WK_12', 'WK_253'}
FULL_ROUTE_PAIRS = {('ALVA', 'TPHT'), ('TPHT', 'ALVA')}


def derive_trip_category(row) -> str:
    """Positioning wins over full_route over partial.

    `row` is any mapping-like object with trip_id / first_stop / last_stop
    (a pandas Series, a dict, a namedtuple — anything subscriptable).
    """
    if row['trip_id'] in POSITIONING_TRIPS:
        return 'positioning'
    if (row['first_stop'], row['last_stop']) in FULL_ROUTE_PAIRS:
        return 'full_route'
    return 'partial'