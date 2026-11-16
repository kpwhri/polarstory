"""Structured descriptive data-quality warnings."""
from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from polarstory.source import DataInput, DataSource, as_source


@dataclass(frozen=True)
class Alert:
    column: str
    code: str
    severity: str
    message: str
    value: float | int | None = None


def from_missingness(
        missing: pl.DataFrame,
        *,
        rows: int,
        threshold: float = 0.5,
) -> list[Alert]:
    """Create missingness alerts from previously computed aggregate counts."""
    if not 0 <= threshold <= 1:
        raise ValueError('threshold must be in [0, 1]')
    result: list[Alert] = []
    for row in missing.iter_rows(named=True):
        nulls = row['null_count']
        if rows and nulls == rows:
            result.append(Alert(row['column'], 'all_null', 'warning',
                                'Every value is null', nulls))
        elif rows and nulls / rows >= threshold:
            result.append(Alert(row['column'], 'high_missingness', 'warning',
                                f'{nulls / rows:.1%} of records are null', nulls / rows))
    return result


def scan(data: DataInput | DataSource, *, columns: tuple[str, ...] | None = None, missing_threshold: float = 0.5,
         unique_threshold: float = 0.98, check_uniqueness: bool = False) -> list[Alert]:
    """Check missingness and optionally compute expensive exact cardinalities."""
    if not 0 <= missing_threshold <= 1 or not 0 <= unique_threshold <= 1:
        raise ValueError('Thresholds must be in [0, 1]')
    source = as_source(data)
    names = tuple(columns) if columns is not None else tuple(source.schema.names())
    if any(name not in source.schema for name in names):
        raise ValueError('Unknown column in columns')
    expressions = [pl.len().alias('_rows')]
    for i, name in enumerate(names):
        c = pl.col(name)
        expressions.append(c.is_null().sum().alias(f'_null_{i}'))
        if check_uniqueness:
            expressions.append(c.n_unique().alias(f'_unique_{i}'))
    row = source.frame.select(*expressions).collect().row(0, named=True)
    n = row['_rows']
    missing = pl.DataFrame(
        [{'column': name, 'null_count': row[f'_null_{i}']} for i, name in enumerate(names)],
        schema={'column': pl.String, 'null_count': pl.Int64},
    )
    found = from_missingness(missing, rows=n, threshold=missing_threshold)
    if check_uniqueness and n:
        for i, name in enumerate(names):
            distinct = row[f'_unique_{i}']
            if distinct == 1:
                found.append(Alert(name, 'constant', 'info', 'Only one distinct value', 1))
            elif distinct / n >= unique_threshold:
                found.append(Alert(name, 'high_cardinality', 'info',
                                   f'{distinct / n:.1%} distinct values', distinct / n))
    return found


def to_frame(found: list[Alert]) -> pl.DataFrame:
    """Convert a sequence of structured quality alerts to a polars DataFrame."""
    return pl.DataFrame([
        {'column': a.column,
         'code': a.code,
         'severity': a.severity,
         'message': a.message,
         'value': float(a.value) if a.value is not None else None
         } for a in found
    ],
        schema={'column': pl.String, 'code': pl.String, 'severity': pl.String,
                'message': pl.String, 'value': pl.Float64},
    )


def from_metrics(metrics: dict[str, dict[str, object]], *, rows: int, skew_threshold: float = 3.0,
                 zero_threshold: float = 0.8, unique_threshold: float = 0.98,) -> list[Alert]:
    """Infer descriptive warnings without triggering additional scans.

    Approximate cardinality alerts are informational, not evidence of errors.
    """
    found: list[Alert] = []
    for name, info in metrics.items():
        n = int(info.get('finite_count') or 0)
        if n >= 2 and info.get('min') is not None and info['min'] == info.get('max'):
            found.append(Alert(name, 'constant', 'info',
                               'All finite numeric values are equal', 1))
        skew = info.get('skew')
        if skew is not None and n >= 3 and abs(float(skew)) >= skew_threshold:
            found.append(Alert(name, 'skewed', 'info',
                               f'Numeric skewness is {float(skew):.2f}', float(skew)))
        zeros = info.get('zero_count')
        if n and zeros is not None and zeros / n >= zero_threshold:
            found.append(Alert(name, 'many_zeros', 'info',
                               f'{zeros / n:.1%} of finite observations are zero', zeros / n))
        nan = info.get('nan_count')
        if nan:
            found.append(Alert(name, 'nan_values', 'info',
                               f'{nan} NaN values (distinct from null)', int(nan)))
        inf = info.get('infinite_count')
        if inf:
            found.append(Alert(name, 'infinite_values', 'warning',
                               f'{inf} infinite values', int(inf)))
        distinct = info.get('approx_unique_count')
        non_null = rows - int(info.get('null_count') or 0)
        if rows >= 25 and distinct is not None and non_null:
            if int(distinct) == 1:
                found.append(Alert(name, 'constant', 'info',
                                   'One approximate distinct category', 1))
            elif distinct / non_null >= unique_threshold:
                found.append(Alert(name, 'near_unique', 'info',
                                   'Approximately all observed values are distinct',
                                   min(1.0, distinct / non_null)))
    return found


def from_frequency(column: str, frame: pl.DataFrame, *, valid_count: int,
                   imbalance_threshold: float = 0.9) -> list[Alert]:
    """Identify categorical dominance from an existing frequency table."""
    if not valid_count or frame.is_empty():
        return []
    categories = frame.filter(pl.col('kind') == 'category')
    if categories.is_empty():
        return []
    maximum = int(categories['count'].max())
    ratio = maximum / valid_count
    if ratio >= imbalance_threshold:
        return [Alert(column, 'imbalanced', 'info',
                      f'{ratio:.1%} of non-null values share one category', ratio)]
    return []
