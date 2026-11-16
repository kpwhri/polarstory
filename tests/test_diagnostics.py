"""Bounded diagnostic statistics and reusable profile components."""

import polars as pl
import pytest

import polarstory as ps


def test_missingness_patterns_count_and_remainder():
    df = pl.DataFrame({
        'a': [None, None, 1, 2, None],
        'b': [None, None, 3, None, 5],
    })
    result = ps.stats.missingness_patterns(df, top_n=2)
    values = result.to_dicts()
    assert sum(item['count'] for item in values) == df.height
    assert next(item['count'] for item in values if item['missing_columns'] == 'a, b') == 2
    assert any(item['missing_columns'] == '(other patterns)' for item in values)
    assert all(0 <= item['percent'] <= 100 for item in values)


def test_missingness_associations_perfect_and_constant():
    df = pl.DataFrame({
        'a': [None, None, 1, 2],
        'b': [None, None, 3, 4],
        'c': [1, 2, 3, 4],
    })
    frame = ps.stats.missingness_associations(df)
    records = {(r['left'], r['right']): r for r in frame.to_dicts()}
    assert records[('a', 'b')]['phi'] == pytest.approx(1.0)
    assert records[('a', 'c')]['phi'] is None
    assert records[('a', 'b')]['both_missing'] == 2


def test_missingness_nan_flag_is_explicit():
    df = pl.DataFrame({'a': [1., float('nan'), None], 'b': [None, 1, 2]})
    ordinary = ps.stats.missingness_patterns(df, include_nan=False)
    extended = ps.stats.missingness_patterns(df, include_nan=True)
    assert sum(r['count'] for r in ordinary.to_dicts()) == 3
    assert sum(r['count'] for r in extended.to_dicts()) == 3
    assert {r['missing_columns'] for r in ordinary.to_dicts()} != {
        r['missing_columns'] for r in extended.to_dicts()
    }


def test_duplicate_rows_are_excess_repeats():
    df = pl.DataFrame({'a': [1, 1, 2, 2, 2], 'b': ['x', 'x', 'y', 'y', 'y']})
    row = ps.stats.duplicates(df).row(0, named=True)
    assert row['rows'] == 5
    assert row['unique_rows'] == 2
    assert row['duplicate_rows'] == 3
    assert row['duplicate_percent'] == pytest.approx(60)


def test_uniqueness_is_non_null_and_explicit_about_method():
    df = pl.DataFrame({'status': ['Y', 'Y', 'N', None]})
    row = ps.stats.uniqueness(df, exact=True).row(0, named=True)
    assert row['distinct'] == 2
    assert row['non_null'] == 3
    assert row['distinct_percent'] == pytest.approx(66.67)
    assert row['method'] == 'exact'


def test_iqr_outlier_counts_and_nonfinite_values():
    df = pl.DataFrame({'age': [1., 2., 2., 3., 100., None, float('nan')]})
    result = ps.stats.outliers(df, 'age')
    row = result.row(0, named=True)
    assert row['finite_count'] == 5
    assert row['outlier_count'] == 1
    assert row['outlier_percent'] == pytest.approx(20)
    with pytest.raises(ValueError, match='positive'):
        ps.stats.outliers(df, 'age', iqr_multiplier=0)


def test_numeric_diagnostics_include_negative_and_cv():
    df = pl.DataFrame({'value': [-2., 0., 2., 4.]})
    row = ps.stats.numeric(df, 'value').row(0, named=True)
    assert row['negative_count'] == 1
    assert row['negative_percent'] == pytest.approx(25)
    assert row['zero_percent'] == pytest.approx(25)
    assert row['coefficient_of_variation'] is not None


def test_text_distinguishes_empty_and_whitespace_only():
    df = pl.DataFrame({'text': ['', '   ', 'hello', None]})
    row = ps.stats.text(df, 'text').row(0, named=True)
    assert row['empty_count'] == 1
    assert row['blank_count'] == 2
    assert row['whitespace_only_count'] == 1


def test_diagnostics_reject_unbounded_column_sets():
    df = pl.DataFrame({'a': [1], 'b': [2], 'c': [3]})
    with pytest.raises(ValueError, match='limited'):
        ps.stats.missingness_patterns(df, max_columns=2)
    with pytest.raises(ValueError, match='limited'):
        ps.stats.missingness_associations(df, max_columns=2)


def test_full_profile_exposes_new_components(df):
    p = ps.profile(df, mode='full')
    assert p.missingness_patterns().kind == 'table'
    assert p.missingness_associations().kind == 'table'
    assert p.uniqueness().kind == 'table'
    assert p.duplicates().kind == 'table'
    assert p.outliers('age').kind == 'table'
    titles = {item.title for item in p.items()}
    assert 'Common missingness patterns' in titles
    assert 'Exact duplicate rows' in titles
    assert 'Variable uniqueness' in titles


