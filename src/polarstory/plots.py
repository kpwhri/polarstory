"""Static, print-friendly Matplotlib figures built from polars aggregations."""

from __future__ import annotations

import polars as pl
from matplotlib.figure import Figure

from polarstory import stats
from polarstory.columns import dtype_kind
from polarstory.source import DataInput, DataSource, as_source


def _figure(*, height: float = 3.3) -> tuple[Figure, object]:
    fig = Figure(figsize=(7.0, height), layout='constrained')
    return fig, fig.subplots()


def frequency(
        data: DataInput | DataSource,
        column: str,
        *,
        top_n: int = 15,
        include_null: bool = True,
        title: str | None = None,
        counts: pl.DataFrame | None = None,
) -> Figure:
    """Horizontal bar chart of the most frequent categorical values."""
    if counts is None:
        counts = stats.frequency(data, column, top_n=top_n, include_null=include_null)
    pairs = [(r['value'], r['count']) for r in counts.to_dicts()]
    fig, ax = _figure(height=min(8.8, max(3.3, 1.35 + .38 * len(pairs))))
    if pairs:
        labels, values = zip(*reversed(pairs))
        ax.barh(range(len(labels)), values, color='#386fa4')
        ax.set_yticks(range(len(labels)), labels=labels)
        ax.set_xlabel('Count')
    else:
        ax.text(0.5, 0.5, 'No observations', transform=ax.transAxes,
                ha='center', va='center')
        ax.set_axis_off()
    ax.set_title(title or column, loc='left')
    ax.spines[['top', 'right']].set_visible(False)
    return fig


def histogram(
        data: DataInput | DataSource,
        column: str,
        *,
        bins: int = 20,
        title: str | None = None,
        summary: pl.DataFrame | None = None,
) -> Figure:
    """Aggregate histogram bin counts lazily without collecting raw values.

    Bin edges are computed from Float64 min/max (an approximate numeric
    representation for very large integers). NaN/infinite values are excluded.
    """
    if bins < 1:
        raise ValueError('bins must be at least 1')
    source = as_source(data)
    if column not in source.schema:
        raise ValueError(f'Unknown column: {column}')
    dtype = source.schema[column]
    if dtype_kind(dtype) != 'numeric':
        raise TypeError(f'{column} is not numeric ({dtype})')

    values = source.frame.select(pl.col(column).cast(pl.Float64).alias('_value'))
    values = values.filter(pl.col('_value').is_not_null() & pl.col('_value').is_finite())
    if summary is None:
        limits = values.select(
            pl.col('_value').min().alias('low'),
            pl.col('_value').max().alias('high'),
            pl.len().alias('n'),
        ).collect().row(0, named=True)
    else:
        metric = summary.row(0, named=True)
        limits = {'low': metric['min'], 'high': metric['max'],
                  'n': metric['finite_count']}
    fig, ax = _figure()
    low, high = limits['low'], limits['high']
    if not limits['n']:
        ax.text(0.5, 0.5, 'No finite observations', transform=ax.transAxes,
                ha='center', va='center')
        ax.set_axis_off()
    elif low == high:
        ax.bar([low], [limits['n']], width=1.0, color='#386fa4')
    else:
        step = (high - low) / bins
        index = (
            ((pl.col('_value') - low) / step).floor()
            .clip(0, bins - 1).cast(pl.Int32).alias('_bin')
        )
        grouped = (
            values.select(index).group_by('_bin')
            .agg(pl.len().alias('n')).collect()
        )
        counts = {r['_bin']: r['n'] for r in grouped.to_dicts()}
        ax.bar(
            [low + i * step for i in range(bins)],
            [counts.get(i, 0) for i in range(bins)],
            width=step * 0.95, align='edge', color='#386fa4',
        )
    if limits['n']:
        ax.set_xlabel(column)
        ax.set_ylabel('Count')
    ax.set_title(title or column, loc='left')
    ax.spines[['top', 'right']].set_visible(False)
    return fig


