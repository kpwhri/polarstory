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
