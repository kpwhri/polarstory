"""polars-native descriptive statistics; each result is a polars DataFrame.

These functions deliberately avoid collecting input rows. Aggregations are
performed lazily and only the (small) resulting tables are materialized.
"""

from __future__ import annotations

from collections import Counter
from math import sqrt
from typing import Literal

import polars as pl

from polarstory.columns import dtype_kind
from polarstory.diagnostics import duplicates, missingness_associations, missingness_patterns, uniqueness
from polarstory.metrics import _numeric_exprs
from polarstory.source import DataInput, DataSource, as_source
from polarstory.table1 import table1

__all__ = [
    'overview',
    'missingness',
    'frequency',
    'numeric',
    'temporal',
    'crosstab',
    'summary',
    'correlations',
    'cramers_v',
    'text',
    'outliers',
    'categorical_diagnostics',
    'table1',
    'duplicates',
    'uniqueness',
    'missingness_patterns',
    'missingness_associations',
]


def _name_check(source: DataSource, column: str) -> pl.DataType:
    schema = source.schema
    if column not in schema:
        raise ValueError(f'Unknown column: {column}')
    return schema[column]


def _one_row(source: DataSource, *expressions: pl.Expr) -> dict:
    return source.frame.select(*expressions).collect().to_dicts()[0]


def overview(data: DataInput | DataSource) -> pl.DataFrame:
    """Dataset-level record count, column count, and null cell count."""
    source = as_source(data)
    names = source.schema.names()
    metrics = _one_row(
        source,
        pl.len().alias('rows'),
        *[pl.col(name).is_null().sum().alias(f'_missing_{i}')
          for i, name in enumerate(names)],
    )
    missing = sum(value for key, value in metrics.items() if key.startswith('_missing_'))
    total = metrics['rows'] * len(names)
    return pl.DataFrame([{
        'rows': metrics['rows'],
        'columns': len(names),
        'null_cells': missing,
        'null_percent': round(100 * missing / total, 2) if total else 0.0,
    }])


def missingness(data: DataInput | DataSource) -> pl.DataFrame:
    """One row per variable; null and NaN are deliberately not conflated."""
    source = as_source(data)
    schema = source.schema
    names = schema.names()
    row = _one_row(
        source,
        pl.len().alias('_rows'),
        *[pl.col(name).is_null().sum().alias(f'_null_{i}') for i, name in enumerate(names)],
    )
    n = row['_rows']
    return pl.DataFrame(
        [{
            'column': name,
            'dtype': str(schema[name]),
            'null_count': row[f'_null_{i}'],
            'null_percent': round(100 * row[f'_null_{i}'] / n, 2) if n else 0.0,
        } for i, name in enumerate(names)],
        schema={'column': pl.String, 'dtype': pl.String,
                'null_count': pl.Int64, 'null_percent': pl.Float64},
    )


def frequency(
        data: DataInput | DataSource,
        column: str,
        *,
        top_n: int = 20,
        include_null: bool = True,
        denominator: Literal['total', 'valid'] = 'total',
) -> pl.DataFrame:
    """Top frequency categories, an optional null row, and an Other remainder.

    Collects only top_n grouped categories, never a full high-cardinality
    frequency table. Category values are stringified for a uniform display
    schema; `kind` distinguishes category, null, and Other rows.
    """
    source = as_source(data)
    _name_check(source, column)
    if top_n < 1:
        raise ValueError('top_n must be at least 1')
    if denominator not in ('total', 'valid'):
        raise ValueError("denominator must be 'total' or 'valid'")

    totals = _one_row(
        source,
        pl.len().alias('total'),
        pl.col(column).is_null().sum().alias('nulls'),
    )
    result = (
        source.frame.select(pl.col(column).alias('_value'))
        .filter(pl.col('_value').is_not_null())
        .group_by('_value')
        .agg(pl.len().alias('_count'))
        .sort(['_count', '_value'], descending=[True, False])
        .head(top_n)
        .collect()
    )
    # stable sorting for stringified category labels
    pairs = sorted(
        ((str(row['_value']), row['_count']) for row in result.to_dicts()),
        key=lambda item: (-item[1], item[0]),
    )
    valid = totals['total'] - totals['nulls']
    denom = totals['total'] if denominator == 'total' else valid

    def make_row(value: str, count: int, kind: str) -> dict:
        # exclude nulls from the valid-value denominator
        # omit null percentages for this denominator
        percent = (None if kind == 'null' and denominator == 'valid'
                   else round(100 * count / denom, 2) if denom else 0.0)
        return {
            'value': value,
            'count': count,
            'percent': percent,
            'kind': kind,
        }

    rows = [make_row(value, n, 'category') for value, n in pairs]
    remainder = valid - sum(n for _, n in pairs)
    if remainder > 0:
        rows.append(make_row('(other categories)', remainder, 'other'))
    if include_null and totals['nulls']:
        rows.append(make_row('(null)', totals['nulls'], 'null'))
    return pl.DataFrame(
        rows,
        schema={'value': pl.String, 'count': pl.Int64,
                'percent': pl.Float64, 'kind': pl.String},
    )


