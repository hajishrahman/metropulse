import plotly.graph_objects as go
from nicegui import ui

from components import tokens
from data import registry
from components.ui_elements import analytics_card, kpi_strip, page_content, plotly_chart, plotly_gridlines, state_card, scenario_tag, status_badge
from components.time_utils import hhmmss_to_sec, sec_to_hhmmss

ui.add_head_html('<style>.modebar-container { display: none !important; }</style>', shared=True)

def hex_to_rgba(hex_color: str, alpha: float = 0.2) -> str:
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return f'rgba({r},{g},{b},{alpha})'


def _chart_legend(items: list[tuple[str, str]]) -> None:
    with ui.row().classes(tokens.TW_ITEMS_CENTER_GAP_3_FLEX_67B820):
        for label, color in items:
            with ui.row().classes(tokens.TW_ITEMS_CENTER_GAP_2_145735):
                ui.element('span').classes(tokens.TW_INLINE_BLOCK_W_2_H_BAF72A).style(
                    f'background-color: {color}'
                )
                ui.label(label).classes(tokens.TW_TEXT_11PX_LEADING_4_TEXT_966011)

def build_line_chart(title: str, yaxis_title: str, traces_data: list) -> go.Figure:
    fig = go.Figure()
    for t in traces_data:
        fig.add_trace(go.Scatter(x=t['x'], y=t['y_p95'], mode='lines', line=dict(width=0, color=t['color']), showlegend=False, hoverinfo='skip'))
        fig.add_trace(go.Scatter(x=t['x'], y=t['y_p5'], mode='lines', line=dict(width=0, color=t['color']), fill='tonexty', fillcolor=hex_to_rgba(t['color'], 0.2), name=f"{t['name']} (p5-p95)", showlegend=False, hoverinfo='skip'))
        fig.add_trace(go.Scatter(x=t['x'], y=t['y_mean'], mode='lines+markers', line=dict(color=t['color'], width=2.5), name=t['name'], showlegend=False))
    fig.update_layout(title=None, xaxis_title='Experiment', yaxis_title=yaxis_title, autosize=True, template='plotly_white', margin=dict(t=16, b=52, l=56, r=28), font=dict(family=tokens.FONT_FAMILY, color=tokens.TEXT_PRIMARY), legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1), plot_bgcolor=tokens.PANEL, paper_bgcolor=tokens.PANEL)
    plotly_gridlines(fig)
    fig.update_xaxes(automargin=True)
    fig.update_yaxes(automargin=True)
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
        line=dict(color=tokens.COOL_GREY, width=14),
            showlegend=False,
                    hovertemplate=(f"Trip: {row['trip_id']}<br>Rake: {r}<br>Scheduled: "
                       f"{sec_to_hhmmss(dep)} - {sec_to_hhmmss(arr)}<extra></extra>"),
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
        if delay_min > 1:
            color = tokens.RED_TEXT
            status = 'LATE'
        else:
            color = tokens.BLUE
            status = 'ON TIME'
        fig.add_trace(go.Scatter(
            x=[dep, arr], y=[y, y], mode='lines',
            line=dict(color=color, width=6),
            showlegend=False,
            hovertemplate=(
                f"<b>{row['trip_id']}</b><br>"
                f"Rake: {r}<br>"
                f"Scheduled: {sec_to_hhmmss(int(row['sched_dep_sec']))} - {sec_to_hhmmss(int(row['sched_arr_sec']))}<br>"
                f"Simulated: {sec_to_hhmmss(dep)} - {sec_to_hhmmss(arr)}<br>"
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
        font=dict(family=tokens.FONT_MONO, color=tokens.TEXT_SECONDARY),
        hoverlabel=dict(font=dict(family=tokens.FONT_MONO)),
        xaxis=dict(
            tickvals=tick_secs,
            ticktext=[sec_to_hhmmss(s)[:5] for s in tick_secs],
            range=[tick_start, tick_end],
            title='Time (IST)',
            gridcolor=tokens.BORDER,
            zeroline=False,
            automargin=True,
        ),
        yaxis=dict(
            tickvals=list(rake_y.values()),
            ticktext=list(rake_y.keys()),
            title='Rake',
            autorange='reversed',
            gridcolor=tokens.BORDER,
            zeroline=False,
            automargin=True,
        ),
        margin=dict(l=72, r=28, t=20, b=60),
        plot_bgcolor=tokens.PANEL,
        paper_bgcolor=tokens.PANEL,
    )
    return fig


def render():
    from components.navigation import create_sidebar
    main = create_sidebar(active_phase='phase2')
    page_content(main)

    kpis_res = registry.load_simulation_kpis()
    timeline_res = registry.load_simulation_timeline()

    with main:
        if kpis_res['status'] != 'ok' or timeline_res['status'] != 'ok':
            msg = kpis_res['message'] if kpis_res['status'] != 'ok' else timeline_res['message']
            state_card(kpis_res['status'] if kpis_res['status'] != 'ok' else timeline_res['status'], 'Data', msg).props('flat').classes(tokens.TW_SHADOW_NONE_AD47D1)
            return

        kpis_data = kpis_res['data']
        timeline_df = timeline_res['data']
        # (removed: KPIs now read from head_exps inside refresh_kpis)
        mc_agg = kpis_data['monte_carlo_aggregate']
        exps = list(mc_agg)
        colors = [tokens.NAVY, tokens.BLUE, tokens.COOL_GREY]

        # Header
        with ui.column().classes(tokens.TW_W_FULL_MIN_W_0_1A781D):
            ui.label('Operational Simulation').classes(tokens.TW_TEXT_22PX_LEADING_7_FONT_4694EF)
            ui.label(f"Monte Carlo delay propagation across {kpis_data['metadata']['n_seeds_monte_carlo']} seeds and {len(exps)} experiments.").classes(tokens.TW_TEXT_14PX_LEADING_5_TEXT_AE0775)
        # Experiment key
        ui.label('Experiments: ' + ', '.join(exps) + ' (increasing delay injection)').classes(tokens.TW_TEXT_12PX_LEADING_4_TEXT_98E62F)

        # 3. Synthetic Banner (moved to bottom, see end of render)

        # Shared experiment selector â€” drives KPIs + Gantt
        head_exps = kpis_data['headline_seed_run']
        exp_selector = ui.select({exp: exp for exp in exps}, value=exps[-1], label='Experiment').props('outlined dense options-dense').classes(
            tokens.TW_W_FULL_MAX_W_240PX_4343F0
        )

        # 4. Headline KPIs â€” live
        kpi_row = ui.grid(columns=3).classes(tokens.TW_W_FULL_MIN_W_0_DB4F2F)
        def refresh_kpis():
            kpi_row.clear()
            key = exp_selector.value
            h = head_exps[key]
            seed = kpis_data['metadata']['headline_seed']
            kpi_strip(3, [
                    (( '±1 min On-Time', f"{h['on_time_1min']['on_time_pct']}%"), {'footnote': f'{key} | seed {seed}'}),
                    (( '±3 min On-Time', f"{h['on_time_3min']['on_time_pct']}%"), {'footnote': f'{key} | seed {seed}'}),
                    (( 'Total Propagated Delay', f"{h['total_propagated_delay']['total_propagated_delay_min']} min"), {'footnote': f'{key} | seed {seed}'}),
                ], flat=True, container=kpi_row)
        refresh_kpis()

        # 5. 2x2 Chart Grid
        on_time_traces = build_on_time_traces(mc_agg, exps, colors)
        fig1 = build_line_chart('On-Time Performance by Threshold', 'On-Time %', on_time_traces)
        fig2 = build_line_chart('Delay Propagation Rate', 'Propagation %', build_single_trace(mc_agg, exps, 'propagation_pct', 'Propagation %', colors[1]))
        fig3 = build_headway_chart(build_single_trace(mc_agg, exps, 'headway_actual_violations', 'Headway Violations', colors[2]))
        fig4 = build_line_chart('Total Propagated Delay', 'Delay (min)', build_single_trace(mc_agg, exps, 'total_propagated_delay_min', 'Total Propagated Delay', colors[1]))

        with ui.grid(columns=2).classes(tokens.TW_W_FULL_MIN_W_0_F1D81E):
            with analytics_card('On-Time Performance by Threshold', header_content=lambda: _chart_legend([
                (trace['name'], trace['color']) for trace in on_time_traces
            ])) as panel:
                panel.props('flat').classes(tokens.TW_SHADOW_NONE_AD47D1)
                plotly_chart(fig1, tokens.PLOTLY_H_400)
            with analytics_card('Delay Propagation Rate', header_content=lambda: _chart_legend([('Propagation', colors[1])])) as panel:
                panel.props('flat').classes(tokens.TW_SHADOW_NONE_AD47D1)
                plotly_chart(fig2, tokens.PLOTLY_H_400)
            with analytics_card('Actual Headway Violations', header_content=lambda: _chart_legend([('Violations', colors[2])])) as panel:
                panel.props('flat').classes(tokens.TW_SHADOW_NONE_AD47D1)
                plotly_chart(fig3, tokens.PLOTLY_H_400)
            with analytics_card('Total Propagated Delay', header_content=lambda: _chart_legend([('Propagated delay', colors[1])])) as panel:
                panel.props('flat').classes(tokens.TW_SHADOW_NONE_AD47D1)
                plotly_chart(fig4, tokens.PLOTLY_H_400)

        # 6. Gantt â€” overlay ghost bars
        gantt_container = None
        def refresh_gantt(e=None):
            if gantt_container is None:
                return
            gantt_container.clear()
            with gantt_container:
                plotly_chart(build_gantt_overlay(exp_selector.value, timeline_df), tokens.PLOTLY_H_600)
        with analytics_card('Gantt - Scheduled vs Simulated') as panel:
            panel.props('flat').classes(tokens.TW_SHADOW_NONE_AD47D1)
            with ui.row().classes(tokens.TW_W_FULL_ITEMS_CENTER_GAP_C12AFB):
                with ui.row().classes(tokens.TW_ITEMS_CENTER_GAP_2_145735):
                    ui.element('span').classes(tokens.TW_INLINE_BLOCK_W_3_H_6755F2).style(tokens.STATUS_MARKER_SCHEDULED)
                    ui.label('Scheduled (ghost)').classes(tokens.TW_TEXT_11PX_TEXT_64748B_FONT_709A50)
                with ui.row().classes(tokens.TW_ITEMS_CENTER_GAP_2_145735):
                    ui.element('span').classes(tokens.TW_INLINE_BLOCK_W_3_H_6755F2).style(tokens.STATUS_MARKER_ON_TIME)
                    ui.label('Actual — on time').classes(tokens.TW_TEXT_11PX_TEXT_64748B_FONT_709A50)
                with ui.row().classes(tokens.TW_ITEMS_CENTER_GAP_2_145735):
                    ui.element('span').classes(tokens.TW_INLINE_BLOCK_W_3_H_6755F2).style(tokens.STATUS_MARKER_ADVERSE)
                    ui.label('Actual — departure variance > 1 min').classes(tokens.TW_TEXT_11PX_TEXT_64748B_FONT_709A50)
            ui.label('Ghost bars show the Phase 1 schedule; colored bars show simulated actuals for the selected experiment.').classes(
                tokens.TW_TEXT_11PX_TEXT_181D1F_60_BD4C3D
            )
            gantt_container = ui.column().classes(tokens.PLOTLY_CONTAINER)
            with gantt_container:
                plotly_chart(build_gantt_overlay(exp_selector.value, timeline_df), tokens.PLOTLY_H_600)

        exp_selector.on_value_change(lambda e: (refresh_kpis(), refresh_gantt()))

        # Methodology & Limitations
        with ui.expansion('Methodology & Honest Limitations', value=False).classes(
            tokens.TW_W_FULL_MIN_W_0_1C8ED6
        ):
            with analytics_card('Simulation methodology') as panel:
                panel.props('flat').classes(tokens.TW_SHADOW_NONE_AD47D1)
                ui.markdown(
                    '**Source headways:** Timetable headways are source-data facts; observed increases in actual violations are simulation results.'
                ).classes(tokens.TW_TEXT_14PX_LEADING_5_TEXT_400C9D)
                ui.markdown(
                    '**Turnaround caveat:** Propagation uses a flat turnaround and is not deadhead-aware. Feasibility depends on the loaded schedule and observed slack.'
                ).classes(tokens.TW_TEXT_14PX_LEADING_5_TEXT_400C9D)
                ui.markdown(
                    '**On-time model property:** The displayed threshold result is a model property, not an operational guarantee.'
                ).classes(tokens.TW_TEXT_14PX_LEADING_5_TEXT_400C9D)
        # Footer: synthetic badge + banner
        with ui.row().classes(tokens.TW_W_FULL_ITEMS_CENTER_GAP_0992AB):
            scenario_tag('SYNTHETIC')
        with analytics_card('Synthetic model limitation') as panel:
            panel.props('flat').classes(tokens.TW_SHADOW_NONE_AD47D1)
            with ui.row().classes(tokens.TW_W_FULL_ITEMS_START_GAP_550770):
                status_badge('WARNING')
                ui.label('Results describe model behaviour under a synthetic delay assumption, not real KMRL performance.').classes(
                    tokens.TW_MIN_W_0_TEXT_14PX_72F108
                )
