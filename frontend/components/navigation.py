from nicegui import ui

from components import tokens


def create_sidebar(active_phase: str = None):
    """Create the fixed mini rail and return the page content column."""
    expanded = {'value': False}
    nav_items = [
        ('home', 'Home', '/'),
        ('dashboard', 'Train Scheduling', '/phase1'),
        ('insights', 'Operational Simulation', '/phase2'),
        ('assignment_ind', 'Crew Scheduling', '/phase3'),
        ('description', 'Explainability', '/phase4'),
        ('alt_route', 'Disruption Response', '/phase5'),
    ]

    drawer = ui.left_drawer(value=True, fixed=True, bordered=True, elevated=False)
    drawer.props('width=64').classes(tokens.NAV_DRAWER)
    labels = []
    rows = []
    with drawer:
        with ui.column().classes(tokens.SIDEBAR_CONTENT + ' overflow-visible'):
            with ui.row().classes(tokens.NAV_TOGGLE_ROW):
                toggle_btn = ui.button(icon='chevron_right').props(
                    'flat round size=sm aria-label="Expand navigation"'
                ).classes(tokens.NAV_TOGGLE)

            for icon, label_text, route in nav_items:
                active = active_phase == (route.strip('/') or 'home')
                with ui.row().classes(tokens.NAV_ROW_ACTIVE if active else tokens.NAV_ROW) as row:
                    row.on('click', lambda r=route: ui.navigate.to(r))
                    rows.append(row)
                    nav_button = ui.button(icon=icon).props(
                        f'flat round size=sm aria-label="{label_text}"'
                    ).classes(tokens.NAV_ICON_ACTIVE if active else tokens.NAV_ICON)
                    with nav_button:
                        ui.tooltip(label_text).props('anchor="center right"')
                    label = ui.label(label_text).classes(
                        tokens.NAV_LABEL_ACTIVE if active else tokens.NAV_LABEL
                    )
                    label.set_visibility(False)
                    labels.append(label)

    main = ui.column().classes(tokens.MAIN_CONTENT)

    def toggle():
        expanded['value'] = not expanded['value']
        if expanded['value']:
            drawer.props('width=240', remove='mini')
        else:
            drawer.props('mini mini-width=64 width=64')
        for label in labels:
            label.set_visibility(expanded['value'])
        for row in rows:
            row.classes(tokens.NAV_ROW_EXPANDED if expanded['value'] else tokens.NAV_ROW,
                        remove='justify-center' if expanded['value'] else 'justify-start')
        toggle_btn.props(
            'icon=chevron_left aria-label="Collapse navigation"' if expanded['value']
            else 'icon=chevron_right aria-label="Expand navigation"'
        )

    toggle_btn.on('click', toggle)
    return main
