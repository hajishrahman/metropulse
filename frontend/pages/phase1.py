# pages/phase1.py
# Written against NiceGUI 4.x. Uses ui.plotly, ui.aggrid.from_pandas,
# ui.expansion, ui.add_head_html — all present in 4.x.

from __future__ import annotations

import math

import plotly.graph_objects as go
from nicegui import ui

from components.trip_category import derive_trip_category
from components.ui_elements import (
    analytics_card,
    kpi_card,
    provenance_footer,
    scenario_tag,
    state_card,
    status_badge,
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
    'full_route':   dict(color="#1E3A5F", dash='solid', label='Full route'),
    'partial':      dict(color="#0D9488", dash='dash',  label='Partial'),
    'positioning':  dict(color="#94A3B8", dash='dot',   label='Positioning'),
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
            hovertemplate=(
                '<b>%{customdata[0]}</b><br>'
                'Rake: %{customdata[1]}<br>'
                '%{customdata[2]} → %{customdata[3]}<br>'
                '%{customdata[4]}–%{customdata[5]}<br>'
                'Trip category: %{customdata[6]}'
                '<extra></extra>'
            ),
        ))

    tick_secs = list(range(5 * 3600, 25 * 3600 + 1, 2 * 3600))
    fig.update_layout(
        showlegend=False,
        xaxis=dict(
            tickvals=tick_secs,
            ticktext=[sec_to_hhmmss(s)[:5] for s in tick_secs],
            tick0=5 * 3600,
            dtick=2 * 3600,
            title='Time (IST)',
            gridcolor='#E2E8F0',
            gridwidth=1,
            zeroline=False,
        ),
        yaxis=dict(
            tickvals=list(rake_y.values()),
            ticktext=list(rake_y.keys()),
            title='Rake',
            range=[len(rake_y) - 0.5, -0.5],
            tick0=0,
            dtick=1,
            gridcolor='#E2E8F0',
            gridwidth=1,
            zeroline=False,
        ),
        margin=dict(l=60, r=20, t=20, b=40),
        plot_bgcolor='white',
        paper_bgcolor='white',
    )
    return fig


def _natural_key(value):
    import re
    s = str(value)
    return tuple(int(p) if p.isdigit() else p
                 for p in re.split(r'(\d+)', s) if p != '')

def _render_gantt_legend() -> None:
    with ui.row().classes('items-center gap-4'):
        for label, color in (('Full route', '#1E3A5F'),
                             ('Partial', '#0D9488'),
                             ('Positioning', '#94A3B8')):
            with ui.row().classes('items-center gap-2'):
                ui.element('span').classes('inline-block w-3 h-3 rounded-full').style(
                    f'background-color: {color}')
                ui.label(label).classes('text-[12px] text-[#6B6B6B]')


