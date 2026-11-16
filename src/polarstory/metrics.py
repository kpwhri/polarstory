"""Batched, lazy univariate statistics for automatic profiles.

Only aggregate rows are collected, not the source records. Chunked projection
bounds expression-plan size for very wide datasets. This cannot guarantee a
constant-memory execution plan (quantiles and cardinality can be expensive).
"""

from __future__ import annotations

import polars as pl

from polarstory.columns import dtype_kind
from polarstory.source import DataSource


def _numeric_exprs(name: str, dtype: pl.DataType, prefix: str) -> list[pl.Expr]:
    c = pl.col(name)
    finite = c.filter(c.is_finite()) if dtype.is_float() else c
    exprs = [
        finite.count().alias(prefix + 'finite_count'),
        finite.min().alias(prefix + 'min'),
        finite.max().alias(prefix + 'max'),
        finite.mean().alias(prefix + 'mean'),
        finite.std().alias(prefix + 'std'),
        finite.median().alias(prefix + 'median'),
        finite.quantile(.05).alias(prefix + 'q05'),
        finite.quantile(.25).alias(prefix + 'q25'),
        finite.quantile(.75).alias(prefix + 'q75'),
        finite.quantile(.95).alias(prefix + 'q95'),
        finite.skew().alias(prefix + 'skew'),
        finite.kurtosis().alias(prefix + 'kurtosis'),
        (finite == 0).sum().alias(prefix + 'zero_count'),
        (finite < 0).sum().alias(prefix + 'negative_count'),
    ]
    if dtype.is_float():
        exprs.extend([
            c.is_nan().sum().alias(prefix + 'nan_count'),
            c.is_infinite().sum().alias(prefix + 'infinite_count'),
        ])
    return exprs


def collect_metrics(
        source: DataSource,
        columns: tuple[str, ...],
        *,
        batch_size: int = 24,
) -> tuple[int, dict[str, dict[str, object]]]:
    """Collect per-variable metrics with at most ceil(n / batch_size) scans.

    Metrics for numeric columns use only finite observations for distribution
    statistics. The returned mapping contains Python scalar values, not rows.
    """
    if batch_size < 1:
        raise ValueError('batch_size must be positive')
    schema = source.schema
    results: dict[str, dict[str, object]] = {}
    if not columns:
        return source.frame.select(pl.len().alias('_rows')).collect().item(), results

    n_rows = 0
    for offset in range(0, len(columns), batch_size):
        chunk = columns[offset:offset + batch_size]
        exprs = [pl.len().alias('_rows')]
        for i, name in enumerate(chunk):
            prefix = f'_c{i}_'
            c = pl.col(name)
            exprs.append(c.is_null().sum().alias(prefix + 'null_count'))
            dtype = schema[name]
            if dtype_kind(dtype) == 'categorical':
                exprs.append(c.approx_n_unique().alias(prefix + 'approx_unique_count'))
            if dtype_kind(dtype) == 'numeric':
                exprs.extend(_numeric_exprs(name, dtype, prefix))
            elif dtype_kind(dtype) == 'temporal':
                exprs.extend([
                    c.min().alias(prefix + 'min'),
                    c.max().alias(prefix + 'max'),
                ])
        # scalar aggregations return one row
        # projection pushdown skips unrelated parquet columns
        record = source.frame.select(*exprs).collect().row(0, named=True)
        n_rows = int(record['_rows'])
        for i, name in enumerate(chunk):
            prefix = f'_c{i}_'
            values = {key[len(prefix):]: value for key, value in record.items()
                      if key.startswith(prefix)}
            values['rows'] = n_rows
            if 'q25' in values and 'q75' in values:
                low, high = values['q25'], values['q75']
                values['iqr'] = high - low if low is not None and high is not None else None
            if 'finite_count' in values:
                n_finite = values['finite_count'] or 0
                mean, std = values.get('mean'), values.get('std')
                values['coefficient_of_variation'] = (
                    float(std) / abs(float(mean))
                    if std is not None and mean not in (None, 0) else None
                )
                values['zero_percent'] = (round(100 * values['zero_count'] / n_finite, 2)
                                          if n_finite else None)
                values['negative_percent'] = (round(100 * values['negative_count'] / n_finite, 2)
                                              if n_finite else None)
            results[name] = values
    return n_rows, results
