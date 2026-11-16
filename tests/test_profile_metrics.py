"""Profile metrics tests."""

from datetime import date

import pytest

import polarstory as ps
from polarstory.metrics import collect_metrics
from polarstory.source import as_source


def test_batched_metrics_match_existing_summaries(df):
    source = as_source(df.lazy())
    rows, metrics = collect_metrics(source, tuple(df.columns), batch_size=2)
    assert rows == df.height
    assert metrics['age']['null_count'] == 1
    assert metrics['age']['nan_count'] == 1
    assert metrics['age']['finite_count'] == 4
    assert metrics['age']['mean'] == pytest.approx(30.75)
    assert metrics['tx_ep_start']['min'] == date(2025, 1, 1)


def test_profile_overview_and_missingness_reuse_batched_metrics(df):
    profile = ps.profile(df, options=ps.ProfileOptions(batch_size=2), mode='quick')
    assert profile.overview.row(0, named=True)['null_cells'] == 3
    assert profile.missingness['null_count'].sum() == 3
    assert profile._metrics is not None
    assert profile.variable('age').table.row(0, named=True)['mean'] == pytest.approx(30.75)
    assert profile._metrics is not None


def test_parquet_lazy_profile_matches_dataframe(df, tmp_path):
    path = tmp_path / 'cohort.parquet'
    df.write_parquet(path)
    memory = ps.profile(df, mode='quick')
    disk = ps.profile(path, mode='quick')
    assert memory.overview.to_dicts() == disk.overview.to_dicts()
    memory_rows = memory.variable('age').table.to_dicts()
    disk_rows = disk.variable('age').table.to_dicts()
    assert len(memory_rows) == len(disk_rows)
    for actual, reference in zip(disk_rows, memory_rows, strict=True):
        assert actual.keys() == reference.keys()
        for key, expected_value in reference.items():
            if isinstance(expected_value, float):
                assert actual[key] == pytest.approx(expected_value, rel=1e-12, abs=1e-12)
            else:
                assert actual[key] == expected_value


def test_single_numeric_variable_only_collects_its_metrics(df):
    p = ps.profile(df, mode='quick')
    p.variable('age')
    assert set(p._metrics) == {'age'}
    assert p.variable('age').table['iqr'].item() is not None
    assert 'skew' in p.variable('age').table.columns
    assert 'kurtosis' in p.variable('age').table.columns
