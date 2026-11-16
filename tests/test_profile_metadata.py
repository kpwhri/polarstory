"""Profile metadata tests."""

import polars as pl
import polars.selectors as cs
import pytest

import polarstory as ps


def test_metadata_labels_and_order_in_profile(df):
    variables = (
        ps.Variables()
        .set('enctype', label='Encounter type')
        .set('ins_medicaid', kind='categorical', order=['N', 'Y', 'U'],
             value_labels={'U': 'Unknown', 'Y': 'Yes', 'N': 'No'})
    )
    p = ps.profile(df, columns=['enctype', 'ins_medicaid'], variables=variables, mode='quick')
    values = p.variable('ins_medicaid').table['value'].to_list()
    assert values == ['No', 'Yes', 'Unknown']
    html = p.to_html()
    assert 'Encounter type' in html
    assert 'Unknown' in html
    assert 'Contents' in html


def test_sensitive_column_suppresses_values_and_charts(df):
    variables = ps.Variables().set('enctype', sensitive=True)
    p = ps.profile(df, columns=['enctype'], variables=variables)
    assert p.variable('enctype').chart is None
    assert p.variable('enctype').table.columns == ['dtype', 'null_count', 'null_percent']
    html = p.to_html()
    assert 'ED' not in html
    assert 'distribution suppressed' in html


def test_sensitive_opt_in(df):
    variables = ps.Variables().set('enctype', sensitive=True)
    p = ps.profile(df, columns=['enctype'], variables=variables, options=ps.ProfileOptions(include_sensitive=True))
    assert p.variable('enctype').chart is not None


def test_explicit_text_summary_and_static_length_chart():
    df = pl.DataFrame({'note': ['foo', 'two words', None, '', '   ']})
    variables = ps.Variables().set('note', kind='text')
    p = ps.profile(df, variables=variables)
    v = p.variable('note')
    assert v.kind == 'text'
    assert v.table.row(0, named=True)['empty_count'] == 1
    assert v.table.row(0, named=True)['blank_count'] == 2
    assert v.chart is not None


def test_auto_text_classification_uses_bounded_preview():
    # distinct values should not produce unbounded frequency tables
    data = pl.DataFrame({'note': [f'unique_{i:03d}' for i in range(80)]})
    p = ps.profile(data, mode='quick')
    assert p.variable('note').kind == 'text'
    assert p.variable('note').table['rows'].item() == 80


def test_categorical_small_dataframe_not_misclassified(df):
    assert ps.profile(df, mode='quick').variable('enctype').kind == 'categorical'


def test_sensitive_text_no_type_preview():
    df = pl.DataFrame({'notes': [f'unique_{i:03d}' for i in range(90)]})
    conf = ps.Variables().set('notes', sensitive=True)
    p = ps.profile(df, variables=conf, mode='quick')
    assert p.variable('notes').chart is None
    assert p._inferred_kinds == {}
    assert 'unique_000' not in p.to_html()


def test_invalid_semantic_override_fails_helpfully(df):
    variables = ps.Variables().set('enctype', kind='numeric')
    with pytest.raises(TypeError, match='cannot be profiled as numeric'):
        ps.profile(df, variables=variables).variable('enctype')


def test_variables_selector_and_label(df):
    config = ps.Variables().set(cs.starts_with('ins_'), kind='categorical')
    config.set('enctype', label='Encounter type')
    profile = ps.profile(df, mode='quick', variables=config)
    assert profile.metadata['ins_medicaid'].kind == 'categorical'
    assert any(item.title.startswith('Encounter type') for item in profile.items())


def test_variables_ignore(df):
    config = ps.Variables().set('age', kind='ignore')
    profile = ps.profile(df, variables=config)
    assert 'age' not in profile.columns
