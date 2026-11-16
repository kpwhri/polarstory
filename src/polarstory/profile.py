"""Automatic, reusable, predominantly streaming-friendly polars profiles."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Callable

import polars as pl
from matplotlib.figure import Figure

from polarstory import alerts as quality_alerts, plots, stats
from polarstory.columns import ColumnSelection, dtype_kind, select_columns
from polarstory.metrics import collect_metrics
from polarstory.source import DataInput, DataSource, as_source
from polarstory.report import Report, ReportItem
from polarstory.variables import Variable, Variables


@dataclass(frozen=True)
class ProfileOptions:
    """Options for low-cost univariate profiling and offline HTML output."""

    max_categories: int = 15
    max_groups: int = 50
    max_chart_groups: int = 20
    max_unique_for_frequency: int = 1000
    histogram_bins: int = 20
    include_null: bool = True
    charts: bool = True
    alerts: bool = True
    check_uniqueness: bool = False
    missing_threshold: float = 0.5
    batch_size: int = 24
    include_sensitive: bool = False
    max_missingness_columns: int = 12
    max_duplicate_columns: int = 100
    max_pattern_rows: int = 20
    include_missingness_diagnostics: bool = False
    include_duplicates: bool = False
    include_outliers: bool = False
    rare_category_max_count: int = 5

    def __post_init__(self) -> None:
        positive_options = (
            'max_categories',
            'max_groups',
            'max_chart_groups',
            'max_unique_for_frequency',
            'histogram_bins',
            'batch_size',
            'max_missingness_columns',
            'max_duplicate_columns',
            'max_pattern_rows',
            'rare_category_max_count',
        )
        for name in positive_options:
            if getattr(self, name) < 1:
                raise ValueError(f'{name} must be positive')
        if not 0 <= self.missing_threshold <= 1:
            raise ValueError('missing_threshold must be in [0, 1]')


@dataclass
class VariableProfile:
    """A cached table and optional static figure for a selected column."""

    name: str
    dtype: str
    kind: str
    table: pl.DataFrame
    _chart: Figure | None = field(default=None, repr=False)
    _chart_factory: Callable[[], Figure] | None = field(default=None, repr=False)
    _items_factory: Callable[[], tuple[ReportItem, ...]] | None = field(
        default=None, repr=False,
    )

    def report_items(self) -> tuple[ReportItem, ...]:
        """Reusable summary and distribution components for this variable."""
        if self._items_factory is None:
            raise RuntimeError('Variable profile is not attached to a Profile')
        return self._items_factory()

    def show(self, *, browser: bool | None = None):
        """Preview this variable in a notebook or a local browser."""
        from polarstory.preview import show_report

        report = Report(f'Variable: {self.name}')
        report.add(self)
        return show_report(report, browser=browser)

    @property
    def chart(self) -> Figure | None:
        """Build a static chart only when requested, then reuse it."""
        if self._chart_factory is not None:
            factory = self._chart_factory
            self._chart_factory = None
            self._chart = factory()
        return self._chart


def _identifier_name(name: str) -> bool:
    lower = name.lower()
    return lower in ('id', 'key', 'uuid', 'guid') or lower.endswith(
        ('_id', '_key', '_uuid', '_guid')
    )


class Profile:
    """Defer evaluation and reuse aggregate summaries across profile sections.

    The source must not change during evaluation. `refresh()` builds a new
    profile with empty caches. No raw observations are included in reports.
    """

    def __init__(
            self,
            data: DataInput | DataSource,
            *,
            columns: ColumnSelection | None = None,
            exclude: ColumnSelection | None = None,
            max_columns: int | None = None,
            mode: str = 'standard',
            title: str | None = None,
            options: ProfileOptions | None = None,
            variables: Variables | None = None,
    ) -> None:
        if mode not in ('quick', 'standard', 'full'):
            raise ValueError("mode must be 'quick', 'standard', or 'full'")
        self.source = as_source(data)
        self.options = options or ProfileOptions()
        self.metadata = variables.resolve(self.source) if variables is not None else {}
        self.variables = variables
        self.columns = tuple(
            name for name in select_columns(self.source, columns, exclude, max_columns)
            if self.metadata.get(name, Variable()).kind != 'ignore'
        )
        self.mode = mode
        if self.source.kind == 'parquet':
            label = (self.source.paths[0].name if len(self.source.paths) == 1
                     else f'{len(self.source.paths)} parquet files')
        else:
            label = self.source.label
        self.title = title or f'Profile: {label}'
        self._variables: dict[str, VariableProfile] = {}
        self._overview: pl.DataFrame | None = None
        self._missingness: pl.DataFrame | None = None
        self._alerts: list[quality_alerts.Alert] | None = None
        self._metrics: dict[str, dict[str, object]] | None = None
        self._rows: int | None = None
        self._inferred_kinds: dict[str, str] | None = None
        self._report_items: dict[tuple[str, str], ReportItem] = {}

    def _ensure_metrics(self, names: tuple[str, ...] | None = None) -> None:
        """Compute only missing metrics, so one variable doesn't profile all."""
        if self._metrics is None:
            self._metrics = {}
        required = self.columns if names is None else names
        pending = tuple(name for name in required if name not in self._metrics)
        if pending or self._rows is None:
            self._rows, new = collect_metrics(
                self.source, pending, batch_size=self.options.batch_size,
            )
            self._metrics.update(new)

    def _inferred(self) -> dict[str, str]:
        """Conservatively infer long/free-text columns from a bounded preview.

        A near-unique, long string is never automatically displayed as a
        category value. The preview is used for type choice only, never exported.
        A low-cardinality string remains categorical.
        """
        if self._inferred_kinds is None:
            self._inferred_kinds = {}
            schema = self.source.schema
            names = [name for name in self.columns
                     if self.metadata.get(name, Variable()).kind == 'auto'
                     and not _identifier_name(name)
                     and schema[name] == pl.String
                     and (not self.metadata.get(name, Variable()).sensitive
                          or self.options.include_sensitive)]
            if names:
                # bounded string preview only
                for offset in range(0, len(names), self.options.batch_size):
                    subset = names[offset:offset + self.options.batch_size]
                    preview = self.source.frame.select(subset).head(128).collect()
                    for name in subset:
                        series = preview.get_column(name).drop_nulls()
                        if series.len() < 40:
                            continue
                        lengths = series.str.len_chars()
                        long_text = lengths.median() is not None and lengths.median() >= 80
                        near_unique = series.n_unique() / series.len() >= .95
                        if long_text or near_unique:
                            self._inferred_kinds[name] = 'text'
        return self._inferred_kinds

    def _kind(self, name: str) -> str:
        meta = self.metadata.get(name, Variable())
        dtype = self.source.schema[name]
        if meta.kind != 'auto':
            if meta.kind == 'numeric' and dtype_kind(dtype) != 'numeric':
                raise TypeError(f'{name} cannot be profiled as numeric ({dtype})')
            if meta.kind == 'temporal' and dtype_kind(dtype) != 'temporal':
                raise TypeError(f'{name} cannot be profiled as temporal ({dtype})')
            if meta.kind == 'text' and dtype.base_type() not in (pl.String, pl.Categorical, pl.Enum):
                raise TypeError(f'{name} cannot be profiled as text ({dtype})')
            return meta.kind
        kind = dtype_kind(dtype)
        if kind in ('categorical', 'numeric') and _identifier_name(name):
            return 'identifier'
        return self._inferred().get(name, kind) if kind == 'categorical' else kind

    @property
    def overview(self) -> pl.DataFrame:
        """Return one-row dataset counts and overall null percentage."""
        if self._overview is None:
            self._ensure_metrics()
            n = int(self._rows)
            count = len(self.columns)
            nulls = sum(int(row['null_count']) for row in self._metrics.values())
            self._overview = pl.DataFrame([{
                'rows': n, 'columns': count, 'null_cells': nulls,
                'null_percent': round(100 * nulls / (n * count), 2) if n * count else 0.0,
            }])
        return self._overview

    @property
    def inventory(self) -> pl.DataFrame:
        """Column inventory with semantic type, label and null percentage."""
        self._ensure_metrics()
        total = int(self._rows)
        records = []
        for name in self.columns:
            meta = self.metadata.get(name, Variable())
            info = self._metrics[name]
            records.append({
                'column': name,
                'label': meta.label or name,
                'dtype': str(self.source.schema[name]),
                'type': self._kind(name),
                'null_percent': round(100 * int(info['null_count']) / total, 2)
                if total else 0.0,
            })
        return pl.DataFrame(records, schema={
            'column': pl.String, 'label': pl.String, 'dtype': pl.String,
            'type': pl.String, 'null_percent': pl.Float64,
        })

    @property
    def missingness(self) -> pl.DataFrame:
        """Return per-column null counts and percentages as a polars table."""
        if self._missingness is None:
            self._ensure_metrics()
            n = int(self._rows)
            schema = self.source.schema
            self._missingness = pl.DataFrame(
                [{
                    'column': name,
                    'dtype': str(schema[name]),
                    'null_count': int(self._metrics[name]['null_count']),
                    'null_percent': round(100 * self._metrics[name]['null_count'] / n, 2)
                    if n else 0.0,
                } for name in self.columns],
                schema={'column': pl.String, 'dtype': pl.String,
                        'null_count': pl.Int64, 'null_percent': pl.Float64},
            )
        return self._missingness

    @property
    def alerts(self) -> list[quality_alerts.Alert]:
        """Return descriptive data-quality alerts for the selected variables."""
        if self._alerts is None:
            self._ensure_metrics()
            if self.options.check_uniqueness:
                found = quality_alerts.scan(
                    self.source, columns=self.columns,
                    missing_threshold=self.options.missing_threshold,
                    check_uniqueness=True,
                )
            else:
                found = quality_alerts.from_missingness(
                    self.missingness, rows=int(self._rows),
                    threshold=self.options.missing_threshold,
                )
            found.extend(quality_alerts.from_metrics(self._metrics, rows=int(self._rows)))
            if self.mode == 'full':
                for name in self.columns:
                    meta = self.metadata.get(name, Variable())
                    if meta.sensitive and not self.options.include_sensitive:
                        continue
                    if self._kind(name) != 'categorical':
                        continue
                    variable = self.variable(name)
                    if 'kind' not in variable.table.columns:
                        continue
                    valid = int(self._rows) - int(self._metrics[name]['null_count'])
                    found.extend(quality_alerts.from_frequency(name, variable.table,
                                                               valid_count=valid))
            if self.mode == 'full' and len(self.columns) <= self.options.max_duplicate_columns:
                for row in self.uniqueness().content.iter_rows(named=True):
                    if row['non_null'] >= 25 and row['distinct_percent'] >= 98:
                        found.append(quality_alerts.Alert(
                            row['column'], 'near_unique', 'info',
                            'Approximately all non-null values are distinct',
                            min(1.0, row['distinct_percent'] / 100),
                        ))
            if (self.mode == 'full' or self.options.include_duplicates) and self._can_check_duplicates():
                duplicate_count = int(self.duplicates().content['duplicate_rows'].item())
                if duplicate_count:
                    found.append(quality_alerts.Alert(
                        '(dataset)', 'duplicate_rows', 'info',
                        f'{duplicate_count} excess duplicate rows', duplicate_count,
                    ))
            self._alerts = sorted({(alert.column, alert.code): alert for alert in found}.values(),
                                  key=lambda alert: (alert.column, alert.code))
        return self._alerts

    def _cardinality(self, name: str) -> int:
        """Cache an approximate count of distinct values when needed."""
        self._ensure_metrics((name,))
        result = self._metrics[name]
        if 'approx_unique_count' not in result:
            result['approx_unique_count'] = int(
                self.source.frame.select(pl.col(name).approx_n_unique()).collect().item()
            )
        return int(result['approx_unique_count'])

    def _missing_only(self, name: str) -> pl.DataFrame:
        self._ensure_metrics((name,))
        nulls = int(self._metrics[name]['null_count'])
        n = int(self._rows)
        return pl.DataFrame([{
            'dtype': str(self.source.schema[name]),
            'null_count': nulls,
            'null_percent': round(100 * nulls / n, 2) if n else 0.0,
        }])

    def _decorate_frequency(self, frame: pl.DataFrame, meta: Variable) -> pl.DataFrame:
        if not meta.order and not meta.value_labels:
            return frame
        # apply labels only to real categories
        # preserve special null and other rows
        rows = frame.to_dicts()
        for row in rows:
            if row['kind'] == 'category':
                row['value'] = meta.value_labels.get(row['value'], row['value'])
        if meta.order:
            ranked = {meta.value_labels.get(value, value): i for i, value in enumerate(meta.order)}
            rows.sort(key=lambda row: (
                0 if row['kind'] == 'category' else 1,
                ranked.get(row['value'], len(ranked)),
                row['value'],
            ))
        return pl.DataFrame(rows, schema=frame.schema) if rows else frame

    def variable(self, name: str) -> VariableProfile:
        """Return a cached summary and optional chart for one variable.
        
        Args:
            name: Column name from the selected profile columns.
        
        Returns:
            VariableProfile with reusable report components.
        
        """
        if name not in self.columns:
            raise ValueError(f'Variable {name!r} is not selected for this profile')
        if name not in self._variables:
            dtype = self.source.schema[name]
            meta = self.metadata.get(name, Variable())
            kind = self._kind(name)
            if kind in ('numeric', 'temporal', 'categorical') and (
                    not meta.sensitive or self.options.include_sensitive):
                self._ensure_metrics((name,))
            chart_factory = None
            make_chart = (self.mode in ('standard', 'full') and self.options.charts
                          and (not meta.sensitive or self.options.include_sensitive))
            if meta.sensitive and not self.options.include_sensitive:
                table = self._missing_only(name)
            elif kind == 'numeric':
                row = dict(self._metrics[name])
                row['non_null_count'] = row['rows'] - row['null_count']
                table = pl.DataFrame([row])
                if make_chart:
                    chart_factory = lambda: plots.histogram(
                        self.source, name, bins=self.options.histogram_bins,
                        title=meta.label or name, summary=table,
                    )
            elif kind == 'categorical':
                unique = self._cardinality(name)
                if unique > self.options.max_unique_for_frequency:
                    table = pl.DataFrame([{
                        'metric': 'frequency table',
                        'value': (f'Suppressed: approximately {unique:,} distinct values '
                                  f'(limit {self.options.max_unique_for_frequency:,})'),
                    }])
                else:
                    table = self._decorate_frequency(
                        stats.frequency(self.source, name, top_n=self.options.max_categories,
                                        include_null=self.options.include_null), meta,
                    )
                    if make_chart:
                        chart_factory = lambda: plots.frequency(
                            self.source, name, title=meta.label or name,
                            counts=table,
                        )
            elif kind == 'temporal':
                row = dict(self._metrics[name])
                table = pl.DataFrame([row])
                if make_chart and dtype.base_type() in (pl.Date, pl.Datetime):
                    chart_factory = lambda: plots.temporal(self.source, name, title=meta.label or name)
            elif kind == 'text':
                table = stats.text(self.source, name)
                if make_chart:
                    chart_factory = lambda: plots.text_length(self.source, name, title=meta.label or name)
            else:
                # suppress record-level identifier and complex values
                table = self._missing_only(name)
            self._variables[name] = VariableProfile(
                name, str(dtype), kind, table, _chart_factory=chart_factory,
                _items_factory=lambda name=name: self.variable_items(name),
            )
        return self._variables[name]

    def item(self, name: str, kind: str = 'summary') -> ReportItem:
        """Get one cached reusable component without building a full profile.

        For a variable, choose `summary` (or `frequency` for categorical and
        bounded-cardinality numeric variables)
        and `distribution` (aliases: histogram, timeline, text_length).
        Dataset components are `overview`, `inventory`, `missingness` and
        `alerts` (prefix with `@` to avoid column-name collisions);
        `item('missingness', 'chart')` returns the missingness bar chart.
        Returned components contain only aggregated results and can be added
        directly to a Report. Sensitive columns obey ProfileOptions.
        """
        globals_ = ('overview', 'inventory', 'missingness', 'alerts',
                    'missingness_patterns', 'missingness_associations', 'duplicates', 'uniqueness')
        global_name = (name[1:] if name.startswith('@') and name[1:] in globals_ else
                       name if name in globals_ and name not in self.columns else None)
        if global_name is not None:
            table_kinds = ('summary', 'table')
            chart_kinds = ('chart', 'distribution')
            if global_name in ('missingness', 'missingness_associations'):
                if kind not in table_kinds + chart_kinds:
                    raise ValueError(f'Invalid missingness component: {kind}')
                normalized = 'chart' if kind in chart_kinds else 'table'
            else:
                if kind not in table_kinds:
                    raise ValueError(f'Dataset {global_name} has no {kind} component')
                normalized = 'table'
            cache_key = ('@' + global_name, normalized)
            if cache_key in self._report_items:
                return self._report_items[cache_key]
            labels = {col: meta.label or col for col, meta in self.metadata.items()}
            if global_name == 'overview':
                result = ReportItem('table', 'Dataset overview', self.overview)
            elif global_name == 'inventory':
                result = ReportItem('table', 'Variable inventory', self.inventory)
            elif global_name == 'missingness':
                shown = self.missingness
                if labels:
                    shown = shown.with_columns(pl.col('column').replace_strict(
                        labels, default=pl.col('column')).alias('column'))
                if normalized == 'chart':
                    if not self.options.charts or self.mode == 'quick':
                        raise ValueError('Missingness chart unavailable in this profile')
                    result = ReportItem('chart', 'Null percentages', plots.missingness(rows=shown))
                else:
                    result = ReportItem('table', 'Missing values by column', shown)
            elif global_name == 'alerts':
                found = quality_alerts.to_frame(self.alerts)
                if labels:
                    found = found.with_columns(pl.col('column').replace_strict(
                        labels, default=pl.col('column')))
                result = ReportItem('table', 'Data-quality alerts', found)
            elif global_name == 'missingness_patterns':
                result = ReportItem(
                    'table', 'Common missingness patterns',
                    stats.missingness_patterns(
                        self.source, self.columns,
                        top_n=self.options.max_pattern_rows,
                        max_columns=self.options.max_missingness_columns,
                    ), caption='Nulls only; categories represent combinations of missing columns',
                )
            elif global_name == 'missingness_associations':
                if normalized == 'chart':
                    result = ReportItem(
                        'chart', 'Missingness association heatmap',
                        plots.missingness_associations(
                            self.item('@missingness_associations').content,
                        ), caption='Phi coefficient for null indicators; gray cells are undefined',
                    )
                else:
                    result = ReportItem(
                        'table', 'Associations between missing values',
                        stats.missingness_associations(
                            self.source, self.columns,
                            max_columns=self.options.max_missingness_columns,
                        ), caption='Phi coefficient for null indicators; undefined for constant indicators',
                    )
            elif global_name == 'uniqueness':
                result = ReportItem(
                    'table', 'Variable uniqueness',
                    stats.uniqueness(self.source, self.columns,
                                     max_columns=self.options.max_duplicate_columns),
                    caption='Approximate non-null distinct counts; estimates may be imprecise',
                )
            else:
                result = ReportItem(
                    'table', 'Exact duplicate rows',
                    stats.duplicates(self.source, max_columns=self.options.max_duplicate_columns),
                    caption='Duplicate rows are excess repeats, not necessarily data errors',
                )
            result = self._with_recipe(result, '@' + global_name, normalized)
            self._report_items[cache_key] = result
            return result

        if name not in self.columns:
            raise ValueError(f'Variable {name!r} is not selected for this profile')
        summary_aliases = {'summary', 'table', 'frequency', 'outliers',
                           'category_diagnostics'}
        chart_aliases = {'distribution', 'chart', 'histogram', 'timeline', 'text_length'}
        if kind not in summary_aliases | chart_aliases:
            raise ValueError(f'Unknown component kind: {kind}')
        normalized = 'summary' if kind in summary_aliases else 'distribution'
        var = self.variable(name)
        meta = self.metadata.get(name, Variable())
        label = meta.label or name
        if kind == 'frequency' and var.kind not in ('categorical', 'numeric'):
            raise ValueError(f'{name} cannot be shown as a frequency table')
        if kind == 'histogram' and var.kind != 'numeric':
            raise ValueError(f'{name} has no numeric histogram')
        if kind == 'timeline' and var.kind != 'temporal':
            raise ValueError(f'{name} has no temporal timeline')
        if kind == 'text_length' and var.kind != 'text':
            raise ValueError(f'{name} has no text-length chart')
        if kind == 'category_diagnostics':
            if var.kind != 'categorical':
                raise ValueError(f'{name} has no categorical diagnostic summary')
            if meta.sensitive and not self.options.include_sensitive:
                raise ValueError(f'Category values suppressed for sensitive column {name}')
            cache_key = (name, 'category_diagnostics')
            if cache_key not in self._report_items:
                result = ReportItem(
                    'table', f'{label} — category diagnostics',
                    stats.categorical_diagnostics(
                        self.source, name,
                        rare_at_most=self.options.rare_category_max_count,
                        max_unique=self.options.max_unique_for_frequency,
                    ), caption='Rare categories are those with counts at or below the configured threshold',
                )
                self._report_items[cache_key] = self._with_recipe(result, name, 'category_diagnostics')
            return self._report_items[cache_key]
        if kind == 'outliers':
            if var.kind != 'numeric':
                raise ValueError(f'{name} has no numeric outlier summary')
            if meta.sensitive and not self.options.include_sensitive:
                raise ValueError(f'Outlier values suppressed for sensitive column {name}')
            cache_key = (name, 'outliers')
            if cache_key not in self._report_items:
                result = ReportItem(
                    'table', f'{label} — IQR outlier summary',
                    stats.outliers(self.source, name, summary=var.table),
                    caption='Descriptive IQR rule; flagged observations are not necessarily errors',
                )
                self._report_items[cache_key] = self._with_recipe(result, name, 'outliers')
            return self._report_items[cache_key]
        if kind == 'frequency' and var.kind == 'numeric':
            cache_key = (name, 'frequency')
            if cache_key not in self._report_items:
                if meta.sensitive and not self.options.include_sensitive:
                    raise ValueError(f'Frequency values suppressed for sensitive column {name}')
                self._ensure_metrics((name,))
                unique = self._cardinality(name)
                if unique > self.options.max_unique_for_frequency:
                    raise ValueError(
                        f'{name} has approximately {unique:,} distinct values; '
                        f'frequency limit is {self.options.max_unique_for_frequency:,}. '
                        'Use histogram() for a numeric distribution.'
                    )
                counts = stats.frequency(
                    self.source, name, top_n=self.options.max_categories,
                    include_null=self.options.include_null,
                )
                item = ReportItem('table', f'{label} — frequency', counts,
                                  caption=f'polars dtype: {var.dtype}')
                self._report_items[cache_key] = self._with_recipe(item, name, 'frequency')
            return self._report_items[cache_key]
        cache_key = (name, normalized)
        if cache_key in self._report_items:
            return self._report_items[cache_key]
        if normalized == 'distribution':
            if var.chart is None:
                raise ValueError(f'No distribution chart available for {name}')
            result = ReportItem('chart', f'{label} — distribution', var.chart)
        else:
            shown = var.table
            if var.kind in ('numeric', 'temporal', 'text') or (meta.sensitive and not self.options.include_sensitive):
                values = var.table.row(0, named=True)
                shown = pl.DataFrame(
                    [{'metric': key, 'value': str(value) if value is not None else None}
                     for key, value in values.items()],
                    schema={'metric': pl.String, 'value': pl.String},
                )
            caption = meta.description or f'polars dtype: {var.dtype}'
            if var.kind == 'text' and name in self._inferred():
                caption += ' · Text classification based on a preview (up to 128 rows)'
            if meta.sensitive and not self.options.include_sensitive:
                caption += ' · Sensitive variable: distribution suppressed'
            result = ReportItem('table', f'{label} — {var.kind} summary', shown, caption=caption)
        result = self._with_recipe(result, name, normalized)
        self._report_items[cache_key] = result
        return result

    def variable_items(self, name: str) -> tuple[ReportItem, ...]:
        """Retrieve the default reusable components for one variable."""
        result = [self.summary(name)]
        var = self.variable(name)
        if var._chart_factory is not None or var._chart is not None:
            result.append(self.distribution(name))
        return tuple(result)

    def show(self, name: str | None = None, *, browser: bool | None = None):
        """Preview one variable, or the whole profile when name is omitted."""
        from polarstory.preview import show_report

        if name is None:
            report = self.to_report()
        else:
            meta = self.metadata.get(name, Variable())
            report = Report(meta.label or name)
            report.add(self.variable(name))
        return show_report(report, browser=browser)

    def explore(self, *, report: Report | None = None, show: bool = True):
        """Open the optional notebook explorer or return its controller."""
        from polarstory.explorer import Explorer

        explorer = Explorer(self, report=report)
        if show:
            explorer.show()
        return explorer

    def summary(self, name: str) -> ReportItem:
        """Return the reusable descriptive table for one variable."""
        return self.item(name, 'summary')

    def frequency(self, name: str) -> ReportItem:
        """Return category counts, including for discrete numeric variables.

        High-cardinality numeric variables are refused rather than grouped
        without bounds. Prefer `histogram()` for continuous measurements.
        """
        return self.item(name, 'frequency')

    def distribution(self, name: str) -> ReportItem:
        """Return the default static distribution chart for a variable."""
        return self.item(name, 'distribution')

    def histogram(self, name: str) -> ReportItem:
        """Return a numeric histogram as a reusable chart component."""
        return self.item(name, 'histogram')

    def timeline(self, name: str) -> ReportItem:
        """Return a Date/Datetime timeline as a reusable chart component."""
        return self.item(name, 'timeline')

    def text_length(self, name: str) -> ReportItem:
        """Return a text-length distribution chart."""
        return self.item(name, 'text_length')

    def category_diagnostics(self, name: str) -> ReportItem:
        """Return rare-category and dominance statistics for one variable."""
        return self.item(name, 'category_diagnostics')

    def outliers(self, name: str) -> ReportItem:
        '''Return an IQR outlier-count table for a numeric variable.'''
        return self.item(name, 'outliers')

    def missingness_patterns(self) -> ReportItem:
        '''Return bounded combinations of null indicators across variables.'''
        return self.item('@missingness_patterns')

    def missingness_associations(self) -> ReportItem:
        '''Return pairwise phi coefficients between null indicators.'''
        return self.item('@missingness_associations')

    def missingness_associations_chart(self) -> ReportItem:
        """Return a static heatmap of missingness phi coefficients."""
        return self.item('@missingness_associations', 'chart')

    def uniqueness(self) -> ReportItem:
        """Return approximate distinct counts for selected variables."""
        return self.item('@uniqueness')

    def duplicates(self) -> ReportItem:
        '''Return opt-in exact duplicate-row counts for the source.'''
        return self.item('@duplicates')

    def missingness_chart(self) -> ReportItem:
        """Return the aggregate missingness chart for selected variables."""
        return self.item('@missingness', 'chart')

    def _with_recipe(self, item: ReportItem, name: str, kind: str) -> ReportItem:
        """Attach a regenerable recipe only when the source is file-backed."""
        if self.source.kind != 'parquet':
            return item
        return replace(item, recipe={
            'type': 'profile_item', 'profile': self.to_spec(),
            'name': name, 'kind': kind,
        })

    def _include_extended(self) -> bool:
        return self.mode == 'full' or self.options.include_missingness_diagnostics

    def _can_check_duplicates(self) -> bool:
        return (len(self.source.schema) <= self.options.max_duplicate_columns and
                all(dtype_kind(dtype) != 'other' for dtype in self.source.schema.values()))

    def _diagnostic_items(self) -> list[ReportItem]:
        """Include expensive checks only when requested and within limits."""
        found: list[ReportItem] = []
        if self._include_extended():
            if len(self.columns) <= self.options.max_missingness_columns:
                found.extend((self.missingness_patterns(), self.missingness_associations()))
                if self.options.charts and self.mode != 'quick':
                    found.append(self.missingness_associations_chart())
            else:
                message = (f'{len(self.columns)} variables exceed the configured limit of '
                           f'{self.options.max_missingness_columns}; select fewer columns')
                found.append(ReportItem(
                    'text', 'Missingness diagnostics omitted', message,
                    recipe={'type': 'text', 'title': 'Missingness diagnostics omitted',
                            'content': message},
                ))
        if self.mode == 'full' and len(self.columns) <= self.options.max_duplicate_columns:
            found.append(self.uniqueness())
        if self.mode == 'full' or self.options.include_duplicates:
            if self._can_check_duplicates():
                found.append(self.duplicates())
            else:
                message = ('Exact duplicate checks require flat scalar columns and at most '
                           f'{self.options.max_duplicate_columns} source columns')
                found.append(ReportItem(
                    'text', 'Duplicate check omitted', message,
                    recipe={'type': 'text', 'title': 'Duplicate check omitted',
                            'content': message},
                ))
        return found

    def items(self) -> list[ReportItem]:
        """All profile components, in deterministic display order."""
        result = [self.item('@overview'), self.item('@inventory'), self.item('@missingness')]
        if self.mode != 'quick' and self.options.charts and self.columns:
            result.append(self.item('@missingness', 'chart'))
        if self.options.alerts and self.columns and self.alerts:
            result.append(self.item('@alerts'))
        result.extend(self._diagnostic_items())
        for name in self.columns:
            result.append(self.summary(name))
            candidate = self.variable(name)
            if candidate._chart_factory is not None or candidate._chart is not None:
                result.append(self.distribution(name))
            if self.mode == 'full' and candidate.kind == 'categorical':
                meta = self.metadata.get(name, Variable())
                if (not meta.sensitive or self.options.include_sensitive) and (
                        self._cardinality(name) <= self.options.max_unique_for_frequency):
                    result.append(self.category_diagnostics(name))
            if (self.mode == 'full' or self.options.include_outliers) and candidate.kind == 'numeric':
                meta = self.metadata.get(name, Variable())
                if not meta.sensitive or self.options.include_sensitive:
                    result.append(self.outliers(name))
        return result

    def to_report(self) -> Report:
        """Group automatic profiling outputs into navigable sections."""
        report = Report(self.title)
        report.add(self.item('@overview'))
        report.add(self.item('@inventory'))
        report.add(self.item('@missingness'))
        if self.mode != 'quick' and self.options.charts and self.columns:
            report.add(self.item('@missingness', 'chart'))
        if self.options.alerts and self.columns and self.alerts:
            report.add(self.item('@alerts'))
        diagnostics = self._diagnostic_items()
        if diagnostics:
            with report.section('Dataset diagnostics'):
                for item in diagnostics:
                    report.add(item)
        for name in self.columns:
            meta = self.metadata.get(name, Variable())
            label = meta.label or name
            with report.section(label if label == name else f'{label} ({name})'):
                report.add(self.summary(name))
                candidate = self.variable(name)
                if candidate._chart_factory is not None or candidate._chart is not None:
                    report.add(self.distribution(name))
                if self.mode == 'full' and candidate.kind == 'categorical':
                    if (not meta.sensitive or self.options.include_sensitive) and (
                            self._cardinality(name) <= self.options.max_unique_for_frequency):
                        report.add(self.category_diagnostics(name))
                if (self.mode == 'full' or self.options.include_outliers) and candidate.kind == 'numeric':
                    if not meta.sensitive or self.options.include_sensitive:
                        report.add(self.outliers(name))
        return report

    def to_spec(self, *, base_dir: str | Path | None = None) -> dict:
        """Serializable **recomputable** specification for a parquet profile.

        Only file-backed profiles are reproducible from JSON alone; an in-memory
        DataFrame or an arbitrary LazyFrame must be regenerated by Python code.
        Resolved columns and metadata are saved (not polars selector objects).
        The spec does not contain observations or cached summary results.
        """
        if self.source.kind != 'parquet':
            raise ValueError('Only file-backed parquet profiles can be saved as reusable specs')
        base = Path(base_dir).resolve() if base_dir is not None else None
        paths = []
        for source_path in self.source.paths:
            if base is None:
                paths.append(str(source_path))
            else:
                try:
                    paths.append(os.path.relpath(source_path, base))
                except ValueError:  # different Windows drives
                    paths.append(str(source_path))
        return {
            'format': 'polarstory.profile/v1',
            'sources': paths,
            'title': self.title,
            'columns': list(self.columns),
            'mode': self.mode,
            'options': asdict(self.options),
            'variables': {name: asdict(meta) for name, meta in self.metadata.items()},
        }

    def write_spec(self, path: str | Path) -> Path:
        """Save a JSON recipe; file paths are relative to the spec directory."""
        destination = Path(path).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(self.to_spec(base_dir=destination.parent),
                                          indent=2, ensure_ascii=False) + '\n', encoding='utf8')
        return destination

    def to_html(self) -> str:
        """Render the complete static profile as a standalone HTML string."""
        return self.to_report().to_html()

    def write_html(self, path: str | Path) -> Path:
        """Write a standalone, print-friendly HTML profile.
        
        Args:
            path: Destination for the HTML document.
        
        Returns:
            Path to the written report.
        
        """
        return self.to_report().write_html(path)

    def refresh(self) -> Profile:
        """Build a new profile snapshot with empty calculation caches."""
        return Profile(self.source, columns=self.columns, mode=self.mode, title=self.title,
                       options=self.options, variables=self.variables)