def numeric(data: DataInput | DataSource, column: str) -> pl.DataFrame:
    """One-row numeric summary with null and floating NaN counts separated."""
    source = as_source(data)
    dtype = _name_check(source, column)
    if dtype_kind(dtype) != 'numeric':
        raise TypeError(f'{column} is not numeric ({dtype})')
    c = pl.col(column)
    summary = source.frame.select(
        pl.len().alias('rows'),
        c.is_null().sum().alias('null_count'),
        c.count().alias('non_null_count'),
        *_numeric_exprs(column, dtype, ''),
    ).collect()
    return summary.with_columns(
        (pl.col('q75') - pl.col('q25')).alias('iqr'),
        pl.when((pl.col('mean').is_not_null()) & (pl.col('mean') != 0))
        .then(pl.col('std') / pl.col('mean').abs())
        .otherwise(None).alias('coefficient_of_variation'),
        pl.when(pl.col('finite_count') > 0)
        .then(100 * pl.col('zero_count') / pl.col('finite_count'))
        .otherwise(None).round(2).alias('zero_percent'),
        pl.when(pl.col('finite_count') > 0)
        .then(100 * pl.col('negative_count') / pl.col('finite_count'))
        .otherwise(None).round(2).alias('negative_percent'),
    )


def temporal(data: DataInput | DataSource, column: str) -> pl.DataFrame:
    """One-row summary for Date/Datetime/Time/Duration columns."""
    source = as_source(data)
    dtype = _name_check(source, column)
    if dtype_kind(dtype) != 'temporal':
        raise TypeError(f'{column} is not temporal ({dtype})')
    c = pl.col(column)
    return source.frame.select(
        pl.len().alias('rows'),
        c.is_null().sum().alias('null_count'),
        c.n_unique().alias('unique_count'),
        c.min().alias('min'),
        c.max().alias('max'),
    ).collect()


