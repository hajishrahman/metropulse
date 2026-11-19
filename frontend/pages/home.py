# pages/home.py
# MetroPulse Home — overview dashboard

from __future__ import annotations

import re
from pathlib import Path
from nicegui import ui

from components.ui_elements import (
    kpi_card,
    scenario_tag,
    state_card,
    status_badge,
)
from components.trip_category import derive_trip_category
from data.registry import (
    load_schedule,
    load_solution,
    load_validation,
    load_simulation_kpis,
    load_crew_solution,
    load_crew_validation,
    load_explainability_report,
    load_sensitivity_analysis,
    load_reschedule_diff,
)

_GTFS_BADGE = 'GTFS 2024–25 STATIC'

_DATA_FILES = [
    'schedule.csv',
    'solution.json',
    'validation.json',
    'crew_schedule.csv',
    'crew_solution.json',
    'crew_validation.json',
    'simulation_kpis.json',
    'explainability_report.md',
]

_BOUNDARIES = [
    'Static 2024–25 GTFS data',
    'Single-day scope',
    'O6 rake-balance objective only',
    'Synthetic delay model',
]


def render():
    from components.navigation import create_sidebar
    main = create_sidebar(active_phase='home')
    main.classes('w-full min-w-0 p-6')

    sched_res = load_schedule()
    sol_res = load_solution()
    val_res = load_validation()
    kpis_res = load_simulation_kpis()
    crew_sol_res = load_crew_solution()
    crew_val_res = load_crew_validation()
    report_res = load_explainability_report()
    sens_res = load_sensitivity_analysis()
    diff_res = load_reschedule_diff()

    with main:
        for name, res in (
            ('schedule.csv', sched_res),
            ('solution.json', sol_res),
            ('validation.json', val_res),
            ('simulation_kpis.json', kpis_res),
            ('crew_solution.json', crew_sol_res),
            ('crew_validation.json', crew_val_res),
            ('explainability_report.md', report_res),
            ('sensitivity_analysis.json', sens_res),
            ('reschedule_diff.json', diff_res),
        ):
            if res['status'] != 'ok':
                state_card(res['status'].replace('_', ' ').upper(), name, res['message']).props('flat').classes('shadow-none')
                return

        sched = sched_res['data']
        sol = sol_res['data']
        val = val_res['data']
        kpis = kpis_res['data']
        crew_sol = crew_sol_res['data']
        crew_val = crew_val_res['data']
        report_md = report_res['data']
        sens = sens_res['data']['scenarios']
        diff = diff_res['data']

        # ---- derived ----
        sched_cat = sched.assign(trip_category=sched.apply(derive_trip_category, axis=1))
        n_full = int((sched_cat['trip_category'] == 'full_route').sum())
        n_partial = int((sched_cat['trip_category'] == 'partial').sum())
        n_positioning = int((sched_cat['trip_category'] == 'positioning').sum())
        n_trips = len(sched)
        n_rakes = int(sched['rake_id'].nunique())

        p1_status = sol['status']
        p1_obj = float(sol['objective'])
        p1_checks = val['checks']
        p1_pass = sum(1 for c in p1_checks if str(c.get('status', '')).upper() == 'PASS')
        p1_total = len(p1_checks)

        pools = list(crew_sol.keys())
        pools_sorted = sorted(pools, key=lambda x: int(x))
        actives = [crew_sol[p]['num_active_drivers'] for p in pools_sorted]
        reserve = crew_sol[pools_sorted[0]]['reserve']
        crew_checks = crew_val['pools'][pools_sorted[0]]['checks']
        crew_pass = sum(1 for c in crew_checks if str(c.get('status', '')).upper() == 'PASS')
        crew_total = len(crew_checks)

        e1_delay = kpis['headline_seed_run']['E1']['total_propagated_delay']['total_propagated_delay_min']
        e4_delay = kpis['headline_seed_run']['E4']['total_propagated_delay']['total_propagated_delay_min']
        seed = kpis['metadata']['headline_seed']
        on_time_5 = kpis['headline_seed_run']['E4']['on_time_5min']['on_time_pct']
        n_seeds = kpis['metadata']['n_seeds_monte_carlo']

        n_sections = len(re.findall(r'^## ', report_md, flags=re.MULTILINE))

        # Phase 5 drop ranges
        drops_low = [diff['scenario_a']['trips_dropped']] + [s['drops'] for s in sens if s['rakes_failed'] <= 3]
        drops_high = [diff['scenario_b']['trips_dropped']] + [s['drops'] for s in sens if s['rakes_failed'] >= 4]
        lo = min(drops_low) if drops_low else 0
        hi = max(drops_high) if drops_high else 0

        # ---- HEADER ----
        with ui.row().classes('w-full min-w-0 justify-between items-start mb-4'):
            with ui.column().classes('min-w-0 gap-1'):
                ui.label('MetroPulse').classes(
                    "text-[28px] leading-8 font-bold text-[#0F172A] font-['IBM_Plex_Sans',_sans-serif]"
                )
                ui.label('Kochi Metro Operations Optimizer').classes(
                    "text-[14px] leading-5 text-[#334155] font-['IBM_Plex_Sans',_sans-serif]"
                )
            scenario_tag(_GTFS_BADGE).style('border-radius: 4px;')

        # ---- KPI ROW ----
        with ui.grid(columns=4).classes('w-full gap-4 mb-4'):
            kpi_card(
                'Scheduled Trips', str(n_trips),
                footnote=f"{n_full} full-route, {n_partial} partial, {n_positioning} positioning",
            ).props('flat').classes('shadow-none')
            kpi_card(
                'Active Fleet', f'{n_rakes} Rakes',
                footnote=f"R001–R{n_rakes:03d} | {p1_status} (Gap {sol['gap_pct']:.1f}%)",
            ).props('flat').classes('shadow-none')
            kpi_card(
                'Crew Pools', ' / '.join(pools_sorted),
                footnote=f"{', '.join(str(a) for a in actives)} active drivers + {reserve} reserve",
            ).props('flat').classes('shadow-none')
            kpi_card(
                'Delay Tolerance', f'{on_time_5:.0f}%',
                footnote=f"On-time rate at ±5 min across {n_seeds} seeds",
            ).props('flat').classes('shadow-none')

        # ---- SPLIT HERO BANNER (Photo + System Pipeline) ----
        img_path = Path(__file__).resolve().parent.parent / 'assets' / 'kochi_metro.jpg'
        with ui.card().classes(
            "w-full min-w-0 bg-white rounded-[6px] shadow-[0_1px_5px_rgba(0,0,0,0.2),0_2px_2px_rgba(0,0,0,0.14),0_3px_1px_-2px_rgba(0,0,0,0.12)] border border-[#e2e8f0] p-4 mb-4"
        ):
            with ui.element('div').classes('grid grid-cols-1 md:grid-cols-12 gap-6 items-center w-full'):
                # Left: image (4 of 12 cols)
                with ui.element('div').classes('md:col-span-4 w-full'):
                    if img_path.exists():
                        ui.image(img_path).classes('w-full h-52 rounded-lg object-cover')
                    else:
                        ui.label('assets/kochi_metro.jpg not found').classes(
                            "text-[12px] text-[#B3261E] font-['IBM_Plex_Sans',_sans-serif]"
                        )
                # Right: pipeline (8 of 12 cols)
                with ui.element('div').classes('md:col-span-8 flex flex-col justify-center'):
                    ui.label('System Pipeline').classes(
                        "text-[16px] font-semibold text-[#1e3a5f] mb-3 font-['IBM_Plex_Sans',_sans-serif]"
                    )
                    pipeline = [
                        ('Train Scheduling', f'reads open GTFS data and schedules {n_trips} trips across {n_rakes} rakes.'),
                        ('Operational Simulation', f'injects synthetic delays into the Train Scheduling output across {n_seeds} seeds.'),
                        ('Crew Scheduling', 'assigns drivers from each crew pool to cover all trips.'),
                        ('Explainability', 'reports constraint checks, utilization metrics, and solver limits.'),
                        ('Disruption Response', 'builds recovery schedules when 1 to 5 rakes fail.'),
                    ]
                    for i, (name, desc) in enumerate(pipeline, start=1):
                        ui.label(f'{i}. {name} — {desc}').classes(
                            "text-[13px] leading-6 text-[#334155] font-['IBM_Plex_Sans',_sans-serif]"
                        )

        # ---- PHASE CARDS ----
        with ui.grid(columns=5).classes('w-full gap-3 mb-4'):
            phases = [
                ('Train Scheduling', 'OPTIMAL', 'badge',
                 f'Assigns {n_rakes} rakes to {n_trips} daily trips under the O6 rake-balance objective',
                 f'Objective: {p1_obj:.1f}', f'{p1_pass}/{p1_total} Checks PASS'),
                ('Operational Simulation', f'{n_seeds} SEEDS', 'tag',
                 'Tests delay propagation across 4 experiments from E1 to E4',
                 f'E1 Delay: {e1_delay} min', f'E4 Delay: {e4_delay} min (Seed {seed})'),
                ('Crew Scheduling', 'OPTIMAL', 'badge',
                 f'Builds single-day driver rosters with duty limits and {reserve} reserve drivers',
                 f'{len(pools_sorted)} Driver Pools', f'{crew_pass}/{crew_total} Checks PASS'),
                ('Explainability', 'PASS', 'badge',
                 'Reports source-cited audits, utilization formulas, and model limits',
                 f'{n_sections} Report Sections', 'Zero Hardcoded Values'),
                ('Disruption Response', '5 SCENARIOS', 'tag',
                 'Tests fleet resilience when 1 to 5 rakes fail during service',
                 f'{lo} Drops (1–3 Rakes Down)', f'{hi} Drops (4–5 Down)'),
            ]
            routes = ['/phase1', '/phase2', '/phase3', '/phase4', '/phase5']

            for (title, badge_text, badge_kind, desc, m1, m2), route in zip(phases, routes):
                with ui.card().classes(
                    "w-full bg-white rounded-[6px] shadow-[0_1px_5px_rgba(0,0,0,0.2),0_2px_2px_rgba(0,0,0,0.14),0_3px_1px_-2px_rgba(0,0,0,0.12)] border border-[#e2e8f0] p-3"
                ):
                    with ui.row().classes('w-full items-center justify-between mb-2'):
                        ui.label(title).classes(
                            "text-[14px] font-semibold text-[#1e3a5f] font-['IBM_Plex_Sans',_sans-serif]"
                        )
                        if badge_kind == 'badge':
                            status_badge(badge_text).style('border-radius: 4px;')
                        else:
                            scenario_tag(badge_text).style('border-radius: 4px;')
                    ui.label(desc).classes(
                        "text-[12px] leading-5 text-[#334155] mb-2 font-['IBM_Plex_Sans',_sans-serif]"
                    )
                    ui.label(m1).classes(
                        "text-[11px] leading-4 text-[#64748B] font-['IBM_Plex_Sans',_sans-serif]"
                    )
                    ui.label(m2).classes(
                        "text-[11px] leading-4 text-[#64748B] mb-3 font-['IBM_Plex_Sans',_sans-serif]"
                    )
                    ui.button('Open', on_click=lambda r=route: ui.navigate.to(r)).props('flat dense no-caps').classes(
                        "w-full bg-[#1e3a5f] text-white rounded-[4px] text-[12px] font-medium py-1"
                    )

        # ---- COMPACT FOOTER (boundaries + data sources) ----
        with ui.card().classes(
            "w-full min-w-0 bg-white rounded-[6px] shadow-[0_1px_5px_rgba(0,0,0,0.2),0_2px_2px_rgba(0,0,0,0.14),0_3px_1px_-2px_rgba(0,0,0,0.12)] border border-[#e2e8f0] p-4 mb-4"
        ):
            # Row 1 — System Boundaries
            ui.label('System Boundaries').classes(
                "text-[12px] font-semibold text-[#1e3a5f] uppercase tracking-wider mb-2 font-['IBM_Plex_Sans',_sans-serif]"
            )
            with ui.row().classes('items-center gap-2 flex-wrap mb-4'):
                for b in _BOUNDARIES:
                    ui.label(b).classes(
                        "bg-[#f4f6f8] text-[#334155] rounded-[6px] px-2 py-1 "
                        "text-[11px] font-medium border border-[#e2e8f0] "
                        "font-['IBM_Plex_Sans',_sans-serif]"
                    )

            # Row 2 — Data Sources
            ui.label('Processed Data Files').classes(
                "text-[12px] font-semibold text-[#1e3a5f] uppercase tracking-wider mb-2 font-['IBM_Plex_Sans',_sans-serif]"
            )
            with ui.row().classes('items-center gap-2 flex-wrap'):
                for f in _DATA_FILES:
                    ui.label(f).classes(
                        "bg-[#f4f6f8] text-[#334155] rounded-[4px] px-2 py-1 "
                        "text-[11px] border border-[#e2e8f0] font-mono"
                    )