def missingness(
        data: DataInput | DataSource | None = None, *,
        title: str = 'Missing values', rows: pl.DataFrame | None = None,
) -> Figure:
    """Compact null percentage chart (not a record-level heat map)."""
    if rows is None:
        if data is None:
            raise ValueError('data or rows must be provided')
        rows = stats.missingness(data)
    rows = rows.sort('null_percent', descending=True).to_dicts()
    fig, ax = _figure(height=min(8.8, max(3.3, 1.35 + .30 * min(len(rows), 30))))
    if rows:
        top = list(reversed(rows[:30]))
        ax.barh(range(len(top)), [r['null_percent'] for r in top], color='#386fa4')
        ax.set_yticks(range(len(top)), labels=[r['column'] for r in top])
        ax.set_xlabel('Null (%)')
        ax.set_xlim(0, 100)
    else:
        ax.set_axis_off()
    ax.set_title(title, loc='left')
    ax.spines[['top', 'right']].set_visible(False)
    return fig


def temporal(
        data: DataInput | DataSource, column: str, *,
        title: str | None = None, max_periods: int = 36,
) -> Figure:
    """Counts per month for Date/Datetime columns, keeping output bounded."""
    source = as_source(data)
    dtype = source.schema[column]
    if dtype.base_type() not in (pl.Date, pl.Datetime):
        raise TypeError('Temporal chart requires a Date or Datetime column')
    if max_periods < 1:
        raise ValueError('max_periods must be positive')
    grouped = (
        source.frame.select(pl.col(column).dt.truncate('1mo').alias('_period'))
        .filter(pl.col('_period').is_not_null())
        .group_by('_period')
        .agg(pl.len().alias('count'))
        .sort('_period')
        .tail(max_periods)
        .collect()
    )
    fig, ax = _figure()
    if grouped.height:
        periods = [str(value)[:7] for value in grouped['_period'].to_list()]
        ax.bar(range(grouped.height), grouped['count'].to_list(), color='#386fa4')
        stride = max(1, (grouped.height + 7) // 8)
        ticks = list(range(0, grouped.height, stride))
        ax.set_xticks(ticks, [periods[i] for i in ticks], rotation=30, ha='right')
        ax.set_ylabel('Count')
    else:
        ax.text(.5, .5, 'No observations', ha='center', va='center',
                transform=ax.transAxes)
        ax.set_axis_off()
    ax.set_title(title or column, loc='left')
    ax.spines[['top', 'right']].set_visible(False)
    return fig


def text_length(data: DataInput | DataSource, column: str, *,
                title: str | None = None, bins: int = 20) -> Figure:
    """Distribution of character lengths, without exporting any text values."""
    source = as_source(data)
    if source.schema[column].base_type() not in (pl.String, pl.Categorical, pl.Enum):
        raise TypeError('Text length chart requires a string column')
    lengths = source.frame.select(
        pl.col(column).cast(pl.String).str.len_chars().alias('_length')
    )
    figure = histogram(lengths, '_length', bins=bins, title=title or column)
    figure.axes[0].set_xlabel('Character length')
    return figure


def grouped_numeric(rows: pl.DataFrame, *, title: str) -> Figure:
    """Show group medians and interquartile ranges using summary statistics."""
    data = rows.to_dicts()
    groups: dict[str, dict[str, float | None]] = {}
    for row in data:
        if row['statistic'] in ('median', 'q25', 'q75'):
            groups.setdefault(row['group'], {})[row['statistic']] = row['value']
    fig, ax = _figure(height=min(8, max(3.3, 1.6 + 0.38 * len(groups))))
    plotted = 0
    for label, values in sorted(groups.items()):
        median, low, high = (values.get('median'), values.get('q25'), values.get('q75'))
        if median is None or low is None or high is None:
            continue
        ax.errorbar(median, plotted, xerr=[[max(0, median - low)],
                                           [max(0, high - median)]], fmt='o',
                    color='#386fa4', capsize=3)
        plotted += 1
    if plotted:
        ax.set_yticks(range(plotted), [label for label, values in sorted(groups.items())
                                       if all(values.get(k) is not None
                                              for k in ('median', 'q25', 'q75'))])
        ax.set_xlabel('Median and interquartile range')
    else:
        ax.text(.5, .5, 'No finite observations', transform=ax.transAxes,
                va='center', ha='center')
        ax.set_axis_off()
    ax.set_title(title, loc='left')
    ax.spines[['top', 'right']].set_visible(False)
    return fig


def grouped_frequency(rows: pl.DataFrame, *, title: str, max_groups: int = 20) -> Figure:
    """Plot grouped percentages from a bounded tidy contingency table."""
    records = rows.to_dicts()
    categories = sorted({r['value'] for r in records})
    groups = sorted({r['group'] for r in records})
    if len(groups) > max_groups or len(categories) > 100:
        raise ValueError(f'Grouped chart limited to {max_groups} groups and 100 categories')
    fig, ax = _figure(height=min(9, max(3.3, 1.8 + .45 * len(categories))))
    if not records:
        ax.text(.5, .5, 'No observations', transform=ax.transAxes,
                ha='center', va='center')
        ax.set_axis_off()
    else:
        values = {(r['group'], r['value']): r['percent'] or 0 for r in records}
        width = 0.8 / len(groups)
        for index, group in enumerate(groups):
            offsets = [i - .4 + width * (index + .5) for i in range(len(categories))]
            ax.barh(offsets, [values.get((group, v), 0) for v in categories],
                    height=width, label=group)
        ax.set_yticks(range(len(categories)), categories)
        ax.set_xlabel('Percent')
        ax.legend(title='Group', loc='best')
    ax.set_title(title, loc='left')
    ax.spines[['top', 'right']].set_visible(False)
    return fig


def missingness_associations(
        rows: pl.DataFrame, *, title: str = 'Missingness associations',
) -> Figure:
    """Static phi-correlation heatmap from aggregated missingness statistics.

    Values are pairwise phi coefficients; undefined values are left blank.
    No source rows or missingness indicator matrix are embedded in the SVG.
    """
    import numpy as np

    names = sorted(set(rows['left'].to_list()) | set(rows['right'].to_list()))
    if len(names) > 20:
        raise ValueError('Missingness heatmap limited to 20 columns')
    fig, ax = _figure(height=min(9, max(3.3, 1.2 + .40 * len(names))))
    if not names:
        ax.text(.5, .5, 'Not enough variables', transform=ax.transAxes,
                ha='center', va='center')
        ax.set_axis_off()
        ax.set_title(title, loc='left')
        return fig
    matrix = np.full((len(names), len(names)), np.nan)
    index = {name: i for i, name in enumerate(names)}
    for row in rows.iter_rows(named=True):
        i, j = index[row['left']], index[row['right']]
        phi = row['phi']
        if phi is not None:
            matrix[i, j] = matrix[j, i] = float(phi)
            matrix[i, i] = matrix[j, j] = 1.0
    cmap = __import__('matplotlib').colormaps['RdBu'].copy()
    cmap.set_bad('#f1f2f4')
    image = ax.imshow(np.ma.masked_invalid(matrix), vmin=-1, vmax=1, cmap=cmap)
    ax.set_xticks(range(len(names)), labels=names, rotation=45, ha='right')
    ax.set_yticks(range(len(names)), labels=names)
    if len(names) <= 10:
        for i in range(len(names)):
            for j in range(len(names)):
                if np.isfinite(matrix[i, j]):
                    ax.text(j, i, f'{matrix[i, j]:.2f}', ha='center', va='center',
                            fontsize=8, color='white' if abs(matrix[i, j]) > .6 else 'black')
    fig.colorbar(image, ax=ax, label='Phi coefficient', fraction=.04, pad=.04)
    ax.set_title(title, loc='left')
    return fig
