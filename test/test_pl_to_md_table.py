import polars as pl
import pytest
from polarstory.report import _pl_to_markdown_table


@pytest.fixture
def sample_df():
    return pl.DataFrame({
        'id': [1, 2, 3],
        'bignumber': [1000000, 2000000, 3000000],
        'percent': [0.1234, 0.2345, 0.3456],
        'precision': [1.23456, 2.34567, 3.45678],
        'text': ['A', 'B', 'C']
    })


def test_basic_table_formatting(sample_df):
    result = _pl_to_markdown_table(sample_df)
    lines = result.split('\n')
    assert '| id | bignumber | percent | precision | text |' == lines[0]
    assert '| :-- | --: | --: | --: | --: |' == lines[1]
    assert len(lines) == 5  # header + separator + 3 rows


def test_integer_comma_formatting(sample_df):
    result = _pl_to_markdown_table(sample_df)
    assert '1,000,000' in result
    assert '2,000,000' in result
    assert '3,000,000' in result


def test_special_percent_formatting(sample_df):
    df = sample_df.with_columns(
        pl.col('percent').alias('percent1'),
        pl.col('percent').alias('percent2'),
    ).select('percent1', 'percent2')

    formatters = {
        'percent1': lambda x: f'{100 * x:,.2f}%',
        'percent2': lambda x: f'{x:,.2f}%',
    }

    result = _pl_to_markdown_table(df, formatters=formatters)
    lines = result.split('\n')
    assert '12.34%' in lines[2]
    assert '0.12%' in lines[2]
    assert '23.45%' in lines[3]
    assert '0.23%' in lines[3]
    assert '34.56%' in lines[4]
    assert '0.35%' in lines[4]


def test_default_percent_formatting(sample_df):
    df = sample_df.with_columns(
        pl.col('percent').alias('percent1'),
        pl.col('percent').alias('percent2'),
    ).select('percent1', 'percent2')

    formatters = {
        'percent1': 'percent100',
        'percent2': 'percent',
    }

    result = _pl_to_markdown_table(df, formatters=formatters)
    lines = result.split('\n')
    assert '12.34%' in lines[2]
    assert '0.12%' in lines[2]
    assert '23.45%' in lines[3]
    assert '0.23%' in lines[3]
    assert '34.56%' in lines[4]
    assert '0.35%' in lines[4]


def test_default_formatting(sample_df):
    result = _pl_to_markdown_table(sample_df)
    lines = result.split('\n')

    assert '1' in lines[2]
    assert '2' in lines[3]
    assert '3' in lines[4]

    assert '1,000,000' in lines[2]
    assert '2,000,000' in lines[3]
    assert '3,000,000' in lines[4]

    assert '0.12' in lines[2]
    assert '0.23' in lines[3]
    assert '0.35' in lines[4]

    assert '1.23' in lines[2]
    assert '2.35' in lines[3]
    assert '3.46' in lines[4]

    assert 'A' in lines[2]
    assert 'B' in lines[3]
    assert 'C' in lines[4]


def test_none_values(sample_df):
    df = sample_df.with_columns(pl.lit(None).alias("NullColumn"))
    result = _pl_to_markdown_table(df)
    assert '|  |' in result  # Empty cell for None values


def test_align_first_col_left():
    df = pl.DataFrame({
        'col1': [1, 2],
        'col2': [3, 4]
    })

    result = _pl_to_markdown_table(df, align_first_col_left=True)
    assert '| :-- | --: |' in result

    result = _pl_to_markdown_table(df, align_first_col_left=False)
    assert '| --: | --: |' in result


def test_empty_dataframe():
    df = pl.DataFrame({
        'col1': [],
        'col2': []
    })
    result = _pl_to_markdown_table(df)
    lines = result.split('\n')
    assert len(lines) == 2  # Only header and separator lines
    assert '| col1 | col2 |' in lines[0]


def test_single_row_dataframe():
    df = pl.DataFrame({
        'col1': [1],
        'col2': [2]
    })
    result = _pl_to_markdown_table(df)
    lines = result.split('\n')
    assert len(lines) == 3  # Header, separator, and one data row
