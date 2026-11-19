# main.py
# Written against NiceGUI 2.x (>=1.4, current 2.x API).
# ui.plotly exists in NiceGUI 1.x and 2.x. ui.aggrid.from_pandas exists in both.
# ui.expansion exists in both. No deprecated APIs used.

from nicegui import ui

from pages import phase1
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
    from pages.home import render as render_home
    render_home()
    
@ui.page('/phase1')
def phase1_page():
    ui.add_head_html(_BACKGROUND_HEAD)
    render_phase1()

@ui.page('/phase2')
def phase2_page():
    ui.add_head_html(_BACKGROUND_HEAD)
    render_phase2()

@ui.page('/phase3')
def phase3_page():
    ui.add_head_html(_BACKGROUND_HEAD)
    from pages.phase3 import render as render_phase3
    render_phase3()

@ui.page('/phase4')
def phase4_page():
    ui.add_head_html(_BACKGROUND_HEAD)
    from pages.phase4 import render as render_phase4
    render_phase4()

@ui.page('/phase5')
def phase5_page():
    ui.add_head_html(_BACKGROUND_HEAD)
    from pages.phase5 import render as render_phase5
    render_phase5()

ui.run(title='MetroPulse', favicon='🚆', reload=True)
