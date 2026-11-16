import polars as pl
import polars.selectors as cs
import pytest

import polarstory as ps


def test_profile_columns(df):
    result = ps.profile(df, columns=cs.starts_with('ins_'))
    assert result.columns == ('ins_medicaid',)
    assert result.variable('ins_medicaid').kind == 'categorical'


def test_profile_no_charts_quick(df):
    result = ps.profile(df, mode='quick')
    assert all(item.kind != 'chart' for item in result.items())


def test_profile_output(df, tmp_path):
    path = ps.profile(df, max_columns=2).write_html(tmp_path / 'profile.html')
    html = path.read_text()
    assert '<!doctype html>' in html
    assert '<svg' in html
    assert 'enctype' in html
    assert '<script' not in html


def test_profile_limited_columns(df):
    result = ps.profile(df, exclude=['age'], max_columns=2)
    assert result.columns == ('enctype', 'ins_medicaid')
    with pytest.raises(ValueError):
        result.variable('age')


def test_full_mode_is_available(df):
    p = ps.profile(df, mode='full')
    assert p.mode == 'full'
    assert p.missingness_patterns().kind == 'table'


def test_profile_refresh(df):
    result = ps.profile(df, mode='quick')
    result.variable('enctype')
    assert result.refresh()._variables == {}


def test_empty_dataset():
    empty = pl.DataFrame(schema={'age': pl.Float64, 'enctype': pl.String})
    p = ps.profile(empty)
    assert p.overview['rows'].item() == 0
    assert p.variable('age').table['finite_count'].item() == 0
    assert '<!doctype html>' in p.to_html()


def test_profile_rejects_invalid_batch_size(df):
    with pytest.raises(ValueError, match='batch_size'):
        ps.ProfileOptions(batch_size=0)
