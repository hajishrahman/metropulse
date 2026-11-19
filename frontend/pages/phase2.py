import plotly.graph_objects as go
from nicegui import ui
from data import registry
from components.ui_elements import analytics_card, kpi_card, scenario_tag, state_card, status_badge
from components.time_utils import hhmmss_to_sec, sec_to_hhmmss

ui.add_head_html('<style>.modebar-container { display: none !important; }</style>', shared=True)

def hex_to_rgba(hex_color: str, alpha: float = 0.2) -> str:
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return f'rgba({r},{g},{b},{alpha})'


def _chart_legend(items: list[tuple[str, str]]) -> None:
    with ui.row().classes('items-center gap-3 flex-wrap'):
        for label, color in items:
            with ui.row().classes('items-center gap-2'):
                ui.element('span').classes('inline-block w-2 h-2 rounded-full').style(
                    f'background-color: {color}'
                )
                ui.label(label).classes('text-[11px] leading-4 text-[#64748B]')

def build_line_chart(title: str, yaxis_title: str, traces_data: list) -> go.Figure:
    fig = go.Figure()
    for t in traces_data:
        fig.add_trace(go.Scatter(x=t['x'], y=t['y_p95'], mode='lines', line=dict(width=0, color=t['color']), showlegend=False, hoverinfo='skip'))
        fig.add_trace(go.Scatter(x=t['x'], y=t['y_p5'], mode='lines', line=dict(width=0, color=t['color']), fill='tonexty', fillcolor=hex_to_rgba(t['color'], 0.2), name=f"{t['name']} (p5-p95)", showlegend=False, hoverinfo='skip'))
        fig.add_trace(go.Scatter(x=t['x'], y=t['y_mean'], mode='lines+markers', line=dict(color=t['color'], width=2.5), name=t['name'], showlegend=False))
    fig.update_layout(title=None, xaxis_title='Experiment', yaxis_title=yaxis_title, autosize=True, template='plotly_white', margin=dict(t=16, b=52, l=56, r=28), font=dict(family='IBM Plex Sans, sans-serif', color='#1E293B'), legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1), plot_bgcolor='white', paper_bgcolor='white')
    fig.update_xaxes(gridcolor='#E2E8F0', zeroline=False, automargin=True)
    fig.update_yaxes(gridcolor='#E2E8F0', zeroline=False, automargin=True)
    return fig

def build_on_time_traces(mc_agg: dict, exps: list, colors: list) -> list:
    metrics = [
        ('on_time_5min', '±5 min On-Time', colors[0]),
        ('on_time_3min', '±3 min On-Time', colors[1]),
        ('on_time_1min', '±1 min On-Time', colors[2]),
    ]
    return [{
        'name': name,
        'x': exps,
        'y_mean': [mc_agg[exp][key]['mean'] for exp in exps],
        'y_p5': [mc_agg[exp][key]['p5'] for exp in exps],
        'y_p95': [mc_agg[exp][key]['p95'] for exp in exps],
        'color': color,
    } for key, name, color in metrics]

def build_single_trace(mc_agg: dict, exps: list, metric_key: str, name: str, color: str) -> list:
    return [{'name': name, 'x': exps, 'y_mean': [mc_agg[exp][metric_key]['mean'] for exp in exps], 'y_p5': [mc_agg[exp][metric_key]['p5'] for exp in exps], 'y_p95': [mc_agg[exp][metric_key]['p95'] for exp in exps], 'color': color}]


