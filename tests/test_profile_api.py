"""Autocomplete-friendly profile components and cardinality safeguards."""

import polars as pl
import pytest

import polarstory as ps


def test_typed_component_methods_reuse_cached_items(df):
    p = ps.profile(df)
    assert p.histogram('age') is p.item('age', 'histogram')
    assert p.frequency('enctype') is p.item('enctype', 'frequency')
    assert p.summary('age') is p.item('age', 'summary')
    assert p.distribution('age') is p.histogram('age')
    assert p.timeline('tx_ep_start').kind == 'chart'
    assert p.missingness_chart().kind == 'chart'


def test_numeric_frequency_for_discrete_values(df):
    p = ps.profile(df)
    item = p.frequency('age')
    assert item.kind == 'table'
    rows = item.content.to_dicts()
    assert sum(r['count'] for r in rows) == df.height
    assert next(r['count'] for r in rows if r['kind'] == 'null') == 1
    assert any(r['value'] == '12.0' for r in rows)
    assert item is p.frequency('age')


def test_numeric_frequency_respects_cardinality_limit():
    df = pl.DataFrame({'value': list(range(500))})
    p = ps.profile(df, options=ps.ProfileOptions(max_unique_for_frequency=10))
    with pytest.raises(ValueError, match='histogram'):
        p.frequency('value')
    assert p.histogram('value').kind == 'chart'


def test_high_cardinality_string_does_not_create_frequency_table():
    df = pl.DataFrame({'code': [f'longcode-{i}' for i in range(200)]})
    variables = ps.Variables().set('code', kind='categorical')
    p = ps.profile(df, variables=variables,
                   options=ps.ProfileOptions(max_unique_for_frequency=10))
    summary = p.summary('code')
    assert 'Suppressed' in str(summary.content)
    with pytest.raises(ValueError, match='No distribution'):
        p.distribution('code')


@pytest.mark.parametrize('values', [['a1', 'b2', 'c3'], [1234567, 2345678, 3456789]])
def test_identifier_like_column_is_suppressed_by_default(values):
    df = pl.DataFrame({'patient_id': values})
    p = ps.profile(df)
    assert p.variable('patient_id').kind == 'identifier'
    html = p.to_html()
    for value in values:
        assert str(value) not in html


def test_inventory_contains_types_and_labels(df):
    variables = ps.Variables().set('enctype', label='Encounter type')
    p = ps.profile(df, variables=variables, mode='quick')
    inventory = p.inventory
    assert set(inventory.columns) == {'column', 'label', 'dtype', 'type', 'null_percent'}
    value = next(v for v in inventory.to_dicts() if v['column'] == 'enctype')
    assert value['label'] == 'Encounter type'
    assert p.item('@inventory').kind == 'table'
    assert 'Variable inventory' in p.to_html()


def test_frequency_numeric_replays_from_parquet(tmp_path):
    path = tmp_path / 'values.parquet'
    pl.DataFrame({'age': [1, 2, 1, None]}).write_parquet(path)
    original = ps.profile(path).frequency('age')
    report = ps.Report('Counts')
    report.add(original)
    recipe = report.write_spec(tmp_path / 'counts.json')
    recreated = ps.Report.from_spec(recipe)
    assert recreated.items[0].content.to_dicts() == original.content.to_dicts()


def test_typed_methods_reject_incompatible_kinds(df):
    p = ps.profile(df)
    with pytest.raises(ValueError, match='histogram'):
        p.histogram('enctype')
    with pytest.raises(ValueError, match='frequency'):
        p.frequency('tx_ep_start')


def test_cardinality_query_only_runs_when_numeric_frequency_requested(df):
    p = ps.profile(df, mode='quick')
    p.summary('age')
    assert 'approx_unique_count' not in p._metrics['age']
    p.frequency('age')
    assert 'approx_unique_count' in p._metrics['age']


def test_rejects_unknown_dataset_component(df):
    p = ps.profile(df)
    with pytest.raises(ValueError, match='no chart'):
        p.item('@overview', 'chart')
