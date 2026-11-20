# pages/phase3.py
# Phase 3 - Crew Scheduling (CP-SAT)

from __future__ import annotations

import plotly.graph_objects as go
from nicegui import ui

from components import tokens

from components.ui_elements import analytics_card, kpi_strip, page_content, plotly_chart, plotly_gridlines, scenario_tag, state_card, status_badge
from components.time_utils import sec_to_hhmmss, hhmmss_to_sec

ui.add_head_html(
    '<style>' + tokens.TAB_ACTIVE_STYLE +
    '.q-tab--active { background-color: transparent !important; color: ' + tokens.NAVY + ' !important; }'
    '.q-tab--active .q-tab__label { color: ' + tokens.NAVY + ' !important; }'
    '.q-tab__indicator { height: 3px !important; background-color: ' + tokens.NAVY + ' !important; }'
    '</style>',
    shared=True,
)

from data.registry import (
    load_crew_schedule,
    load_crew_solution,
    load_crew_validation,
    load_drivers,
    load_schedule,
)

_TRIPS_COLOR = tokens.NAVY
_BUFFER_FILL = tokens.BORDER_STRONG
_BUFFER_BORDER = tokens.COOL_GREY


def _reserve_ids(pool: str, drivers_df, crew_df) -> list[str]:
    """Reserve = first N driver_ids minus active drivers in this pool."""
    n = int(pool)
    pool_drivers = drivers_df['driver_id'].tolist()[:n]
    active = set(crew_df[crew_df['pool_size'] == n]['driver_id'].unique())
    return [d for d in pool_drivers if d not in active]


