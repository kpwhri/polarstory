"""Independently specified differences between synthetic cohort extracts."""

import polars as pl
import pytest

import polarstory as ps
from reference_healthcare import BASELINE, CURRENT, COMPARISON_EXPECTED


@pytest.mark.parametrize('source_kind', ['dataframe', 'lazyframe', 'parquet'])
def test_known_cohort_changes(source_kind, tmp_path):
    before, after = pl.DataFrame(BASELINE), pl.DataFrame(CURRENT)
    if source_kind == 'lazyframe':
        before, after = before.lazy(), after.lazy()
    elif source_kind == 'parquet':
        before_path = tmp_path / 'baseline cohort.parquet'
        after_path = tmp_path / 'followup cohort.parquet'
        before.write_parquet(before_path)
        after.write_parquet(after_path)
        before, after = before_path, after_path

    result = ps.compare(before, after, exclude=['note_text'])
    overview = {r['metric']: r for r in result.overview.to_dicts()}
    assert overview['rows']['baseline'] == COMPARISON_EXPECTED['baseline_rows']
    assert overview['rows']['current'] == COMPARISON_EXPECTED['current_rows']
    assert overview['rows']['difference'] == 2
    schema = {r['column']: r['status'] for r in result.schema_changes.to_dicts()}
    assert schema['legacy'] == 'removed'
    assert schema['cohort'] == 'added'
    assert schema['age'] == 'unchanged'

    missing = {r['column']: r for r in result.missingness.to_dicts()}
    assert missing['flag_a']['baseline_nulls'] == 3
    assert missing['flag_a']['current_nulls'] == 4
    assert missing['flag_a']['change_pp'] == pytest.approx(2.5)
    assert missing['flag_c']['baseline_nulls'] == 2
    assert missing['flag_c']['current_nulls'] == 0
    assert missing['flag_c']['change_pp'] == pytest.approx(-25)
    assert missing['ins_medicaid']['change_pp'] == pytest.approx(-2.5)

    numeric = {(r['column'], r['metric']): r for r in result.numeric.to_dicts()}
    assert numeric['age', 'mean']['baseline'] == pytest.approx(32.625)
    assert numeric['age', 'mean']['current'] == pytest.approx(30.8)
    assert numeric['age', 'mean']['difference'] == pytest.approx(-1.825)
    assert numeric['lab_result', 'mean']['baseline'] == pytest.approx(2.5)
    assert numeric['lab_result', 'mean']['current'] == pytest.approx(4)
    assert numeric['lab_result', 'mean']['difference'] == pytest.approx(1.5)
    assert numeric['lab_result', 'finite_count']['difference'] == 3
    assert 'patient_id' not in result.numeric['column'].to_list()

    categorical = {(r['column'], r['kind'], r['value']): r
                   for r in result.categorical.to_dicts()}
    yes = categorical['ins_medicaid', 'category', 'Y']
    assert yes['baseline_count'] == 3
    assert yes['current_count'] == 4
    assert yes['baseline_percent'] == pytest.approx(37.5)
    assert yes['current_percent'] == pytest.approx(40)
    assert yes['change_pp'] == pytest.approx(2.5)
    assert categorical['ins_medicaid', 'category', 'U']['change_pp'] == pytest.approx(5)
    assert categorical['ins_medicaid', 'null', '(null)']['change_pp'] == pytest.approx(-2.5)
    assert categorical['enctype', 'category', 'ED']['change_pp'] == pytest.approx(10)

    skipped = {r['column']: r['reason'] for r in result.skipped.to_dicts()}
    assert skipped['patient_id'] == 'identifier-like name'
    assert skipped['cohort'] == 'column not present in both datasets'
    assert skipped['legacy'] == 'column not present in both datasets'


def test_comparison_is_descriptive_and_can_be_reported(tmp_path):
    comparison = ps.compare(pl.DataFrame(BASELINE), pl.DataFrame(CURRENT),
                            exclude=['patient_id', 'note_text'])
    output = comparison.write_html(tmp_path / 'cohort comparison.html')
    html = output.read_text(encoding='utf8')
    assert 'Dataset Comparison' in html
    assert 'Missingness Comparison' in html
    assert 'Category Distribution Changes' in html
    assert '<script' not in html
    assert 'patient_id' not in comparison.columns
    assert 'note_text' not in comparison.columns
    assert 'P001' not in html
