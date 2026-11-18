import plotly.graph_objects as go
from nicegui import ui
from data import registry
from components.ui_elements import kpi_card, state_card
from components.time_utils import hhmmss_to_sec, sec_to_hhmmss

ui.add_head_html('<style>.modebar-container { display: none !important; }</style>', shared=True)

def hex_to_rgba(hex_color: str, alpha: float = 0.2) -> str:
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return f'rgba({r},{g},{b},{alpha})'

def build_line_chart(title: str, yaxis_title: str, traces_data: list) -> go.Figure:
    fig = go.Figure()
    for t in traces_data:
        fig.add_trace(go.Scatter(x=t['x'], y=t['y_p95'], mode='lines', line=dict(width=0, color=t['color']), showlegend=False, hoverinfo='skip'))
        fig.add_trace(go.Scatter(x=t['x'], y=t['y_p5'], mode='lines', line=dict(width=0, color=t['color']), fill='tonexty', fillcolor=hex_to_rgba(t['color'], 0.2), name=f"{t['name']} (p5-p95)", showlegend=False, hoverinfo='skip'))
        fig.add_trace(go.Scatter(x=t['x'], y=t['y_mean'], mode='lines+markers', line=dict(color=t['color'], width=2.5), name=t['name']))
    fig.update_layout(title=title, xaxis_title='Experiment', yaxis_title=yaxis_title, autosize=True, template='plotly_white', margin=dict(t=80, b=40, l=40, r=20), font=dict(family='IBM Plex Sans, sans-serif', color='#181d1f'), legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1))
    return fig

def build_on_time_traces(mc_agg: dict, exps: list, colors: list) -> list:
    metrics = [('on_time_5min', '±5 On-Time', colors[0]), ('on_time_3min', '±3 On-Time', colors[1]), ('on_time_1min', '±1 On-Time', colors[2])]
    return [{'name': name, 'x': exps, 'y_mean': [mc_agg[exp][key]['mean'] for exp in exps], 'y_p5': [mc_agg[exp][key]['p5'] for exp in exps], 'y_p95': [mc_agg[exp][key]['p95'] for exp in exps], 'color': color} for key, name, color in metrics]

def build_single_trace(mc_agg: dict, exps: list, metric_key: str, name: str, color: str) -> list:
    return [{'name': name, 'x': exps, 'y_mean': [mc_agg[exp][metric_key]['mean'] for exp in exps], 'y_p5': [mc_agg[exp][metric_key]['p5'] for exp in exps], 'y_p95': [mc_agg[exp][metric_key]['p95'] for exp in exps], 'color': color}]


def build_headway_chart(traces_data: list) -> go.Figure:
    fig = build_line_chart('Actual Headway Violations', 'Violations', traces_data)
    fig.update_yaxes(rangemode='tozero')
    fig.add_hline(y=3, line=dict(color='#94A3B8', width=1, dash='dash'),
                  annotation_text='GTFS source baseline (3)',
                  annotation_position='top right',
                  annotation_font=dict(size=11, color='#64748B'))
    return fig


