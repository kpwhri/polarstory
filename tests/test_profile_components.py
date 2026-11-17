"""Profile components tests."""

import polars as pl
import pytest

import polarstory as ps


def test_profile_item_is_lazy_reusable_and_cached(df):
    profile = ps.profile(df, mode='quick')
    item = profile.item('age', 'summary')
    assert item.kind == 'table'
    assert item is profile.item('age', 'summary')
    assert set(profile._metrics) == {'age'}
    assert profile.item('overview').title == 'Dataset Overview'
    assert profile.item('enctype', 'frequency') is profile.item('enctype', 'summary')
    assert profile.item('missingness').kind == 'table'


def test_profile_item_distribution_and_error(df):
    profile = ps.profile(df, columns=['age', 'enctype'])
    chart = profile.item('age', 'histogram')
    assert chart.kind == 'chart'
    assert chart is profile.item('age', 'distribution')
    assert profile.item('enctype', 'distribution').kind == 'chart'
    # invalid aliases must not bypass validation after cache population
    with pytest.raises(ValueError, match='histogram'):
        profile.item('enctype', 'histogram')
    with pytest.raises(ValueError, match='No distribution'):
        ps.profile(df, mode='quick').item('age', 'histogram')
    assert profile.item('age', 'frequency').kind == 'table'


def test_profile_sensitive_selected_component_stays_suppressed(df):
    meta = ps.Variables().set('enctype', sensitive=True)
    profile = ps.profile(df, variables=meta)
    item = profile.item('enctype', 'frequency')
    assert item.content.columns == ['metric', 'value']
    assert 'distribution suppressed' in item.caption
    with pytest.raises(ValueError, match='No distribution'):
        profile.item('enctype', 'distribution')


def test_profile_dataset_component_names_do_not_hide_real_columns():
    df = pl.DataFrame({'overview': ['A', 'B'], 'alerts': [1, 2]})
    p = ps.profile(df, mode='quick')
    assert p.item('overview', 'frequency').kind == 'table'
    assert p.item('@overview').title == 'Dataset Overview'
    assert p.item('@alerts').title == 'Data Quality Alerts'
