# pages/phase1.py
# Written against NiceGUI 4.x. Uses ui.plotly, ui.aggrid.from_pandas,
# ui.expansion, ui.add_head_html — all present in 4.x.

from __future__ import annotations

import math

import plotly.graph_objects as go
from nicegui import ui

from components import tokens

from components.trip_category import derive_trip_category
from components.ui_elements import (
    analytics_card,
    data_grid,
    kpi_strip,
    page_content,
    plotly_chart,
    plotly_base_layout,
    plotly_hovertemplate,
    provenance_footer,
    scenario_tag,
    state_card,
    validation_accordion,
)
from components.time_utils import IST_LABEL, hhmmss_to_sec, sec_to_hhmmss
from data.registry import load_schedule, load_solution, load_validation

# EXPECTED VALUES — DRIFT DETECTION ONLY. Never displayed as KPI values.
EXPECTED_TRIPS = 255
EXPECTED_RAKES = 18
EXPECTED_POSITIONING = 5
EXPECTED_STATUS = 'OPTIMAL'
EXPECTED_OBJECTIVE = 900.0
EXPECTED_GAP_PCT = 0.0

_TRACE_STYLE = {
    'full_route':   dict(color=tokens.NAVY, dash='solid', label='Full route'),
    'partial':      dict(color=tokens.BLUE, dash='dash',  label='Partial'),
    'positioning':  dict(color=tokens.COOL_GREY, dash='dot',   label='Positioning'),
}

# Exact sentence from the spec's clarification. Do not paraphrase.
_UP_DOWN_CAVEAT = (
    'UP/DOWN direction is determined by station-index comparison, not by a '
    'fixed terminal-to-terminal definition. A trip labeled UP means its last '
    'station index is greater than its first station index (ALVA=0 … TPHT=24). '
    'Partial trips can carry an unexpected direction label: KVTR→ALVA is '
    'labeled UP because KVTR (index 17) > ALVA (index 0), even though it is '
    'traveling toward the Aluva terminal. Do not interpret UP as "toward '
    'TPHT" or DOWN as "toward ALVA."'
)


def _derive_categories(df):
    return df.assign(trip_category=df.apply(derive_trip_category, axis=1))


def _validate_schedule(df) -> str | None:
    for _, row in df.iterrows():
        tid = row['trip_id']
        for col in ('departure', 'arrival'):
            raw = row[col]
            if raw is None or (isinstance(raw, float) and math.isnan(raw)) or raw == '':
                return f'Empty value in {col} at trip {tid}'
            try:
                hhmmss_to_sec(raw)
            except (ValueError, TypeError):
                return f'Bad value in {col} at trip {tid}: {raw!r}'
        if hhmmss_to_sec(row['arrival']) <= hhmmss_to_sec(row['departure']):
            return (f'Arrival not after departure at trip {tid}: '
                    f'{row["departure"]} -> {row["arrival"]}')
    return None


def _validate_solution(solution: dict) -> str | None:
    for field in ('objective', 'gap_pct'):
        val = solution.get(field)
        if val is None:
            return f'Null value in field: {field}'
        try:
            float(val)
        except (TypeError, ValueError):
            return f'Non-numeric value in field: {field} ({val!r})'
    if not isinstance(solution.get('status'), str) or not solution['status'].strip():
        return 'Missing or empty field: status'
    return None


def _validate_validation(v: dict) -> str | None:
    checks = v.get('checks')
    if not isinstance(checks, list):
        return 'Field "checks" is not a list'
    for i, c in enumerate(checks):
        if not isinstance(c, dict):
            return f'checks[{i}] is not an object'
        for key in ('check', 'status', 'details'):
            if key not in c:
                return f'checks[{i}] missing field: {key}'
        if not isinstance(c['details'], dict):
            return f'checks[{i}].details is not an object'
    return None


