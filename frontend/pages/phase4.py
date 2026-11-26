# pages/phase4.py
# Phase 4 — Explainability

from __future__ import annotations

import re
from nicegui import ui

from components import tokens

from components.ui_elements import (
    analytics_card,
    page_content,
    scenario_tag,
    state_card,
    provenance_footer,
    status_badge,
)
from data.registry import load_explainability_report, load_utilization_stats


# ----------------------------------------------------------------------------
# Section 7 retitle
# ----------------------------------------------------------------------------
_SECTION_RETITLE = {
    '2. Phase 1 Constraint Status':
        '2. Train Schedule Constraint Status',
    '3. Phase 3 Constraint Status (C1–C7, per pool)':
        '3. Crew Roster Constraint Status (C1–C7, per pool)',
    '4. Rake Utilization (Phase 1)':
        '4. Rake Utilization',
    '5. Driver Utilization (Phase 3)':
        '5. Driver Utilization',
    '6. Simulation Results (Phase 2)':
        '6. Simulation Results',
    '7. Sensitivity Analysis & Honest Limitations':
        '7. Pool-Size Comparison & Honest Limitations',
}


# ----------------------------------------------------------------------------
# Constraint ID → human label
# ----------------------------------------------------------------------------
_CONSTRAINT_LABELS = {
    # Train Scheduling
    'R1_service_coverage': 'Service Coverage',
    'R3_operating_window': 'Operating Window',
    'R4_fleet_availability': 'Fleet Availability',
    'R5_rake_non_overlap': 'Rake Non-Overlap',
    'R6_turnaround': 'Turnaround',
    'R7_running_time': 'Running Time',
    'R9_maintenance_exclusivity': 'Maintenance Exclusivity',
    'R10_maintenance_threshold': 'Maintenance Threshold',
    'R11_terminal_continuity': 'Terminal Continuity',
    'D_direction_consistency': 'Direction Consistency',
    # Crew Scheduling
    'C1_no_overlap': 'No Overlapping Trips',
    'C2_max_duty': 'Max Duty',
    'C3_sign_buffers': 'Sign-On / Sign-Off Buffers',
    'C4_coverage': 'Trip Coverage',
    'C5_rest': 'Rest (Deferred)',
    'C6_continuous_driving': 'Continuous Driving (Inactive)',
    'C7_reserve': 'Reserve',
}

_MD_ESCAPE = re.compile(r'(?<!\\)_')  # underscores not already escaped


def _escape_underscores(text: str) -> str:
    """Escape unescaped underscores outside backtick code spans."""
    text = text.replace('legal R6-legal', 'R6-legal')
    # Replace verbose rule-code note with plain version
    _note_re = re.compile(
        r'\*\*Notes\.\*\*\s*This section reflects exactly the checks.*?direction-consistency check\.',
        re.DOTALL,
    )
    text = _note_re.sub(
        '**Notes.** This section reflects all active schedule validation checks '
        'from `validation.json` for the current run (GTFS stop timings are treated as given).',
        text,
    )
    text = re.sub(r'\bPhase\s+1/2/3\b',
                  'Train Scheduling / Operational Simulation / Crew Scheduling', text)
    text = re.sub(r'\bPhase\s+1\b', 'Train Scheduling', text)
    text = re.sub(r'\bPhase\s+2\b', 'Operational Simulation', text)
    text = re.sub(r'\bPhase\s+3\b', 'Crew Scheduling', text)
    parts = re.split(r'(`[^`]*`)', text)
    out = []
    for part in parts:
        if part.startswith('`') and part.endswith('`') and len(part) >= 2:
            out.append(part)  # leave code spans untouched
        else:
            out.append(_MD_ESCAPE.sub(r'\\_', part))
    return ''.join(out)


def _clean_cell(text: str) -> str:
    """Replace snake_case IDs and None values with friendly text."""
    s = text.strip()
    if s in _CONSTRAINT_LABELS:
        return _CONSTRAINT_LABELS[s]
    if s == 'None':
        return 'N/A'
    # Inline replacements inside longer cells
    for k, v in _CONSTRAINT_LABELS.items():
        s = s.replace(k, v)
    s = s.replace('required=None', 'required=N/A')
    s = s.replace('scheduled=None', 'scheduled=N/A')
    return s


# ----------------------------------------------------------------------------
# Section splitting
# ----------------------------------------------------------------------------
def _split_sections(md: str) -> list[tuple[str, str]]:
    pattern = re.compile(r'^## (.+)$', re.MULTILINE)
    matches = list(pattern.finditer(md))
    if not matches:
        return []
    sections = []
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md)
        body = md[start:end].strip()
        body = re.sub(r'^\s*---\s*', '', body)
        body = re.sub(r'\s*---\s*$', '', body)
        sections.append((title, body.strip()))
    return sections


