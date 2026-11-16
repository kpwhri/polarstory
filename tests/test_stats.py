import polars as pl
import pytest

import polarstory as ps
from polarstory import stats


def test_overview(df):
    summary = stats.overview(df).row(0, named=True)
    assert summary['rows'] == 6
    assert summary['columns'] == 4
    assert summary['null_cells'] == 3


def test_missingness(df):
    values = {row['column']: row for row in stats.missingness(df).to_dicts()}
    assert values['age']['null_count'] == 1
    assert values['ins_medicaid']['null_count'] == 0
    assert values['tx_ep_start']['null_count'] == 1


def test_frequency_preserves_unknown(df):
    result = stats.frequency(df, 'ins_medicaid')
    values = {r['value']: r for r in result.to_dicts()}
    assert values['U']['count'] == 2
    assert values['U']['kind'] == 'category'
    assert set(values) == {'Y', 'N', 'U'}
    assert sum(r['count'] for r in result.to_dicts()) == 6


def test_frequency_other_and_null(df):
    rows = stats.frequency(df, 'enctype', top_n=1).to_dicts()
    assert any(r['kind'] == 'other' for r in rows)
    assert any(r['kind'] == 'null' and r['count'] == 1 for r in rows)
    assert sum(r['count'] for r in rows) == 6


def test_frequency_valid_denominator(df):
    rows = stats.frequency(df, 'enctype', denominator='valid').to_dicts()
    assert next(r['percent'] for r in rows if r['value'] == 'ED') == 60.0
    assert next(r['percent'] for r in rows if r['kind'] == 'null') is None


def test_numeric_separates_nan_and_null(df):
    row = stats.numeric(df, 'age').row(0, named=True)
    assert row['rows'] == 6
    assert row['null_count'] == 1
    assert row['nan_count'] == 1
    assert row['finite_count'] == 4
    assert row['mean'] == 30.75


def test_temporal(df):
    row = stats.temporal(df, 'tx_ep_start').row(0, named=True)
    assert row['null_count'] == 1
    assert row['unique_count'] >= 4


def test_bad_numeric_dtype(df):
    with pytest.raises(TypeError):
        stats.numeric(df, 'enctype')


def test_empty_frequency_and_missingness():
    empty = pl.DataFrame(schema={'group': pl.String, 'value': pl.Float64})
    assert stats.frequency(empty, 'group').height == 0
    assert stats.missingness(empty)['null_percent'].to_list() == [0.0, 0.0]


def test_text_rejects_numeric(df):
    with pytest.raises(TypeError):
        ps.stats.text(df, 'age')


def test_frequency_works_with_internal_alias_like_column_names():
    frame = pl.DataFrame({'_count': ['a', 'b', 'a']})
    assert ps.stats.frequency(frame, '_count')['count'].sum() == 3


def test_crosstab_null_category_name_does_not_change_denominator():
    frame = pl.DataFrame({'label': ['(null)', None, 'A'], 'group': ['X', 'X', 'X']})
    table = ps.stats.crosstab(frame, 'label', by='group', denominator='row')
    assert table['count'].sum() == 3
    assert table['percent'].to_list() == [100.0, 100.0, 100.0]


def test_crosstab(df):
    result = ps.stats.crosstab(df, 'enctype', by='ins_medicaid')
    rows = result.to_dicts()
    assert sum(row['count'] for row in rows) == df.height
    group_n = sum(r['count'] for r in rows if r['group'] == 'Y')
    assert group_n == 2
    assert sum(r['percent'] for r in rows if r['group'] == 'Y') == 100


def test_crosstab_no_null(df):
    result = ps.stats.crosstab(df, 'enctype', by='ins_medicaid', include_null=False)
    assert result['count'].sum() == 5
    assert '(null)' not in result['value'].to_list()


def test_summary(df):
    result = ps.stats.summary(df, ['age', 'enctype'], by='ins_medicaid')
    assert set(result['group']) == {'Y', 'N', 'U'}
    assert 'mean' in result['statistic'].to_list()
    assert 'count' in result['statistic'].to_list()


def test_correlations(df):
    data = df.with_columns((pl.col('age') * 2).alias('age_twice'))
    result = ps.stats.correlations(data, columns=['age', 'age_twice'])
    row = result.row(0, named=True)
    assert row['n'] == 4  # nulls and NaNs excluded
    assert row['correlation'] == pytest.approx(1.0)


def test_correlations_rejects_non_numeric(df):
    with pytest.raises(TypeError):
        ps.stats.correlations(df, columns=['enctype'])
