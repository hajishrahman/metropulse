from nicegui import ui

def create_sidebar(active_phase: str = None):
    """Collapsible left rail + main content, side-by-side (no overlay)."""
    
    expanded = {'value': False}
    
    nav_items = [
        ('home', 'Home', '/'),
        ('dashboard', 'Scheduling', '/phase1'),
        ('insights', 'Simulation', '/phase2'),
        ('assignment_ind', 'Crew Scheduling ', '/phase3'),
        ('description', 'Explainability', '/phase4'),
    ]
    
    with ui.row().classes('w-full min-w-0 h-screen flex-nowrap items-stretch gap-0'):
        
        # ---- SIDEBAR (rail) ----
        sidebar = ui.column().classes(
            'bg-white border-r border-[#E2E8F0] shadow-none h-full '
            'flex-shrink-0'
        ).style('width: 64px; flex: 0 0 64px;')
        
        with sidebar:
            # Toggle button row — always visible, centered
            with ui.row().classes('w-full items-center justify-center pt-4 pb-2'):
                toggle_btn = ui.button(icon='chevron_right').props(
                    'flat round size=sm aria-label="Expand navigation"'
                ).classes('text-[#475569] hover:text-[#1E3A5F] rounded-[4px] shadow-none')
            
            # Nav items
            labels = []
            nav_rows = []
            for idx, (icon, label_text, route) in enumerate(nav_items):
                is_active = (active_phase == route.strip('/'))
                color = 'text-[#1E3A5F]' if is_active else 'text-[#475569]'
                bg = 'bg-[#F1F5F9]' if is_active else ''
                
                with ui.row().classes(
                    f'w-full min-w-0 items-center justify-center gap-3 px-2 py-2 cursor-pointer '
                    f'hover:bg-[#F8FAFC] rounded-[4px] {bg}'
                ) as row:
                    row.on('click', lambda r=route: ui.navigate.to(r))
                    nav_rows.append(row)
                    btn = ui.button(icon=icon).props(
                        f'flat round size=sm aria-label="{label_text}"'
                    ).classes(
                        f'{color} hover:text-[#1E3A5F] shadow-none rounded-[4px]'
                    )
                    if not expanded['value']:
                        ui.tooltip(label_text).props('anchor="center right"')
                    label = ui.label(label_text).classes(
                        f"text-[14px] font-medium font-['IBM_Plex_Sans',_sans-serif] {color} whitespace-nowrap"
                    )
                    label.set_visibility(False)
                    labels.append(label)
        
        # ---- MAIN CONTENT slot ----
        main = ui.column().classes('flex-1 min-w-0 h-full overflow-auto')
        main_container = main  # pages render into this
    
    # Toggle logic
    def toggle():
        expanded['value'] = not expanded['value']
        if expanded['value']:
            sidebar.style('width: 240px; flex: 0 0 240px;')
            for lbl in labels:
                lbl.set_visibility(True)
            for row in nav_rows:
                row.classes('justify-start', remove='justify-center')
            toggle_btn.props('icon=chevron_left aria-label="Collapse navigation"')
        else:
            sidebar.style('width: 64px; flex: 0 0 64px;')
            for lbl in labels:
                lbl.set_visibility(False)
            for row in nav_rows:
                row.classes('justify-center', remove='justify-start')
            toggle_btn.props('icon=chevron_right aria-label="Expand navigation"')
    
    toggle_btn.on('click', toggle)
    
    # Render page content into main container (pages must call with create_sidebar(...))
    return main_container
