# pages/phase3.py
# Phase 3 - Crew Scheduling (CP-SAT)

from __future__ import annotations

import plotly.graph_objects as go
from nicegui import ui

from components.ui_elements import analytics_card, kpi_card, scenario_tag, state_card, status_badge
from components.time_utils import sec_to_hhmmss, hhmmss_to_sec

ui.add_head_html(
    '<style>'
    '.q-tab--active { background-color: #1E3A5F !important; color: #ffffff !important; }'
    '.q-tab--active .q-tab__label { color: #ffffff !important; }'
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

_TRIPS_COLOR = '#1E3A5F'
_BUFFER_FILL = '#CBD5E1'
_BUFFER_BORDER = '#94A3B8'


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
                line=dict(color="#191715", width=2.5, dash='dash'),
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
                line=dict(color="#191715", width=2, dash='dash'),
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
            f"Duty: {sec_to_hhmmss(first_dep)} - {sec_to_hhmmss(last_arr)}<br>"
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
        height=550,
        font=dict(family='IBM Plex Mono, monospace', color='#334155'),
        hoverlabel=dict(bgcolor='#0F172A', font=dict(color='#FFFFFF', family='IBM Plex Mono, monospace')),
        xaxis=dict(
            tickvals=tick_secs,
            ticktext=[sec_to_hhmmss(s)[:5] for s in tick_secs],
            range=[X_MIN, X_MAX], automargin=True,
            title='Time (IST)',
            gridcolor='#E2E8F0',
            zeroline=False,
        ),
        yaxis=dict(
            tickvals=list(range(n_rows)), range=[-0.5, max(n_rows - 0.5, 0.5)], automargin=True,
            ticktext=list(reversed(driver_list)),
            gridcolor='#E2E8F0',
            zeroline=False,
            tickfont=dict(size=10),
        ),
        margin=dict(l=60, r=10, t=10, b=40),
        plot_bgcolor='white',
        paper_bgcolor='white',
    )
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
    main.classes('w-full min-w-0 p-6')

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
                state_card(res['status'].replace('_', ' ').upper(), name, res['message']).props('flat').classes('shadow-none')
                return

        sol = sol_res['data']
        val = val_res['data']
        crew_df = crew_res['data']
        drivers_df = drv_res['data']
        sched_df = sched_res['data']

        # Header
        with ui.row().classes('w-full min-w-0 justify-between items-center mb-2'):
            with ui.column().classes('min-w-0 gap-1'):
                ui.label('Crew Scheduling').classes("text-[22px] leading-7 font-bold text-[#0F172A] font-['IBM_Plex_Sans',_sans-serif]")
                ui.label('CP-SAT optimized single-day crew rostering respecting duty limits and reserve buffers.').classes(
                    "text-[14px] text-[#181d1f]/70 font-['IBM_Plex_Sans',_sans-serif]"
                )
            solver_badge = ui.row().classes('items-center')

        # Pool summary strip
        pool_summary = ui.row().classes(
            'w-full min-w-0 tabular-nums items-center gap-4 mb-2 p-3 rounded-[6px] ' +
            'bg-[#F8FAFC] border border-[#E2E8F0]'
        )

        # Pool tabs
        pool_ids = list(sol)
        with ui.tabs(value=pool_ids[0]).props('dense no-caps align=left active-color=white indicator-color=white').classes(
            'w-full min-w-0 mb-2 bg-[#F8FAFC] rounded-[6px] p-1 border border-[#E2E8F0] shadow-none'
        ) as tabs:
            for pool_id in pool_ids:
                ui.tab(pool_id).classes('text-[12px] font-medium rounded-[4px]')
        ui.label(
            f"Reserve-compliance check across {len(pool_ids)} configured caps, not a driver-count tradeoff."
        ).classes("text-[12px] text-[#181d1f]/60 mb-4 font-['IBM_Plex_Sans',_sans-serif]")

        # Pool state
        pool_state = {'value': pool_ids[0]}

        # KPI container (re-rendered on tab change)
        kpi_container = ui.grid(columns=3).classes('w-full min-w-0 tabular-nums gap-4 mb-4')

        # Fleet Crew Roster (2-column, all drivers)
        roster_exp = ui.expansion('Fleet Crew Roster', value=True).classes(
            "w-full min-w-0 bg-white rounded-[6px] shadow-none border border-[#E2E8F0] mb-4"
        )
        with roster_exp:
            with ui.column().classes('p-4 w-full min-w-0'):
                # Shared legend
                with ui.row().classes('items-center gap-4 mb-3 flex-wrap'):
                    with ui.row().classes('items-center gap-2'):
                        ui.element('span').classes('inline-block w-3 h-3 rounded-sm').style('background-color: #CBD5E1; border: 1px solid #94A3B8')
                        ui.label('Sign-on / Sign-off buffer').classes("text-[11px] text-[#64748B] font-['IBM_Plex_Sans',_sans-serif]")
                    with ui.row().classes('items-center gap-2'):
                        ui.element('span').classes('inline-block w-3 h-3 rounded-sm').style('background-color: #1E3A5F')
                        ui.label('Revenue trip').classes("text-[11px] text-[#64748B] font-['IBM_Plex_Sans',_sans-serif]")
                    with ui.row().classes('items-center gap-2'):
                        ui.element('span').classes('inline-block w-3 h-3 rounded-sm').style('background-color: transparent; border: 2px dashed #191715')
                        ui.label('Reserv line=dict(color / Standby').classes("text-[11px] text-[#64748B] font-['IBM_Plex_Sans',_sans-serif]")
                roster_container = ui.row().classes('w-full min-w-0 gap-3 flex-wrap')

        # Validation panel
        with ui.expansion('Independent Validator Results', value=False).classes(
            "w-full min-w-0 bg-white rounded-[6px] shadow-none border border-[#E2E8F0] mb-4"
        ):
            with ui.column().classes('p-4 w-full min-w-0 gap-3'):
                val_container = ui.column().classes('w-full min-w-0 gap-3')

        # Methodology & Honest Limitations
        with ui.expansion('Methodology & Honest Limitations', value=False).classes(
            "w-full min-w-0 bg-white rounded-[6px] shadow-none border border-[#E2E8F0] mb-4"
        ):
            with analytics_card('Crew scheduling methodology') as panel:
                panel.props('flat').classes('shadow-none')
                ui.markdown(
                    '**Crew coverage**\n\n'
                    'The loaded schedule defines required trips. C4 checks that each trip is assigned once per pool.'
                ).classes("text-[14px] leading-5 text-[#334155]")
                ui.markdown(
                    '**Duty and terminal continuity**\n\n'
                    'Sign-on and sign-off bound each shift. C1 checks each trip sequence against the configured terminal connection rules.'
                ).classes("text-[14px] leading-5 text-[#334155]")
                ui.markdown(
                    '**Reserve and objective**\n\n'
                    'C7 evaluates reserve requirements. The objective is a configured penalty sum, not a quality score. Objective, bound, gap, and status come from the selected pool loaded solver output.'
                ).classes("text-[14px] leading-5 text-[#334155]")
        # ----- inner refresh functions -----

        def refresh_kpis():
            # Pool summary strip
            pool_summary.clear()
            p = pool_state['value']
            entry = sol[p]
            with pool_summary:
                ui.label(f"Pool {p}").classes(
                    "text-[13px] font-semibold text-[#181d1f] font-['IBM_Plex_Sans',_sans-serif]"
                )
                ui.label(f"Total drivers: {entry['pool_size']}").classes(
                    "text-[12px] text-[#181d1f]/80 font-['IBM_Plex_Sans',_sans-serif]"
                )
                ui.label(f"Active: {entry['num_active_drivers']}").classes(
                    "text-[12px] text-[#334155] font-medium tabular-nums font-['IBM_Plex_Sans',_sans-serif]"
                )
                ui.label(f"Reserve: {entry['reserve']}").classes(
                    "text-[12px] text-[#64748B] font-medium tabular-nums font-['IBM_Plex_Sans',_sans-serif]"
                )

            kpi_container.clear()
            with kpi_container:
                kpi_card(
                    'Active Drivers',
                    str(entry['num_active_drivers']),
                    footnote=f"Reserve: {entry['reserve']}",
                ).props('flat').classes('shadow-none')
                kpi_card(
                    'Solver Status',
                    entry['status'],
                    badge_status=entry['status'],
                    footnote=f"Gap: {entry['gap_pct']}%",
                ).props('flat').classes('shadow-none')
                kpi_card(
                    'Solve Time',
                    f"{entry['elapsed_sec']:.2f} s",
                    footnote=f"For {entry['num_trips']} trips",
                ).props('flat').classes('shadow-none')

            solver_badge.clear()
            with solver_badge:
                status_badge(entry['status']).style('border-radius: 4px; border: 1px solid #E2E8F0;')
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
                with ui.column().classes('flex-1 min-w-0'):
                    fig_l, _ = _build_fleet_gantt(left_drivers, p, crew_df, sched_df)
                    ui.plotly(fig_l).classes('w-full min-w-0 h-[550px]')
                with ui.column().classes('flex-1 min-w-0'):
                    fig_r, _ = _build_fleet_gantt(right_drivers, p, crew_df, sched_df)
                    ui.plotly(fig_r).classes('w-full min-w-0 h-[550px]')

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
                with ui.grid(columns=2).classes('w-full min-w-0 gap-2'):
                    for check in pool_val['checks']:
                        with ui.row().classes('w-full min-w-0 items-start gap-2'):
                            status_badge(check['status']).style('border-radius: 4px; border: 1px solid #E2E8F0;')
                            with ui.expansion(_check_label(check['check']), value=False).classes(
                                'flex-1 min-w-0 bg-[#F8FAFC] rounded-[6px] border border-[#E2E8F0] shadow-none'
                            ):
                                with ui.column().classes('w-full min-w-0 p-3 gap-1'):
                                    for k, v in check['details'].items():
                                        ui.label(_fmt_detail(k, v)).classes(
                                            "text-[12px] leading-5 tabular-nums text-[#334155] font-['IBM_Plex_Sans',_sans-serif]"
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
