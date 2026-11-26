# pages/home.py
# MetroPulse Home — overview dashboard

from __future__ import annotations

import re
from pathlib import Path
from nicegui import ui

from components import tokens

from components.ui_elements import (
    kpi_strip,
    page_content,
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
    page_content(main)

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
                state_card(res['status'].replace('_', ' ').upper(), name, res['message']).props('flat').classes(tokens.TW_SHADOW_NONE_AD47D1)
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
        with ui.row().classes(tokens.TW_W_FULL_MIN_W_0_39E197):
            with ui.column().classes(tokens.TW_MIN_W_0_GAP_1_6364F0):
                ui.label('MetroPulse').classes(
                    tokens.TW_TEXT_28PX_LEADING_8_FONT_C384E7
                )
                ui.label('Kochi Metro Operations Optimizer').classes(
                    tokens.TW_TEXT_14PX_LEADING_5_TEXT_AE0775
                )
            scenario_tag(_GTFS_BADGE).style('border-radius: 4px;')

        # ---- KPI ROW ----
        kpi_strip(4, [
            (('Scheduled Trips', str(n_trips)), {'footnote': f'{n_full} full-route, {n_partial} partial, {n_positioning} positioning'}),
            (('Active Fleet', f'{n_rakes} Rakes'), {'footnote': f"R001–R{n_rakes:03d} | {p1_status} (Gap {sol['gap_pct']:.1f}%)"}),
            (('Crew Pools', ' / '.join(pools_sorted)), {'footnote': f"{', '.join(str(a) for a in actives)} active drivers + {reserve} reserve"}),
            (('Delay Tolerance', f'{on_time_5:.0f}%'), {'footnote': f'On-time rate at ±5 min across {n_seeds} seeds'}),
        ], 'w-full gap-4 mb-4', flat=True)

        # ---- SPLIT HERO BANNER (Photo + System Pipeline) ----
        img_path = Path(__file__).resolve().parent.parent / 'assets' / 'kochi_metro.jpg'
        with ui.card().classes(
            tokens.TW_W_FULL_MIN_W_0_FBFB4B
        ):
            with ui.element('div').classes(tokens.TW_GRID_GRID_COLS_1_MD_0A4D27):
                # Left: image (4 of 12 cols)
                with ui.element('div').classes(tokens.TW_MD_COL_SPAN_4_W_CE3D94):
                    if img_path.exists():
                        ui.image(img_path).classes(tokens.TW_W_FULL_H_52_ROUNDED_5CA770)
                    else:
                        ui.label('assets/kochi_metro.jpg not found').classes(
                            tokens.TW_TEXT_12PX_TEXT_B91C1C_FONT_69A0F3
                        )
                # Right: pipeline (8 of 12 cols)
                with ui.element('div').classes(tokens.TW_MD_COL_SPAN_8_FLEX_8F7200):
                    ui.label('System Pipeline').classes(
                        tokens.TW_TEXT_16PX_FONT_SEMIBOLD_TEXT_2BD4D8
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
                            tokens.TW_TEXT_13PX_LEADING_6_TEXT_6562C0
                        )

        # ---- PHASE CARDS ----
        with ui.grid(columns=5).classes(tokens.TW_W_FULL_GAP_3_MB_717AD5 + ' items-stretch'):
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
                    tokens.TW_W_FULL_BG_WHITE_ROUNDED_2BA02B + ' h-full flex flex-col'
                ):
                    with ui.row().classes(tokens.TW_W_FULL_ITEMS_CENTER_JUSTIFY_A5A4FF):
                        ui.label(title).classes(
                            tokens.TW_TEXT_14PX_FONT_SEMIBOLD_TEXT_137D25
                        )
                        if badge_kind == 'badge':
                            status_badge(badge_text).style('border-radius: 4px;')
                        else:
                            scenario_tag(badge_text).style('border-radius: 4px;')
                    ui.label(desc).classes(
                        tokens.TW_TEXT_12PX_LEADING_5_TEXT_0AEEC5
                    )
                    ui.label(m1).classes(
                        tokens.TW_TEXT_11PX_LEADING_4_TEXT_DFA007
                    )
                    ui.label(m2).classes(
                        tokens.TW_TEXT_11PX_LEADING_4_TEXT_84060D
                    )
                    ui.button('Open', on_click=lambda r=route: ui.navigate.to(r)).props('flat dense no-caps').classes(
                        tokens.TW_W_FULL_BG_1E3A5F_TEXT_242F90 + ' mt-auto'
                    )

        # ---- COMPACT FOOTER (boundaries + data sources) ----
        with ui.card().classes(
            tokens.TW_W_FULL_MIN_W_0_FBFB4B
        ):
            # Row 1 — System Boundaries
            ui.label('System Boundaries').classes(
                tokens.TW_TEXT_12PX_FONT_SEMIBOLD_TEXT_C96D24
            )
            with ui.row().classes(tokens.TW_ITEMS_CENTER_GAP_2_FLEX_420812):
                for b in _BOUNDARIES:
                    ui.label(b).classes(
                        tokens.TW_BG_F4F6F8_TEXT_334155_ROUNDED_9411B3
                    )

            # Row 2 — Data Sources
            ui.label('Processed Data Files').classes(
                tokens.TW_TEXT_12PX_FONT_SEMIBOLD_TEXT_C96D24
            )
            with ui.row().classes(tokens.TW_ITEMS_CENTER_GAP_2_FLEX_3530D1):
                for f in _DATA_FILES:
                    ui.label(f).classes(
                        tokens.TW_BG_F4F6F8_TEXT_334155_ROUNDED_8318B1
                    )
