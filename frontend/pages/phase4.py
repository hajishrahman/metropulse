# pages/phase4.py
# Phase 4 — Explainability

from __future__ import annotations

import re
from nicegui import ui

from components.ui_elements import (
    analytics_card,
    scenario_tag,
    state_card,
    provenance_footer,
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
    # Phase 1
    'R1_service_coverage': 'R1 — Service Coverage',
    'R3_operating_window': 'R3 — Operating Window',
    'R4_fleet_availability': 'R4 — Fleet Availability',
    'R5_rake_non_overlap': 'R5 — Rake Non-Overlap',
    'R6_turnaround': 'R6 — Turnaround',
    'R7_running_time': 'R7 — Running Time',
    'R9_maintenance_exclusivity': 'R9 — Maintenance Exclusivity',
    'R10_maintenance_threshold': 'R10 — Maintenance Threshold',
    'R11_terminal_continuity': 'R11 — Terminal Continuity',
    'D_direction_consistency': 'D — Direction Consistency',
    # Phase 3
    'C1_no_overlap': 'C1 — No Overlapping Trips',
    'C2_max_duty': 'C2 — Max Duty',
    'C3_sign_buffers': 'C3 — Sign-On / Sign-Off Buffers',
    'C4_coverage': 'C4 — Trip Coverage',
    'C5_rest': 'C5 — Rest (Deferred)',
    'C6_continuous_driving': 'C6 — Continuous Driving (Inactive)',
    'C7_reserve': 'C7 — Reserve',
}

_MD_ESCAPE = re.compile(r'(?<!\\)_')  # underscores not already escaped


