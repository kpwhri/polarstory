"""Descriptive, publication-ready cohort summaries; no inferential testing.

Output is a small, formatted polars DataFrame for the static HTML renderer.
The implementation only collects aggregate results from LazyFrames. Exact
category group-bys and quantiles can nevertheless require substantial memory.
"""

from __future__ import annotations

from typing import Literal

import polars as pl

from polarstory.columns import dtype_kind
from polarstory.source import DataInput, DataSource, as_source
from polarstory.variables import Variable, Variables


def _label(value: object, *, null_label: str = '(null)') -> str:
    return null_label if value is None else str(value)


def _display_number(value: object, decimals: int) -> str:
    if value is None:
        return '—'
    return f'{float(value):,.{decimals}f}'


def table1(
        data: DataInput | DataSource,
        columns: list[str] | tuple[str, ...],
        *,
        by: str | None = None,
        numeric: Literal['median_iqr', 'mean_sd'] = 'median_iqr',
        percent: Literal['total', 'valid'] = 'total',
        include_total: bool = True,
        include_missing: bool = True,
        max_categories: int = 20,
        max_strata: int = 12,
        decimals: int = 1,
        variables: Variables | None = None,
        include_sensitive: bool = False,
) -> pl.DataFrame:
    """Return a wide, formatted descriptive Table 1.

    Categorical cells contain `n (percent%)`; numeric cells contain a median
    [Q1, Q3] or mean (SD) plus a nonmissing-n row. Percentages use either all
    records (`total`) or nonmissing records (`valid`) in each stratum; missing
    percentages always use all records. `Other categories` aggregates levels
    outside the globally selected top `max_categories`.

    The table is explicitly descriptive: no p-values, confidence intervals,
    regression, or significance tests are computed. No raw rows are collected.
    Sensitive variables are refused unless explicitly authorized.
    """
    if numeric not in ('median_iqr', 'mean_sd'):
        raise ValueError("numeric must be 'median_iqr' or 'mean_sd'")
    if percent not in ('total', 'valid'):
        raise ValueError("percent must be 'total' or 'valid'")
    if max_categories < 1 or max_strata < 1 or decimals < 0 or decimals > 8:
        raise ValueError('max_categories, max_strata and decimals must be in range')
    source = as_source(data)
    names = list(columns)
    if len(names) != len(set(names)):
        raise ValueError('columns must not contain duplicates')
    if by is not None and by in names:
        raise ValueError('by must not also be a summarized column')
    schema = source.schema
    for name in names + ([by] if by else []):
        if name not in schema:
            raise ValueError(f'Unknown column: {name}')
    metadata = variables.resolve(source) if variables is not None else {}
    for name in names + ([by] if by else []):
        meta = metadata.get(name, Variable())
        if meta.sensitive and not include_sensitive:
            raise ValueError(f'{name} is marked sensitive; pass include_sensitive=True to include it')
        if meta.kind in ('identifier', 'text', 'ignore'):
            raise ValueError(f'{name} is configured as {meta.kind}; omit it from Table 1')

    count = int(source.frame.select(pl.len()).collect().item())
    total_key = object()  # avoid collisions with real category values
    # keep raw values separate from display labels
    group_counts: dict[object, int] = {}
    if by is not None:
        grouped = source.frame.group_by(by).agg(pl.len().alias('_n'))
        bounded = grouped.limit(max_strata + 1).collect()
        if bounded.height > max_strata:
            raise ValueError(f'Too many strata (limit {max_strata}); use a lower-cardinality by')
        group_counts = {row[by]: int(row['_n']) for row in bounded.to_dicts()}
    strata = sorted(group_counts, key=lambda x: (x is None, str(x)))
    group_keys = ([total_key] if by is None else
                  ([total_key] if include_total else []) + strata)
    if not group_keys:
        raise ValueError('No strata found; enable include_total for an empty dataset')

    display_groups: dict[object, str] = {}
    seen: set[str] = set()
    for key in group_keys:
        label = 'Overall' if key is total_key else _label(key)
        if key is not total_key and key is not None and label == '(null)':
            label += ' [literal]'
        if label in seen:
            label += ' [category]'
        seen.add(label)
        n = count if key is total_key else group_counts[key]
        display_groups[key] = f'{label} (N={n:,})'

    rows: list[dict[str, str]] = []

    def append(variable: str, level: str, cells: dict[object, str]) -> None:
        row = {'Variable': variable, 'Level': level}
        row.update({display_groups[key]: cells.get(key, '—') for key in group_keys})
        rows.append(row)

    def get_numeric(frame: pl.LazyFrame, name: str, group: str | None) -> dict[object, dict]:
        c = pl.col(name)
        finite = c.filter(c.is_finite()) if schema[name].is_float() else c.drop_nulls()
        exprs = [
            finite.count().alias('_valid'),
            c.is_null().sum().alias('_missing'),
            finite.mean().alias('_mean'),
            finite.std().alias('_sd'),
            finite.median().alias('_median'),
            finite.quantile(.25).alias('_q25'),
            finite.quantile(.75).alias('_q75'),
        ]
        if group is None:
            return {total_key: frame.select(*exprs).collect().row(0, named=True)}
        return {row[group]: row for row in frame.group_by(group).agg(*exprs).collect().to_dicts()}

    for name in names:
        meta = metadata.get(name, Variable())
        dtype = schema[name]
        kind = meta.kind if meta.kind != 'auto' else dtype_kind(dtype)
        label = meta.label or name
        if kind == 'numeric':
            if dtype_kind(dtype) != 'numeric':
                raise TypeError(f'{name} is not numeric ({dtype})')
            values = get_numeric(source.frame, name, by)
            overall = get_numeric(source.frame, name, None) if by else values

            def measure(row: dict | None) -> str:
                if not row or not row['_valid']:
                    return '—'
                if numeric == 'median_iqr':
                    vals = (row['_median'], row['_q25'], row['_q75'])
                    return (f'{_display_number(vals[0], decimals)} '
                            f'[{_display_number(vals[1], decimals)}, '
                            f'{_display_number(vals[2], decimals)}]')
                return (f'{_display_number(row["_mean"], decimals)} '
                        f'({_display_number(row["_sd"], decimals)})')

            def metric_row(key: object) -> dict | None:
                return overall.get(total_key) if key is total_key else values.get(key)

            level = 'Median [Q1, Q3]' if numeric == 'median_iqr' else 'Mean (SD)'
            append(label, level, {key: measure(metric_row(key)) for key in group_keys})
            append('', 'Non-missing, n', {
                key: f'{metric_row(key)["_valid"]:,}' if metric_row(key) else '0'
                for key in group_keys
            })
            if include_missing:
                # exclude null, NaN, and infinite values from finite summaries
                # show the excluded count
                append('', 'Excluded (null / NaN / infinity), n (%)', {
                    key: (f'{(count if key is total_key else group_counts[key]) - metric_row(key)["_valid"]:,} '
                          f'({100 * ((count if key is total_key else group_counts[key]) - metric_row(key)["_valid"]) / (count if key is total_key else group_counts[key]):.{decimals}f}%)'
                          if metric_row(key) and (count if key is total_key else group_counts[key]) else '0 (—)')
                    for key in group_keys
                })
            continue

        if kind not in ('categorical', 'boolean'):
            raise TypeError(f'{name} is {dtype}; Table 1 supports numeric or categorical columns')

        c = pl.col(name)
        # select global top categories, keeping strata and denominators comparable
        top = (source.frame
               .filter(c.is_not_null())
               .group_by(name)
               .agg(pl.len().alias('_n'))
               .sort(['_n', name], descending=[True, False])
               .limit(max_categories).collect().to_dicts())
        levels = [row[name] for row in top]
        ranks = {value: index for index, value in enumerate(meta.order)}
        levels.sort(key=lambda v: (ranks.get(str(v), len(ranks)),
                                   -next(r['_n'] for r in top if r[name] == v), str(v)))
        # restrict aggregation to selected levels, bounding the output by categories and strata
        selected = source.frame.filter(c.is_in(levels)) if levels else source.frame.filter(pl.lit(False))
        if by:
            grouped_counts = selected.group_by(name, by).agg(pl.len().alias('_n')).collect().to_dicts()
            per_group = {(r[by], r[name]): int(r['_n']) for r in grouped_counts}
        else:
            per_group = {}
        overall_counts = {r[name]: int(r['_n']) for r in top}
        nulls = source.frame.select(c.is_null().sum()).collect().item()
        if by:
            group_nulls = {r[by]: int(r['_missing']) for r in source.frame.group_by(by).agg(
                c.is_null().sum().alias('_missing')).collect().to_dicts()}
        else:
            group_nulls = {}

        def category_count(key: object, value: object) -> int:
            return (overall_counts.get(value, 0) if key is total_key
                    else per_group.get((key, value), 0))

        def total_for(key: object) -> int:
            return count if key is total_key else group_counts[key]

        def missing_for(key: object) -> int:
            return int(nulls) if key is total_key else group_nulls.get(key, 0)

        def cell(key: object, n: int, *, missing: bool = False) -> str:
            denom = total_for(key)
            if percent == 'valid' and not missing:
                denom -= missing_for(key)
            return f'{n:,} ({100 * n / denom:.{decimals}f}%)' if denom else f'{n:,} (—)'

        for index, value in enumerate(levels):
            value_label = meta.value_labels.get(str(value), str(value))
            if value_label in ('(null)', 'Other categories'):
                value_label += ' [literal]'
            append(label if index == 0 else '', value_label, {
                key: cell(key, category_count(key, value)) for key in group_keys
            })
        # include an other row for remaining categories
        other = {key: total_for(key) - missing_for(key) -
                      sum(category_count(key, value) for value in levels) for key in group_keys}
        if any(n > 0 for n in other.values()):
            append('' if levels else label, 'Other categories', {
                key: cell(key, other[key]) for key in group_keys
            })
        if include_missing and any(missing_for(key) for key in group_keys):
            append('' if levels else label, '(null)', {
                key: cell(key, missing_for(key), missing=True) for key in group_keys
            })

    return pl.DataFrame(
        rows,
        schema={name: pl.String for name in ['Variable', 'Level', *display_groups.values()]},
    )
