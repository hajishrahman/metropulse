# pages/phase3.py
# Phase 3 — Crew Scheduling (CP-SAT)

from __future__ import annotations

import plotly.graph_objects as go
from nicegui import ui

from components.ui_elements import kpi_card, state_card, status_badge
from components.time_utils import sec_to_hhmmss, hhmmss_to_sec

ui.add_head_html(
    '<style>'
    '.q-tab--active { background-color: #1B7A43 !important; color: #ffffff !important; }'
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

_TRIPS_COLOR = '#1B7A43'
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
    sched_lookup = sched_df.set_index('trip_id')[['departure', 'arrival', 'first_stop', 'last_stop']]

    # Fixed x-axis range: 04:30 → 24:00
    X_MIN = 4 * 3600 + 1800
    X_MAX = 24 * 3600
    tick_secs = list(range(5 * 3600, X_MAX + 1, 2 * 3600))

    fig = go.Figure()
    n_rows = len(driver_list)

    for i, did in enumerate(driver_list):
        y = n_rows - 1 - i  # top driver first
        rows = pool_crew[pool_crew['driver_id'] == did]

        if rows.empty:
            # Reserve row — dashed track
            fig.add_trace(go.Scatter(
                x=[X_MIN, X_MAX], y=[y, y], mode='lines',
                line=dict(color='#A16207', width=4, dash='dash'),
                showlegend=False,
                hovertemplate=f"{did} · Reserve / Standby (0 trips)<extra></extra>",
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
                line=dict(color='#CBD5E1', width=2, dash='dash'),
                showlegend=False,
                hovertemplate=f"{did} · Reserve / Standby (0 trips)<extra></extra>",
            ))
            continue

        first_dep = int(merged['dep_sec'].iloc[0])
        last_arr = int(merged['arr_sec'].iloc[-1])
        active_duty = last_arr - first_dep
        total_depot = sign_off_sec - sign_on_sec
        trip_count = len(merged)

        hover = (
            f"<b>{did}</b><br>"
            f"Active duty: {sec_to_hhmmss(active_duty)}<br>"
            f"Depot: {sec_to_hhmmss(total_depot)}<br>"
            f"{trip_count} trips<br>"
            f"{sec_to_hhmmss(first_dep)[:5]} → {sec_to_hhmmss(last_arr)[:5]}"
            f"<extra></extra>"
        )

        # Sign-on buffer
        fig.add_trace(go.Scatter(
            x=[sign_on_sec, first_dep], y=[y, y], mode='lines',
            line=dict(color=_BUFFER_BORDER, width=20),
            showlegend=False, hovertemplate=hover,
        ))
        # Trips
        for _, row in merged.iterrows():
            fig.add_trace(go.Scatter(
                x=[row['dep_sec'], row['arr_sec']], y=[y, y], mode='lines',
                line=dict(color=_TRIPS_COLOR, width=20),
                showlegend=False, hovertemplate=hover,
            ))
        # Sign-off buffer
        fig.add_trace(go.Scatter(
            x=[last_arr, sign_off_sec], y=[y, y], mode='lines',
            line=dict(color=_BUFFER_BORDER, width=20),
            showlegend=False, hovertemplate=hover,
        ))

    fig.update_layout(
        showlegend=False,
        height=550,
        xaxis=dict(
            tickvals=tick_secs,
            ticktext=[sec_to_hhmmss(s)[:5] for s in tick_secs],
            range=[X_MIN, X_MAX],
            title='Time (IST)',
            gridcolor='#E2E8F0',
            zeroline=False,
        ),
        yaxis=dict(
            tickvals=list(range(n_rows)),
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
        'C1_no_overlap': 'C1 — No overlapping trips per driver',
        'C2_max_duty': 'C2 — Max 8h duty enforced',
        'C3_sign_buffers': 'C3 — Sign-on / sign-off buffers correct',
        'C4_coverage': 'C4 — All trips covered',
        'C7_reserve': 'C7 — Reserve ≥ minimum',
    }
    return m.get(name, name)


def render():
    from components.navigation import create_sidebar
    main = create_sidebar(active_phase='phase3')
    main.classes('p-6')

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
                state_card(res['status'].replace('_', ' ').upper(), name, res['message'])
                return

        sol = sol_res['data']
        val = val_res['data']
        crew_df = crew_res['data']
        drivers_df = drv_res['data']
        sched_df = sched_res['data']

        # Header
        with ui.row().classes('w-full justify-between items-center mb-2'):
            with ui.column().classes('gap-1'):
                ui.label('Phase 3 — Crew Scheduling').classes(
                    "text-[28px] font-bold text-[#181d1f] font-['IBM_Plex_Sans',_sans-serif]"
                )
                ui.label('CP-SAT optimized single-day crew rostering respecting duty limits and reserve buffers.').classes(
                    "text-[14px] text-[#181d1f]/70 font-['IBM_Plex_Sans',_sans-serif]"
                )
            ui.label('OPTIMAL · 0.0% GAP').classes(
                "bg-[#f4f6f8] text-[#181d1f] rounded-[6px] px-3 py-1 text-[12px] "
                "font-medium uppercase tracking-wider border border-[#e2e8f0] "
                "font-['IBM_Plex_Sans',_sans-serif]"
            )

        # Pool summary strip
        pool_summary = ui.row().classes(
            'w-full items-center gap-4 mb-2 p-3 rounded-[6px] '
            'bg-[#f4f6f8] border border-[#e2e8f0]'
        )

        # Pool tabs
        with ui.tabs().props('dense no-caps align=left active-color=white indicator-color=transparent').classes(
            'mb-2 bg-[#f4f6f8] rounded-[6px] p-1 border border-[#e2e8f0]'
        ) as tabs:
            t45 = ui.tab('45').classes('text-[12px] font-medium rounded-[4px]')
            t50 = ui.tab('50').classes('text-[12px] font-medium rounded-[4px]')
            t55 = ui.tab('55').classes('text-[12px] font-medium rounded-[4px]')
        ui.label(
            'Reserve-compliance check at three caps, not a driver-count tradeoff.'
        ).classes("text-[12px] text-[#181d1f]/60 mb-4 font-['IBM_Plex_Sans',_sans-serif]")

        # Pool state
        pool_state = {'value': '45'}

        # KPI container (re-rendered on tab change)
        kpi_container = ui.grid(columns=3).classes('w-full gap-4 mb-4')

        # Positive claim card (static)
        with ui.card().classes(
            "w-full bg-[#E8F5E9] rounded-[6px] shadow-[0_1px_5px_rgba(0,0,0,0.2),0_2px_2px_rgba(0,0,0,0.14),0_3px_1px_-2px_rgba(0,0,0,0.12)] p-4 mb-4 border-l-4 border-[#1B7A43]"
        ):
            ui.label(
                'Physically drivable roster — zero impossible terminal transitions '
                'across all three pools, independently verified.'
            ).classes(
                "text-[14px] font-medium text-[#1B7A43] font-['IBM_Plex_Sans',_sans-serif]"
            )

               # Fleet Crew Roster (2-column, all drivers)
        roster_exp = ui.expansion('Fleet Crew Roster', value=True).classes(
            "w-full bg-white rounded-[6px] shadow-[0_1px_5px_rgba(0,0,0,0.2),0_2px_2px_rgba(0,0,0,0.14),0_3px_1px_-2px_rgba(0,0,0,0.12)] mb-4"
        )
        with roster_exp:
            with ui.column().classes('p-4 w-full'):
                # Shared legend
                with ui.row().classes('items-center gap-4 mb-3 flex-wrap'):
                    with ui.row().classes('items-center gap-2'):
                        ui.element('span').classes('inline-block w-3 h-3 rounded-sm').style('background-color: #CBD5E1; border: 1px solid #94A3B8')
                        ui.label('Sign-on / Sign-off buffer').classes("text-[11px] text-[#64748B] font-['IBM_Plex_Sans',_sans-serif]")
                    with ui.row().classes('items-center gap-2'):
                        ui.element('span').classes('inline-block w-3 h-3 rounded-sm').style('background-color: #1B7A43')
                        ui.label('Revenue trip').classes("text-[11px] text-[#64748B] font-['IBM_Plex_Sans',_sans-serif]")
                    with ui.row().classes('items-center gap-2'):
                        ui.element('span').classes('inline-block w-3 h-3 rounded-sm').style('background-color: #A16207; border: 1px dashed #A16207')
                        ui.label('Reserve / Standby').classes("text-[11px] text-[#64748B] font-['IBM_Plex_Sans',_sans-serif]")
                roster_container = ui.row().classes('w-full gap-3 flex-nowrap')

        # Validation panel
        with ui.expansion('Independent Validator Results', value=False).classes(
            "w-full bg-white rounded-[6px] shadow-[0_1px_5px_rgba(0,0,0,0.2),0_2px_2px_rgba(0,0,0,0.14),0_3px_1px_-2px_rgba(0,0,0,0.12)] mb-4"
        ):
            with ui.column().classes('p-4 w-full gap-3'):
                val_container = ui.column().classes('w-full gap-3')

        # Methodology & Honest Limitations
        with ui.expansion('Methodology ', value=False).classes(
            "w-full bg-white rounded-[6px] shadow-[0_1px_5px_rgba(0,0,0,0.2),0_2px_2px_rgba(0,0,0,0.14),0_3px_1px_-2px_rgba(0,0,0,0.12)] mb-4"
        ):
            with ui.column().classes('p-4 gap-3'):
                # Constraint status
                ui.markdown(
                    '**HOW CONSTRAINTS ARE ENFORCED**\n\n'
                    
                    '- **Total depot time** = sign-on → sign-off (≤ 8h 30m). '
                    '**Active duty** = first departure → last arrival (≤ 8h per C2). '
                    'They differ by exactly 30 min (the two 15-min buffers).'
                ).classes("text-[13px] text-[#181d1f]/80 font-['IBM_Plex_Sans',_sans-serif]")

                # 1. Trip coverage
                ui.markdown(
                    '**1. Trip coverage**\n\n'
                    '```\n'
                    'crew_schedule.csv rows = num_trips × num_pools\n'
                    '                       = 255 × 3\n'
                    '                       = 765\n'
                    '```\n'
                    'Every trip appears exactly once per pool (C4 enforces this). The validator '
                    'confirms `required = 255`, `scheduled = 255`, `failures = []` at every pool.'
                ).classes("text-[13px] text-[#181d1f]/80 font-['IBM_Plex_Sans',_sans-serif]")

                # 2. Terminal-continuity gap
                ui.markdown(
                    '**2. Terminal-continuity gap requirement**\n\n'
                    '```\n'
                    'required_gap(a, b) =\n'
                    '    300 s   if a.last_stop == b.first_stop        (same-stop turnaround)\n'
                    '    480 s   if {a.last_stop, b.first_stop} touches MUTT and a terminal\n'
                    '    900 s   otherwise                              (cross-terminal / KVTR / unknown)\n'
                    '```\n'
                    'A pair (a, b) on the same driver is allowed iff `a.arr + required_gap ≤ b.dep`. '
                    'This is C1\'s rule, applied in both the solver and the validator. The post-fix '
                    'diagnostic found **0 violations** — every pair satisfies it.'
                ).classes("text-[13px] text-[#181d1f]/80 font-['IBM_Plex_Sans',_sans-serif]")

                # 3. Active and reserve
                ui.markdown(
                    '**3. Active and reserve drivers**\n\n'
                    '```\n'
                    'active_drivers  = count of distinct driver_id in crew_schedule.csv for the pool\n'
                    'reserve         = pool_size − active_drivers\n'
                    '```\n'
                    'At all three pools: active = 40 / 45 / 50, reserve = 5 / 5 / 5. '
                    'The solver uses exactly `pool_size − 5` drivers at every pool — this is C7\'s '
                    'target and it held without exception.'
                ).classes("text-[13px] text-[#181d1f]/80 font-['IBM_Plex_Sans',_sans-serif]")

                # 4. Objective decomposition
                ui.markdown(
                    '**4. Objective decomposition**\n\n'
                    '```\n'
                    'objective = OBJ_SCALE × (W_CONTINUOUS_DRIVING × C6_penalty\n'
                    '                        + W_RESERVE_BUFFER     × C7_penalty)\n'
                    '          = 100 × (10 × C6_penalty + 15 × C7_penalty)\n'
                    '```\n'
                    '`C6_penalty = 0` (C6 chains never exceed 5 h under the current config — but see '
                    'the honest note; this is not a fatigue claim).  \n'
                    '`C7_penalty = 0` (reserve held at 5 at every pool).  \n'
                    '`objective = 0.0` at all pools, proven optimal (best bound = 0.0, gap = 0.0%).\n\n'
                    'The objective is **not a quality score** — it is a penalty sum. Zero means both '
                    'soft rules were fully satisfied. It does not mean "optimal driver count" or '
                    '"optimal fatigue."'
                ).classes("text-[13px] text-[#181d1f]/80 font-['IBM_Plex_Sans',_sans-serif]")

                # 5. Optimality gap
                ui.markdown(
                    '**5. Optimality gap**\n\n'
                    '```\n'
                    'gap_pct = 0.0                                      if status == OPTIMAL\n'
                    '        = (objective − best_bound) / objective × 100   otherwise\n'
                    '```\n'
                    'All three pools returned OPTIMAL with `best_bound = objective = 0.0`, so '
                    '`gap = 0.0%`. This is a **proof** — CP-SAT proved no schedule can have a lower '
                    'objective under the stated weights. It is not an estimate.'
                ).classes("text-[13px] text-[#181d1f]/80 font-['IBM_Plex_Sans',_sans-serif]")

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
                    "text-[12px] text-[#1B7A43] font-medium font-['IBM_Plex_Sans',_sans-serif]"
                )
                ui.label(f"Reserve: {entry['reserve']}").classes(
                    "text-[12px] text-[#A16207] font-medium font-['IBM_Plex_Sans',_sans-serif]"
                )

            kpi_container.clear()
            with kpi_container:
                kpi_card(
                    'Active Drivers',
                    str(entry['num_active_drivers']),
                    footnote=f"Reserve: {entry['reserve']}",
                )
                kpi_card(
                    'Solver Status',
                    entry['status'],
                    footnote=f"Gap: {entry['gap_pct']}%",
                )
                kpi_card(
                    'Solve Time',
                    f"{entry['elapsed_sec']:.2f} s",
                    footnote=f"For {entry['num_trips']} trips",
                )

        def refresh_drivers():
            roster_container.clear()
            p = pool_state['value']
            n = int(p)
            pool_drivers = [f"D{i:03d}" for i in range(1, n + 1)]
            half = n // 2
            left_drivers = pool_drivers[:half]
            right_drivers = pool_drivers[half:]

            with roster_container:
                with ui.column().classes('flex-1 min-w-0'):
                    fig_l, _ = _build_fleet_gantt(left_drivers, p, crew_df, sched_df)
                    ui.plotly(fig_l).classes('w-full')
                with ui.column().classes('flex-1 min-w-0'):
                    fig_r, _ = _build_fleet_gantt(right_drivers, p, crew_df, sched_df)
                    ui.plotly(fig_r).classes('w-full')

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
                with ui.grid(columns=2).classes('w-full gap-2'):
                    for check in pool_val['checks']:
                        with ui.card().classes(
                            "w-full bg-white rounded-[6px] border border-[#E2E8F0] p-2"
                        ):
                            with ui.row().classes('w-full items-center justify-between mb-1'):
                                ui.label(_check_label(check['check'])).classes(
                                    "text-[12px] font-medium text-[#181d1f] font-['IBM_Plex_Sans',_sans-serif]"
                                )
                                status_badge(check['status'])
                            for k, v in check['details'].items():
                                ui.label(_fmt_detail(k, v)).classes(
                                    "text-[11px] leading-4 text-[#181d1f]/70 font-['IBM_Plex_Sans',_sans-serif]"
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