def crosstab(
        data: DataInput | DataSource,
        column: str,
        *,
        by: str,
        denominator: Literal['total', 'group', 'row'] = 'group',
        include_null: bool = True,
        max_cells: int = 1000,
) -> pl.DataFrame:
    """Tidy two-way counts/percentages, with explicit denominator semantics.

    `group` means within each `by` category; `row` means within each
    `column` category. Results are deterministically sorted by string labels.
    """
    source = as_source(data)
    _name_check(source, column)
    _name_check(source, by)
    if column == by:
        raise ValueError('column and by must differ')
    if denominator not in ('total', 'group', 'row'):
        raise ValueError('Unknown denominator')
    if max_cells < 1:
        raise ValueError('max_cells must be positive')
    frame = source.frame.select(column, by)
    if not include_null:
        frame = frame.filter(pl.all_horizontal(pl.col(column).is_not_null(), pl.col(by).is_not_null()))
    # bound grouped output before collection
    grouped = frame.group_by(column, by).agg(pl.len().alias('count'))
    observed = grouped.limit(max_cells + 1).collect()
    if observed.height > max_cells:
        raise ValueError('Too many categories for crosstab; filter or reduce categories')
    counts = observed.to_dicts()
    total = sum(r['count'] for r in counts)

    def key(value: object) -> tuple[str, str]:
        # distinguish literal null labels from missing values
        return ('null', '') if value is None else ('value', repr(value))

    group_totals: dict[tuple[str, str], int] = {}
    row_totals: dict[tuple[str, str], int] = {}
    for r in counts:
        group_key, row_key = key(r[by]), key(r[column])
        group_totals[group_key] = group_totals.get(group_key, 0) + r['count']
        row_totals[row_key] = row_totals.get(row_key, 0) + r['count']
    rows = []
    for r in counts:
        group = str(r[by]) if r[by] is not None else '(null)'
        row = str(r[column]) if r[column] is not None else '(null)'
        denom = (total if denominator == 'total' else
                 group_totals[key(r[by])] if denominator == 'group' else
                 row_totals[key(r[column])])
        rows.append({'value': row, 'group': group, 'count': r['count'],
                     'percent': round(100 * r['count'] / denom, 2) if denom else 0.0})
    rows.sort(key=lambda r: (r['group'], r['value']))
    return pl.DataFrame(rows, schema={'value': pl.String, 'group': pl.String,
                                      'count': pl.Int64, 'percent': pl.Float64})


def summary(
        data: DataInput | DataSource,
        columns: list[str] | tuple[str, ...],
        *,
        by: str | None = None,
        max_categories: int = 20,
        max_groups: int = 50,
) -> pl.DataFrame:
    """Tidy descriptive summaries, with grouped numeric metrics in one query.

    Grouping executes one aggregated scan per numeric variable, instead of
    one scan per group. Categorical values use one bounded crosstab.
    """
    if max_categories < 1 or max_groups < 1:
        raise ValueError('max_categories and max_groups must be positive')
    source = as_source(data)
    names = list(columns)
    if by is not None:
        _name_check(source, by)
        distinct = source.frame.select(pl.col(by)).unique().limit(max_groups + 1).collect()
        if distinct.height > max_groups:
            raise ValueError(
                f'Grouping {by!r} has more than {max_groups} groups; '
                'filter the dataset or increase max_groups'
            )
    for name in names:
        _name_check(source, name)
    results: list[dict] = []
    for name in names:
        kind = dtype_kind(source.schema[name])
        if kind == 'numeric':
            if by is None:
                summarized = numeric(source, name).to_dicts()
                grouped = [('Overall', summarized[0])]
            else:
                # one grouped numeric aggregation across every stratum
                rows = source.frame.group_by(by).agg(
                    *_numeric_exprs(name, source.schema[name], ''),
                ).collect().to_dicts()
                grouped = [(('(null)' if row[by] is None else str(row[by])), row)
                           for row in rows]
                grouped.sort(key=lambda item: item[0])
            for group, row in grouped:
                for metric in ('finite_count', 'mean', 'std', 'median', 'q25', 'q75'):
                    val = row[metric]
                    results.append({'variable': name, 'group': group,
                                    'level': '', 'statistic': metric,
                                    'value': float(val) if val is not None else None})
        elif kind == 'categorical':
            if by is None:
                grouped_rows = [('Overall', row) for row in
                                frequency(source, name, top_n=max_categories).to_dicts()]
                for group, row in grouped_rows:
                    for metric in ('count', 'percent'):
                        results.append({'variable': name, 'group': group,
                                        'level': row['value'], 'statistic': metric,
                                        'value': float(row[metric]) if row[metric] is not None else None})
            else:
                frequencies = crosstab(
                    source, name, by=by, denominator='group',
                    max_cells=max(2000, max_categories * max_groups),
                )
                for row in frequencies.iter_rows(named=True):
                    for metric in ('count', 'percent'):
                        results.append({'variable': name, 'group': row['group'],
                                        'level': row['value'], 'statistic': metric,
                                        'value': float(row[metric]) if row[metric] is not None else None})
    return pl.DataFrame(results, schema={'variable': pl.String, 'group': pl.String,
                                         'level': pl.String, 'statistic': pl.String,
                                         'value': pl.Float64})


