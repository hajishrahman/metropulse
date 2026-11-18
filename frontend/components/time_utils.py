# components/time_utils.py
"""Integer-only time handling. Rule 3: never datetime.strptime / dateutil.

Hours do not wrap at 24 — the solver emits post-midnight arrivals like
"24:03:45", which must map to 86625 seconds.
"""
##Z:\metropulse\frontend\components\time_utils.py##
from __future__ import annotations

IST_LABEL = 'IST (Asia/Kolkata)'


def hhmmss_to_sec(s: str) -> int:
    """'24:03:45' -> 86625. No wrap, no exception on >24h."""
    if s is None:
        raise ValueError('hhmmss_to_sec received None')
    parts = str(s).strip().split(':')
    if len(parts) != 3:
        raise ValueError(f'Expected HH:MM:SS, got {s!r}')
    h, m, sec = (int(p) for p in parts)
    if m < 0 or m >= 60 or sec < 0 or sec >= 60 or h < 0:
        raise ValueError(f'Out-of-range component in {s!r}')
    return h * 3600 + m * 60 + sec


def sec_to_hhmmss(n: int) -> str:
    """86625 -> '24:03:45'. Hours do not wrap."""
    n = int(n)
    if n < 0:
        raise ValueError(f'Negative time: {n}')
    h, rem = divmod(n, 3600)
    m, s = divmod(rem, 60)
    return f'{h:02d}:{m:02d}:{s:02d}'


def format_time(s: str) -> str:
    """Pretty HH:MM for display; tolerates bad input gracefully."""
    try:
        sec = hhmmss_to_sec(s)
    except (ValueError, TypeError):
        return str(s)
    h, rem = divmod(sec, 3600)
    m, _ = divmod(rem, 60)
    return f'{h:02d}:{m:02d}'