def build_gantt_overlay(experiment: str, timeline_df) -> go.Figure:
    """Scheduled ghost bars (grey, thin) behind actual bars (colored, thicker), by rake."""
    sched_res = registry.load_schedule()
    if sched_res['status'] != 'ok':
        return go.Figure()

    sched = sched_res['data']
    actual = timeline_df[timeline_df['experiment'] == experiment]

    rakes = sorted(sched['rake_id'].unique())
    rake_y = {r: i for i, r in enumerate(rakes)}

    fig = go.Figure()

    # Scheduled ghost bars
    for _, row in sched.iterrows():
        r = row['rake_id']
        if r not in rake_y:
            continue
        y = rake_y[r]
        dep = hhmmss_to_sec(row['departure'])
        arr = hhmmss_to_sec(row['arrival'])
        fig.add_trace(go.Scatter(
            x=[dep, arr], y=[y, y], mode='lines',
            line=dict(color="#5B7C99", width=14),
            showlegend=False, hoverinfo='skip',
        ))

    # Actual bars (overlay)
    for _, row in actual.iterrows():
        r = row['rake_id']
        if r not in rake_y:
            continue
        y = rake_y[r]
        dep = int(row['actual_dep_sec'])
        arr = int(row['actual_arr_sec'])
        delay_min = float(row['dep_delay_sec']) / 60.0
        color = '#B3261E' if delay_min > 1 else '#1B7A43'
        fig.add_trace(go.Scatter(
            x=[dep, arr], y=[y, y], mode='lines',
            line=dict(color=color, width=6),
            showlegend=False,
            hovertemplate=(
                f"<b>{row['trip_id']}</b><br>"
                f"Rake: {r}<br>"
                f"Sched dep: {sec_to_hhmmss(int(row['sched_dep_sec']))}<br>"
                f"Actual dep: {sec_to_hhmmss(dep)}<br>"
                f"Delay: {delay_min:.1f} min<extra></extra>"
            ),
        ))

    tick_secs = list(range(5 * 3600, 25 * 3600 + 1, 2 * 3600))
    fig.update_layout(
        showlegend=False,
        xaxis=dict(
            tickvals=tick_secs,
            ticktext=[sec_to_hhmmss(s)[:5] for s in tick_secs],
            title='Time (IST)',
            gridcolor='#E2E8F0',
            zeroline=False,
        ),
        yaxis=dict(
            tickvals=list(rake_y.values()),
            ticktext=list(rake_y.keys()),
            title='Rake',
            autorange='reversed',
            gridcolor='#E2E8F0',
            zeroline=False,
        ),
        margin=dict(l=60, r=20, t=20, b=60),
        plot_bgcolor='white',
        paper_bgcolor='white',
    )
    return fig