def correlations(
        data: DataInput | DataSource,
        *,
        columns=None,
        method: Literal['pearson', 'spearman'] = 'pearson',
        max_columns: int = 20,
) -> pl.DataFrame:
    """Pairwise numeric correlations in tidy form (opt-in; never in quick mode).

    Null, NaN, and infinite observations are excluded pairwise. Correlations
    with fewer than two valid paired values return null. This can require
    O(number of variable pairs) scans and is intentionally bounded.
    """
    if method not in ('pearson', 'spearman'):
        raise ValueError('method must be pearson or spearman')
    if max_columns < 1:
        raise ValueError('max_columns must be positive')
    source = as_source(data)
    names = (list(columns) if columns is not None else
             [name for name, dtype in source.schema.items() if dtype_kind(dtype) == 'numeric'])
    if len(names) > max_columns:
        raise ValueError(f'Correlation limited to {max_columns} columns')
    for name in names:
        dtype = _name_check(source, name)
        if dtype_kind(dtype) != 'numeric':
            raise TypeError(f'{name} is not numeric ({dtype})')
    result = []
    for i, left in enumerate(names):
        for right in names[i + 1:]:
            x, y = pl.col(left), pl.col(right)
            paired = source.frame.filter(x.is_finite() & y.is_finite())
            row = paired.select(
                pl.len().alias('n'),
                pl.corr(left, right, method=method).alias('correlation'),
            ).collect().row(0, named=True)
            result.append({'left': left, 'right': right, 'method': method,
                           'n': row['n'],
                           'correlation': (float(row['correlation'])
                                           if row['n'] >= 2 and row['correlation'] is not None else None)})
    return pl.DataFrame(result, schema={'left': pl.String, 'right': pl.String,
                                        'method': pl.String, 'n': pl.Int64,
                                        'correlation': pl.Float64})