def _gantt_figure(df) -> go.Figure:
    rakes = sorted(df['rake_id'].unique(), key=lambda r: _natural_key(r))
    rake_y = {r: i for i, r in enumerate(rakes)}

    fig = go.Figure()
    for cat, style in _TRACE_STYLE.items():
        sub = df[df['trip_category'] == cat]
        if sub.empty:
            fig.add_trace(go.Scatter(
                x=[], y=[], mode='lines', name=style['label'],
                line=dict(color=style['color'], dash=style['dash'], width=10),
                hoverinfo='skip',
            ))
            continue
        xs, ys, cd = [], [], []
        for _, row in sub.iterrows():
            dep = hhmmss_to_sec(row['departure'])
            arr = hhmmss_to_sec(row['arrival'])
            y = rake_y[row['rake_id']]
            xs.extend([dep, arr, None])
            ys.extend([y, y, None])
            pair = (
                row['trip_id'], row['rake_id'], row['first_stop'],
                row['last_stop'], row['departure'], row['arrival'],
                row['trip_category'],
            )
            cd.extend([pair, pair, None])
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode='lines', name=style['label'],
            line=dict(color=style['color'], dash=style['dash'], width=10),
            customdata=cd,
            hovertemplate=plotly_hovertemplate(
                '<b>%{customdata[0]}</b>', 'Rake: %{customdata[1]}',
                '%{customdata[2]} → %{customdata[3]}',
                '%{customdata[4]}–%{customdata[5]}',
                'Trip category: %{customdata[6]}',
            ),
        ))

    tick_secs = list(range(5 * 3600, 25 * 3600 + 1, 2 * 3600))
    plotly_base_layout(fig,
        showlegend=False,
        xaxis=dict(
            tickvals=tick_secs,
            ticktext=[sec_to_hhmmss(s)[:5] for s in tick_secs],
            tick0=5 * 3600,
            dtick=2 * 3600,
            title='Time (IST)',
            gridcolor=tokens.BORDER, gridwidth=1,
            zeroline=False,
        ),
        yaxis=dict(
            tickvals=list(rake_y.values()),
            ticktext=list(rake_y.keys()),
            title='Rake',
            range=[len(rake_y) - 0.5, -0.5],
            tick0=0,
            dtick=1,
            gridcolor=tokens.BORDER, gridwidth=1,
            zeroline=False,
        ),
        margin=dict(l=60, r=20, t=20, b=40),
    )
    return fig


def _natural_key(value):
    import re
    s = str(value)
    return tuple(int(p) if p.isdigit() else p
                 for p in re.split(r'(\d+)', s) if p != '')

def _render_gantt_legend() -> None:
    with ui.row().classes(tokens.TW_ITEMS_CENTER_GAP_4_45A68C):
        for label, color in (('Full route', tokens.NAVY),
                             ('Partial', tokens.BLUE),
                             ('Positioning', tokens.COOL_GREY)):
            with ui.row().classes(tokens.TW_ITEMS_CENTER_GAP_2_145735):
                ui.element('span').classes(tokens.TW_INLINE_BLOCK_W_3_H_12A685).style(
                    f'background-color: {color}')
                ui.label(label).classes(tokens.TW_TEXT_12PX_TEXT_64748B_C9195F)


def _render_limitations() -> None:
    with ui.expansion('Limitations & methodology').classes(tokens.TW_W_FULL_6DA6A3):
        ui.markdown(
            '- **Objective 900.0 is rake-balance deviation**, not an '
            'optimisation "score".\n'
            f'- **UP/DOWN caveat:** {_UP_DOWN_CAVEAT}\n'
            '- **Positioning trips:** WK_4, WK_256, WK_18, WK_12, WK_253.\n'
            '- **Post-midnight arrivals** (e.g. 24:03:45) are kept in '
            'extended HH:MM:SS form; hours do not wrap at 24.\n'
            f'- **Timezone:** All times in {IST_LABEL}. No UTC conversion applied.\n'
            '- FEASIBLE is never shown as OPTIMAL.\n'
            '- Schedule and validation values are observed outputs.'
        )



 