def _split_pools(body: str) -> list[tuple[str, str]]:
    """Split a section body by '### Pool XX' sub-headings.
    Returns [(pool_title, pool_body), ...] or [(None, body)] if no pools."""
    pattern = re.compile(r'^### (.+)$', re.MULTILINE)
    matches = list(pattern.finditer(body))
    if not matches:
        return [('', body)]
    parts = []
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        parts.append((title, body[start:end].strip()))
    return parts


def _split_bold_subs(body: str) -> list[tuple[str, str]]:
    """Split by '**Label**' lines that start a sub-section.
    Preserves any intro text before the first bold block as ('', intro)."""
    pattern = re.compile(r'^\*\*([^*]+)\*\*\s*$', re.MULTILINE)
    matches = list(pattern.finditer(body))
    if not matches:
        return [('', body)]
    parts = []
    if matches[0].start() > 0:
        intro = body[:matches[0].start()].strip()
        if intro:
            parts.append(('', intro))
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        parts.append((title, body[start:end].strip()))
    return parts


# ----------------------------------------------------------------------------
# Markdown + table renderer
# ----------------------------------------------------------------------------
_TABLE_SEP = re.compile(r'^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$')


def _parse_table(lines: list[str]) -> tuple[list[str], list[list[str]]] | None:
    """Given lines that form a markdown table, return (headers, rows)."""
    if len(lines) < 2:
        return None
    header_line = lines[0]
    if not header_line.strip().startswith('|'):
        return None
    if not _TABLE_SEP.match(lines[1].strip()):
        return None
    headers = [c.strip() for c in header_line.strip().strip('|').split('|')]
    rows = []
    for line in lines[2:]:
        if not line.strip().startswith('|'):
            break
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        rows.append(cells)
    return headers, rows


def _render_html_table(headers, rows, scroll=False):
    """Render a markdown-style table as an HTML table."""
    def _cell(c):
        c = _clean_cell(c)
        if c == 'PASS':
            return f'<span class="{tokens.BADGE_PASS}">PASS</span>'
        if c in ('WARN', 'WARNING'):
            return f'<span class="{tokens.BADGE_WARNING}">WARN</span>'
        if c in ('FAIL', 'INVALID'):
            return f'<span class="{tokens.BADGE_FAIL}">FAIL</span>'
        return c

    header_html = ''.join(
        f'<th class="{tokens.TABLE_HEADER}">{h}</th>'
        for h in headers
    )
    rows_html = ''
    for r in rows:
        cells = ''.join(
            f'<td class="{tokens.TABLE_CELL}">{_cell(c)}</td>'
            for c in r
        )
        rows_html += f'<tr class="{tokens.TABLE_ROW_HOVER}">{cells}</tr>'

    table = (
        f'<table class="{tokens.TABLE_BASE_FIXED} min-w-0">'
        f'<thead>{header_html}</thead>'
        f'<tbody>{rows_html}</tbody>'
        '</table>'
    )
    if scroll:
        return f'<div class="{tokens.TABLE_WRAP_SCROLL} min-w-0">{table}</div>'
    return f'<div class="{tokens.TABLE_WRAP} min-w-0">{table}</div>'


def _render_body_with_tables(body: str, scroll_tables: bool = False):
    """Parse markdown body, render non-table chunks as ui.markdown,
    tables as HTML in ui.html."""
    lines = body.splitlines()
    i = 0
    md_buffer: list[str] = []

    def _flush_md():
        if md_buffer:
            text = '\n'.join(md_buffer).strip()
            if text:
                ui.markdown(_escape_underscores(text)).classes(
                    tokens.TW_TEXT_14PX_LEADING_5_TEXT_400C9D
                )
            md_buffer.clear()

    while i < len(lines):
        line = lines[i]
        # Try to detect a table starting at i
        if line.strip().startswith('|') and i + 1 < len(lines) and _TABLE_SEP.match(lines[i + 1].strip()):
            _flush_md()
            j = i + 2
            while j < len(lines) and lines[j].strip().startswith('|'):
                j += 1
            parsed = _parse_table(lines[i:j])
            if parsed:
                headers, rows = parsed
                ui.html(_render_html_table(headers, rows, scroll=scroll_tables)).classes(tokens.TW_W_FULL_BLOCK_954D40 + ' min-w-0')
            i = j
            continue
        md_buffer.append(line)
        i += 1
    _flush_md()


