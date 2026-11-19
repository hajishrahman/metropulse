# components/ui_elements.py
"""Design-system primitives. Pages may NEVER choose a status color —
this module is the only place hex values for badges are selected.

FIX: status_badge now returns a ui.label styled with Tailwind arbitrary
hex classes, not a ui.badge. Quasar's .q-badge sets colour via class with
`!important`, which beats an inline style — so a ui.badge would render as
the default blue/white and OPTIMAL and FAIL would look identical.
ui.label with `bg-[#...] text-[#...]` classes is not fought by Quasar.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Callable, Iterator, Optional

from nicegui import ui

# STRICT status -> (bg, text) map. Keys are uppercased before lookup.
_STATUS_MAP: dict[str, tuple[str, str]] = {
    # Green is reserved for pass/optimal states.
    'OPTIMAL': ('#E8F5E9', '#1B7A43'),
    'PASS':    ('#E8F5E9', '#1B7A43'),
    'OK':      ('#E8F5E9', '#1B7A43'),
    # Neutral or restrained operational states.
    'FEASIBLE': ('#FFF8E1', '#8A6100'),
    'WARNING':  ('#FFF4E5', '#9A6700'),
    'PARTIAL':  ('#EFF6FF', '#475569'),
    # red
    'DROPPED':    ('#FFEBEE', '#B3261E'),
    'CANCELLED':  ('#FFEBEE', '#B3261E'),
    'FAIL':       ('#FFEBEE', '#B3261E'),
    'INVALID':    ('#FFEBEE', '#B3261E'),
    # grey
    'DEFERRED':      ('#F5F5F5', '#5C5C5C'),
    'INACTIVE':      ('#F5F5F5', '#5C5C5C'),
    'NOT GENERATED': ('#F5F5F5', '#5C5C5C'),
}
_UNKNOWN = ('#F5F5F5', '#5C5C5C')

_CARD_CLASSES = (
    'w-full min-w-0 bg-white border border-[#E2E8F0] rounded-[6px] p-4 mb-4'
)


def status_badge(text: str) -> ui.label:
    """Return a label styled as a badge with the design-system colour.

    Unknown statuses fall back to neutral grey and display the raw text —
    colour is never guessed.
    """
    raw = '' if text is None else str(text)
    key = raw.strip().upper()
    bg, fg = _STATUS_MAP.get(key, _UNKNOWN)
    return (
        ui.label(raw or 'UNKNOWN')
        .classes(
            f'bg-[{bg}] text-[{fg}] rounded-[6px] px-2 py-1 '
            f'text-[11px] leading-5 font-medium'
        )
    )


def scenario_tag(text: str) -> ui.label:
    return (
        ui.label(text.upper())
        .classes(
            'bg-[#F1F5F9] text-[#475569] border border-[#E2E8F0] rounded-[6px] px-2 py-1 '
            'text-[11px] leading-5 font-medium'
        )
    )


def kpi_card(
    label: str,
    value: str,
    badge_status: Optional[str] = None,
    footnote: Optional[str] = None,
    warning: Optional[str] = None,
) -> ui.card:
    card = ui.card().classes(_CARD_CLASSES)
    with card:
        ui.label(label.upper()).classes(
            'text-[12px] leading-5 font-medium text-[#64748B]'
        )
        with ui.row().classes('items-center gap-2 mt-2'):
            ui.label(str(value)).classes(
                'text-[28px] leading-8 font-semibold text-[#1E293B]'
            ).style('font-variant-numeric: tabular-nums;')
            if badge_status is not None:
                status_badge(badge_status)
        if footnote:
            ui.label(footnote).classes('text-[11px] leading-5 text-[#64748B] mt-1')
        if warning:
            ui.label(warning).classes(
                'bg-[#FFF8E1] text-[#8A6100] rounded-[6px] '
                'px-2 py-1 text-[11px] leading-5 mt-1'
            )
    return card


@contextmanager
def analytics_card(
    title: str,
    category: Optional[str] = None,
    header_content: Optional[Callable[[], None]] = None,
) -> Iterator[ui.card]:
    """Card with title (+ optional category). Use with `with`.

    FIX: content_builder removed. The page only ever used the `with` form;
    a @contextmanager that also accepted a builder was dead code that would
    silently render nothing if called the obvious way (i.e. without `with`).
    """
    card = ui.card().classes(_CARD_CLASSES)
    with card:
        with ui.row().classes('w-full items-center justify-between mb-4'):
            ui.label(title).classes('text-[16px] leading-5 font-semibold text-[#1E293B]')
            if header_content:
                header_content()
            elif category:
                ui.label(category.upper()).classes(
                    'text-[11px] leading-5 font-medium text-[#64748B]'
                )
        yield card


def provenance_footer(path: str, mtime: float) -> None:
    stamp = 'missing' if not mtime else f'{mtime:.0f}'
    ui.label(f'Source: {path} · mtime {stamp}').classes(
        'text-[12px] leading-5 text-[#64748B]'
    )


def state_card(status: str, filename: str, message: str) -> ui.card:
    card = ui.card().classes(_CARD_CLASSES)
    with card:
        with ui.row().classes('items-center gap-3'):
            status_badge(status)
            ui.label(filename).classes('text-[14px] font-semibold text-[#111111]')
        ui.label(message or status.replace('_', ' ').title()).classes(
            'text-[13px] leading-5 text-[#64748B] mt-2'
        )
    return card