def render():
    from components.navigation import create_sidebar
    main = create_sidebar(active_phase='phase2')
    main.classes('p-6')

    kpis_res = registry.load_simulation_kpis()
    timeline_res = registry.load_simulation_timeline()

    with main:
        if kpis_res['status'] != 'ok' or timeline_res['status'] != 'ok':
            msg = kpis_res['message'] if kpis_res['status'] != 'ok' else timeline_res['message']
            state_card(kpis_res['status'] if kpis_res['status'] != 'ok' else timeline_res['status'], 'Data', msg)
            return

        kpis_data = kpis_res['data']
        timeline_df = timeline_res['data']
        # (removed: KPIs now read from head_exps inside refresh_kpis)
        mc_agg = kpis_data['monte_carlo_aggregate']
        exps = ['E1', 'E2', 'E3', 'E4']
        colors = ['#1B7A43', '#2196F3', '#FF9800', '#B3261E']

        # 2. Header
        with ui.column().classes('gap-1 mb-2'):
            ui.label('Phase 2 — Operational Simulation').classes("text-[28px] font-bold text-[#181d1f] font-['IBM_Plex_Sans',_sans-serif]")
            ui.label('Monte Carlo delay propagation analysis across 100 seeds and 4 experiments.').classes("text-[14px] text-[#181d1f]/70 font-['IBM_Plex_Sans',_sans-serif]")

        # Experiment key
        ui.label('Experiments: E1 = Low · E2 = Moderate · E3 = High · E4 = Stress (increasing delay injection)').classes("text-[12px] text-[#181d1f]/60 mb-4 font-['IBM_Plex_Sans',_sans-serif]")

        # 3. Synthetic Banner (moved to bottom, see end of render)

        # Shared experiment selector — drives KPIs + Gantt
        head_exps = kpis_data['headline_seed_run']
        exp_selector = ui.select(
            {
                'E1': 'E1 — Low (baseline)',
                'E2': 'E2 — Moderate',
                'E3': 'E3 — High',
                'E4': 'E4 — Stress',
            },
            value='E4',
            label='Experiment',
        ).props('outlined dense options-dense').classes(
            'w-[240px] bg-white rounded-[6px] mb-2'
        )

        # 4. Headline KPIs — live
        kpi_row = ui.grid(columns=3).classes('w-full gap-4 mb-6')
        def refresh_kpis():
            kpi_row.clear()
            key = exp_selector.value
            h = head_exps[key]
            with kpi_row:
                kpi_card('±1 On-Time', f"{h['on_time_1min']['on_time_pct']}%", footnote=f'{key} · seed 42')
                kpi_card('±3 On-Time', f"{h['on_time_3min']['on_time_pct']}%", footnote=f'{key} · seed 42')
                kpi_card('Total Propagated Delay', f"{h['total_propagated_delay']['total_propagated_delay_min']} min", footnote=f'{key} · seed 42')
        refresh_kpis()

        # 5. 2x2 Chart Grid
        fig1 = build_line_chart('On-Time Performance by Threshold', 'On-Time %', build_on_time_traces(mc_agg, exps, colors))
        fig2 = build_line_chart('Delay Propagation Rate', 'Propagation %', build_single_trace(mc_agg, exps, 'propagation_pct', 'Propagation %', colors[1]))
        fig3 = build_headway_chart(build_single_trace(mc_agg, exps, 'headway_actual_violations', 'Headway Violations', colors[3]))
        fig4 = build_line_chart('Total Propagated Delay', 'Delay (min)', build_single_trace(mc_agg, exps, 'total_propagated_delay_min', 'Total Propagated Delay', colors[2]))

        with ui.grid(columns=2).classes('w-full gap-4 mb-6'):
            with ui.card().classes("bg-white rounded-[6px] shadow-[0_1px_5px_rgba(0,0,0,0.2),0_2px_2px_rgba(0,0,0,0.14),0_3px_1px_-2px_rgba(0,0,0,0.12)] p-4"):
                ui.plotly(fig1).classes('w-full h-[400px] md:h-[400px] h-[320px]')
            with ui.card().classes("bg-white rounded-[6px] shadow-[0_1px_5px_rgba(0,0,0,0.2),0_2px_2px_rgba(0,0,0,0.14),0_3px_1px_-2px_rgba(0,0,0,0.12)] p-4"):
                ui.plotly(fig2).classes('w-full h-[400px] md:h-[400px] h-[320px]')
            with ui.card().classes("bg-white rounded-[6px] shadow-[0_1px_5px_rgba(0,0,0,0.2),0_2px_2px_rgba(0,0,0,0.14),0_3px_1px_-2px_rgba(0,0,0,0.12)] p-4"):
                ui.plotly(fig3).classes('w-full h-[400px] md:h-[400px] h-[320px]')
            with ui.card().classes("bg-white rounded-[6px] shadow-[0_1px_5px_rgba(0,0,0,0.2),0_2px_2px_rgba(0,0,0,0.14),0_3px_1px_-2px_rgba(0,0,0,0.12)] p-4"):
                ui.plotly(fig4).classes('w-full h-[400px] md:h-[400px] h-[320px]')

        # 6. Gantt — overlay ghost bars
        gantt_container = None
        def refresh_gantt(e=None):
            if gantt_container is None:
                return
            gantt_container.clear()
            with gantt_container:
                ui.plotly(build_gantt_overlay(exp_selector.value, timeline_df)).classes(
                    'w-full h-[600px] md:h-[600px] h-[480px]'
                )
        with ui.card().classes("w-full bg-white rounded-[6px] shadow-[0_1px_5px_rgba(0,0,0,0.2),0_2px_2px_rgba(0,0,0,0.14),0_3px_1px_-2px_rgba(0,0,0,0.12)] p-4 mb-6"):
            with ui.row().classes('w-full items-center justify-between mb-1'):
                ui.label('Gantt — Scheduled (ghost) vs Actuals (colored)').classes(
                    "text-[16px] font-semibold text-[#181d1f] font-['IBM_Plex_Sans',_sans-serif]"
                )
            with ui.row().classes('items-center gap-4 mb-4'):
                with ui.row().classes('items-center gap-2'):
                    ui.element('span').classes('inline-block w-3 h-3 rounded-full').style('background-color: #5B7C99')
                    ui.label('Scheduled (ghost)').classes("text-[11px] text-[#64748B] font-['IBM_Plex_Sans',_sans-serif]")
                with ui.row().classes('items-center gap-2'):
                    ui.element('span').classes('inline-block w-3 h-3 rounded-full').style('background-color: #1B7A43')
                    ui.label('Actual — on time').classes("text-[11px] text-[#64748B] font-['IBM_Plex_Sans',_sans-serif]")
                with ui.row().classes('items-center gap-2'):
                    ui.element('span').classes('inline-block w-3 h-3 rounded-full').style('background-color: #B3261E')
                    ui.label('Actual — delayed > 1 min').classes("text-[11px] text-[#64748B] font-['IBM_Plex_Sans',_sans-serif]")
            ui.label('Ghost bars show the Phase 1 schedule; colored bars show simulated actuals for the selected experiment.').classes(
                "text-[11px] text-[#181d1f]/60 mb-3 font-['IBM_Plex_Sans',_sans-serif]"
            )
            gantt_container = ui.column().classes('w-full')
            with gantt_container:
                ui.plotly(build_gantt_overlay(exp_selector.value, timeline_df)).classes(
                    'w-full h-[600px] md:h-[600px] h-[480px]'
                )

        exp_selector.on_value_change(lambda e: (refresh_kpis(), refresh_gantt()))

        # 7. Methodology & Limitations
        with ui.expansion('Methodology & Honest Limitations', value=False).classes(
            "w-full bg-white rounded-[6px] shadow-[0_1px_5px_rgba(0,0,0,0.2),0_2px_2px_rgba(0,0,0,0.14),0_3px_1px_-2px_rgba(0,0,0,0.12)] mb-6"
        ):
            with ui.column().classes('p-4 gap-2'):
                ui.markdown(
                    '**GTFS headway note:** The GTFS timetable contains 3 same-direction adjacent '
                    'departure pairs with 0s separation. These are source-data facts, not simulation '
                    'artifacts. Actual violations rising above 3 is the legitimate simulation signal.'
                ).classes("text-[13px] text-[#181d1f]/80 font-['IBM_Plex_Sans',_sans-serif]")
                ui.markdown(
                    '**300s Floor Caveat:** The propagation recurrence uses a flat 300-second turnaround '
                    'and is not deadhead-aware. It is physically feasible for the current schedule because '
                    'all 237 consecutive-trip pairs satisfy R6 deadhead requirements. This limitation '
                    'should be reconsidered if Phase 1 is re-solved with tighter cross-terminal gaps.'
                ).classes("text-[13px] text-[#181d1f]/80 font-['IBM_Plex_Sans',_sans-serif]")
                ui.markdown(
                    '**±5 On-Time Model Property:** ±5 on-time = 100% is a model property '
                    '(own-delay cap 300s + inclusive ±5 threshold), not an operational guarantee.'
                ).classes("text-[13px] text-[#181d1f]/80 font-['IBM_Plex_Sans',_sans-serif]")

        # Footer: synthetic badge + banner
        with ui.row().classes('w-full items-center gap-3 mb-2'):
            ui.label('SYNTHETIC').classes("bg-[#f4f6f8] text-[#181d1f] rounded-[6px] px-3 py-1 text-[12px] font-medium uppercase tracking-wider border border-[#e2e8f0] font-['IBM_Plex_Sans',_sans-serif]")
        with ui.row().classes('w-full mb-6'):
            ui.label('Results describe model behaviour under a synthetic delay assumption, not real KMRL performance.').classes("w-full bg-[#FFF8E1] text-[#8A6100] border-l-4 border-[#8A6100] p-3 rounded-[6px] text-[13px] font-medium font-['IBM_Plex_Sans',_sans-serif]")