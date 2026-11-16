"""Synthetic healthcare reference checks for univariate and grouped metrics."""

import math

import polars as pl
import pytest

import polarstory as ps
from reference_healthcare import BASELINE, DUPLICATE_ROWS, EXPECTED, check_reference_contract


@pytest.fixture(params=['dataframe', 'lazyframe', 'parquet'])
def source(request, tmp_path):
    """Exercise all supported source pathways with identical observations."""
    frame = pl.DataFrame(BASELINE)
    if request.param == 'dataframe':
        return frame
    if request.param == 'lazyframe':
        return frame.lazy()
    path = tmp_path / 'synthetic cohort.parquet'
    frame.write_parquet(path)
    return path


def test_fixed_reference_contract():
    """Catch accidental changes to observations or their frozen targets."""
    check_reference_contract()


def test_numeric_distribution_and_iqr_outlier_rule(source):
    row = ps.stats.numeric(source, 'age').row(0, named=True)
    assert row['rows'] == EXPECTED['rows']
    assert row['finite_count'] == 8
    assert row['mean'] == pytest.approx(EXPECTED['age_mean'], abs=1e-12)
    assert row['std'] == pytest.approx(EXPECTED['age_sample_sd'], abs=1e-10)
    assert row['q25'] == pytest.approx(EXPECTED['age_q25'])
    assert row['q75'] == pytest.approx(EXPECTED['age_q75'])
    assert row['iqr'] == pytest.approx(3)

    outliers = ps.stats.outliers(source, 'age').row(0, named=True)
    assert outliers['lower_bound'] == pytest.approx(17.5)
    assert outliers['upper_bound'] == pytest.approx(29.5)
    assert outliers['outlier_count'] == EXPECTED['age_outlier_count']
    assert outliers['outlier_percent'] == pytest.approx(12.5)


def test_null_nan_and_infinities_are_distinct(source):
    row = ps.stats.numeric(source, 'lab_result').row(0, named=True)
    assert row['finite_count'] == EXPECTED['lab_finite_count']
    assert row['null_count'] == EXPECTED['lab_null_count']
    assert row['nan_count'] == EXPECTED['lab_nan_count']
    assert row['infinite_count'] == EXPECTED['lab_infinite_count']
    assert row['mean'] == pytest.approx(EXPECTED['lab_mean'])
    assert row['std'] == pytest.approx(math.sqrt(5 / 3))
    inventory = {r['column']: r for r in ps.stats.missingness(source).to_dicts()}
    assert inventory['lab_result']['null_count'] == 1
    assert inventory['lab_result']['null_percent'] == pytest.approx(12.5)


def test_insurance_unknown_and_null_are_separate(source):
    records = ps.stats.frequency(source, 'ins_medicaid', top_n=5).to_dicts()
    counts = {(r['kind'], r['value']): r for r in records}
    assert counts['category', 'Y']['count'] == 3
    assert counts['category', 'N']['count'] == 2
    assert counts['category', 'U']['count'] == 2
    assert counts['category', 'U']['percent'] == pytest.approx(25)
    assert counts['null', '(null)']['count'] == 1
    assert counts['null', '(null)']['percent'] == pytest.approx(12.5)
    assert sum(r['count'] for r in records) == EXPECTED['rows']

    valid = ps.stats.frequency(source, 'ins_medicaid', denominator='valid').to_dicts()
    valid_by_kind = {(r['kind'], r['value']): r for r in valid}
    assert valid_by_kind['category', 'Y']['percent'] == pytest.approx(42.86)
    assert valid_by_kind['null', '(null)']['percent'] is None


def test_group_percentages_use_correct_denominators(source):
    rows = ps.stats.crosstab(
        source, 'ins_medicaid', by='enctype', denominator='group'
    ).to_dicts()
    cells = {(r['group'], r['value']): r for r in rows}
    assert cells['ED', 'Y']['count'] == 2
    assert cells['ED', 'Y']['percent'] == 50
    assert cells['ED', 'N']['percent'] == 25
    assert cells['ED', '(null)']['percent'] == 25
    assert cells['IP', 'U']['count'] == 2
    assert cells['IP', 'U']['percent'] == 50
    assert sum(r['count'] for r in rows) == 8


def test_missingness_patterns_with_independently_counted_combinations(source):
    rows = ps.stats.missingness_patterns(
        source, columns=['flag_a', 'flag_b', 'flag_c'], top_n=10,
    ).to_dicts()
    observed = {r['missing_columns']: r['count'] for r in rows}
    assert observed == EXPECTED['missingness_patterns']
    assert sum(r['count'] for r in rows) == 8
    assert next(r['percent'] for r in rows if r['missing_columns'] == '(none)') == 37.5


def test_distinct_non_null_values_and_diagnostic_text(source):
    by_column = {r['column']: r for r in ps.stats.uniqueness(
        source, columns=['ins_medicaid', 'patient_id'], exact=True,
    ).to_dicts()}
    assert by_column['ins_medicaid']['non_null'] == 7
    assert by_column['ins_medicaid']['distinct'] == 3
    assert by_column['ins_medicaid']['distinct_percent'] == pytest.approx(42.86)
    assert by_column['patient_id']['distinct'] == 8
    assert by_column['patient_id']['distinct_percent'] == 100

    text = ps.stats.text(source, 'note_text').row(0, named=True)
    assert text['empty_count'] == EXPECTED['text_empty_count']
    assert text['blank_count'] == EXPECTED['text_blank_count']
    assert text['whitespace_only_count'] == EXPECTED['text_whitespace_only_count']
    assert text['null_count'] == 1


def test_rare_categories_and_category_imbalance(source):
    row = ps.stats.categorical_diagnostics(
        source, 'ins_medicaid', rare_at_most=2,
    ).row(0, named=True)
    assert row['distinct_count'] == 3
    assert row['non_null_count'] == 7
    assert row['rare_categories'] == 2
    assert row['rare_records'] == 4
    assert row['dominant_percent'] == pytest.approx(42.86)


def test_stratified_numeric_mean(source):
    rows = ps.stats.summary(source, ['age'], by='enctype').to_dicts()
    summary = {(r['group'], r['statistic']): r['value'] for r in rows}
    assert summary['ED', 'finite_count'] == 4
    assert summary['ED', 'mean'] == pytest.approx(22.75)
    assert summary['IP', 'finite_count'] == 4
    assert summary['IP', 'mean'] == pytest.approx(42.5)


def test_duplicate_rows_are_excess_rows_not_all_members(tmp_path):
    frame = pl.DataFrame(DUPLICATE_ROWS)
    path = tmp_path / 'duplicate examples.parquet'
    frame.write_parquet(path)
    for source in (frame, frame.lazy(), path):
        row = ps.stats.duplicates(source).row(0, named=True)
        assert row['rows'] == 8
        assert row['unique_rows'] == 4
        assert row['duplicate_rows'] == EXPECTED['excess_duplicate_rows']
        assert row['duplicate_percent'] == EXPECTED['duplicate_percent']


def test_table1_fixed_grouped_cells(source):
    summary = ps.stats.table1(source, ['ins_medicaid'], by='enctype')
    rows = {r['Level']: r for r in summary.to_dicts()}
    assert rows['Y']['Overall (N=8)'] == '3 (37.5%)'
    assert rows['Y']['ED (N=4)'] == '2 (50.0%)'
    assert rows['U']['IP (N=4)'] == '2 (50.0%)'
    assert rows['(null)']['ED (N=4)'] == '1 (25.0%)'
