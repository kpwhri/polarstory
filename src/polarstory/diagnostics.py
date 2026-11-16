"""Bounded, descriptive dataset diagnostics using lazy polars expressions.

Expensive operations are invoked explicitly or through full profiles. No raw
records are returned, and missingness analyses treat null separately from NaN.
"""

from __future__ import annotations

from math import sqrt

import polars as pl

from polarstory.columns import dtype_kind
from polarstory.metrics import _numeric_exprs  # type: ignore[unused-imports]
from polarstory.source import DataInput, DataSource, as_source


def _names(source: DataSource, columns: list[str] | tuple[str, ...] | None,
           max_columns: int) -> tuple[str, ...]:
    if max_columns < 1:
        raise ValueError('max_columns must be positive')
    names = tuple(source.schema.names() if columns is None else columns)
    if len(names) > max_columns:
        raise ValueError(f'Diagnostic limited to {max_columns} columns; select fewer columns')
    if len(names) != len(set(names)):
        raise ValueError('Column names must be unique')
    for name in names:
        if name not in source.schema:
            raise ValueError(f'Unknown column: {name}')
    return names


def _missing(source: DataSource, column: str, include_nan: bool) -> pl.Expr:
    value = pl.col(column)
    flag = value.is_null()
    if include_nan and source.schema[column].is_float():
        flag = flag | value.is_nan().fill_null(False)
    return flag.fill_null(False)


def missingness_patterns(
        data: DataInput | DataSource,
        columns=None,
        *, top_n: int = 20, max_columns: int = 12,
        include_nan: bool = False,
) -> pl.DataFrame:
    """Most frequent missingness combinations, with a remainder row.

    The `missing_columns` field lists *column names*, never observations.
    For a large input, computation groups at most `max_columns` Boolean flags.
    Percentages use all rows, including complete observations.
    """
    if top_n < 1:
        raise ValueError('top_n must be positive')
    source = as_source(data)
    names = _names(source, columns, max_columns)
    schema = {'missing_columns': pl.String, 'missing_count': pl.Int64,
              'count': pl.Int64, 'percent': pl.Float64}
    if not names:
        return pl.DataFrame(schema=schema)
    flags = [f'_missing_{i}' for i in range(len(names))]
    frame = source.frame.select(
        [_missing(source, name, include_nan).alias(flag)
         for name, flag in zip(names, flags)]
    )
    groups = (
        frame
        .group_by(flags)
        .agg(pl.len().alias('_count'))
        .sort(['_count', *flags], descending=[True, *([False] * len(flags))])
        .head(top_n)
        .collect()
    )
    total = int(source.frame.select(pl.len()).collect().item())
    records = []
    for row in groups.iter_rows(named=True):
        missing = [name for name, flag in zip(names, flags) if row[flag]]
        count = int(row['_count'])
        records.append({'missing_columns': ', '.join(missing) if missing else '(none)',
                        'missing_count': len(missing), 'count': count,
                        'percent': round(100 * count / total, 2) if total else 0.0})
    remainder = total - sum(row['count'] for row in records)
    if remainder:
        records.append({'missing_columns': '(other patterns)', 'missing_count': -1,
                        'count': remainder, 'percent': round(100 * remainder / total, 2)})
    records.sort(key=lambda row: (-row['count'], row['missing_columns']))
    return pl.DataFrame(records, schema=schema)


