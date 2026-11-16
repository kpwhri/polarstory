"""Dataset comparison against hand-calculated research extract changes."""

import polars as pl
import pytest

import polarstory as ps


@pytest.fixture
def extracts():
    baseline = pl.DataFrame({
        'age': [20.0, 30.0, 40.0, None],
        'enctype': ['ED', 'ED', 'IP', None],
        'ins_medicaid': ['Y', 'N', 'U', 'Y'],
        'legacy': [1, 2, 3, 4],
    })
    current = pl.DataFrame({
        'age': [30.0, 40.0, 50.0, 60.0, None],
        'enctype': ['ED', 'IP', 'IP', None, 'ED'],
        'ins_medicaid': ['Y', 'Y', 'N', 'U', 'U'],
        'cohort': ['A', 'A', 'B', 'B', 'B'],
    })
    return baseline, current


def test_schema_and_dataset_counts(extracts):
    result = ps.compare(*extracts)
    schema = {row['column']: row['status'] for row in result.schema_changes.to_dicts()}
    assert schema['legacy'] == 'removed'
    assert schema['cohort'] == 'added'
    assert schema['age'] == 'unchanged'
    counts = {row['metric']: row for row in result.overview.to_dicts()}
    assert counts['rows'] == {'metric': 'rows', 'baseline': 4, 'current': 5, 'difference': 1}
    assert counts['columns']['difference'] == 0


def test_null_denominators_and_numeric_changes(extracts):
    result = ps.compare(*extracts)
    missing = {row['column']: row for row in result.missingness.to_dicts()}
    assert missing['age']['baseline_nulls'] == 1
    assert missing['age']['current_nulls'] == 1
    assert missing['age']['baseline_percent'] == 25
    assert missing['age']['current_percent'] == 20
    assert missing['age']['change_pp'] == -5
    numeric = {(row['column'], row['metric']): row for row in result.numeric.to_dicts()}
    assert numeric[('age', 'mean')]['baseline'] == 30
    assert numeric[('age', 'mean')]['current'] == 45
    assert numeric[('age', 'mean')]['difference'] == 15
    assert numeric[('age', 'std')]['baseline'] == pytest.approx(10)


def test_categorical_changes_and_unknown_values(extracts):
    rows = ps.compare(*extracts).categorical.to_dicts()
    by_key = {(r['column'], r['kind'], r['value']): r for r in rows}
    ed = by_key['enctype', 'category', 'ED']
    assert (ed['baseline_count'], ed['current_count']) == (2, 2)
    assert ed['change_pp'] == pytest.approx(-10)
    unknown = by_key['ins_medicaid', 'category', 'U']
    assert unknown['change_pp'] == pytest.approx(15)
    missing = by_key['enctype', 'null', '(null)']
    assert missing['change_pp'] == pytest.approx(-5)


def test_same_results_for_lazy_and_parquet(extracts, tmp_path):
    before, after = extracts
    a, b = tmp_path / 'older.parquet', tmp_path / 'newer.parquet'
    before.write_parquet(a)
    after.write_parquet(b)
    for left, right in ((before.lazy(), after.lazy()), (a, b)):
        result = ps.compare(left, right)
        expected = ps.compare(before, after)
        assert result.schema_changes.to_dicts() == expected.schema_changes.to_dicts()
        assert result.missingness.to_dicts() == expected.missingness.to_dicts()
        numeric_rows = result.numeric.to_dicts()
        expected_rows = expected.numeric.to_dicts()
        assert len(numeric_rows) == len(expected_rows)
        for actual, reference in zip(numeric_rows, expected_rows, strict=True):
            assert actual.keys() == reference.keys()
            for key, expected_value in reference.items():
                if isinstance(expected_value, float):
                    assert actual[key] == pytest.approx(expected_value, rel=1e-12, abs=1e-12)
                else:
                    assert actual[key] == expected_value
        assert result.categorical.to_dicts() == expected.categorical.to_dicts()


def test_type_change_is_reported_and_not_compared(extracts):
    before, after = extracts
    changed = after.with_columns(pl.col('age').cast(pl.String))
    result = ps.compare(before, changed)
    schema = {r['column']: r for r in result.schema_changes.to_dicts()}
    assert schema['age']['status'] == 'type_changed'
    assert 'age' not in result.numeric['column'].to_list()


