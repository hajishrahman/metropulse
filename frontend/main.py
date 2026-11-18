# main.py
# Written against NiceGUI 2.x (>=1.4, current 2.x API).
# ui.plotly exists in NiceGUI 1.x and 2.x. ui.aggrid.from_pandas exists in both.
# ui.expansion exists in both. No deprecated APIs used.

from nicegui import ui

from pages.phase1 import render as render_phase1

# NOTE (NiceGUI 2.x): background is set via injected <style> per page, NOT
# ui.query('body').classes(...) (unreliable against Quasar internals) and NOT
# ui.colors(background=...) (that kwarg does not exist on ui.colors).
_BACKGROUND_HEAD = '''
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Roboto+Mono:wght@400;500&display=swap');
  html, body, .q-page, .nicegui-content {
    font-family: 'Inter', sans-serif;
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
        ui.label(
            'Read-only dashboard over frozen backend output.'
        ).classes('text-[14px] text-[#6B6B6B]')
        ui.button(
            'Enter Dashboard',
            on_click=lambda: ui.navigate.to('/phase1'),
        ).props('unelevated').classes(
            'bg-[#7138F5] text-white rounded-[12px] px-6 py-2 '
            'font-medium uppercase tracking-wider'
        )


@ui.page('/phase1')
def phase1_page():
    ui.add_head_html(_BACKGROUND_HEAD)
    render_phase1()


ui.run(title='MetroPulse', favicon='🚆', reload=False)