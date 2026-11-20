# pages/phase5.py
# Disruption Response

from __future__ import annotations

import plotly.graph_objects as go
from nicegui import ui

from components import tokens

from components.ui_elements import (
    analytics_card,
    page_content,
    plotly_chart,
    plotly_gridlines,
    scenario_tag,
    state_card,
    status_badge,
)
from components.time_utils import hhmmss_to_sec, sec_to_hhmmss
from data.registry import (
    load_reschedule_diff,
    load_sensitivity_analysis,
    load_reschedule_scenario_a, load_reschedule_scenario_b,
    load_reschedule_scenario_c, load_reschedule_scenario_d,
    load_reschedule_scenario_e,
    load_disruption_scenario_a, load_disruption_scenario_b,
    load_disruption_scenario_c, load_disruption_scenario_d,
    load_disruption_scenario_e,
    load_schedule,
)

_COLORS = {
    'unchanged': tokens.NAVY,
    'forced': tokens.BLUE,
    'rebalanced': tokens.COOL_GREY,
    'dropped': tokens.RED_TEXT,
}

_SCEN_ORDER = ['a', 'b', 'c', 'd', 'e']


def _build_sensitivity_chart(rows):
    """rows = list of dicts with 'rakes_down', 'drops', 'status'."""
    x = [r['rakes_down'] for r in rows]
    y = [r['drops'] for r in rows]
    colors = [tokens.NAVY if r['drops'] == 0 else tokens.RED_TEXT for r in rows]
    tick_labels = {}
    for row in rows:
        tick_labels.setdefault(row['rakes_down'], []).append(row['letter'].upper())
    fig = go.Figure(go.Bar(
        x=x, y=y,
        marker_color=colors,
        text=[str(v) for v in y],
        textposition='outside',
        hovertemplate='Rakes down: %{x}<br>Drops: %{y}<extra></extra>',
    ))
    fig.update_layout(
        height=340,
        showlegend=False,
        font=dict(family=tokens.FONT_MONO, color=tokens.TEXT_SECONDARY),
        xaxis=dict(
            title='Rakes Down',
            tickmode='array',
            tickvals=sorted(tick_labels),
            ticktext=[f'{value} ({", ".join(tick_labels[value])})' for value in sorted(tick_labels)],
            showline=True, linewidth=1, linecolor=tokens.BORDER_STRONG,
            ticks='outside', ticklen=5, tickcolor=tokens.COOL_GREY,
            gridcolor=tokens.BORDER,
        ),
        yaxis=dict(
            title='Dropped Trips',
            showline=True, linewidth=1, linecolor=tokens.BORDER_STRONG,
            ticks='outside', ticklen=5, tickcolor=tokens.COOL_GREY,
            showgrid=True, gridcolor=tokens.BORDER,
        ),
        margin=dict(l=60, r=20, t=20, b=60),
        plot_bgcolor=tokens.PANEL,
        paper_bgcolor=tokens.PANEL,
        hoverlabel=dict(bgcolor=tokens.TEXT_PRIMARY, font=dict(color=tokens.WHITE)),
    )
    plotly_gridlines(fig, tokens.BORDER)
    return fig