def render() -> None:
    from components.navigation import create_sidebar
    main = create_sidebar(active_phase='phase1')
    page_content(main)

    with main:
        with ui.row().classes(tokens.TW_W_FULL_ITEMS_CENTER_JUSTIFY_BDEEFE):
            with ui.column().classes(tokens.TW_GAP_2_77A2A2):
                ui.label('Train Scheduling').classes(tokens.TW_TEXT_24PX_LEADING_7_FONT_C8DEAA)
                ui.label('Frozen backend output · read-only dashboard').classes(tokens.TW_TEXT_14PX_LEADING_5_TEXT_69208B)
            scenario_tag('FROZEN OUTPUT')

        schedule = load_schedule()
        solution = load_solution()
        validation = load_validation()

        for name, res in (('schedule.csv', schedule),
                          ('solution.json', solution),
                          ('validation.json', validation)):
            if res['status'] != 'ok':
                state_card(res['status'].replace('_', ' ').upper(), name, res['message'])
                provenance_footer(res['path'], res['mtime'])
                return

        df = schedule['data']
        sol = solution['data']
        val = validation['data']

        for bad, name, path, mtime in (
            (_validate_schedule(df), 'schedule.csv', schedule['path'], schedule['mtime']),
            (_validate_solution(sol), 'solution.json', solution['path'], solution['mtime']),
            (_validate_validation(val), 'validation.json', validation['path'], validation['mtime']),
        ):
            if bad:
                state_card('INVALID', name, bad)
                provenance_footer(path, mtime)
                return

        df = _derive_categories(df)
        n_full = int((df['trip_category'] == 'full_route').sum())
        n_partial = int((df['trip_category'] == 'partial').sum())
        n_positioning = int((df['trip_category'] == 'positioning').sum())
        n_trips = len(df)
        n_rakes = int(df['rake_id'].nunique())
        rakes = sorted(df['rake_id'].unique(), key=_natural_key)

        w = None
        if n_trips != EXPECTED_TRIPS:
            w = f'Expected {EXPECTED_TRIPS}, found {n_trips}.'
        if n_positioning != EXPECTED_POSITIONING:
            extra = f'Positioning: expected {EXPECTED_POSITIONING}, found {n_positioning}.'
            w = f'{w} {extra}' if w else extra
        rw = f'Expected {EXPECTED_RAKES}, found {n_rakes}.' if n_rakes != EXPECTED_RAKES else None
        sv = sol['status']
        obj = float(sol['objective'])
        gap = float(sol['gap_pct'])
        ow = None if math.isclose(obj, EXPECTED_OBJECTIVE, abs_tol=0.01) \
             else f'Expected {EXPECTED_OBJECTIVE}, found {obj}.'
        fn = f'rake-balance deviation, not a score. Gap {gap:.1f}%'
        if not math.isclose(gap, EXPECTED_GAP_PCT, abs_tol=0.01):
            fn += f' — gap drifted: expected {EXPECTED_GAP_PCT}, found {gap}'
        kpi_strip(4, [
            (('Trips', str(n_trips)), {'footnote': f'{n_full} full-route + {n_partial} partial (incl. {n_positioning} positioning)', 'warning': w}),
            (('Rakes', str(n_rakes)), {'footnote': f'{rakes[0]}–{rakes[-1]}' if rakes else None, 'warning': rw}),
            (('Status', sv), {'badge_status': sv, 'warning': f'Expected {EXPECTED_STATUS}, found {sv}.' if sv != EXPECTED_STATUS else None}),
            (('Objective', f'{obj:.1f}'), {'footnote': fn, 'warning': ow}),
        ])

        with analytics_card('Rake Schedule (Gantt)', header_content=_render_gantt_legend):
            plotly_chart(_gantt_figure(df), tokens.PLOTLY_H_620)

        cols = ['trip_id', 'rake_id', 'direction', 'first_stop',
                'last_stop', 'departure', 'arrival', 'trip_category']
        with ui.element('div').classes(tokens.TW_W_FULL_GRID_GRID_COLS_0EADA3 + ' items-stretch'):
            with analytics_card('Schedule', category='frozen') as card:
                card.classes(tokens.TW_LG_COL_SPAN_8_MIN_6AEAD7 + ' h-full flex flex-col')
                with ui.column().classes('flex-1 min-h-0 w-full'):
                    data_grid(df[cols], cols)

            with analytics_card('Validation Checks', category='frozen') as card:
                card.classes(tokens.TW_LG_COL_SPAN_4_MIN_D5150C + ' h-full flex flex-col')
                validation_accordion(val['checks'])

        _render_limitations()
        with ui.row().classes(tokens.TW_W_FULL_FLEX_WRAP_GAP_BB092F):
            for res in (schedule, solution, validation):
                provenance_footer(res['path'], res['mtime'])