def cramers_v(
        data: DataInput | DataSource,
        column: str,
        by: str,
        *,
        bias_corrected: bool = True,
        include_null: bool = False,
        max_categories: int = 50,
        max_cells: int = 1000,
) -> pl.DataFrame:
    """Calculate Cramér's V for two nominal or categorical-coded variables.

    Parameters
    ----------
    data
        A polars DataFrame, LazyFrame, or parquet source.
    column, by
        Distinct columns representing categorical variables. Integer-coded
        and other bounded numeric categories are accepted. Nulls are
        excluded pairwise unless ``include_null=True``. Floating NaN and
        infinity are always excluded.
    bias_corrected
        Apply the finite-sample correction proposed by Bergsma (2013).
        Defaults to ``True``; ``False`` gives the conventional estimate,
        without a Yates continuity correction.
    include_null
        Treat null as a distinct category in each column. A literal string
        ``'(null)'`` is not conflated with an actual null.
    max_categories
        Maximum number of observed levels per column. This is a practical
        guard, not a guarantee of fixed peak memory use.
    max_cells
        Maximum full contingency-table size (row levels × column levels).

    Returns
    -------
    pl.DataFrame
        A one-row table with ``cramers_v`` (null when undefined), sample
        size, contingency-table dimensions, chi-square statistic, and
        expected-cell diagnostics. No p-values or source category values
        are returned.

    Notes
    -----
    Cramér's V describes association strength, not direction or causation.
    Pairwise-complete records are used by default. For patient-level
    interpretation, consider whether repeated encounters are independent.
    """
    if column == by:
        raise ValueError('column and by must differ')
    if max_categories < 1:
        raise ValueError('max_categories must be positive')
    if max_cells < 1:
        raise ValueError('max_cells must be positive')
    source = as_source(data)
    kinds = {}
    for name in (column, by):
        dtype = _name_check(source, name)
        kind = dtype_kind(dtype)
        if kind not in ('numeric', 'categorical'):
            raise TypeError(f'{name} must be categorical or category-coded numeric ({dtype})')
        kinds[name] = dtype

    # private aliases avoid source-column naming conflicts
    frame = source.frame.select(
        pl.col(column).alias('_left'),
        pl.col(by).alias('_right'),
    )
    if not include_null:
        frame = frame.filter(
            pl.col('_left').is_not_null() & pl.col('_right').is_not_null()
        )
    for name, alias in ((column, '_left'), (by, '_right')):
        if kinds[name] in (pl.Float32, pl.Float64):
            condition = pl.col(alias).is_finite()
            if include_null:
                condition = condition | pl.col(alias).is_null()
            frame = frame.filter(condition)

    # exact level counts before full contingency-table grouping
    levels = frame.select(
        pl.len().alias('n'),
        pl.col('_left').n_unique().alias('r'),
        pl.col('_right').n_unique().alias('c'),
    ).collect().row(0, named=True)
    n = int(levels['n'])
    r = int(levels['r']) if n else 0
    c = int(levels['c']) if n else 0
    if r > max_categories or c > max_categories:
        raise ValueError(
            f'Cramér\'s V has {r} × {c} categories; '
            f'limit is {max_categories} per variable'
        )
    if r * c > max_cells:
        raise ValueError(
            f'Cramér\'s V contingency table has {r * c} cells; '
            f'limit is {max_cells}'
        )

    chi2 = None
    value = None
    min_expected = None
    small_expected = 0
    if n and r and c:
        counts = (
            frame.group_by('_left', '_right')
            .agg(pl.len().alias('_count'))
            .collect().to_dicts()
        )
        marginal_left = Counter()
        marginal_right = Counter()
        observed = {}
        for row in counts:
            left, right = row['_left'], row['_right']
            count = int(row['_count'])
            marginal_left[left] += count
            marginal_right[right] += count
            observed[left, right] = count
        chi2 = 0.0
        for left, left_n in marginal_left.items():
            for right, right_n in marginal_right.items():
                expected = left_n * right_n / n
                min_expected = expected if min_expected is None else min(
                    min_expected, expected
                )
                small_expected += expected < 5
                difference = observed.get((left, right), 0) - expected
                chi2 += difference * difference / expected
        if r > 1 and c > 1 and n > 1:
            phi2 = chi2 / n
            if bias_corrected:
                adjusted = max(0.0, phi2 - (r - 1) * (c - 1) / (n - 1))
                r_adjusted = r - (r - 1) ** 2 / (n - 1)
                c_adjusted = c - (c - 1) ** 2 / (n - 1)
                divisor = min(r_adjusted - 1, c_adjusted - 1)
            else:
                adjusted = phi2
                divisor = min(r - 1, c - 1)
            if divisor > 0:
                value = min(1.0, sqrt(max(0.0, adjusted / divisor)))

    return pl.DataFrame([{
        'column': column,
        'by': by,
        'n': n,
        'n_rows': r,
        'n_columns': c,
        'cramers_v': value,
        'bias_corrected': bias_corrected,
        'chi2': chi2,
        'min_expected': min_expected,
        'small_expected_cells': small_expected,
        'small_expected_fraction': (
            small_expected / (r * c) if r and c else None
        ),
    }], schema={
        'column': pl.String,
        'by': pl.String,
        'n': pl.Int64,
        'n_rows': pl.Int64,
        'n_columns': pl.Int64,
        'cramers_v': pl.Float64,
        'bias_corrected': pl.Boolean,
        'chi2': pl.Float64,
        'min_expected': pl.Float64,
        'small_expected_cells': pl.Int64,
        'small_expected_fraction': pl.Float64,
    })


def text(data: DataInput | DataSource, column: str) -> pl.DataFrame:
    """Profile text length and emptiness without exporting example strings.

    Useful for long free-text columns and high-cardinality string variables.
    """
    source = as_source(data)
    dtype = _name_check(source, column)
    if dtype.base_type() not in (pl.String, pl.Categorical, pl.Enum):
        raise TypeError(f'{column} is not a text dtype ({dtype})')
    c = pl.col(column).cast(pl.String)
    length = c.str.len_chars()
    return source.frame.select(
        pl.len().alias('rows'),
        c.is_null().sum().alias('null_count'),
        (c == '').sum().alias('empty_count'),
        (c.str.strip_chars() == '').sum().alias('blank_count'),
        ((c.str.strip_chars() == '') & (c != '')).sum().alias('whitespace_only_count'),
        length.min().alias('min_length'),
        length.max().alias('max_length'),
        length.mean().alias('mean_length'),
        length.median().alias('median_length'),
    ).collect()


