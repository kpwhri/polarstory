"""parquet-backed automatic profiles and reusable aggregate outputs."""

import polars as pl

import polarstory as ps


def test_file_backed_profile_stays_lazy_and_exports_html(tmp_path):
    path = tmp_path / 'encounters.parquet'
    n = 12000
    frame = pl.DataFrame({
        'encounter_id': list(range(n)),
        'enctype': ['ED', 'IP', 'OP'] * (n // 3),
        'age': [float(value % 90) for value in range(n)],
    })
    frame.write_parquet(path)

    p = ps.profile(path, mode='quick')
    assert isinstance(p.source.frame, pl.LazyFrame)
    assert p.overview['rows'].item() == n
    assert p.variable('encounter_id').kind == 'identifier'
    assert p.frequency('enctype').content['count'].sum() == n
    assert p.frequency('age').content['count'].sum() == n

    output = p.write_html(tmp_path / 'profile.html')
    html = output.read_text(encoding='utf8')
    assert 'Variable inventory' in html
    assert '12,000' in html
    assert '<script' not in html
    assert '@media print' in html


def test_profile_options_round_trip_in_file_recipe(tmp_path):
    path = tmp_path / 'values.parquet'
    pl.DataFrame({'x': [0, 1, 2]}).write_parquet(path)
    options = ps.ProfileOptions(max_unique_for_frequency=25)
    recipe = ps.profile(path, mode='quick', options=options).write_spec(tmp_path / 'config.json')
    result = ps.profile_from_spec(recipe)
    assert result.options.max_unique_for_frequency == 25
