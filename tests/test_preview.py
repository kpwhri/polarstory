"""Static single-component and single-variable previews."""

import polarstory as ps


def test_report_item_html(df):
    item = ps.profile(df).histogram('age')
    html = item.to_html()
    assert '<svg' in html
    assert '<script' not in html
    assert 'age' in html


def test_single_variable_browser_preview_writes_file(df):
    p = ps.profile(df)
    path = p.show('age', browser=False)
    assert path.is_file()
    html = path.read_text(encoding='utf8')
    assert '<svg' in html
    assert 'age' in html
    assert 'enctype — categorical summary' not in html


def test_report_item_browser_preview_writes_file(df):
    item = ps.profile(df).frequency('enctype')
    path = item.show(browser=False)
    assert path.is_file()
    assert '<table' in path.read_text(encoding='utf8')


def test_variable_profile_show(df):
    p = ps.profile(df)
    path = p.variable('age').show(browser=False)
    assert '<svg' in path.read_text(encoding='utf8')


def test_full_profile_preview_as_file(df):
    path = ps.profile(df, mode='quick').show(browser=False)
    assert path.exists()
    assert '<script' not in path.read_text(encoding='utf8')


def test_notebook_preview_uses_scoped_light_surface(df):
    report = ps.Report('Light preview')
    report.add_table(ps.stats.frequency(df, 'enctype'), title='Encounter types')
    report.add_chart(ps.plots.frequency(df, 'enctype'), title='Encounter chart')
    notebook = report._to_notebook_html()
    standalone = report.to_html()
    assert '<div class="polarstory-notebook"' in notebook
    assert '.polarstory-notebook {' in notebook
    assert 'background: #fff' in notebook
    assert 'color: #243348' in notebook
    assert '<table' in notebook
    assert '<svg' in notebook
    assert '<!doctype html>' not in notebook
    assert 'body {' not in notebook
    assert ':root {' not in notebook
    assert '<!doctype html>' in standalone
    assert 'background: #fff' in standalone


def test_explorer_controls_have_local_light_styles(df, monkeypatch):
    import pytest
    widgets = pytest.importorskip('ipywidgets')
    display_module = pytest.importorskip('IPython.display')
    from polarstory.explorer import Explorer

    monkeypatch.setattr(display_module, 'display', lambda widget: None)
    explorer = Explorer(ps.profile(df))
    widget = explorer.show()
    assert isinstance(widget, widgets.VBox)
    assert 'polarstory-explorer' in widget._dom_classes
    stylesheet = widget.children[0].value
    assert '<style>' in stylesheet
    assert '.polarstory-explorer {' in stylesheet
    assert '.polarstory-explorer input,' in stylesheet
    assert 'background: #fff' in stylesheet
    assert 'body {' not in stylesheet
    assert ':root {' not in stylesheet


def test_notebook_preview_escapes_user_values():
    report = ps.Report('<unknown>')
    report.add_text('<script>alert(1)</script>')
    preview = report._to_notebook_html()
    assert '&lt;unknown&gt;' in preview
    assert '&lt;script&gt;' in preview
    assert '<script>' not in preview


def test_notebook_display_uses_fragment(monkeypatch):
    import polarstory.preview as preview
    import pytest

    ipython_display = pytest.importorskip('IPython.display')
    shown = []
    monkeypatch.setattr(preview, '_in_notebook', lambda: True)
    monkeypatch.setattr(ipython_display, 'display', lambda value: shown.append(value))
    report = ps.Report('Notebook test')
    report.add_text('Hello')
    assert preview.show_report(report) is None
    assert len(shown) == 1
    assert 'polarstory-notebook' in shown[0].data
    assert '<!doctype html>' not in shown[0].data


def test_notebook_preview_inherits_host_theme(df):
    report = ps.Report('Theme-aware preview')
    report.add_table(ps.stats.frequency(df, 'enctype'), title='Encounter types')
    report.add_chart(ps.plots.frequency(df, 'enctype'), title='Encounter chart')
    notebook = report._to_notebook_html()
    standalone = report.to_html()
    assert '<div class="polarstory-notebook"' in notebook
    # assert '--vscode-editor-foreground' in notebook
    assert 'background: transparent' in notebook
    assert '<table' in notebook
    assert '<svg' in notebook
    assert '<!doctype html>' not in notebook
    assert 'body {' not in notebook
    assert ':root {' not in notebook
    assert '<!doctype html>' in standalone
    assert 'background: #fff' in standalone
