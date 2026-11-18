# main.py
# Written against NiceGUI 2.x (>=1.4, current 2.x API).
# ui.plotly exists in NiceGUI 1.x and 2.x. ui.aggrid.from_pandas exists in both.
# ui.expansion exists in both. No deprecated APIs used.

from nicegui import ui

from pages.phase1 import render as render_phase1
from pages.phase2 import render as render_phase2

_BACKGROUND_HEAD = '''
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=Roboto+Mono:wght@400;500&display=swap');
  html, body, .q-page, .nicegui-content {
    font-family: 'IBM Plex Sans', sans-serif;
  }
  code, pre, .tabular-nums {
    font-family: 'Roboto Mono', monospace;
  }
  body, .q-page, .nicegui-content {
    background-color: #F4F6F8 !important;
  }
</style>
'''

@ui.page('/')
def index():
    ui.add_head_html(_BACKGROUND_HEAD)
    with ui.column().classes('w-full h-screen overflow-hidden flex items-center justify-center gap-6'):
        ui.label('MetroPulse').classes('text-[28px] font-bold text-[#111111]')
        ui.label('Read-only dashboard over frozen backend output.').classes('text-[14px] text-[#6B6B6B]')
        
        with ui.row().classes('gap-4 mt-4'):
            ui.button('Phase 1 Dashboard', on_click=lambda: ui.navigate.to('/phase1')).props('unelevated').classes(
                'bg-[#7138F5] text-white rounded-[12px] px-6 py-2 font-medium uppercase tracking-wider')
            ui.button('Phase 2 Simulation', on_click=lambda: ui.navigate.to('/phase2')).props('unelevated').classes(
                'bg-[#1B7A43] text-white rounded-[12px] px-6 py-2 font-medium uppercase tracking-wider')

@ui.page('/phase1')
def phase1_page():
    ui.add_head_html(_BACKGROUND_HEAD)
    render_phase1()

@ui.page('/phase2')
def phase2_page():
    ui.add_head_html(_BACKGROUND_HEAD)
    render_phase2()

ui.run(title='MetroPulse', favicon='🚆', reload=True)
