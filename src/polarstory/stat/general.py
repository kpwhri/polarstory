import polars as pl

from polarstory.writers import to_pd_markdown, to_tab_markdown


def get_cumsum(df, *, header_name='labels', sort=None, as_markdown=False):
    """
    Calculate column sums and percentages from a polars DataFrame.

    ```python

    ```

    :param df: Input Polars DataFrame to calculate sums from
    :param header_name: Name for the labels column in output DataFrame (default: 'labels')
    :param sort: Column name to sort results by; defaults to header_name if None
    :return: Polars DataFrame with columns: [header_name, 'count', 'percent']
             where 'count' contains column sums and 'percent' shows percentage of total rows
    """
    if sort is None:
        sort = header_name
    res_df = (
        df
        .sum()
        .transpose(include_header=True, header_name=header_name, column_names=['value'])
        .with_columns([
            pl.col('value').alias('count'),
            (pl.col('value') * 100 / df.height)
            .round(2)
            .map_elements(lambda x: f"{x}%")  # or use .cast(str) + pl.lit('%')
            .alias('percent')
        ])
        .select([header_name, 'count', 'percent'])
        .sort(sort)
    )
    if as_markdown:
        if as_markdown == 'polars':
            return to_pd_markdown(res_df, index=header_name)
        else:
            return to_tab_markdown(res_df)
    return res_df