def build_headway_chart(traces_data: list) -> go.Figure:
    fig = build_line_chart('Actual Headway Violations', 'Violations', traces_data)
    fig.update_yaxes(rangemode='tozero')
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
        line=dict(color="#94A3B8", width=14),
            showlegend=False,
            hovertemplate=(f"Trip: {row['trip_id']}<br>Rake: {r}<br>Scheduled: "
                           f"{sec_to_hhmmss(dep)}â€“{sec_to_hhmmss(arr)}<extra></extra>"),
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
        delay_min = float(row['dep_delay_sec']) / 60.0
        if delay_min > 1:
            color = '#B3261E'
            status = 'DELAYED'
        else:
            color = '#0D9488'
            status = 'ON TIME'
        fig.add_trace(go.Scatter(
            x=[dep, arr], y=[y, y], mode='lines',
            line=dict(color=color, width=6),
            showlegend=False,
            hovertemplate=(
                f"<b>{row['trip_id']}</b><br>"
                f"Rake: {r}<br>"
                f"Scheduled: {sec_to_hhmmss(int(row['sched_dep_sec']))}â€“{sec_to_hhmmss(int(row['sched_arr_sec']))}<br>"
                f"Simulated: {sec_to_hhmmss(dep)}â€“{sec_to_hhmmss(arr)}<br>"
                f"Delta: {delay_min:.1f} min<br>Status: {status}<extra></extra>"
            ),
        ))

    observed_times = (
        [hhmmss_to_sec(value) for value in sched['departure'].tolist() + sched['arrival'].tolist()]
        + actual['actual_dep_sec'].astype(int).tolist()
        + actual['actual_arr_sec'].astype(int).tolist()
    )
    tick_start = (min(observed_times) // 7200) * 7200
    tick_end = ((max(observed_times) + 7199) // 7200) * 7200
    tick_secs = list(range(tick_start, tick_end + 1, 7200))
    fig.update_layout(
        showlegend=False,
        font=dict(family='IBM Plex Mono, monospace', color='#334155'),
        hoverlabel=dict(font=dict(family='IBM Plex Mono, monospace')),
        xaxis=dict(
            tickvals=tick_secs,
            ticktext=[sec_to_hhmmss(s)[:5] for s in tick_secs],
            range=[tick_start, tick_end],
            title='Time (IST)',
            gridcolor='#E2E8F0',
            zeroline=False,
            automargin=True,
        ),
        yaxis=dict(
            tickvals=list(rake_y.values()),
            ticktext=list(rake_y.keys()),
            title='Rake',
            autorange='reversed',
            gridcolor='#E2E8F0',
            zeroline=False,
            automargin=True,
        ),
        margin=dict(l=72, r=28, t=20, b=60),
        plot_bgcolor='white',
        paper_bgcolor='white',
    )
    return fig


def render():
    from components.navigation import create_sidebar
    main = create_sidebar(active_phase='phase2')
    main.classes('w-full min-w-0 p-6')

    kpis_res = registry.load_simulation_kpis()
    timeline_res = registry.load_simulation_timeline()

    with main:
        if kpis_res['status'] != 'ok' or timeline_res['status'] != 'ok':
            msg = kpis_res['message'] if kpis_res['status'] != 'ok' else timeline_res['message']
            state_card(kpis_res['status'] if kpis_res['status'] != 'ok' else timeline_res['status'], 'Data', msg).props('flat').classes('shadow-none')
            return

        kpis_data = kpis_res['data']
        timeline_df = timeline_res['data']
        # (removed: KPIs now read from head_exps inside refresh_kpis)
        mc_agg = kpis_data['monte_carlo_aggregate']
        exps = list(mc_agg)
        colors = ['#1E3A5F', '#0D9488', '#94A3B8']

        # Header
        with ui.column().classes('w-full min-w-0 gap-1 mb-2'):
            ui.label('Operational Simulation').classes("text-[22px] leading-7 font-bold text-[#0F172A] font-['IBM_Plex_Sans',_sans-serif]")
            ui.label(f"Monte Carlo delay propagation across {kpis_data['metadata']['n_seeds_monte_carlo']} seeds and {len(exps)} experiments.").classes("text-[14px] leading-5 text-[#334155] font-['IBM_Plex_Sans',_sans-serif]")
        # Experiment key
        ui.label('Experiments: ' + ', '.join(exps) + ' (increasing delay injection)').classes('text-[12px] leading-4 text-[#64748B] mb-4')

        # 3. Synthetic Banner (moved to bottom, see end of render)

        # Shared experiment selector â€” drives KPIs + Gantt
        head_exps = kpis_data['headline_seed_run']
        exp_selector = ui.select({exp: exp for exp in exps}, value=exps[-1], label='Experiment').props('outlined dense options-dense').classes(
            'w-full max-w-[240px] bg-white rounded-[4px] border border-[#E2E8F0] shadow-none mb-2'
        )

        # 4. Headline KPIs â€” live
        kpi_row = ui.grid(columns=3).classes('w-full min-w-0 tabular-nums gap-4 mb-4')
        def refresh_kpis():
            kpi_row.clear()
            key = exp_selector.value
            h = head_exps[key]
            seed = kpis_data['metadata']['headline_seed']
            with kpi_row:
                kpi_card('±1 min On-Time', f"{h['on_time_1min']['on_time_pct']}%", footnote=f'{key} | seed {seed}').props('flat').classes('shadow-none')
                kpi_card('±3 min On-Time', f"{h['on_time_3min']['on_time_pct']}%", footnote=f'{key} | seed {seed}').props('flat').classes('shadow-none')
                kpi_card('Total Propagated Delay', f"{h['total_propagated_delay']['total_propagated_delay_min']} min", footnote=f'{key} | seed {seed}').props('flat').classes('shadow-none')
        refresh_kpis()

        # 5. 2x2 Chart Grid
        on_time_traces = build_on_time_traces(mc_agg, exps, colors)
        fig1 = build_line_chart('On-Time Performance by Threshold', 'On-Time %', on_time_traces)
        fig2 = build_line_chart('Delay Propagation Rate', 'Propagation %', build_single_trace(mc_agg, exps, 'propagation_pct', 'Propagation %', colors[1]))
        fig3 = build_headway_chart(build_single_trace(mc_agg, exps, 'headway_actual_violations', 'Headway Violations', colors[2]))
        fig4 = build_line_chart('Total Propagated Delay', 'Delay (min)', build_single_trace(mc_agg, exps, 'total_propagated_delay_min', 'Total Propagated Delay', colors[1]))

        with ui.grid(columns=2).classes('w-full min-w-0 gap-4 mb-4'):
            with analytics_card('On-Time Performance by Threshold', header_content=lambda: _chart_legend([
                (trace['name'], trace['color']) for trace in on_time_traces
            ])) as panel:
                panel.props('flat').classes('shadow-none')
                ui.plotly(fig1).classes('w-full min-w-0 h-[400px]')
            with analytics_card('Delay Propagation Rate', header_content=lambda: _chart_legend([('Propagation', colors[1])])) as panel:
                panel.props('flat').classes('shadow-none')
                ui.plotly(fig2).classes('w-full min-w-0 h-[400px]')
            with analytics_card('Actual Headway Violations', header_content=lambda: _chart_legend([('Violations', colors[2])])) as panel:
                panel.props('flat').classes('shadow-none')
                ui.plotly(fig3).classes('w-full min-w-0 h-[400px]')
            with analytics_card('Total Propagated Delay', header_content=lambda: _chart_legend([('Propagated delay', colors[1])])) as panel:
                panel.props('flat').classes('shadow-none')
                ui.plotly(fig4).classes('w-full min-w-0 h-[400px]')

        # 6. Gantt â€” overlay ghost bars
        gantt_container = None
        def refresh_gantt(e=None):
            if gantt_container is None:
                return
            gantt_container.clear()
            with gantt_container:
                ui.plotly(build_gantt_overlay(exp_selector.value, timeline_df)).classes(
                    'w-full min-w-0 h-[600px]'
                )
        with analytics_card('Gantt - Scheduled vs Simulated') as panel:
            panel.props('flat').classes('shadow-none')
            with ui.row().classes('w-full items-center gap-4 mb-4'):
                with ui.row().classes('items-center gap-2'):
                    ui.element('span').classes('inline-block w-3 h-3 rounded-sm').style('background-color: #94A3B8')
                    ui.label('Scheduled (ghost)').classes("text-[11px] text-[#64748B] font-['IBM_Plex_Sans',_sans-serif]")
                with ui.row().classes('items-center gap-2'):
                    ui.element('span').classes('inline-block w-3 h-3 rounded-sm').style('background-color: #0D9488')
                    ui.label('Actual — on time').classes("text-[11px] text-[#64748B] font-['IBM_Plex_Sans',_sans-serif]")
                with ui.row().classes('items-center gap-2'):
                    ui.element('span').classes('inline-block w-3 h-3 rounded-sm').style('background-color: #B3261E')
                    ui.label('Actual — delayed > 1 min').classes("text-[11px] text-[#64748B] font-['IBM_Plex_Sans',_sans-serif]")
            ui.label('Ghost bars show the Phase 1 schedule; colored bars show simulated actuals for the selected experiment.').classes(
                "text-[11px] text-[#181d1f]/60 mb-3 font-['IBM_Plex_Sans',_sans-serif]"
            )
            gantt_container = ui.column().classes('w-full min-w-0')
            with gantt_container:
                ui.plotly(build_gantt_overlay(exp_selector.value, timeline_df)).classes(
                    'w-full min-w-0 h-[600px]'
                )

        exp_selector.on_value_change(lambda e: (refresh_kpis(), refresh_gantt()))

        # Methodology & Limitations
        with ui.expansion('Methodology & Honest Limitations', value=False).classes(
            "w-full min-w-0 bg-white rounded-[6px] shadow-none border border-[#E2E8F0] mb-4"
        ):
            with analytics_card('Simulation methodology') as panel:
                panel.props('flat').classes('shadow-none')
                ui.markdown(
                    '**Source headways:** Timetable headways are source-data facts; observed increases in actual violations are simulation results.'
                ).classes("text-[14px] leading-5 text-[#334155]")
                ui.markdown(
                    '**Turnaround caveat:** Propagation uses a flat turnaround and is not deadhead-aware. Feasibility depends on the loaded schedule and observed slack.'
                ).classes("text-[14px] leading-5 text-[#334155]")
                ui.markdown(
                    '**On-time model property:** The displayed threshold result is a model property, not an operational guarantee.'
                ).classes("text-[14px] leading-5 text-[#334155]")
        # Footer: synthetic badge + banner
        with ui.row().classes('w-full items-center gap-3 mb-2'):
            scenario_tag('SYNTHETIC').style('border-radius: 4px; border: 1px solid #E2E8F0;')
        with analytics_card('Synthetic model limitation') as panel:
            panel.props('flat').classes('shadow-none')
            with ui.row().classes('w-full items-start gap-2'):
                status_badge('WARNING').style('border-radius: 4px; border: 1px solid #E2E8F0;')
                ui.label('Results describe model behaviour under a synthetic delay assumption, not real KMRL performance.').classes(
                    'min-w-0 text-[14px] leading-5 text-[#334155]'
                )