def _build_gantt(scen_letter, reschedule_df, base_sched_df, disruption, diff_entry=None):
    """4-category Gantt: unchanged, forced, rebalanced, dropped."""
    if reschedule_df is None or reschedule_df.empty:
        return go.Figure()

    failed_rakes = set(disruption.get('rakes_down', []))
    base_lookup = base_sched_df.set_index('trip_id')[['rake_id']]
    dropped_ids = set()
    if diff_entry is not None and diff_entry.get('dropped_trip_ids'):
        dropped_ids = set(diff_entry.get('dropped_trip_ids', []))
    else:
        # infer drops: rows where rake_id == 'DROPPED'
        dropped_ids = set(
            reschedule_df.loc[
                reschedule_df['rake_id'].astype(str).str.upper() == 'DROPPED',
                'trip_id',
            ].astype(str).str.strip()
        )
        # fallback: base trips missing from reschedule entirely
        if not dropped_ids:
            dropped_ids = set(base_lookup.index) - set(reschedule_df['trip_id'])

    rakes = sorted(
        (set(reschedule_df['rake_id'].unique()) | set(base_sched_df['rake_id'].unique()))
        - {'DROPPED', 'CANCELLED'}
    )
    rake_y = {r: i for i, r in enumerate(rakes)}

    fig = go.Figure()

    # Group reschedule trips by category
    by_cat = {'unchanged': [], 'forced': [], 'rebalanced': []}
    for _, row in reschedule_df.iterrows():
        new_rake = str(row['rake_id']).strip()
        if new_rake in ('DROPPED', 'CANCELLED'):
            continue
        tid = row['trip_id']
        old_rake = base_lookup.loc[tid, 'rake_id'] if tid in base_lookup.index else None
        if old_rake is None:
            continue
        if old_rake == new_rake:
            by_cat['unchanged'].append(row)
        elif old_rake in failed_rakes:
            by_cat['forced'].append(row)
        else:
            by_cat['rebalanced'].append(row)

    for cat, color in (('unchanged', _COLORS['unchanged']),
                       ('rebalanced', _COLORS['rebalanced']),
                       ('forced', _COLORS['forced'])):
        xs, ys, cd = [], [], []
        for row in by_cat[cat]:
            dep_raw = str(row['departure']).strip()
            arr_raw = str(row['arrival']).strip()
            if not dep_raw or not arr_raw or dep_raw.lower() == 'nan' or arr_raw.lower() == 'nan':
                continue
            try:
                dep = int(hhmmss_to_sec(dep_raw))
                arr = int(hhmmss_to_sec(arr_raw))
            except (ValueError, TypeError):
                continue
            y = int(rake_y[row['rake_id']])
            xs.extend([dep, arr, None])
            ys.extend([y, y, None])
            cd.extend([[row['trip_id'], row['rake_id']]] * 2 + [None])
        if xs:
            fig.add_trace(go.Scatter(
                x=xs, y=ys, mode='lines',
                line=dict(color=color, width=14),
                showlegend=False,
                customdata=cd,
                hovertemplate=(
                    f"<b>%{{customdata[0]}}</b><br>"
                    f"Rake: %{{customdata[1]}}<br>"
                    f"Category: {cat}<extra></extra>"
                ),
            ))

    # Dropped trips — one Bar trace + one Scatter of ✕ markers
    y_cancel = int(len(rakes))
    dropped_xs, dropped_ys, dropped_hover = [], [], []
    bar_x, bar_base, bar_hover = [], [], []
    for tid in sorted(dropped_ids):
        tid = str(tid).strip()
        try:
            match = base_sched_df[base_sched_df['trip_id'].astype(str).str.strip() == tid]
            if match.empty:
                continue
            base_row = match.iloc[0]
            dep_raw = base_row.get('departure', base_row.get('departure_time'))
            arr_raw = base_row.get('arrival', base_row.get('arrival_time'))
            if dep_raw is None or arr_raw is None:
                continue
            dep_s = str(dep_raw).strip()
            arr_s = str(arr_raw).strip()
            if not dep_s or not arr_s or dep_s.lower() == 'nan' or arr_s.lower() == 'nan':
                continue
            dep = hhmmss_to_sec(dep_s) if isinstance(dep_raw, str) else int(dep_raw)
            arr = hhmmss_to_sec(arr_s) if isinstance(arr_raw, str) else int(arr_raw)
            dep = int(dep)
            arr = int(arr)
            if arr <= dep:
                continue
            bar_x.append(int(arr - dep))
            bar_base.append(int(dep))
            bar_hover.append(
                f"<b>{tid}</b><br>Status: CANCELLED<br>"
                f"Sched: {sec_to_hhmmss(dep)} - {sec_to_hhmmss(arr)}<extra></extra>"
            )
            dropped_xs.append(int((dep + arr) // 2))
            dropped_ys.append(int(y_cancel))
            dropped_hover.append(
                f"<b>{tid}</b><br>Status: CANCELLED<br>"
                f"Sched: {sec_to_hhmmss(dep)} - {sec_to_hhmmss(arr)}<extra></extra>"
            )
        except Exception:
            import logging
            logging.exception(f'Failed to plot dropped trip {tid}')
            continue

    if bar_x:
        fig.add_trace(go.Bar(
            x=bar_x,
            y=[int(y_cancel)] * len(bar_x),
            base=bar_base,
            orientation='h',
            marker=dict(
                color=_COLORS['dropped'],
                pattern=dict(shape='/', fgcolor=tokens.WHITE, fillmode='overlay'),
            ),
            customdata=bar_hover,
            hovertemplate='%{customdata}',
            showlegend=False,
        ))
        fig.add_trace(go.Scatter(
            x=dropped_xs,
            y=dropped_ys,
            mode='markers',
            marker=dict(symbol='x', size=10, color=tokens.WHITE,
                        line=dict(color=_COLORS['dropped'], width=2)),
            customdata=dropped_hover,
            hovertemplate='%{customdata}',
            showlegend=False,
        ))

    tick_secs = list(range(5 * 3600, 24 * 3600 + 1, 2 * 3600))
    fig.update_layout(
        height=600,
        showlegend=False,
        font=dict(family=tokens.FONT_MONO, color=tokens.TEXT_SECONDARY),
        xaxis=dict(
            tickvals=tick_secs,
            ticktext=[sec_to_hhmmss(s)[:5] for s in tick_secs],
            range=[17400, 86400],
            title='Time (IST)',
            gridcolor=tokens.BORDER,
            zeroline=False,
            automargin=True,
        ),
        yaxis=dict(
            tickvals=list(rake_y.values()) + [y_cancel],
            ticktext=list(rake_y.keys()) + ['  CANCELLED'],
            title='Rake',
            autorange='reversed',
            gridcolor=tokens.BORDER,
            zeroline=False,
            automargin=True,
            ticklabelposition='outside left',
        ),
        margin=dict(l=80, r=20, t=20, b=60),
        plot_bgcolor=tokens.PANEL,
        paper_bgcolor=tokens.PANEL,
        hoverlabel=dict(bgcolor=tokens.TEXT_PRIMARY, font=dict(color=tokens.WHITE)),
    )
    return fig


def _render_html_table(headers, rows, status_cols=()):
    def _cell(c, idx):
        if idx in status_cols:
            key = str(c).strip().upper()
            if key in tokens.STATUS_BADGE_CLASSES:
                return f'<span class="{tokens.STATUS_BADGE_CLASSES[key]}">{c}</span>'
            if key in ('WARN', 'WARNING'):
                return f'<span class="{tokens.BADGE_WARNING}">{c}</span>'
        return str(c)

    header_html = ''.join(
        f'<th class="{tokens.TABLE_HEADER_WIDE}">{h}</th>'
        for h in headers
    )
    rows_html = ''
    for r in rows:
        cells = ''.join(
            f'<td class="{tokens.TABLE_CELL_WIDE}">{_cell(c, i)}</td>'
            for i, c in enumerate(r)
        )
        rows_html += f'<tr class="{tokens.TABLE_ROW_HOVER}">{cells}</tr>'
    table = (
        f'<table class="{tokens.TABLE_BASE} min-w-0">'
        f'<thead>{header_html}</thead><tbody>{rows_html}</tbody></table>'
    )
    return f'<div class="{tokens.TABLE_WRAP_WIDE} min-w-0">{table}</div>'


def render():
    from components.navigation import create_sidebar
    main = create_sidebar(active_phase='phase5')
    page_content(main)

    diff_res = load_reschedule_diff()
    sens_res = load_sensitivity_analysis()
    sched_res = load_schedule()
    scen_res = {
        'a': load_reschedule_scenario_a(),
        'b': load_reschedule_scenario_b(),
        'c': load_reschedule_scenario_c(),
        'd': load_reschedule_scenario_d(),
        'e': load_reschedule_scenario_e(),
    }
    disrupt_res = {
        'a': load_disruption_scenario_a(),
        'b': load_disruption_scenario_b(),
        'c': load_disruption_scenario_c(),
        'd': load_disruption_scenario_d(),
        'e': load_disruption_scenario_e(),
    }

    with main:
        for name, res in (
            ('reschedule_diff.json', diff_res),
            ('sensitivity_analysis.json', sens_res),
            ('schedule.csv', sched_res),
        ):
            if res['status'] != 'ok':
                state_card(res['status'].replace('_', ' ').upper(), name, res['message']).props('flat').classes(tokens.TW_SHADOW_NONE_AD47D1)
                return
        for letter, res in scen_res.items():
            if res['status'] != 'ok':
                state_card(res['status'].replace('_', ' ').upper(), f'reschedule_scenario_{letter}.csv', res['message']).props('flat').classes(tokens.TW_SHADOW_NONE_AD47D1)
                return
        for letter, res in disrupt_res.items():
            if res['status'] != 'ok':
                state_card(res['status'].replace('_', ' ').upper(), f'scenario_{letter}.json', res['message']).props('flat').classes(tokens.TW_SHADOW_NONE_AD47D1)
                return

        diff = diff_res['data']
        sens = sens_res['data']['scenarios']
        base_sched = sched_res['data']
        scen_dfs = {k: v['data'] for k, v in scen_res.items()}
        disruptions = {k: v['data'] for k, v in disrupt_res.items()}

        # Header
        with ui.row().classes(tokens.TW_W_FULL_MIN_W_0_29D4FF):
            with ui.column().classes(tokens.TW_MIN_W_0_GAP_1_6364F0 + ' w-full'):
                ui.label('Disruption Response').classes(
                    tokens.TW_TEXT_22PX_LEADING_7_FONT_4694EF
                )
                ui.label('Counterfactual rescheduling under fleet capacity constraints.').classes(
                    tokens.TW_TEXT_14PX_LEADING_5_TEXT_AE0775
                )
            scenario_tag('COUNTERFACTUAL').style('border-radius: 4px;')

        # Build consolidated scenario rows for chart + table
        sens_by_letter = {s['id']: s for s in sens}
        base_rake_count = base_sched['rake_id'].nunique()
        a = diff['scenario_a']
        b = diff['scenario_b']
        scenario_rows = [
            {'letter': 'a', 'rakes_down': len(a['disruption']['rakes_down']),
             'drops': a['trips_dropped'], 'status': a['solver_status'],
             'gap_pct': a['gap_pct'],
             'recovery_pct': 100.0 if a['trips_dropped'] == 0 else round(100 * (a['trips_withdrawn'] - a['trips_dropped']) / max(a['trips_withdrawn'], 1), 2),
             'disruption_time': a['disruption']['time'],
             'active_rakes': a['rakes_active_count']},
            {'letter': 'b', 'rakes_down': len(diff['scenario_b']['disruption']['rakes_down']),
             'drops': b['trips_dropped'], 'status': b['solver_status'],
             'gap_pct': b['gap_pct'],
             'recovery_pct': round(100 * (b['trips_withdrawn'] - b['trips_dropped']) / max(b['trips_withdrawn'], 1), 2),
             'disruption_time': b['disruption']['time'],
             'active_rakes': b['rakes_active_count']},
        ]
        for s in sens:
            scenario_rows.append({
                'letter': s['id'],
                'rakes_down': s['rakes_failed'],
                'drops': s['drops'],
                'status': s['status'],
                'gap_pct': s['gap_pct'],
                'recovery_pct': s['recovery_pct'],
                'disruption_time': s['disruption_time'],
                'active_rakes': base_rake_count - s['rakes_failed'],
            })
        scenario_rows.sort(key=lambda r: r['letter'])

        observed_summary = '; '.join(
            f"{row['drops']} drops at {row['active_rakes']} active rakes"
            for row in sorted(scenario_rows, key=lambda row: row['active_rakes'], reverse=True)
        )
        with analytics_card('Observed model output'):
            ui.label(
                f'{observed_summary}. This is not a mathematical threshold.'
            ).classes(tokens.TW_TEXT_14PX_LEADING_5_TEXT_400C9D + ' tabular-nums')

        # Sensitivity chart
        chart_rows = sorted(scenario_rows, key=lambda r: r['rakes_down'])
        with analytics_card('Fleet Resilience Sensitivity') as card:
            card.props('flat').classes(
                tokens.TW_SHADOW_NONE_BG_WHITE_BORDER_00AA57
            )
            plotly_chart(_build_sensitivity_chart(chart_rows), tokens.PLOTLY_H_320)
            ui.label(
                'Observed disruption times: ' + '; '.join(
                    f"Scenario {row['letter'].upper()} ({row['disruption_time']})"
                    for row in scenario_rows
                ) + '. Compare results with disruption time in mind.'
            ).classes(
                tokens.TW_TEXT_12PX_LEADING_5_TEXT_C90136
            )

        # Comparison table
        with analytics_card('Scenario Comparison') as card:
            card.props('flat').classes(
                tokens.TW_SHADOW_NONE_BG_WHITE_BORDER_00AA57
            )
            table_rows = []
            for r in scenario_rows:
                table_rows.append([
                    r['letter'].upper(),
                    str(r['rakes_down']),
                    r['status'],
                    f"{r['gap_pct']:.2f}%",
                    str(r['drops']),
                    f"{r['recovery_pct']:.2f}%",
                    r['disruption_time'],
                ])
            ui.html(_render_html_table(
                ['Scenario', 'Rakes Down', 'Status', 'Gap %', 'Drops', 'Recovery %', 'Disruption Time'],
                table_rows,
                status_cols=(2,),
            )).classes(tokens.TW_W_FULL_BLOCK_954D40 + ' min-w-0')

        # Scenario A & B detail cards side by side
        # Helper: compute E's dropped IDs from CSV vs schedule
        base_trip_ids_for_e = set(base_sched['trip_id'].astype(str).str.strip())
        e_resched_dropped = set(
            scen_dfs['e'].loc[
                scen_dfs['e']['rake_id'].astype(str).str.upper() == 'DROPPED',
                'trip_id',
            ].astype(str).str.strip()
        )

        # Helper to render one unified scenario card
        def render_scenario_card(letter, s, extra_note=None, dropped_ids=None):
            with analytics_card(f'Scenario {letter.upper()}') as card:
                card.props('flat').classes(
                    tokens.TW_SHADOW_NONE_BG_WHITE_BORDER_9ACBE0
                )
                with ui.row().classes(tokens.TW_ITEMS_CENTER_GAP_2_MB_866593 + ' w-full min-w-0'):
                    ui.label(f'Scenario {letter.upper()}').classes(
                        tokens.TW_TEXT_16PX_FONT_SEMIBOLD_TEXT_D60850
                    )
                    status_badge(s['status'])
                    if letter == 'b' and s['drops'] != b_rescheduled_drops:
                        status_badge('WARNING')
                ui.label(f"Rakes failed: {', '.join(s['rake_ids'])}").classes(
                    tokens.TW_TEXT_12PX_LEADING_5_TEXT_A5AACA
                )
                ui.label(f"Disruption time: {s['disruption_time']}").classes(
                    tokens.TW_TEXT_12PX_LEADING_5_TEXT_988CBF + ' tabular-nums'
                )
                ui.label(f"Active fleet: {s['active_rakes']} rakes").classes(
                    tokens.TW_TEXT_12PX_LEADING_5_TEXT_988CBF + ' tabular-nums'
                )
                ui.label(f"Drops: {s['drops']}").classes(
                    tokens.TW_TEXT_14PX_FONT_SEMIBOLD_TEXT_490C57 + ' tabular-nums'
                )
                ui.label(f"Observed recovery: {s['recovery_pct']:.2f}%").classes(
                    tokens.TW_TEXT_12PX_LEADING_5_TEXT_988CBF + ' tabular-nums'
                )
                ui.label(f"Gap: {s['gap_pct']:.2f}%").classes(
                    tokens.TW_TEXT_12PX_LEADING_5_TEXT_988CBF + ' tabular-nums'
                )
                if dropped_ids:
                    ui.label('Dropped trip IDs:').classes(
                        tokens.TW_TEXT_12PX_FONT_SEMIBOLD_TEXT_52C4A7
                    )
                    ui.label(', '.join(dropped_ids)).classes(
                        tokens.TW_FONT_MONO_TEXT_12PX_LEADING_A3D745 + ' tabular-nums'
                    )
                if extra_note:
                    ui.label(extra_note).classes(
                        tokens.TW_TEXT_12PX_LEADING_5_TEXT_7EA866 + ' tabular-nums'
                    )

        # Build row data for each scenario (unified shape)
        def _row_for_diff(letter, entry):
            failed = entry['disruption']['rakes_down']
            return {
                'letter': letter,
                'rake_ids': failed,
                'disruption_time': entry['disruption']['time'],
                'active_rakes': entry['rakes_active_count'],
                'drops': entry['trips_dropped'],
                'recovery_pct': round(
                    100 * (entry['trips_withdrawn'] - entry['trips_dropped'])
                    / max(entry['trips_withdrawn'], 1), 2
                ),
                'gap_pct': entry['gap_pct'],
                'status': entry['solver_status'],
            }

        def _row_for_sens(entry):
            return {
                'letter': entry['id'],
                'rake_ids': entry['rake_ids'],
                'disruption_time': entry['disruption_time'],
                'active_rakes': base_rake_count - entry['rakes_failed'],
                'drops': entry['drops'],
                'recovery_pct': entry['recovery_pct'],
                'gap_pct': entry['gap_pct'],
                'status': entry['status'],
            }

        card_rows = {
            'a': _row_for_diff('a', a),
            'b': _row_for_diff('b', b),
            'c': _row_for_sens(sens_by_letter['c']),
            'd': _row_for_sens(sens_by_letter['d']),
            'e': _row_for_sens(sens_by_letter['e']),
        }

        # Top row: A, B
        b_rescheduled_drops = len(
            set(base_sched['trip_id'].astype(str).str.strip())
            - set(scen_dfs['b']['trip_id'].astype(str).str.strip())
        )
        with ui.grid(columns=2).classes(tokens.TW_W_FULL_GAP_4_MB_5C549B + ' min-w-0'):
            render_scenario_card('a', card_rows['a'])
            render_scenario_card(
                'b', card_rows['b'],
                extra_note=(
                    f"Observed drops - comparison: {b['trips_dropped']}; "
                    f"rescheduled file: {b_rescheduled_drops}."
                ),
                dropped_ids=b['dropped_trip_ids'],
            )

        # Bottom row: C, D, E
        with ui.grid(columns=3).classes(tokens.TW_W_FULL_GAP_4_MB_5C549B + ' min-w-0'):
            render_scenario_card('c', card_rows['c'])
            render_scenario_card('d', card_rows['d'])
            render_scenario_card('e', card_rows['e'], dropped_ids=sorted(e_resched_dropped))
        # B ∩ E overlap note
        b_dropped = set(b['dropped_trip_ids'])
        # E drops aren't in sensitivity json individually — infer from diff of CSV vs schedule
        base_trip_ids = set(base_sched['trip_id'])
        e_resched_ids = set(scen_dfs['e']['trip_id'])
        e_dropped = base_trip_ids - e_resched_ids
        overlap = b_dropped & e_dropped
        if overlap:
            with analytics_card('Observed B/E dropped-trip overlap'):
                ui.label(
                    f"B/E dropped-trip overlap: {len(overlap)} trips "
                    f"({', '.join(sorted(overlap))})"
                ).classes(
                    tokens.TW_TEXT_12PX_LEADING_5_TEXT_15C65E + ' tabular-nums'
                )
        # Gantt
        gantt_exp = ui.expansion('Rescheduled Timeline', value=True).classes(
            tokens.TW_W_FULL_BG_WHITE_ROUNDED_0B600A + ' min-w-0'
        )
        with gantt_exp:
            with ui.column().classes(tokens.TW_P_4_W_FULL_DDD10D + ' min-w-0'):
                sel = ui.select(
                    {'a': 'A', 'b': 'B', 'c': 'C', 'd': 'D', 'e': 'E'},
                    value='a', label='Scenario',
                ).props('outlined dense options-dense').classes(tokens.TW_W_140PX_BG_WHITE_ROUNDED_DC251F)
                with ui.row().classes(tokens.TW_ITEMS_CENTER_GAP_4_MB_31342C + ' w-full min-w-0'):
                    for cat, color, label in (
                        ('unchanged', _COLORS['unchanged'], 'Unchanged (same rake)'),
                        ('forced', _COLORS['forced'], 'Forced recovery (was on failed rake)'),
                        ('rebalanced', _COLORS['rebalanced'], 'Shifted by rebalancing'),
                        ('dropped', _COLORS['dropped'], 'CANCELLED'),
                    ):
                        with ui.row().classes(tokens.TW_ITEMS_CENTER_GAP_2_145735 + ' w-full min-w-0'):
                            ui.element('span').classes(tokens.TW_INLINE_BLOCK_W_3_H_6755F2).style('background-color: ' + color)
                            ui.label(label).classes(tokens.TW_TEXT_11PX_TEXT_64748B_CDF71A)
                ui.label(
                    "The re-solve rebalances the whole schedule, so most trips changed rake; "
                    "only amber trips were forced by the failure."
                ).classes(tokens.TW_TEXT_11PX_TEXT_64748B_MB_E556F6)
                gantt_container = ui.column().classes(tokens.TW_W_FULL_6DA6A3 + ' min-w-0')

                def refresh_gantt():
                    gantt_container.clear()
                    letter = sel.value
                    diff_entry = diff.get(f'scenario_{letter}') if letter in ('a', 'b') else None
                    with gantt_container:
                        try:
                            fig = _build_gantt(
                                letter, scen_dfs[letter], base_sched,
                                disruptions[letter], diff_entry,
                            )
                            plotly_chart(fig, tokens.PLOTLY_H_600)
                        except Exception as exc:
                            import logging
                            logging.exception('Gantt build failed')
                            ui.label(f'Chart failed to render: {exc}').classes(
                                tokens.TW_TEXT_12PX_TEXT_B91C1C_FONT_69A0F3
                            )

                sel.on_value_change(lambda e: refresh_gantt())
                refresh_gantt()

        # Methodology
        methodology = ui.expansion('', value=False).classes(tokens.TW_W_FULL_MIN_W_0_1C8ED6)
        with methodology.add_slot('header'):
            with ui.row().classes(tokens.TW_W_FULL_ITEMS_CENTER_JUSTIFY_A0250D + ' min-w-0'):
                ui.label('Methodology').classes(tokens.TW_TEXT_16PX_LEADING_5_FONT_50EC06)
                status_badge('observed')
        with methodology:
            with ui.column().classes(tokens.TW_P_4_W_FULL_MIN_47E22F):
                ui.markdown(
                    '**What Disruption Response does**\n\n'
                    'For each scenario, a set of rakes is removed from service at a chosen time. '
                    'The model re-solves the trip-to-rake assignment under the same Train Scheduling constraints, '
                    'with the reduced fleet. Trips that cannot be reassigned are marked CANCELLED.'
                ).classes(tokens.TW_TEXT_14PX_LEADING_5_TEXT_400C9D)
                ui.markdown(
                    '**Constraints enforced during re-solve**\n\n'
                    '- **R1 — Service Coverage:** every surviving trip assigned to exactly one rake.\n'
                    '- **R3 — Operating Window:** all trips inside the service-day window.\n'
                    '- **R4 — Fleet Availability:** only rakes not down are used.\n'
                    '- **R5 — Rake Non-Overlap:** one rake cannot run two trips at once.\n'
                    '- **R6 — Turnaround:** required gap between trips on the same rake.\n'
                    '- **R7 — Running Time:** each trip keeps its scheduled duration.\n'
                    '- **R11 — Terminal Continuity:** consecutive trips must connect via deadhead.'
                ).classes(tokens.TW_TEXT_14PX_LEADING_5_TEXT_400C9D)
                ui.markdown(
                    '**What is NOT modeled**\n\n'
                    '- Crew is not rescheduled — driver assignments stay as in Crew Scheduling.\n'
                    '- No mid-trip abort: an in-progress trip completes normally.\n'
                    '- No cascading delay propagation — this is a reschedule, not a simulation.\n'
                    '- FEASIBLE is never shown as OPTIMAL. The solver hit its time limit.\n'
                    '- Solve time depends on scenario complexity.'
                ).classes(tokens.TW_TEXT_14PX_LEADING_5_TEXT_400C9D)