def _render_validation(v: dict) -> None:
    for check in v['checks']:
        label = check['check'].replace('_', ' ').title().replace(' ', ' — ', 1)
        expansion = ui.expansion('', value=False).classes('w-full')
        with expansion.add_slot('header'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label(label).classes('text-[14px] font-medium text-[#111111]')
                with ui.row().classes('items-center gap-2'):
                    status_badge(check['status'])
                    ui.icon('expand_more').classes('text-[#6B6B6B]')
        with expansion:
            for k, val in check['details'].items():
                if isinstance(val, list) and val:
                    ui.label(f'{k}:').classes('text-[13px] leading-5 font-medium')
                    for item in val:
                        ui.label(f'  • {item}').classes('text-[13px] leading-5')
                elif isinstance(val, list):
                    ui.label(f'{k}: (none)').classes('text-[13px] leading-5')
                else:
                    ui.label(f'{k}: {val}').classes('text-[13px] leading-5')


def _render_limitations() -> None:
    with ui.expansion('Limitations & methodology').classes('w-full'):
        ui.markdown(
            '- **Objective 900.0 is rake-balance deviation**, not an '
            'optimisation "score".\n'
            f'- **UP/DOWN caveat:** {_UP_DOWN_CAVEAT}\n'
            '- **Positioning trips:** WK_4, WK_256, WK_18, WK_12, WK_253.\n'
            '- **Post-midnight arrivals** (e.g. 24:03:45) are kept in '
            'extended HH:MM:SS form; hours do not wrap at 24.\n'
            f'- **Timezone:** All times in {IST_LABEL}. No UTC conversion applied.\n'
            '- FEASIBLE is never shown as OPTIMAL.\n'
            '- Schedule and validation values are observed; they are not stated as proven.'
        )



 
def render() -> None:
    from components.navigation import create_sidebar
    main = create_sidebar(active_phase='phase1')
    main.classes('p-6')

    with main:
        with ui.row().classes('w-full items-center justify-between mb-4'):
            with ui.column().classes('gap-2'):
                ui.label('Phase 1 — Train Scheduling').classes('text-[24px] leading-7 font-semibold text-[#1E293B]')
                ui.label('Frozen backend output · read-only dashboard').classes('text-[14px] leading-5 text-[#64748B]')
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

        with ui.grid(columns=4).classes('w-full gap-4'):
            w = None
            if n_trips != EXPECTED_TRIPS:
                w = f'Expected {EXPECTED_TRIPS}, found {n_trips}.'
            if n_positioning != EXPECTED_POSITIONING:
                extra = f'Positioning: expected {EXPECTED_POSITIONING}, found {n_positioning}.'
                w = f'{w} {extra}' if w else extra
            kpi_card('Trips', str(n_trips),
                     footnote=f'{n_full} full-route + {n_partial} partial '
                              f'(incl. {n_positioning} positioning)',
                     warning=w)

            rw = f'Expected {EXPECTED_RAKES}, found {n_rakes}.' if n_rakes != EXPECTED_RAKES else None
            kpi_card('Rakes', str(n_rakes),
                     footnote=f'{rakes[0]}–{rakes[-1]}' if rakes else None,
                     warning=rw)

            sv = sol['status']
            kpi_card('Status', sv, badge_status=sv,
                     footnote='Under configured objective (O6) only',
                     warning=f'Expected {EXPECTED_STATUS}, found {sv}.' if sv != EXPECTED_STATUS else None)

            obj = float(sol['objective'])
            gap = float(sol['gap_pct'])
            ow = None if math.isclose(obj, EXPECTED_OBJECTIVE, abs_tol=0.01) \
                 else f'Expected {EXPECTED_OBJECTIVE}, found {obj}.'
            fn = f'rake-balance deviation, not a score. Gap {gap:.1f}%'
            if not math.isclose(gap, EXPECTED_GAP_PCT, abs_tol=0.01):
                fn += f' — gap drifted: expected {EXPECTED_GAP_PCT}, found {gap}'
            kpi_card('Objective', f'{obj:.1f}', footnote=fn, warning=ow)

        with analytics_card('Rake Schedule (Gantt)', header_content=_render_gantt_legend):
            ui.plotly(_gantt_figure(df)).classes('w-full h-[620px]')

        cols = ['trip_id', 'rake_id', 'direction', 'first_stop',
                'last_stop', 'departure', 'arrival', 'trip_category']
        with ui.element('div').classes('w-full grid grid-cols-1 lg:grid-cols-12 gap-4 items-start'):
            with analytics_card('Schedule', category='frozen') as card:
                card.classes('lg:col-span-8 min-w-0')
                ui.aggrid.from_pandas(
                    df[cols], options={
                        'columnDefs': [
                            {'field': col, 'minWidth': 128 if col == 'trip_category' else 96}
                            for col in cols
                        ],
                        'defaultColDef': {'flex': 1},
                    }
                ).classes('w-full min-w-0')

            with analytics_card('Validation Checks', category='frozen') as card:
                card.classes('lg:col-span-4 min-w-0')
                _render_validation(val)

        _render_limitations()
        with ui.row().classes('w-full flex-wrap gap-x-4 gap-y-2 mt-4'):
            for res in (schedule, solution, validation):
                provenance_footer(res['path'], res['mtime'])
