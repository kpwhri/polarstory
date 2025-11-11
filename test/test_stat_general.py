import polars as pl
import pytest

from polarstory.stat import get_cumsum


@pytest.fixture()
def cumsum_df():
    return pl.DataFrame({
        'id': ['a', 'b', 'c', 'd', 'e', 'f'],
        'col1': [1, 0, 1, 0, 1, 1],
        'col2': [1, 1, 1, 0, 0, 0],
        'col3': [0, 0, 0, 0, 0, 0],
    })

def test_cumsum(cumsum_df):
    res_df = get_cumsum(cumsum_df.drop('id'))
    rows = res_df.rows()

    assert rows[0][0] == 'col1'
    assert rows[0][1] == 4
    assert rows[0][2] == '66.67%'
    assert rows[1][0] == 'col2'
    assert rows[1][1] == 3
    assert rows[1][2] == '50.0%'
    assert rows[2][0] == 'col3'
    assert rows[2][1] == 0
    assert rows[2][2] == '0.0%'


def test_cumsum_to_pd_markdown(cumsum_df):
    try:
        import pandas as pd
    except ImportError:
        pytest.skip('Pandas not installed.')
    md_text = get_cumsum(cumsum_df.drop('id'), as_markdown='polars')
    lines = md_text.split('\n')
    assert lines[0] == '|    | labels   |   count | percent   |'
    assert lines[1] == '|---:|:---------|--------:|:----------|'
    assert lines[2] == '|  0 | col1     |       4 | 66.67%    |'
    assert lines[3] == '|  1 | col2     |       3 | 50.0%     |'
    assert lines[4] == '|  2 | col3     |       0 | 0.0%      |'


def test_cumsum_to_tab_markdown(cumsum_df):
    md_text = get_cumsum(cumsum_df.drop('id'), as_markdown=True)
    lines = md_text.split('\n')
    assert lines[0] == '| labels   |   count | percent   |'
    assert lines[1] == '|:---------|--------:|:----------|'
    assert lines[2] == '| col1     |       4 | 66.67%    |'
    assert lines[3] == '| col2     |       3 | 50.0%     |'
    assert lines[4] == '| col3     |       0 | 0.0%      |'