def test_diagnostics_not_run_in_quick_mode(df):
    p = ps.profile(df, mode='quick')
    titles = {item.title for item in p.items()}
    assert 'Exact duplicate rows' not in titles
    assert 'Common missingness patterns' not in titles
    assert p.outliers('age').kind == 'table'


def test_file_backed_diagnostic_recipes_round_trip(tmp_path):
    path = tmp_path / 'data.parquet'
    pl.DataFrame({'a': [1, 1, 2, None], 'b': ['x', 'x', None, 'y']}).write_parquet(path)
    profile = ps.profile(path, mode='full')
    report = ps.Report('Diagnostic findings')
    report.add(profile.missingness_patterns())
    report.add(profile.duplicates())
    report.add(profile.uniqueness())
    recipe = report.write_spec(tmp_path / 'recipe.json')
    replay = ps.Report.from_spec(recipe)
    assert [item.content.to_dicts() for item in replay.items] == [
        item.content.to_dicts() for item in report.items
    ]


def test_full_profile_skips_diagnostics_with_explicit_message(tmp_path):
    source = tmp_path / 'wide.parquet'
    pl.DataFrame({'a': [1, 2], 'b': [3, 4], 'c': [5, 6]}).write_parquet(source)
    options = ps.ProfileOptions(max_missingness_columns=2, max_duplicate_columns=2)
    report = ps.profile(source, mode='full', options=options).to_report()
    assert any(item.title == 'Missingness diagnostics omitted' for item in report.items)
    assert any(item.title == 'Duplicate check omitted' for item in report.items)
    recipe = report.write_spec(tmp_path / 'wide.json')
    replay = ps.Report.from_spec(recipe)
    assert len(replay.items) == len(report.items)


def test_categorical_diagnostics_are_bounded_and_aggregate():
    df = pl.DataFrame({'status': ['N'] * 8 + ['Y', 'U', None]})
    row = ps.stats.categorical_diagnostics(
        df, 'status', rare_at_most=2,
    ).row(0, named=True)
    assert row['non_null_count'] == 10
    assert row['distinct_count'] == 3
    assert row['rare_categories'] == 2
    assert row['rare_records'] == 2
    assert row['dominant_percent'] == pytest.approx(80)
    assert ps.profile(df, mode='full').category_diagnostics('status').kind == 'table'


def test_categorical_diagnostics_reject_high_cardinality():
    df = pl.DataFrame({'label': [f'c{i}' for i in range(150)]})
    with pytest.raises(ValueError, match='distinct values'):
        ps.stats.categorical_diagnostics(df, 'label', max_unique=10)


def test_missingness_heatmap_is_static(df):
    profile = ps.profile(df, mode='full')
    chart = profile.missingness_associations_chart()
    assert chart.kind == 'chart'
    report = ps.Report('Missingness')
    report.add(chart)
    html = report.to_html()
    assert '<svg' in html
    assert '<script' not in html
    assert 'Phi coefficient' in html


def test_explorer_outlier_view_reuses_profile(df):
    p = ps.profile(df)
    controller = p.explore(show=False)
    selected = controller.preview('age', view='outliers')
    assert len(selected) == 1
    assert selected[0] is p.outliers('age')
    with pytest.raises(ValueError, match='numeric'):
        controller.preview('enctype', view='outliers')


def test_complex_duplicate_types_are_omitted_in_full_profile():
    df = pl.DataFrame({'id': [1, 1], 'nested': [[1, 2], [1, 2]]})
    with pytest.raises(ValueError, match='flat scalar'):
        ps.stats.duplicates(df)
    p = ps.profile(df, mode='full')
    assert any(item.title == 'Duplicate check omitted' for item in p.items())


def test_full_profile_includes_category_diagnostics(df):
    p = ps.profile(df, mode='full')
    titles = [item.title for item in p.items()]
    assert any('category diagnostics' in title for title in titles)


def test_cli_full_mode(tmp_path):
    from polarstory.cli import main

    file_path = tmp_path / 'small.parquet'
    output = tmp_path / 'profile.html'
    pl.DataFrame({'score': [1., 2., 3., 100.], 'status': ['Y', 'Y', 'N', 'U']}).write_parquet(file_path)
    assert main(['profile', str(file_path), '--mode', 'full', '-o', str(output)]) == 0
    html = output.read_text(encoding='utf8')
    assert 'Common missingness patterns' in html
    assert 'IQR outlier summary' in html
    assert '<script' not in html