def profile(
        data: DataInput | DataSource,
        *,
        columns: ColumnSelection | None = None,
        exclude: ColumnSelection | None = None,
        max_columns: int | None = None,
        mode: str = 'standard',
        title: str | None = None,
        options: ProfileOptions | None = None,
        variables: Variables | None = None,
) -> Profile:
    """Create an automatically profiled polars DataFrame/LazyFrame/parquet file."""
    return Profile(data, columns=columns, exclude=exclude, max_columns=max_columns,
                   mode=mode, title=title, options=options, variables=variables)


def _profile_from_definition(data: dict, *, base_dir: Path) -> Profile:
    """Internal validated recipe reader, also used for curated reports."""
    if not isinstance(data, dict) or data.get('format') != 'polarstory.profile/v1':
        raise ValueError('Unsupported polarstory profile specification')
    sources = data.get('sources')
    if not isinstance(sources, list) or not sources or not all(isinstance(s, str) for s in sources):
        raise ValueError('Profile specification must contain file paths')
    paths = tuple((base_dir / item).resolve() for item in sources)
    if any(not item.is_file() or item.suffix.lower() != '.parquet' for item in paths):
        raise FileNotFoundError('A parquet source from the profile specification was not found')
    source = as_source(paths[0]) if len(paths) == 1 else DataSource(
        pl.scan_parquet([str(p) for p in paths]), 'Spec: ' + base_dir.name,
        'parquet', paths=paths,
    )
    config = Variables()
    raw_vars = data.get('variables', {})
    if not isinstance(raw_vars, dict):
        raise ValueError('Invalid variable configuration in profile spec')
    for name, metadata in raw_vars.items():
        if not isinstance(metadata, dict):
            raise ValueError(f'Invalid variable configuration: {name}')
        config.set(name, **metadata)
    return profile(
        source,
        columns=data.get('columns'),
        mode=data.get('mode', 'standard'),
        title=data.get('title'),
        options=ProfileOptions(**data.get('options', {})),
        variables=config,
    )


def profile_from_spec(path: str | Path) -> Profile:
    """Recompute a parquet profile from a previously saved JSON recipe.

    This performs fresh scans; input files must still exist and have compatible
    schemas. This intentionally does not deserialize arbitrary Python objects.
    """
    spec_path = Path(path).expanduser().resolve()
    data = json.loads(spec_path.read_text(encoding='utf8'))
    return _profile_from_definition(data, base_dir=spec_path.parent)