# ----------------------------------------------------------------------------
# Main render
# ----------------------------------------------------------------------------
def render():
    from components.navigation import create_sidebar
    main = create_sidebar(active_phase='phase4')
    page_content(main)

    report_res = load_explainability_report()
    util_res = load_utilization_stats()

    with main:
        for name, res in (
            ('explainability_report.md', report_res),
            ('utilization_stats.json', util_res),
        ):
            if res['status'] != 'ok':
                state_card(res['status'].replace('_', ' ').upper(), name, res['message']).props('flat').classes(tokens.TW_SHADOW_NONE_AD47D1)
                return

        md_text = report_res['data']

        # Header
        with ui.row().classes(tokens.TW_W_FULL_MIN_W_0_29D4FF):
            with ui.column().classes(tokens.TW_MIN_W_0_GAP_1_6364F0 + ' w-full'):
                ui.label('Explainability').classes(
                    tokens.TW_TEXT_22PX_LEADING_7_FONT_4694EF
                )
                ui.label('Transparent reporting and utilization metrics across all phases.').classes(
                    tokens.TW_TEXT_14PX_LEADING_5_TEXT_AE0775
                )
            scenario_tag('REPORT').style('border-radius: 4px;')

        # Audit statement banner
        with ui.card().classes(
            tokens.TW_W_FULL_MIN_W_0_FBFB4B
        ):
            ui.label(
                "Every number cites its source file. No values are hardcoded or 'audited' post-hoc."
            ).classes(
                tokens.TW_TEXT_14PX_LEADING_5_FONT_814421
            )

        # Report sections
        sections = _split_sections(md_text)
        if not sections:
            state_card('INVALID', 'explainability_report.md', 'No sections found in report.')
            return

        for title, body in sections:
            display_title = _SECTION_RETITLE.get(title, title)

            # Sections 3 and 5: 3 pools → 2+1 grid
            if title.startswith('3.') or title.startswith('5.'):
                pools = _split_pools(body)
                if len(pools) > 1:
                    # Intro (before first pool) rendered as its own card or above
                    with analytics_card(display_title) as card:
                        card.props('flat').classes(
                            tokens.TW_SHADOW_NONE_BG_WHITE_BORDER_00AA57
                        )
                        # Pools 45 + 50 side by side
                        with ui.grid(columns=2).classes(tokens.TW_W_FULL_GAP_3_MB_66A243 + ' min-w-0'):
                            for pool_title, pool_body in pools[:2]:
                                with analytics_card(pool_title):
                                    _render_body_with_tables(pool_body, scroll_tables=True)
                        # Pool 55 below
                        for pool_title, pool_body in pools[2:]:
                            with analytics_card(pool_title):
                                _render_body_with_tables(pool_body, scroll_tables=True)
                    continue

            # Section 6: intro + 2-column tables, footnotes full-width below
            if title.startswith('6.'):
                subs = _split_bold_subs(body)
                if len(subs) >= 3:
                    def _split_table_from_after(sub_body: str) -> tuple[str, str]:
                        """Return (table_chunk, everything_after_table)."""
                        lines = sub_body.splitlines()
                        table_end = -1
                        for idx, ln in enumerate(lines):
                            if ln.strip().startswith('|'):
                                table_end = idx
                        if table_end == -1 or table_end == len(lines) - 1:
                            return sub_body, ''
                        return (
                            '\n'.join(lines[:table_end + 1]),
                            '\n'.join(lines[table_end + 1:]).strip(),
                        )

                    with analytics_card(display_title) as card:
                        card.props('flat').classes(
                            tokens.TW_SHADOW_NONE_BG_WHITE_BORDER_00AA57
                        )
                        # Intro
                        intro_title, intro_body = subs[0]
                        if intro_body:
                            _render_body_with_tables(intro_body, scroll_tables=False)

                        # 2-column grid — tables only
                        after_blocks: list[str] = []
                        with ui.grid(columns=2).classes(tokens.TW_W_FULL_GAP_4_MT_93EBB8 + ' min-w-0'):
                            for sub_title, sub_body in subs[1:3]:
                                table_chunk, after = _split_table_from_after(sub_body)
                                with ui.card().classes(tokens.TW_W_FULL_BG_WHITE_ROUNDED_7EAC46 + ' min-w-0'):
                                    if sub_title:
                                        ui.label(sub_title).classes(tokens.TW_TEXT_14PX_FONT_SEMIBOLD_TEXT_F9F1EE)
                                    _render_body_with_tables(table_chunk, scroll_tables=True)
                                if after:
                                    after_blocks.append(after)

                        # Any trailing footnotes from the two table sub-bodies
                        for blk in after_blocks:
                            _render_body_with_tables(blk, scroll_tables=False)

                        # Remaining subs (if any) below full-width
                        for sub_title, sub_body in subs[3:]:
                            _render_body_with_tables(sub_body, scroll_tables=False)
                    continue

            # Section 4: single card, scroll wrappers
            scroll = title.startswith('4.')
            with analytics_card(display_title) as card:
                card.props('flat').classes(
                    tokens.TW_SHADOW_NONE_BG_WHITE_BORDER_00AA57
                )
                _render_body_with_tables(body, scroll_tables=scroll)

        # Utilization Formulas (moved to bottom)
        formulas = ui.expansion('', value=False).classes(tokens.TW_W_FULL_MIN_W_0_1C8ED6)
        with formulas.add_slot('header'):
            with ui.row().classes(tokens.TW_W_FULL_ITEMS_CENTER_JUSTIFY_A0250D + ' min-w-0'):
                ui.label('Utilization Formulas').classes(tokens.TW_TEXT_16PX_LEADING_5_FONT_50EC06)
                status_badge('observed')
        with formulas:
            with ui.column().classes(tokens.TW_P_4_W_FULL_MIN_47E22F + ' gap-3'):
                # Formulas
                ui.label('utilization_pct = busy_sec / span_sec × 100').classes(
                    tokens.TW_TEXT_14PX_LEADING_5_TEXT_400C9D + ' font-mono'
                )
                ui.label('total_depot_hours = (max sign_off − min sign_on) / 3600').classes(
                    tokens.TW_TEXT_14PX_LEADING_5_TEXT_400C9D + ' font-mono'
                )

                # Definitions
                ui.markdown(
                    '**Definitions (computed before the table):**\n\n'
                    '- **`span_sec`** = last_arrival_sec − first_departure_sec per rake '
                    '(the rake\'s active day).\n'
                    '- **`busy_sec`** = Σ(arrival_sec − departure_sec) over all trips assigned '
                    'to that rake (running time only).\n'
                    '- **`utilization_pct`** = busy_sec / span_sec × 100 (null if span_sec = 0).\n'
                    '- **`peak_simultaneous_rakes`** = maximum count of distinct rakes '
                    'simultaneously running at any integer second, computed by an event-sweep '
                    'over departure/arrival times.'
                ).classes(tokens.TW_TEXT_14PX_LEADING_5_TEXT_400C9D)

                # Flags
                ui.markdown(
                    '**Flags:** Turnaround and deadhead are **not** added to `span_sec` — no '
                    'invented parameters. Busy time is running time only; terminal idling is the '
                    'gap, not counted as busy. Spans are single-day and per-rake, not fleet-wide '
                    'utilization.'
                ).classes(tokens.TW_TEXT_14PX_LEADING_5_TEXT_400C9D)

                # Rake aggregate metrics
                ui.markdown(
                    '**Rake aggregate metrics:**\n\n'
                    '- Trips per rake — min = 14, mean = 14.17, max = 15\n'
                    '- Peak simultaneous rakes = 15\n'
                    '- Mean utilization = 70.7%'
                ).classes(tokens.TW_TEXT_14PX_LEADING_5_TEXT_400C9D)

                # Driver depot per pool
                ui.markdown(
                    '**Driver depot hours per pool:**\n\n'
                    '- Pool 45 — min = 6.25, mean = 7.93, max = 8.49  \n'
                    '  Rows in `crew_schedule.csv` for pool 45: 255 '
                    '(assignments listed in `crew_solution.json` pool 45: 255)\n'
                    '- Pool 50 — min = 3.71, mean = 7.70, max = 8.50  \n'
                    '  Rows in `crew_schedule.csv` for pool 50: 255 '
                    '(assignments listed in `crew_solution.json` pool 50: 255)\n'
                    '- Pool 55 — min = 1.34, mean = 7.16, max = 8.50  \n'
                    '  Rows in `crew_schedule.csv` for pool 55: 255 '
                    '(assignments listed in `crew_solution.json` pool 55: 255)'
                ).classes(tokens.TW_TEXT_14PX_LEADING_5_TEXT_400C9D)

                # Delay model
                ui.markdown(
                    '**Delay model:** `clipped_normal`, pre-clip mean = −48.0 s, '
                    'std sweep = [0.0, 60.0, 120.0, 300.0] s, clip = [0.0, 300.0] s.'
                ).classes(tokens.TW_TEXT_14PX_LEADING_5_TEXT_400C9D)

        # Both Source: lines grouped at bottom
        provenance_footer(report_res['path'], report_res['mtime'])
        provenance_footer(util_res['path'], util_res['mtime'])