def _build_fleet_gantt(driver_list, pool: str, crew_df, sched_df) -> tuple[go.Figure, int]:
    """Fleet row chart: one row per driver, sign-on | trips | sign-off.
    Returns (fig, number_of_rows)."""
    n = int(pool)
    pool_crew = crew_df[crew_df['pool_size'] == n]
    sched_lookup = sched_df.set_index('trip_id')[['rake_id', 'departure', 'arrival', 'first_stop', 'last_stop']]

    pool_trip_ids = pool_crew['trip_id'].unique()
    pool_schedule = sched_lookup.loc[sched_lookup.index.isin(pool_trip_ids)]
    observed_times = (
        [hhmmss_to_sec(value) for value in pool_crew['sign_on'].tolist() + pool_crew['sign_off'].tolist()]
        + [hhmmss_to_sec(value) for value in pool_schedule['departure'].tolist() + pool_schedule['arrival'].tolist()]
    )
    X_MIN = (min(observed_times) // 7200) * 7200
    X_MAX = ((max(observed_times) + 7199) // 7200) * 7200
    tick_secs = list(range(X_MIN, X_MAX + 1, 7200))

    fig = go.Figure()
    n_rows = len(driver_list)

    for i, did in enumerate(driver_list):
        y = n_rows - 1 - i  # top driver first
        rows = pool_crew[pool_crew['driver_id'] == did]

        if rows.empty:
            # Reserve row - dashed track
            fig.add_trace(go.Scatter(
                x=[X_MIN, X_MAX], y=[y, y], mode='lines',
                line=dict(color=tokens.TEXT_SECONDARY, width=2.5, dash='dash'),
                showlegend=False,
                hovertemplate=f"{did} - Reserve / Standby<extra></extra>",
            ))
            continue

        sign_on_sec = hhmmss_to_sec(rows['sign_on'].iloc[0])
        sign_off_sec = hhmmss_to_sec(rows['sign_off'].iloc[0])

        merged = rows.merge(sched_lookup, on='trip_id', how='inner')
        merged['dep_sec'] = merged['departure'].apply(hhmmss_to_sec)
        merged['arr_sec'] = merged['arrival'].apply(hhmmss_to_sec)
        merged = merged.sort_values(['dep_sec', 'trip_id']).reset_index(drop=True)

        if merged.empty:
            fig.add_trace(go.Scatter(
                x=[X_MIN, X_MAX], y=[y, y], mode='lines',
                line=dict(color=tokens.TEXT_SECONDARY, width=2, dash='dash'),
                showlegend=False,
                hovertemplate=f"{did} - Reserve / Standby<extra></extra>",
            ))
            continue

        first_dep = int(merged['dep_sec'].iloc[0])
        last_arr = int(merged['arr_sec'].iloc[-1])
        shift_hover = (
            f"<b>{did}</b> - Pool {pool}<br>"
            f"Shift: {sec_to_hhmmss(sign_on_sec)} - {sec_to_hhmmss(sign_off_sec)}<extra></extra>"
        )
        trip_hover = (
            f"<b>{did}</b> - Pool {pool}<br>"
            f"Duty window: {sec_to_hhmmss(sign_on_sec)} - {sec_to_hhmmss(sign_off_sec)}<br>"
            f"Trip: %{{customdata[0]}}<br>Rake: %{{customdata[1]}}<br>"
            f"Trip time: %{{customdata[2]}} - %{{customdata[3]}}<extra></extra>"
        )

        # Sign-on buffer
        fig.add_trace(go.Scatter(
            x=[sign_on_sec, first_dep], y=[y, y], mode='lines',
            line=dict(color=_BUFFER_BORDER, width=20),
            showlegend=False, hovertemplate=shift_hover,
        ))
        # Trips
        for _, row in merged.iterrows():
            fig.add_trace(go.Scatter(
                x=[row['dep_sec'], row['arr_sec']], y=[y, y], mode='lines',
                customdata=[[row['trip_id'], row['rake_id'], sec_to_hhmmss(row['dep_sec']), sec_to_hhmmss(row['arr_sec'])]] * 2,
                line=dict(color=_TRIPS_COLOR, width=20),
                showlegend=False, hovertemplate=trip_hover,
            ))
        # Sign-off buffer
        fig.add_trace(go.Scatter(
            x=[last_arr, sign_off_sec], y=[y, y], mode='lines',
            line=dict(color=_BUFFER_BORDER, width=20),
            showlegend=False, hovertemplate=shift_hover,
        ))

    fig.update_layout(
        showlegend=False,
        height=max(320, n_rows * 36 + 100),
        font=dict(family=tokens.FONT_MONO, color=tokens.TEXT_SECONDARY),
        hoverlabel=dict(bgcolor=tokens.TEXT_PRIMARY, font=dict(color=tokens.WHITE, family=tokens.FONT_MONO)),
        xaxis=dict(
            tickvals=tick_secs,
            ticktext=[sec_to_hhmmss(s)[:5] for s in tick_secs],
            range=[X_MIN, X_MAX], automargin=True, dtick=7200,
            title='Time (IST)',
            gridcolor=tokens.BORDER,
            zeroline=False,
        ),
        yaxis=dict(
            tickvals=list(range(n_rows)), range=[-0.5, max(n_rows - 0.5, 0.5)], automargin=True,
            ticktext=list(reversed(driver_list)),
            gridcolor=tokens.BORDER,
            zeroline=False,
            tickfont=dict(size=10),
        ),
        margin=dict(l=100, r=10, t=10, b=40),
        plot_bgcolor=tokens.PANEL,
        paper_bgcolor=tokens.PANEL,
    )
    plotly_gridlines(fig, tokens.BORDER)
    return fig, n_rows

def _check_label(name: str) -> str:
    m = {
        'C1_no_overlap': 'C1 - No overlapping trips per driver',
        'C2_max_duty': 'C2 - Duty limit',
        'C3_sign_buffers': 'C3 - Sign-on / sign-off buffers correct',
        'C4_coverage': 'C4 - All trips covered',
        'C7_reserve': 'C7 - Reserve at least minimum',
    }
    return m.get(name, name)


def render():
    from components.navigation import create_sidebar
    main = create_sidebar(active_phase='phase3')
    page_content(main)

    sol_res = load_crew_solution()
    val_res = load_crew_validation()
    crew_res = load_crew_schedule()
    drv_res = load_drivers()
    sched_res = load_schedule()

    with main:
        for name, res in (
            ('crew_solution.json', sol_res),
            ('crew_validation.json', val_res),
            ('crew_schedule.csv', crew_res),
            ('drivers.csv', drv_res),
            ('schedule.csv', sched_res),
        ):
            if res['status'] != 'ok':
                state_card(res['status'].replace('_', ' ').upper(), name, res['message']).props('flat').classes(tokens.TW_SHADOW_NONE_AD47D1)
                return

        sol = sol_res['data']
        val = val_res['data']
        crew_df = crew_res['data']
        drivers_df = drv_res['data']
        sched_df = sched_res['data']

        # Header
        with ui.row().classes(tokens.TW_W_FULL_MIN_W_0_29D4FF):
            with ui.column().classes(tokens.TW_MIN_W_0_GAP_1_6364F0 + ' w-full'):
                ui.label('Crew Scheduling').classes(tokens.TW_TEXT_22PX_LEADING_7_FONT_4694EF)
                ui.label('CP-SAT optimized single-day crew rostering respecting duty limits and reserve buffers.').classes(
                    tokens.TW_TEXT_14PX_TEXT_181D1F_70_ED2ACD
                )
            solver_badge = ui.row().classes(tokens.TW_ITEMS_CENTER_3960FF)

        # Pool summary strip
        pool_summary = ui.row().classes(
            tokens.TW_W_FULL_MIN_W_0_2F723F
        )

        # Pool tabs
        pool_ids = list(sol)
        with ui.tabs(value=pool_ids[0]).props('dense no-caps align=left active-color=white indicator-color=white').classes(
            tokens.TW_W_FULL_MIN_W_0_B8C2ED
        ) as tabs:
            for pool_id in pool_ids:
                ui.tab(pool_id).classes(tokens.TW_TEXT_12PX_FONT_MEDIUM_ROUNDED_ACE678 + ' w-full min-w-0')
        ui.label(
            f"Reserve-compliance check across {len(pool_ids)} configured caps, not a driver-count tradeoff."
        ).classes(tokens.TW_TEXT_12PX_TEXT_181D1F_60_9A9C51)

        # Pool state
        pool_state = {'value': pool_ids[0]}

        # KPI container (re-rendered on tab change)
        kpi_container = ui.grid(columns=3).classes(tokens.TW_W_FULL_MIN_W_0_DB4F2F)

        # Fleet Crew Roster (2-column, all drivers)
        roster_exp = ui.expansion('Fleet Crew Roster', value=True).classes(
            tokens.TW_W_FULL_MIN_W_0_1C8ED6
        )
        with roster_exp:
            with ui.column().classes(tokens.TW_P_4_W_FULL_MIN_47E22F):
                # Shared legend
                with ui.row().classes(tokens.TW_ITEMS_CENTER_GAP_4_MB_1E6237):
                    with ui.row().classes(tokens.TW_ITEMS_CENTER_GAP_2_145735):
                        ui.element('span').classes(tokens.TW_INLINE_BLOCK_W_3_H_6755F2).style(tokens.BUFFER_MARKER)
                        ui.label('Sign-on / Sign-off buffer').classes(tokens.TW_TEXT_11PX_TEXT_64748B_FONT_709A50)
                    with ui.row().classes(tokens.TW_ITEMS_CENTER_GAP_2_145735):
                        ui.element('span').classes(tokens.TW_INLINE_BLOCK_W_3_H_6755F2).style('background-color: ' + tokens.NAVY)
                        ui.label('Revenue trip').classes(tokens.TW_TEXT_11PX_TEXT_64748B_FONT_709A50)
                    with ui.row().classes(tokens.TW_ITEMS_CENTER_GAP_2_145735):
                        ui.element('span').classes(tokens.TW_INLINE_BLOCK_W_3_H_6755F2).style(tokens.RESERVE_MARKER)
                        ui.label('Reserve / Standby').classes(tokens.TW_TEXT_11PX_TEXT_64748B_FONT_709A50)
                roster_container = ui.row().classes(tokens.TW_W_FULL_MIN_W_0_A7F597)

        # Validation panel
        with ui.expansion('Independent Validator Results', value=False).classes(
            tokens.TW_W_FULL_MIN_W_0_1C8ED6
        ):
            with ui.column().classes(tokens.TW_P_4_W_FULL_MIN_2A7C77):
                val_container = ui.column().classes(tokens.TW_W_FULL_MIN_W_0_6E3805)

        # Methodology & Honest Limitations
        with ui.expansion('Methodology & Honest Limitations', value=False).classes(
            tokens.TW_W_FULL_MIN_W_0_1C8ED6
        ):
            with analytics_card('Crew scheduling methodology') as panel:
                panel.props('flat').classes(tokens.TW_SHADOW_NONE_AD47D1)
                ui.markdown(
                    '**Crew coverage**\n\n'
                    'The loaded schedule defines required trips. C4 checks that each trip is assigned once per pool.'
                ).classes(tokens.TW_TEXT_14PX_LEADING_5_TEXT_400C9D)
                ui.markdown(
                    '**Duty and terminal continuity**\n\n'
                    'Sign-on and sign-off bound each shift. C1 checks each trip sequence against the configured terminal connection rules.'
                ).classes(tokens.TW_TEXT_14PX_LEADING_5_TEXT_400C9D)
                ui.markdown(
                    '**Reserve and objective**\n\n'
                    'C7 evaluates reserve requirements. The objective is a configured penalty sum, not a quality score. Objective, bound, gap, and status come from the selected pool loaded solver output.'
                ).classes(tokens.TW_TEXT_14PX_LEADING_5_TEXT_400C9D)
        # ----- inner refresh functions -----

        def refresh_kpis():
            # Pool summary strip
            pool_summary.clear()
            p = pool_state['value']
            entry = sol[p]
            with pool_summary:
                ui.label(f"Pool {p}").classes(
                    tokens.TW_TEXT_13PX_FONT_SEMIBOLD_TEXT_06A1B0
                )
                ui.label(f"Total drivers: {entry['pool_size']}").classes(
                    tokens.TW_TEXT_12PX_TEXT_181D1F_80_39CC56
                )
                ui.label(f"Active: {entry['num_active_drivers']}").classes(
                    tokens.TW_TEXT_12PX_TEXT_334155_FONT_CAD0CA
                )
                ui.label(f"Reserve: {entry['reserve']}").classes(
                    tokens.TW_TEXT_12PX_TEXT_64748B_FONT_145E61
                )

            kpi_container.clear()
            kpi_strip(3, [
                (('Active Drivers', str(entry['num_active_drivers']),), {'footnote': f"Reserve: {entry['reserve']}"}),
                (('Solver Status', entry['status']), {'badge_status': entry['status'], 'footnote': f"Gap: {entry['gap_pct']}%"}),
                (('Solve Time', f"{entry['elapsed_sec']:.2f} s"), {'footnote': f"For {entry['num_trips']} trips"}),
            ], classes='w-full min-w-0 tabular-nums gap-4 mb-4', flat=True, container=kpi_container)

            solver_badge.clear()
            with solver_badge:
                status_badge(entry['status'])
                scenario_tag('OPTIMIZED - CONFIGURED MODEL').style('border-radius: 4px;')

        def refresh_drivers():
            roster_container.clear()
            p = pool_state['value']
            n = int(p)
            pool_drivers = drivers_df['driver_id'].tolist()[:n]
            half = n // 2
            left_drivers = pool_drivers[:half]
            right_drivers = pool_drivers[half:]

            with roster_container:
                with ui.column().classes(tokens.TW_FLEX_1_MIN_W_0_5D5142 + ' w-full'):
                    fig_l, _ = _build_fleet_gantt(left_drivers, p, crew_df, sched_df)
                    plotly_chart(fig_l, tokens.PLOTLY_CONTAINER)
                with ui.column().classes(tokens.TW_FLEX_1_MIN_W_0_5D5142 + ' w-full'):
                    fig_r, _ = _build_fleet_gantt(right_drivers, p, crew_df, sched_df)
                    plotly_chart(fig_r, tokens.PLOTLY_CONTAINER)

        _KEY_LABEL = {
            'failures': 'Failures',
            'total': 'Total violations',
            'required': 'Required trips',
            'scheduled': 'Scheduled trips',
            'pool_size': 'Pool size',
            'active': 'Active drivers',
            'reserve': 'Reserve',
            'min_reserve': 'Min reserve',
        }

        def _fmt_detail(k, v):
            label = _KEY_LABEL.get(k, k.replace('_', ' ').title())
            if isinstance(v, list):
                return f'{label}: {len(v)} failure(s)' if v else f'{label}: (none)'
            return f'{label}: {v}'

        def refresh_validation():
            val_container.clear()
            p = pool_state['value']
            pool_val = val['pools'][p]
            with val_container:
                with ui.grid(columns=2).classes(tokens.TW_W_FULL_MIN_W_0_97DB31):
                    for check in pool_val['checks']:
                        with ui.row().classes(tokens.TW_W_FULL_MIN_W_0_3D7184):
                            status_badge(check['status'])
                            with ui.expansion(_check_label(check['check']), value=False).classes(
                                tokens.TW_FLEX_1_MIN_W_0_9FE364
                            ):
                                with ui.column().classes(tokens.TW_W_FULL_MIN_W_0_7C581E):
                                    for k, v in check['details'].items():
                                        ui.label(_fmt_detail(k, v)).classes(
                                            tokens.TW_TEXT_12PX_LEADING_5_TABULAR_376296
                                        )

        def on_pool_change(e):
            pool_state['value'] = e.value
            refresh_kpis()
            refresh_drivers()
            refresh_validation()

        tabs.on_value_change(on_pool_change)

        # Initial render
        refresh_kpis()
        refresh_drivers()
        refresh_validation()
