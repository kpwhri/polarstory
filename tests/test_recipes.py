"""Recipes tests."""

import json

import polars as pl
import pytest

import polarstory as ps
from polarstory.cli import main


def test_profile_spec_round_trip_and_relative_files(df, tmp_path):
    data_path = tmp_path / 'data.parquet'
    df.write_parquet(data_path)
    variables = ps.Variables().set('enctype', label='Encounter type')
    profile = ps.profile(
        data_path,
        columns=['enctype', 'age'],
        mode='quick',
        variables=variables,
        options=ps.ProfileOptions(max_categories=4),
    )
    target = tmp_path / 'reports' / 'profile.json'
    profile.write_spec(target)
    recipe = json.loads(target.read_text(encoding='utf8'))
    assert recipe['format'] == 'polarstory.profile/v1'
    assert len(recipe['sources']) == 1
    assert (target.parent / recipe['sources'][0]).resolve() == data_path.resolve()
    restored = ps.profile_from_spec(target)
    assert restored.columns == profile.columns
    assert restored.metadata['enctype'].label == 'Encounter type'
    assert restored.options.max_categories == 4
    assert restored.overview.to_dicts() == profile.overview.to_dicts()
    assert '<!doctype html>' in restored.to_html()


def test_in_memory_spec_not_reproducible(df, tmp_path):
    with pytest.raises(ValueError, match='file-backed'):
        ps.profile(df).write_spec(tmp_path / 'cannot.json')


def test_cli_profile_spec_reproduce(df, tmp_path):
    data = tmp_path / 'data.parquet'
    df.write_parquet(data)
    profile_html = tmp_path / 'profile.html'
    config = tmp_path / 'profile.json'
    assert main(['profile', str(data), '--mode', 'quick', '--no-charts',
                 '--max-categories', '3', '-o', str(profile_html),
                 '--write-spec', str(config)]) == 0
    assert config.is_file() and profile_html.is_file()
    rerun = tmp_path / 'rerun.html'
    assert main(['reproduce', str(config), '-o', str(rerun)]) == 0
    assert 'data-quality' in rerun.read_text(encoding='utf8').lower() or '<!doctype html>' in rerun.read_text(
        encoding='utf8')


def test_curated_report_spec_round_trip(df, tmp_path):
    path = tmp_path / 'data.parquet'
    df.write_parquet(path)
    auto = ps.profile(path, columns=['enctype', 'age'], mode='quick')
    report = ps.Report('Selected variables')
    report.add(auto.item('enctype', 'frequency'))
    report.add_table1(path, ['age', 'enctype'], by='ins_medicaid')
    report.add_text('Descriptive results; interpretation to follow.')
    spec = tmp_path / 'outputs' / 'curated.json'
    report.write_spec(spec)
    recipe = json.loads(spec.read_text(encoding='utf8'))
    assert recipe['format'] == 'polarstory.report/v1'
    sources = recipe['sections'][0]['items'][0]['recipe']['profile']['sources']
    assert len(sources) == 1
    assert (spec.parent / sources[0]).resolve() == path.resolve()
    restored = ps.Report.from_spec(spec)
    assert [item.id for item in restored.items] == [item.id for item in report.items]
    assert restored.items[0].content.to_dicts() == report.items[0].content.to_dicts()
    assert restored.items[1].content.to_dicts() == report.items[1].content.to_dicts()
    assert 'Descriptive results' in restored.to_html()
    assert main(['reproduce', str(spec), '-o', str(tmp_path / 'curated.html')]) == 0


def test_report_spec_rejects_nonreplayable_custom_tables(df, tmp_path):
    report = ps.Report('Custom')
    report.add_table(df.select('enctype'), title='Raw data (explicit)')
    with pytest.raises(ValueError, match='cannot be regenerated'):
        report.write_spec(tmp_path / 'custom.json')


def test_curated_profile_chart_recipe_and_no_raw_rows(tmp_path):
    df = pl.DataFrame({'category': ['SENSITIVE_SAMPLE_VALUE', 'A', 'A'],
                       'measure': [1.0, 2.0, 3.0]})
    path = tmp_path / 'data.parquet'
    df.write_parquet(path)
    p = ps.profile(path, columns=['measure'])
    r = ps.Report('Charts')
    r.add(p.item('measure', 'histogram'))
    spec_path = tmp_path / 'chart.json'
    r.write_spec(spec_path)
    text = spec_path.read_text(encoding='utf8')
    assert 'SENSITIVE_SAMPLE_VALUE' not in text
    restored = ps.Report.from_spec(spec_path)
    html = restored.to_html()
    assert '<svg' in html
    assert '<script' not in html
