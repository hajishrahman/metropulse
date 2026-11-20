import ast
from pathlib import Path
import re

import plotly.graph_objects as go

from components import tokens, ui_elements


FRONTEND = Path(__file__).resolve().parents[1]
PROTECTED = {
    'rake-balance deviation, not a score',
    'CANCELLED',
    'observed',
    'FEASIBLE is never shown as OPTIMAL.',
}
UI_HELPERS = {'kpi_card', 'kpi_strip', 'status_badge', 'scenario_tag', 'state_card', 'analytics_card', 'provenance_footer', 'validation_accordion', 'data_grid'}


def _source_trees():
    paths = [* (FRONTEND / 'pages').glob('*.py'), *(FRONTEND / 'components').glob('*.py')]
    return [(path, ast.parse(path.read_text(encoding='utf-8'))) for path in paths]


def _string_values(node):
    docstrings = set()
    for child in ast.walk(node):
        if isinstance(child, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = child.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str) and id(child) not in docstrings:
            yield child.value


def test_ui_calls_do_not_use_forbidden_wording():
    for path, tree in _source_trees():
        for call in (n for n in ast.walk(tree) if isinstance(n, ast.Call)):
            func = call.func
            is_ui_call = (
                isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == 'ui'
            ) or (
                isinstance(func, ast.Attribute) and func.attr in {'classes', 'style', 'props', 'tooltip', 'add_head_html'}
            ) or isinstance(func, ast.Name) and func.id in UI_HELPERS
            if is_ui_call:
                values = [value for arg in (*call.args, *(kw.value for kw in call.keywords)) for value in _string_values(arg)]
                assert not any('delayed' in value or 'proven' in value for value in values), path


def test_protected_strings_remain_in_page_or_component_literals():
    found = {}
    for path, tree in _source_trees():
        literals = list(_string_values(tree))
        for text in PROTECTED:
            if any(text in literal for literal in literals):
                found[text] = path
    # rake-balance deviation and the FEASIBLE sentence are in pages/phase1.py;
    # CANCELLED is in components/ui_elements.py and pages/phase5.py; observed is in pages/phase1.py.
    assert PROTECTED <= found.keys()


def test_color_literals_live_only_in_tokens():
    color_literal = re.compile(r'#[0-9A-Fa-f]{3,8}\b')
    for path in FRONTEND.rglob('*.py'):
        if path == FRONTEND / 'components' / 'tokens.py':
            continue
        assert not color_literal.search(path.read_text(encoding='utf-8')), path


def test_feasible_badge_stays_amber_and_distinct(monkeypatch):
    class Label:
        def __init__(self, text):
            self.text = text
            self.class_names = ''

        def classes(self, value):
            self.class_names = value
            return self

    monkeypatch.setattr(ui_elements.ui, 'label', Label)
    feasible = ui_elements.status_badge('FEASIBLE')
    optimal = ui_elements.status_badge('OPTIMAL')
    assert feasible.class_names != optimal.class_names
    assert tokens.BADGE_FEASIBLE == feasible.class_names
    assert tokens.AMBER_BG in feasible.class_names
    assert tokens.AMBER_TEXT in feasible.class_names
    assert tokens.AMBER_BORDER in feasible.class_names
    assert tokens.GREEN_BG not in feasible.class_names
    assert tokens.GREEN_TEXT not in feasible.class_names
    assert tokens.GREEN_BORDER not in feasible.class_names
    assert tokens.BADGE_OPTIMAL == optimal.class_names
    assert tokens.GREEN_BG in optimal.class_names
    assert tokens.GREEN_TEXT in optimal.class_names
    assert tokens.GREEN_BORDER in optimal.class_names


def test_plotly_helpers_preserve_gridline_and_hover_settings():
    fig = ui_elements.plotly_base_layout(go.Figure(), title='Sample')
    assert fig.layout.title.text == 'Sample'
    assert fig.layout.plot_bgcolor == tokens.PANEL
    assert ui_elements.plotly_gridlines(fig) is fig
    assert fig.layout.xaxis.gridcolor == tokens.BORDER
    assert fig.layout.yaxis.gridcolor == tokens.BORDER
    assert fig.layout.xaxis.gridwidth == 1
    assert ui_elements.plotly_hovertemplate('Trip: %{x}', 'Rake: %{y}') == 'Trip: %{x}<br>Rake: %{y}<extra></extra>'