def _escape_underscores(text: str) -> str:
    """Escape unescaped underscores outside backtick code spans."""
    text = text.replace('legal R6-legal', 'R6-legal')
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
            return '<span class="bg-[#E8F5E9] text-[#1B7A43] rounded-[6px] px-2 py-0.5 text-[11px] font-medium">PASS</span>'
        if c in ('WARN', 'WARNING'):
            return '<span class="bg-[#FFF8E1] text-[#8A6100] rounded-[6px] px-2 py-0.5 text-[11px] font-medium">WARN</span>'
        if c in ('FAIL', 'INVALID'):
            return '<span class="bg-[#FFEBEE] text-[#B3261E] rounded-[6px] px-2 py-0.5 text-[11px] font-medium">FAIL</span>'
        return c

    header_html = ''.join(
        f'<th class="px-2 py-1 text-left text-[11px] font-semibold text-[#1e3a5f] uppercase tracking-wider bg-[#f4f6f8] border-b border-[#e2e8f0] sticky top-0 z-10">{h}</th>'
        for h in headers
    )
    rows_html = ''
    for r in rows:
        cells = ''.join(
            f'<td class="px-2 py-1 text-[12px] text-[#334155] border-b border-[#e2e8f0]">{_cell(c)}</td>'
            for c in r
        )
        rows_html += f'<tr class="hover:bg-[#f4f6f8]">{cells}</tr>'

    table = (
        '<table class="w-full text-left border-collapse table-fixed">'
        f'<thead>{header_html}</thead>'
        f'<tbody>{rows_html}</tbody>'
        '</table>'
    )
    if scroll:
        return f'<div class="w-full max-h-[360px] overflow-y-auto block">{table}</div>'
    return f'<div class="w-full overflow-x-auto block">{table}</div>'


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
                    "text-[13px] leading-6 text-[#334155] font-['IBM_Plex_Sans',_sans-serif]"
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
                ui.html(_render_html_table(headers, rows, scroll=scroll_tables)).classes('w-full block')
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
    main.classes('w-full min-w-0 p-6')

    report_res = load_explainability_report()
    util_res = load_utilization_stats()

    with main:
        for name, res in (
            ('explainability_report.md', report_res),
            ('utilization_stats.json', util_res),
        ):
            if res['status'] != 'ok':
                state_card(res['status'].replace('_', ' ').upper(), name, res['message']).props('flat').classes('shadow-none')
                return

        md_text = report_res['data']

        # Header
        with ui.row().classes('w-full min-w-0 justify-between items-center mb-2'):
            with ui.column().classes('min-w-0 gap-1'):
                ui.label('Explainability').classes(
                    "text-[22px] leading-7 font-bold text-[#0F172A] font-['IBM_Plex_Sans',_sans-serif]"
                )
                ui.label('Transparent reporting and utilization metrics across all phases.').classes(
                    "text-[14px] leading-5 text-[#334155] font-['IBM_Plex_Sans',_sans-serif]"
                )
            scenario_tag('REPORT').style('border-radius: 4px;')

        # Audit statement banner
        with ui.card().classes(
            "w-full min-w-0 bg-white rounded-[6px] shadow-[0_1px_5px_rgba(0,0,0,0.2),0_2px_2px_rgba(0,0,0,0.14),0_3px_1px_-2px_rgba(0,0,0,0.12)] border border-[#e2e8f0] p-4 mb-4"
        ):
            ui.label(
                "Every number cites its source file. No values are hardcoded or 'audited' post-hoc."
            ).classes(
                "text-[14px] leading-5 font-medium text-[#1e3a5f] font-['IBM_Plex_Sans',_sans-serif]"
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
                            'shadow-none bg-white border border-[#e2e8f0] rounded-[6px] p-4 mb-4'
                        )
                        # Pools 45 + 50 side by side
                        with ui.grid(columns=2).classes('w-full gap-3 mb-3'):
                            for pool_title, pool_body in pools[:2]:
                                with ui.card().classes(
                                    'w-full bg-white rounded-[6px] border border-[#e2e8f0] p-3'
                                ):
                                    ui.label(pool_title).classes(
                                        "text-[14px] font-semibold text-[#1e3a5f] mb-2 font-['IBM_Plex_Sans',_sans-serif]"
                                    )
                                    _render_body_with_tables(pool_body, scroll_tables=True)
                        # Pool 55 below
                        for pool_title, pool_body in pools[2:]:
                            with ui.card().classes(
                                'w-full bg-white rounded-[6px] border border-[#e2e8f0] p-3'
                            ):
                                ui.label(pool_title).classes(
                                    "text-[14px] font-semibold text-[#1e3a5f] mb-2 font-['IBM_Plex_Sans',_sans-serif]"
                                )
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
                            'shadow-none bg-white border border-[#e2e8f0] rounded-[6px] p-4 mb-4'
                        )
                        # Intro
                        intro_title, intro_body = subs[0]
                        if intro_body:
                            _render_body_with_tables(intro_body, scroll_tables=False)

                        # 2-column grid — tables only
                        after_blocks: list[str] = []
                        with ui.grid(columns=2).classes('w-full gap-4 mt-3'):
                            for sub_title, sub_body in subs[1:3]:
                                table_chunk, after = _split_table_from_after(sub_body)
                                with ui.card().classes(
                                    'w-full bg-white rounded-[6px] border border-[#e2e8f0] p-3'
                                ):
                                    if sub_title:
                                        ui.label(sub_title).classes(
                                            "text-[14px] font-semibold text-[#1e3a5f] mb-2 font-['IBM_Plex_Sans',_sans-serif]"
                                        )
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
                    'shadow-none bg-white border border-[#e2e8f0] rounded-[6px] p-4 mb-4'
                )
                _render_body_with_tables(body, scroll_tables=scroll)

        # Utilization Formulas (moved to bottom)
        with analytics_card('Utilization Formulas') as card:
            card.props('flat').classes(
                'shadow-none bg-white border border-[#e2e8f0] rounded-[6px] p-4 mb-4'
            )
            ui.label('utilization_pct = busy_sec / span_sec × 100').classes(
                "font-mono text-[14px] leading-6 text-[#334155]"
            )
            ui.label('total_depot_hours = (max sign_off − min sign_on) / 3600').classes(
                "font-mono text-[14px] leading-6 text-[#334155]"
            )

        # Both Source: lines grouped at bottom
        provenance_footer(report_res['path'], report_res['mtime'])
        provenance_footer(util_res['path'], util_res['mtime'])