def test_bounded_categories_and_identifier_suppression():
    ids = [f'p-{i:03}' for i in range(30)]
    before = pl.DataFrame({'patient_id': ids, 'facility': ids, 'sex': ['F'] * 20 + ['M'] * 10})
    after = pl.DataFrame({'patient_id': ids, 'facility': ids, 'sex': ['F'] * 15 + ['M'] * 15})
    result = ps.compare(before, after, max_unique_for_frequency=10)
    assert set(result.skipped['column']) == {'patient_id', 'facility'}
    assert set(result.categorical['column']) == {'sex'}


def test_numeric_coded_categories(extracts):
    a, b = extracts
    a = a.with_columns(pl.Series('ins_medicaid', [1, 0, 2, 1]))
    b = b.with_columns(pl.Series('ins_medicaid', [1, 1, 0, 2, 2]))
    result = ps.compare(a, b, categorical_columns=['ins_medicaid'])
    assert 'ins_medicaid' in result.categorical['column'].to_list()
    assert 'ins_medicaid' not in result.numeric['column'].to_list()


def test_render_static_html_and_escape_values(extracts, tmp_path):
    a, b = extracts
    a = a.with_columns(pl.lit('<script>alert(1)</script>').alias('bad_label'))
    b = b.with_columns(pl.lit('<script>alert(1)</script>').alias('bad_label'))
    result = ps.compare(a, b)
    path = result.write_html(tmp_path / 'comparison.html')
    html = path.read_text(encoding='utf8')
    assert 'Dataset Comparison' in html
    assert '&lt;script&gt;' in html
    assert '<script>alert(1)</script>' not in html
    assert 'print' in html


def test_validation_limits_and_unknown_column(extracts):
    with pytest.raises(ValueError, match='max_columns'):
        ps.compare(*extracts, max_columns=2)
    with pytest.raises(ValueError, match='Unknown comparison columns'):
        ps.compare(*extracts, columns=['does_not_exist'])
    with pytest.raises(ValueError, match='max_categories'):
        ps.compare(*extracts, max_categories=0)


def test_cli_compare(tmp_path, extracts, capsys):
    from polarstory.cli import main

    a, b = tmp_path / 'older extract.parquet', tmp_path / 'new extract.parquet'
    extracts[0].write_parquet(a)
    extracts[1].write_parquet(b)
    output = tmp_path / 'comparison.html'
    assert main(['compare', str(a), str(b), '-o', str(output)]) == 0
    assert output.is_file()
    assert 'comparison.html' in capsys.readouterr().out


def test_identifier_like_numeric_not_described():
    before = pl.DataFrame({'patient_id': [1001, 1002, 1003], 'age': [20, 30, 40]})
    after = pl.DataFrame({'patient_id': [1004, 1005, 1006], 'age': [30, 40, 50]})
    result = ps.compare(before, after)
    assert 'patient_id' not in result.numeric['column'].to_list()
    assert {r['reason'] for r in result.skipped.to_dicts()} == {'identifier-like name'}


def test_missing_and_literal_null_distinct():
    a = pl.DataFrame({'status': ['(null)', None, 'U', '(null)']})
    b = pl.DataFrame({'status': [None, 'U', 'U']})
    rows = ps.compare(a, b).categorical.to_dicts()
    labels = {(r['kind'], r['value']): r for r in rows}
    assert labels['category', '(null)']['baseline_count'] == 2
    assert labels['null', '(null)']['baseline_count'] == 1
    assert labels['null', '(null)']['current_count'] == 1


def test_other_remainder_uses_exact_counts_from_both_sources():
    before = pl.DataFrame({'category': ['a'] * 4 + ['b'] * 3 + ['c'] * 2 + ['d']})
    after = pl.DataFrame({'category': ['b'] * 5 + ['c'] * 3 + ['d'] * 2})
    result = ps.compare(before, after, max_categories=2).categorical.to_dicts()
    rows = {(row['kind'], row['value']): row for row in result}
    assert rows['other', '(other categories)']['baseline_count'] == 3
    assert rows['other', '(other categories)']['current_count'] == 5
    assert sum(row['baseline_count'] for row in result) == 10
    assert sum(row['current_count'] for row in result) == 10


def test_empty_frame_comparison():
    a = pl.DataFrame(schema={'age': pl.Int64, 'enctype': pl.String})
    result = ps.compare(a, a.clone())
    assert result.overview['baseline'].to_list()[0] == 0
    assert result.missingness['baseline_percent'].to_list() == [0, 0]
    assert result.categorical.height == 0