def missingness_associations(data: DataInput | DataSource, columns=None, *, max_columns: int = 12,
                             include_nan: bool = False) -> pl.DataFrame:
    """Pairwise phi coefficients between binary missingness indicators.

    Constant indicators have undefined phi and are returned as null, not zero.
    The result is descriptive and contains no significance tests or row data.
    """
    source = as_source(data)
    names = _names(source, columns, max_columns)
    schema = {'left': pl.String, 'right': pl.String, 'rows': pl.Int64, 'both_missing': pl.Int64, 'phi': pl.Float64}
    if len(names) < 2:
        return pl.DataFrame(schema=schema)
    expressions = [pl.len().alias('_rows')]
    indicators = [_missing(source, name, include_nan) for name in names]
    for i, flag in enumerate(indicators):
        expressions.append(flag.cast(pl.Int64).sum().alias(f'_m{i}'))
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            expressions.append((indicators[i] & indicators[j]).cast(pl.Int64)
                               .sum().alias(f'_both_{i}_{j}'))
    result = source.frame.select(expressions).collect().row(0, named=True)
    n = int(result['_rows'])
    records = []
    for i, left in enumerate(names):
        for j in range(i + 1, len(names)):
            a = int(result[f'_m{i}'])
            b = int(result[f'_m{j}'])
            both = int(result[f'_both_{i}_{j}'])
            denominator = sqrt(a * (n - a) * b * (n - b))
            phi = (n * both - a * b) / denominator if denominator else None
            records.append({'left': left, 'right': names[j], 'rows': n, 'both_missing': both, 'phi': phi})
    return pl.DataFrame(records, schema=schema)


def duplicates(data: DataInput | DataSource, *, max_columns: int = 100) -> pl.DataFrame:
    """Exact excess duplicate rows, including the first row in each group once.

    `duplicate_rows` is `rows - unique_rows`, not the number of rows belonging
    to duplicate groups. This operation may require substantial memory and is
    never included in a standard profile by default.
    """
    source = as_source(data)
    names = _names(source, None, max_columns)
    if any(dtype_kind(source.schema[name]) == 'other' for name in names):
        raise ValueError('Exact duplicate checks require flat scalar columns')
    if names:
        result = source.frame.select(
            pl.len().alias('rows'),
            pl.struct([pl.col(name) for name in names]).n_unique().alias('unique_rows'),
        ).collect().row(0, named=True)
        rows, unique = int(result['rows']), int(result['unique_rows'])
    else:
        rows = int(source.frame.select(pl.len()).collect().item())
        unique = min(rows, 1)
    excess = rows - unique
    return pl.DataFrame([{
        'rows': rows,
        'unique_rows': unique,
        'duplicate_rows': excess,
        'duplicate_percent': round(100 * excess / rows, 2) if rows else 0.0,
    }])


def uniqueness(data: DataInput | DataSource, columns=None, *, exact: bool = False,
               max_columns: int = 100) -> pl.DataFrame:
    """Distinct *non-null* values and ratios, exact or approximate.

    Approximate cardinalities are estimates and should not be interpreted as
    a guarantee that values are unique. Complex unhashable types are omitted.
    """
    source = as_source(data)
    names = _names(source, columns, max_columns)
    schema = {'column': pl.String, 'rows': pl.Int64, 'non_null': pl.Int64,
              'distinct': pl.Int64, 'distinct_percent': pl.Float64,
              'method': pl.String}
    eligible = [name for name in names if dtype_kind(source.schema[name]) != 'other']
    if not eligible:
        return pl.DataFrame(schema=schema)
    expressions = [pl.len().alias('_rows')]
    for i, name in enumerate(eligible):
        value = pl.col(name)
        expressions.append(value.count().alias(f'_count{i}'))
        expressions.append((value.drop_nulls().n_unique() if exact else
                            value.drop_nulls().approx_n_unique()).alias(f'_distinct{i}'))
    record = source.frame.select(expressions).collect().row(0, named=True)
    result = []
    for i, name in enumerate(eligible):
        non_null = int(record[f'_count{i}'])
        distinct = int(record[f'_distinct{i}'])
        result.append({'column': name, 'rows': int(record['_rows']),
                       'non_null': non_null, 'distinct': distinct,
                       'distinct_percent': round(100 * distinct / non_null, 2)
                       if non_null else 0.0,
                       'method': 'exact' if exact else 'approximate'})
    return pl.DataFrame(result, schema=schema)
