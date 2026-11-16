"""Bound custom report table materialization."""

import polars as pl
import pytest

import polarstory as ps


@pytest.mark.parametrize('lazy', [False, True])
def test_large_custom_table_rejected(lazy):
    df = pl.DataFrame({'n': [1, 2, 3]})
    source = df.lazy() if lazy else df
    report = ps.Report(max_table_rows=2)
    with pytest.raises(ValueError, match='more than 2'):
        report.add_table(source, title='Too large')


def test_custom_table_limit_override():
    report = ps.Report(max_table_rows=None)
    item = report.add_table(pl.DataFrame({'n': [1, 2, 3]}), title='All rows')
    assert item.content.height == 3


def test_invalid_table_limit():
    with pytest.raises(ValueError):
        ps.Report(max_table_rows=0)
