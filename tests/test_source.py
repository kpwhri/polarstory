import polars as pl
import pytest

from polarstory.source import as_source


def test_eager_source(df):
    source = as_source(df)
    assert source.kind == 'dataframe'
    assert source.row_count == 6
    assert source.schema.names() == df.columns


def test_parquet_file(tmp_path, df):
    path = tmp_path / 'cohort.parquet'
    df.write_parquet(path)
    source = as_source(path)
    assert source.kind == 'parquet'
    assert source.size_bytes > 0
    assert source.frame.collect().height == 6


def test_parquet_folder(tmp_path):
    for index in range(2):
        pl.DataFrame({'id': [index]}).write_parquet(tmp_path / f'{index}.parquet')
    assert as_source(tmp_path).frame.select(pl.len()).collect().item() == 2


def test_missing_source(tmp_path):
    with pytest.raises(FileNotFoundError):
        as_source(tmp_path / 'missing.parquet')


def test_nonparquet_source(tmp_path):
    path = tmp_path / 'data.txt'
    path.write_text('hello')
    with pytest.raises(ValueError, match='parquet'):
        as_source(path)
