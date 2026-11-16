"""Single-variable explorer, stratification, and report collection tests."""

import polars as pl
import pytest

import polarstory as ps


def test_explorer_without_notebook_dependency(df):
    p = ps.profile(df)
    e = p.explore(show=False)
    assert isinstance(e, ps.Explorer)
    assert e.profile is p
    assert e.report.title == 'Selected findings'
    assert ps.explore(df, show=False).profile.columns == p.columns


def test_default_variable_preview_is_cached(df):
    explorer = ps.explore(df, show=False)
    first = explorer.preview('age')
    assert [item.kind for item in first] == ['table', 'chart']
    assert first is explorer.preview('age')
    assert explorer.preview('enctype', view='frequency')[0].kind == 'table'


def test_optional_numeric_bin_setting(df):
    e = ps.explore(df, show=False)
    result = e.preview('age', view='distribution', bins=7)
    assert result[0].kind == 'chart'
    with pytest.raises(ValueError, match='bins'):
        e.preview('age', bins=0)


def test_categorical_percent_denominator(df):
    e = ps.explore(df, show=False)
    rows = e.preview('enctype', view='frequency', denominator='valid')[0].content
    assert rows['kind'].to_list().count('null') == 1
    null = next(row for row in rows.to_dicts() if row['kind'] == 'null')
    assert null['percent'] is None


def test_stratified_numeric_and_categorical(df):
    e = ps.explore(df, show=False)
    numeric = e.preview('age', by='enctype')
    assert [item.kind for item in numeric] == ['table', 'chart']
    assert set(numeric[0].content['statistic'].to_list()) >= {'median', 'q25', 'q75'}
    categorical = e.preview('ins_medicaid', by='enctype', denominator='group')
    assert [item.kind for item in categorical] == ['table', 'chart']
    assert 'percent' in categorical[0].content.columns


def test_stratification_restrictions(df):
    e = ps.explore(df, show=False)
    with pytest.raises(ValueError, match='categorical'):
        e.preview('enctype', by='age')
    with pytest.raises(ValueError, match='different'):
        e.preview('enctype', by='enctype')
    with pytest.raises(ValueError, match='denominator'):
        e.preview('enctype', by='ins_medicaid', denominator='valid')


def test_complete_variable_can_be_added_to_report(df):
    p = ps.profile(df)
    report = ps.Report('Selected')
    selected = p.variable('age')
    assert selected.report_items() == p.variable_items('age')
    added = report.add(selected)
    assert len(added) == 2
    assert [item.kind for item in added] == ['table', 'chart']
    assert added == report.items
    assert '<svg' in report.to_html()


def test_explorer_add_to_report_preserves_view(df):
    e = ps.explore(df, show=False)
    added = e.add_to_report('enctype', view='frequency', top_n=2, denominator='total')
    assert len(added) == 1
    assert added[0].kind == 'table'
    assert len(e.report.items) == 1
    assert sum(row['count'] for row in added[0].content.to_dicts()) == df.height


def test_sensitive_variable_values_never_leak_in_explorer():
    data = pl.DataFrame({'patient_id': ['top-secret-1', 'top-secret-2']})
    meta = ps.Variables().set('patient_id', kind='categorical', sensitive=True)
    e = ps.explore(data, variables=meta, show=False)
    assert 'top-secret' not in e.preview('patient_id')[0].content.__repr__()
    with pytest.raises(ValueError, match='suppressed'):
        e.preview('patient_id', view='frequency')
    with pytest.raises(ValueError, match='suppressed'):
        e.preview('patient_id', view='distribution')


def test_identifier_like_column_does_not_expose_values():
    data = pl.DataFrame({'patient_id': [100001, 100002]})
    e = ps.explore(data, show=False)
    assert '100001' not in str(e.preview('patient_id'))


def test_explorer_recipe_round_trip(tmp_path, df):
    path = tmp_path / 'input.parquet'
    df.write_parquet(path)
    e = ps.explore(path, show=False)
    e.add_to_report('age', view='distribution', bins=7)
    e.add_to_report('enctype', view='frequency', top_n=2, denominator='valid')
    e.add_to_report('age', view='summary', by='enctype')
    spec = e.report.write_spec(tmp_path / 'report.json')
    recreated = ps.Report.from_spec(spec)
    assert len(recreated.items) == 3
    assert recreated.items[1].content.to_dicts() == e.report.items[1].content.to_dicts()
    assert recreated.items[2].content.to_dicts() == e.report.items[2].content.to_dicts()
    assert '<svg' in recreated.to_html()


def test_cached_preview_bounded(df):
    e = ps.explore(df, show=False)
    for bins in range(1, 21):
        e.preview('age', bins=bins)
    assert len(e._cache) == 12


def test_missing_widget_error_is_helpful(df, monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, 'ipywidgets', None)
    e = ps.explore(df, show=False)
    with pytest.raises(ImportError, match='polarstory\\[notebook\\]'):
        e.show()


def test_thirty_three_groups_allow_table_but_not_default_chart():
    data = pl.DataFrame({
        'facility': [f'facility-{i:02}' for i in range(33)],
        'age': [float(i + 20) for i in range(33)],
        'flag': ['Y' if i % 2 else 'N' for i in range(33)],
    })
    metadata = ps.Variables().set('facility', kind='categorical')
    explorer = ps.explore(data, show=False, variables=metadata)
    table_only = explorer.preview('age', by='facility')
    assert [item.kind for item in table_only] == ['table']
    assert table_only[0].content['group'].n_unique() == 33
    with pytest.raises(ValueError, match='33 selected groups; chart limit is 20'):
        explorer.preview('age', by='facility', view='distribution')
    chart = explorer.preview('age', by='facility', view='distribution',
                             groups=['facility-00', 'facility-01'])
    assert chart[0].kind == 'chart'
    counts = explorer.preview('flag', by='facility', view='frequency')
    assert counts[0].content['group'].n_unique() == 33


def test_grouping_limits_and_selection(tmp_path):
    data = pl.DataFrame({
        'facility': [f'f{i:02}' for i in range(33)],
        'age': list(range(33)),
    })
    variables = ps.Variables().set('facility', kind='categorical')
    path = tmp_path / 'grouped.parquet'
    data.write_parquet(path)
    explorer = ps.explore(path, show=False, variables=variables)
    explorer.add_to_report('age', by='facility', view='summary', groups=['f01', 'f03'])
    spec = explorer.report.write_spec(tmp_path / 'selection.json')
    restored = ps.Report.from_spec(spec)
    assert restored.items[0].content.to_dicts() == explorer.report.items[0].content.to_dicts()
    limited = ps.explore(data, show=False, variables=variables,
                         options=ps.ProfileOptions(max_groups=10))
    with pytest.raises(ValueError, match='summary-table limit is 10'):
        limited.preview('age', by='facility')
    with pytest.raises(ValueError, match='Select at least one group'):
        explorer.preview('age', by='facility', groups=[])
    with pytest.raises(ValueError, match='not present'):
        explorer.preview('age', by='facility', groups=['unknown'])
