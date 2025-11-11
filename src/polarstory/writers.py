import polars as pl

from tabulate import tabulate


def to_markdown(df: pl.DataFrame, kind=True, *args, **kwargs):
    match kind:
        case True:
            return to_tab_markdown(df, *args, **kwargs)
        case 'tabulate':
            return to_tab_markdown(df, *args, **kwargs)
        case 'polars':
            return to_pd_markdown(df, *args, **kwargs)
        case _:
            raise ValueError(f'Unrecognized: {_}')

def to_pd_markdown(df: pl.DataFrame, *, index=None, **kwargs):
    try:
        import pandas as pd
    except ImportError:
        raise ImportError(f'Missing optional requirement `pandas`: run `pip install pandas`.')
    pd_df = df.to_pandas()
    if index:
        pd_df.set_index(index)
    return pd_df.to_markdown(**kwargs)


def to_tab_markdown(df: pl.DataFrame,
                floatfmt: str = 'g',
                headers: str = 'keys',
                showindex: bool = False,
                **tabulate_kwargs) -> str:
    """
    Convert a polars DataFrame to a markdown table using tabulate.

    Args:
        df: Polars DataFrame
        floatfmt: float format specifier (default 'g')
        headers: header format ('keys' uses column names)
        showindex: whether to show index column
        **tabulate_kwargs: additional kwargs passed to tabulate

    Returns:
        markdown formatted table as string
    """
    data = df.to_numpy().tolist()
    headers = df.columns if headers == 'keys' else headers
    return tabulate(
        data,
        headers=headers,
        tablefmt='pipe',
        floatfmt=floatfmt,
        showindex=showindex,
        **tabulate_kwargs,
    )
