from nicegui import ui

def create_sidebar(active_phase: str = None):
    """Collapsible left rail + main content, side-by-side (no overlay)."""
    
    expanded = {'value': False}
    
    nav_items = [
        ('home', 'Home', '/'),
        ('dashboard', 'Phase 1 — Scheduling', '/phase1'),
        ('insights', 'Phase 2 — Simulation', '/phase2'),
        ('assignment_ind', 'Phase 3 — Crew', '/phase3'),
    ]
    
    with ui.row().classes('w-full h-screen flex-nowrap items-stretch gap-0'):
        
        # ---- SIDEBAR (rail) ----
        sidebar = ui.column().classes(
            'bg-white border-r border-[#e2e8f0] h-full '
            'transition-all duration-300 flex-shrink-0'
        ).style('width: 64px;')
        
        with sidebar:
            # Toggle button row — always visible, centered
            with ui.row().classes('w-full items-center justify-center pt-4 pb-2'):
                toggle_btn = ui.button(icon='chevron_right').props(
                    'flat round size=sm'
                ).classes('text-[#181d1f]/70 hover:text-[#181d1f]')
            
            # Nav items
            labels = []
            for idx, (icon, label_text, route) in enumerate(nav_items):
                is_active = (active_phase == route.strip('/'))
                color = 'text-[#1B7A43]' if is_active else 'text-[#181d1f]/70'
                bg = 'bg-[#f4f6f8]' if is_active else ''
                
                with ui.row().classes(
                    f'w-full items-center justify-center gap-3 px-2 py-2 cursor-pointer '
                    f'hover:bg-[#f4f6f8] rounded-[6px] {bg} overflow-hidden'
                ) as row:
                    row.on('click', lambda r=route: ui.navigate.to(r))
                    btn = ui.button(icon=icon).props('flat round size=sm').classes(
                        f'{color} hover:text-[#181d1f]'
                    )
                    if not expanded['value']:
                        ui.tooltip(label_text).props('anchor="center right"')
                    label = ui.label(label_text).classes(
                        f"text-[14px] font-medium font-['IBM_Plex_Sans',_sans-serif] {color} whitespace-nowrap"
                    )
                    label.set_visibility(False)
                    labels.append(label)
        
        # ---- MAIN CONTENT slot ----
        main = ui.column().classes('flex-grow min-w-0 h-full overflow-auto')
        main_container = main  # pages render into this
    
    # Toggle logic
    def toggle():
        expanded['value'] = not expanded['value']
        if expanded['value']:
            sidebar.style('width: 240px;')
            for lbl in labels:
                lbl.set_visibility(True)
            toggle_btn.props('icon=chevron_left')
        else:
            sidebar.style('width: 64px;')
            for lbl in labels:
                lbl.set_visibility(False)
            toggle_btn.props('icon=chevron_right')
    
    toggle_btn.on('click', toggle)
    
    # Render page content into main container (pages must call with create_sidebar(...))
    return main_container