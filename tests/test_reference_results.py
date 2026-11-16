"""Statistical reference values independent of polarstory's implementations."""

from math import sqrt
from statistics import mean, stdev

import polars as pl
import pytest

import polarstory as ps


@pytest.fixture
def clinical_reference():
    return pl.DataFrame({
        'age': [10.0, 11.0, 12.0, 13.0, 100.0],
        'insurance': ['Y', 'N', 'U', 'Y', None],
        'encounter': ['ED', 'ED', 'IP', 'ED', 'IP'],
    })


def test_known_numeric_distribution(clinical_reference):
    values = [10, 11, 12, 13, 100]
    result = ps.stats.numeric(clinical_reference, 'age').row(0, named=True)
    assert result['mean'] == pytest.approx(mean(values))
    assert result['std'] == pytest.approx(stdev(values))
    assert result['min'] == 10
    assert result['max'] == 100
    assert result['finite_count'] == 5
    assert result['iqr'] == pytest.approx(2)


def test_hand_counted_categories_and_percentages(clinical_reference):
    result = ps.stats.frequency(clinical_reference, 'insurance').to_dicts()
    rows = {(r['kind'], r['value']): r for r in result}
    assert rows['category', 'Y']['count'] == 2
    assert rows['category', 'Y']['percent'] == 40
    assert rows['category', 'U']['count'] == 1
    assert rows['category', 'U']['percent'] == 20
    assert rows['null', '(null)']['count'] == 1
    assert rows['null', '(null)']['percent'] == 20
    assert sum(r['count'] for r in result) == 5


def test_outlier_and_duplicate_reference(clinical_reference):
    outliers = ps.stats.outliers(clinical_reference, 'age').row(0, named=True)
    assert outliers['outlier_count'] == 1
    rows = pl.DataFrame({'x': [1, 1, 2, 2, 2], 'y': ['a', 'a', 'b', 'b', 'b']})
    duplicates = ps.stats.duplicates(rows).row(0, named=True)
    assert duplicates['rows'] == 5
    assert duplicates['unique_rows'] == 2
    assert duplicates['duplicate_rows'] == 3


def test_source_equivalence(clinical_reference, tmp_path):
    path = tmp_path / 'clinical.parquet'
    clinical_reference.write_parquet(path)
    eager = ps.stats.numeric(clinical_reference, 'age').row(0, named=True)
    for data in (clinical_reference.lazy(), path):
        result = ps.stats.numeric(data, 'age').row(0, named=True)
        assert result['mean'] == pytest.approx(eager['mean'])
        assert result['std'] == pytest.approx(eager['std'])
        assert ps.stats.frequency(data, 'insurance').to_dicts() == (
            ps.stats.frequency(clinical_reference, 'insurance').to_dicts()
        )


def test_known_missingness_association():
    # identical missing indicators imply phi=1
    rows = pl.DataFrame({'a': [None, None, 1, 2], 'b': [None, None, 8, 9]})
    result = ps.stats.missingness_associations(rows).row(0, named=True)
    assert result['both_missing'] == 2
    assert result['phi'] == pytest.approx(1.0)


def test_reference_sample_sd_definition():
    # independent standard-library reference
    expected = stdev([2, 4, 6])
    actual = ps.stats.numeric(pl.DataFrame({'value': [2, 4, 6]}), 'value')
    assert actual['std'].item() == pytest.approx(expected)
    assert expected == pytest.approx(sqrt(4))


def test_null_is_distinct_from_nan_and_infinity():
    frame = pl.DataFrame({'value': [1.0, float('nan'), None, float('inf'), 3.0]})
    result = ps.stats.numeric(frame, 'value').row(0, named=True)
    assert result['finite_count'] == 2
    assert result['null_count'] == 1
    assert result['nan_count'] == 1
    assert result['infinite_count'] == 1
    assert result['mean'] == pytest.approx(2)
    assert ps.stats.missingness(frame)['null_count'].to_list() == [1]


def test_crosstab_group_denominators_from_known_counts(clinical_reference):
    result = ps.stats.crosstab(clinical_reference, 'insurance', by='encounter', denominator='group')
    rows = {(row['group'], row['value']): row for row in result.to_dicts()}
    assert rows['ED', 'Y']['count'] == 2
    assert rows['ED', 'Y']['percent'] == pytest.approx(66.67)
    assert rows['IP', 'U']['percent'] == 50
    assert rows['IP', '(null)']['count'] == 1


def test_known_negative_correlation():
    # y is an exact negative linear transformation of x
    df = pl.DataFrame({'x': [1., 2., 3., 4.], 'y': [8., 6., 4., 2.]})
    row = ps.stats.correlations(df, columns=['x', 'y']).row(0, named=True)
    assert row['n'] == 4
    assert row['correlation'] == pytest.approx(-1)


def test_complementary_missingness_phi():
    frame = pl.DataFrame({'a': [None, None, 1, 2], 'b': [1, 2, None, None]})
    row = ps.stats.missingness_associations(frame).row(0, named=True)
    assert row['both_missing'] == 0
    assert row['phi'] == pytest.approx(-1)