def outliers(
        data: DataInput | DataSource, column: str, *, iqr_multiplier: float = 1.5,
        summary: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """Count IQR-rule outliers among finite observations of one numeric column.

    Whisker limits are descriptive and do not imply invalid observations.
    This calculation scans finite values once after determining quantiles.
    """
    if iqr_multiplier <= 0:
        raise ValueError('iqr_multiplier must be positive')
    source = as_source(data)
    if dtype_kind(_name_check(source, column)) != 'numeric':
        raise TypeError(f'{column} is not numeric')
    row = (summary if summary is not None else numeric(source, column)).row(0, named=True)
    n = int(row['finite_count'])
    q25, q75 = row['q25'], row['q75']
    low = (float(q25) - iqr_multiplier * (float(q75) - float(q25))
           if q25 is not None and q75 is not None else None)
    high = (float(q75) + iqr_multiplier * (float(q75) - float(q25))
            if q25 is not None and q75 is not None else None)
    count = None
    if n and low is not None and high is not None:
        c = pl.col(column).cast(pl.Float64)
        count = int(source.frame.select(
            ((c.is_finite()) & ((c < low) | (c > high))).fill_null(False)
            .cast(pl.Int64).sum().alias('outliers')
        ).collect().item())
    return pl.DataFrame([{
        'column': column, 'finite_count': n, 'lower_bound': low,
        'upper_bound': high, 'outlier_count': count,
        'outlier_percent': (round(100 * count / n, 2)
                            if count is not None and n else None),
        'method': f'IQR × {iqr_multiplier:g}',
    }])


def categorical_diagnostics(
        data: DataInput | DataSource,
        column: str, *, rare_at_most: int = 5, max_unique: int = 1000,
) -> pl.DataFrame:
    """Bounded rare-category and imbalance statistics, without category values.

    A cardinality guard runs before exact grouping; the guard is approximate,
    so it is a practical safeguard rather than a strict memory guarantee.
    """
    if rare_at_most < 1 or max_unique < 1:
        raise ValueError('rare_at_most and max_unique must be positive')
    source = as_source(data)
    dtype = _name_check(source, column)
    if dtype_kind(dtype) != 'categorical':
        raise TypeError(f'{column} is not categorical')
    c = pl.col(column)
    estimate = source.frame.select(c.approx_n_unique()).collect().item()
    if estimate > max_unique:
        raise ValueError(f'{column} has approximately {estimate:,} distinct values; '
                         f'limit is {max_unique:,}')
    grouped = (
        source.frame.select(c.alias('_category'))
        .filter(pl.col('_category').is_not_null())
        .group_by('_category').agg(pl.len().alias('_n'))
    )
    row = grouped.select(
        pl.len().alias('distinct_count'),
        pl.col('_n').sum().alias('non_null_count'),
        (pl.col('_n') <= rare_at_most).sum().alias('rare_categories'),
        pl.col('_n').filter(pl.col('_n') <= rare_at_most)
        .sum().alias('rare_records'),
        pl.col('_n').max().alias('largest_category_count'),
    ).collect().row(0, named=True)
    non_null = int(row['non_null_count'] or 0)
    max_n = int(row['largest_category_count'] or 0)
    return pl.DataFrame([{
        'column': column,
        'non_null_count': non_null,
        'distinct_count': int(row['distinct_count'] or 0),
        'rare_categories': int(row['rare_categories'] or 0),
        'rare_records': int(row['rare_records'] or 0),
        'dominant_percent': round(100 * max_n / non_null, 2) if non_null else None,
        'rare_max_count': rare_at_most,
    }])
