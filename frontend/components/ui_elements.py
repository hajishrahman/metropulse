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

from components import tokens

def status_badge(text: str) -> ui.label:
    """Return a label styled as a badge with the design-system colour.

    Unknown statuses fall back to neutral grey and display the raw text —
    colour is never guessed.
    """
    raw = '' if text is None else str(text)
    key = raw.strip().upper()
    return (
        ui.label(raw or 'UNKNOWN')
        .classes(tokens.STATUS_BADGE_CLASSES.get(key, tokens.BADGE_NEUTRAL))
    )


def scenario_tag(text: str) -> ui.label:
    return (
        ui.label(text.upper())
        .classes(tokens.SCENARIO_TAG)
    )


def kpi_card(
    label: str,
    value: str,
    badge_status: Optional[str] = None,
    footnote: Optional[str] = None,
    warning: Optional[str] = None,
) -> ui.card:
    card = ui.card().classes(tokens.CARD_PANEL)
    with card:
        ui.label(label.upper()).classes(
            tokens.TW_TEXT_12PX_LEADING_5_FONT_147900
        )
        with ui.row().classes(tokens.TW_ITEMS_CENTER_GAP_2_MT_9F4AAA):
            ui.label(str(value)).classes(
                tokens.TW_TEXT_28PX_LEADING_8_FONT_7CC1E3
            ).style('font-variant-numeric: tabular-nums;')
            if badge_status is not None:
                status_badge(badge_status)
        if footnote:
            ui.label(footnote).classes(tokens.TW_TEXT_11PX_LEADING_5_TEXT_21AFE4)
        if warning:
            ui.label(warning).classes(
                tokens.TW_BG_FFFBEB_TEXT_B45309_ROUNDED_9DBC2C
            )
    return card


def kpi_strip(
    columns: int,
    items: list[tuple],
    classes: str = tokens.KPI_STRIP,
    flat: bool = False,
    container=None,
) -> None:
    grid = container if container is not None else ui.grid(columns=columns).classes(classes)
    with grid:
        for args, kwargs in items:
            card = kpi_card(*args, **kwargs)
            if flat:
                card.props('flat').classes(tokens.TW_SHADOW_NONE_AD47D1)


def plotly_gridlines(fig, color: str = tokens.BORDER):
    fig.update_xaxes(gridcolor=color, gridwidth=1, zeroline=False)
    fig.update_yaxes(gridcolor=color, gridwidth=1, zeroline=False)
    return fig


def plotly_base_layout(fig, **layout):
    layout.setdefault('plot_bgcolor', tokens.PANEL)
    layout.setdefault('paper_bgcolor', tokens.PANEL)
    fig.update_layout(**layout)
    return fig


def plotly_hovertemplate(*lines: str) -> str:
    return '<br>'.join(lines) + '<extra></extra>'


def data_grid(data, columns: list[str]) -> ui.element:
    return ui.aggrid.from_pandas(data, options={
        'columnDefs': [
            {'field': col, 'minWidth': 128 if col == 'trip_category' else 96}
            for col in columns
        ],
        'defaultColDef': {'flex': 1},
    }).classes(tokens.PLOTLY_CONTAINER)


def page_content(container) -> None:
    container.classes(tokens.PAGE_CONTENT)


def plotly_chart(fig, classes: str = tokens.PLOTLY_CONTAINER):
    return ui.plotly(fig).classes(classes)


def validation_accordion(checks: list[dict]) -> None:
    for check in checks:
        label = check['check'].replace('_', ' ').title().replace(' ', ' — ', 1)
        expansion = ui.expansion('', value=False).classes(tokens.TW_W_FULL_6DA6A3)
        with expansion.add_slot('header'):
            with ui.row().classes(tokens.TW_W_FULL_ITEMS_CENTER_JUSTIFY_A0250D):
                ui.label(label).classes(tokens.TW_TEXT_14PX_FONT_MEDIUM_TEXT_D551FB)
                with ui.row().classes(tokens.TW_ITEMS_CENTER_GAP_2_145735):
                    status_badge(check['status'])
                    ui.icon('expand_more').classes(tokens.TW_TEXT_64748B_B562FF)
        with expansion:
            for key, value in check['details'].items():
                if isinstance(value, list) and value:
                    ui.label(f'{key}:').classes(tokens.TW_TEXT_13PX_LEADING_5_FONT_115083)
                    for item in value:
                        ui.label(f'  • {item}').classes(tokens.TW_TEXT_13PX_LEADING_5_0E02BC)
                elif isinstance(value, list):
                    ui.label(f'{key}: (none)').classes(tokens.TW_TEXT_13PX_LEADING_5_0E02BC)
                else:
                    ui.label(f'{key}: {value}').classes(tokens.TW_TEXT_13PX_LEADING_5_0E02BC)


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
    card = ui.card().classes(tokens.CARD_PANEL)
    with card:
        with ui.row().classes(tokens.TW_W_FULL_ITEMS_CENTER_JUSTIFY_BDEEFE):
            ui.label(title).classes(tokens.TW_TEXT_16PX_LEADING_5_FONT_50EC06)
            if header_content:
                header_content()
            elif category:
                ui.label(category.upper()).classes(
                    tokens.TW_TEXT_11PX_LEADING_5_FONT_5FAE9F
                )
        yield card


def provenance_footer(path: str, mtime: float) -> None:
    stamp = 'missing' if not mtime else f'{mtime:.0f}'
    ui.label(f'Source: {path} · mtime {stamp}').classes(
        tokens.TW_TEXT_12PX_LEADING_5_TEXT_0F6875
    )


def state_card(status: str, filename: str, message: str) -> ui.card:
    card = ui.card().classes(tokens.CARD_PANEL)
    with card:
        with ui.row().classes(tokens.TW_ITEMS_CENTER_GAP_3_A8B1B5):
            status_badge(status)
            ui.label(filename).classes(tokens.TW_TEXT_14PX_FONT_SEMIBOLD_TEXT_C1D1CD)
        ui.label(message or status.replace('_', ' ').title()).classes(
            tokens.TW_TEXT_13PX_LEADING_5_TEXT_BB5519
        )
    return card
