"""Descriptive comparison of two polars datasets or parquet sources.

Comparisons are aggregate-only and do not imply statistical significance.
No source rows are embedded in generated reports. Columns may be excluded
when they contain identifying or otherwise sensitive values.
"""

from __future__ import annotations

from functools import cached_property
from pathlib import Path
from typing import Sequence

import polars as pl

from polarstory.columns import dtype_kind
from polarstory.metrics import collect_metrics
from polarstory.report import Report
from polarstory.source import DataInput, DataSource, as_source

_SCHEMA = {
    'column': pl.String,
    'baseline_dtype': pl.String,
    'current_dtype': pl.String,
    'status': pl.String,
}
_MISSING = {
    'column': pl.String,
    'baseline_nulls': pl.Int64,
    'current_nulls': pl.Int64,
    'baseline_percent': pl.Float64,
    'current_percent': pl.Float64,
    'change_pp': pl.Float64,
}
_NUMERIC = {
    'column': pl.String,
    'metric': pl.String,
    'baseline': pl.Float64,
    'current': pl.Float64,
    'difference': pl.Float64,
}
_CATEGORICAL = {
    'column': pl.String,
    'value': pl.String,
    'kind': pl.String,
    'baseline_count': pl.Int64,
    'current_count': pl.Int64,
    'baseline_percent': pl.Float64,
    'current_percent': pl.Float64,
    'change_pp': pl.Float64,
}
_SKIPPED = {'column': pl.String, 'reason': pl.String}

_NUMERIC_OR_CAT = 'numeric', 'categorical'


def _identifier_name(name: str) -> bool:
    name = name.lower()
    return name in ('id', 'key', 'uuid', 'guid') or name.endswith(
        ('_id', '_key', '_uuid', '_guid')
    )


def _percent(count: int, total: int) -> float:
    return 100 * count / total if total else 0.0


def _numeric(value: object) -> float | None:
    return float(value) if value is not None else None


class DatasetComparison:
    """Lazy, reusable descriptive comparison of two dataset snapshots.

    Both sources must remain unchanged during evaluation. Percentages use
    all rows in their respective dataset. Numeric summaries omit nonfinite
    values, consistent with ``polarstory.stats.numeric``. The ``change_pp``
    column is current minus baseline, in percentage points.

    High-cardinality categorical and identifier-like columns are omitted from
    value-level comparisons by default, but remain in the schema inventory.
    """

    def __init__(
            self,
            baseline: DataInput | DataSource,
            current: DataInput | DataSource,
            *,
            labels: tuple[str, str] = ('Baseline', 'Current'),
            columns: Sequence[str] | None = None,
            exclude: Sequence[str] = (),
            categorical_columns: Sequence[str] = (),
            max_columns: int = 100,
            max_categories: int = 15,
            max_unique_for_frequency: int = 1000,
            title: str = 'Dataset comparison',
    ) -> None:
        if len(labels) != 2 or any(not isinstance(label, str) or not label.strip()
                                   for label in labels):
            raise ValueError('labels must contain two nonempty strings')
        for key, value in (
                ('max_columns', max_columns),
                ('max_categories', max_categories),
                ('max_unique_for_frequency', max_unique_for_frequency),
        ):
            if value < 1:
                raise ValueError(f'{key} must be positive')
        self.baseline = as_source(baseline)
        self.current = as_source(current)
        self.labels = labels
        self.title = title
        self.max_categories = max_categories
        self.max_unique_for_frequency = max_unique_for_frequency
        available = list(dict.fromkeys([*self.baseline.schema.names(),
                                        *self.current.schema.names()]))
        available_set = set(available)
        omitted = set(exclude)
        if columns is None:
            selected = [name for name in available if name not in omitted]
        else:
            selected = list(dict.fromkeys(columns))
            unknown = [name for name in selected if name not in available_set]
            if unknown:
                raise ValueError(f'Unknown comparison columns: {unknown}')
            selected = [name for name in selected if name not in omitted]
        if len(selected) > max_columns:
            raise ValueError(
                f'Comparison has {len(selected)} columns; max_columns={max_columns}. '
                'Select columns or raise the limit explicitly.'
            )
        self.columns = tuple(selected)
        forced = set(categorical_columns)
        if forced - set(self.columns):
            raise ValueError(f'Unknown categorical_columns: {sorted(forced - set(self.columns))}')
        for name in forced:
            for source in (self.baseline, self.current):
                if name in source.schema and dtype_kind(source.schema[name]) not in _NUMERIC_OR_CAT:
                    raise TypeError(f'{name} cannot be compared as categorical')
        self.categorical_columns = frozenset(forced)

    @cached_property
    def _metrics(self) -> tuple[int, dict, int, dict]:
        baseline_names = tuple(n for n in self.columns if n in self.baseline.schema)
        current_names = tuple(n for n in self.columns if n in self.current.schema)
        n1, m1 = collect_metrics(self.baseline, baseline_names)
        n2, m2 = collect_metrics(self.current, current_names)
        return int(n1), m1, int(n2), m2

    @property
    def overview(self) -> pl.DataFrame:
        """Row and column counts for each dataset, including differences."""
        a, _, b, _ = self._metrics
        return pl.DataFrame([
            {'metric': 'rows', 'baseline': a, 'current': b, 'difference': b - a},
            {'metric': 'columns',
             'baseline': len(self.baseline.schema),
             'current': len(self.current.schema),
             'difference': len(self.current.schema) - len(self.baseline.schema),
             },
        ])

    @cached_property
    def schema_changes(self) -> pl.DataFrame:
        """All selected columns, with added/removed/type-changed status."""
        rows = []
        for name in self.columns:
            dtype1 = self.baseline.schema.get(name)
            dtype2 = self.current.schema.get(name)
            status = ('added' if dtype1 is None else 'removed' if dtype2 is None
            else 'type_changed' if dtype1 != dtype2 else 'unchanged')
            rows.append({
                'column': name,
                'baseline_dtype': str(dtype1) if dtype1 is not None else None,
                'current_dtype': str(dtype2) if dtype2 is not None else None,
                'status': status,
            })
        return pl.DataFrame(rows, schema=_SCHEMA)

    @cached_property
    def missingness(self) -> pl.DataFrame:
        """Exact null counts and percentage-point differences by variable."""
        a, ma, b, mb = self._metrics
        rows = []
        for name in self.columns:
            na = int(ma[name]['null_count']) if name in ma else None
            nb = int(mb[name]['null_count']) if name in mb else None
            pa = _percent(na, a) if na is not None else None
            pb = _percent(nb, b) if nb is not None else None
            rows.append({
                'column': name,
                'baseline_nulls': na,
                'current_nulls': nb,
                'baseline_percent': pa,
                'current_percent': pb,
                'change_pp': pb - pa if pa is not None and pb is not None else None,
            })
        return pl.DataFrame(rows, schema=_MISSING)

    def _compatible(self, name: str) -> str | None:
        if _identifier_name(name):
            return None
        d1 = self.baseline.schema.get(name)
        d2 = self.current.schema.get(name)
        if d1 is None or d2 is None:
            return None
        k1 = dtype_kind(d1)
        k2 = dtype_kind(d2)
        if name in self.categorical_columns and k1 in _NUMERIC_OR_CAT and k2 in _NUMERIC_OR_CAT:
            return 'categorical'
        if k1 == k2 and k1 in _NUMERIC_OR_CAT:
            return k1
        return None

    @cached_property
    def numeric(self) -> pl.DataFrame:
        """Numeric summary differences; nonfinite values are excluded."""
        _, ma, _, mb = self._metrics
        rows = []
        for name in self.columns:
            if self._compatible(name) != 'numeric':
                continue
            for metric in ('finite_count', 'mean', 'std', 'median', 'q25', 'q75', 'min', 'max'):
                av, bv = _numeric(ma[name].get(metric)), _numeric(mb[name].get(metric))
                rows.append({'column': name, 'metric': metric, 'baseline': av, 'current': bv,
                             'difference': bv - av if av is not None and bv is not None else None})
        return pl.DataFrame(rows, schema=_NUMERIC)

    def _top_values(self, source: DataSource, name: str) -> dict[object, int]:
        result = (
            source.frame.select(pl.col(name))
            .filter(pl.col(name).is_not_null())
            .group_by(name).agg(pl.len().alias('_n'))
            .sort('_n', descending=True)
            .head(self.max_categories)
            .collect()
        )
        return {row[name]: int(row['_n']) for row in result.iter_rows(named=True)}

    def _counts(self, source: DataSource, name: str, values: list[object]) -> dict[object, int]:
        if not values:
            return {}
        result = (
            source.frame
            .select(pl.col(name))
            .filter(pl.col(name).is_in(values))
            .group_by(name)
            .agg(pl.len().alias('_n'))
            .collect()
        )
        return {row[name]: int(row['_n']) for row in result.iter_rows(named=True)}

    @cached_property
    def _categorical_results(self) -> tuple[pl.DataFrame, pl.DataFrame]:
        a, ma, b, mb = self._metrics
        rows, skipped = [], []
        for name in self.columns:
            kind = self._compatible(name)
            if kind is None:
                d1 = self.baseline.schema.get(name)
                d2 = self.current.schema.get(name)
                if _identifier_name(name):
                    reason = 'identifier-like name'
                elif d1 is None or d2 is None:
                    reason = 'column not present in both datasets'
                elif dtype_kind(d1) != dtype_kind(d2):
                    reason = 'incompatible variable types'
                else:
                    reason = 'unsupported variable type'
                skipped.append({'column': name, 'reason': reason})
                continue
            if kind != 'categorical':
                continue
            unique_a = ma[name].get('approx_unique_count')
            unique_b = mb[name].get('approx_unique_count')
            # numeric-coded categories need a separate cardinality check
            if unique_a is None or unique_b is None:
                unique_a = int(self.baseline.frame.select(
                    pl.col(name).approx_n_unique()).collect().item())
                unique_b = int(self.current.frame.select(
                    pl.col(name).approx_n_unique()).collect().item())
            if max(int(unique_a), int(unique_b)) > self.max_unique_for_frequency:
                skipped.append({'column': name, 'reason': 'high cardinality'})
                continue
            top_a = self._top_values(self.baseline, name)
            top_b = self._top_values(self.current, name)
            union = list(dict.fromkeys([*top_a, *top_b]))
            union.sort(key=lambda x: (-(top_a.get(x, 0) + top_b.get(x, 0)), repr(x)))
            selected = union[:self.max_categories]
            counts_a = self._counts(self.baseline, name, selected)
            counts_b = self._counts(self.current, name, selected)
            null_a = int(ma[name]['null_count'])
            null_b = int(mb[name]['null_count'])

            def append(value: str, kind: str, na: int, nb: int) -> None:
                pa, pb = _percent(na, a), _percent(nb, b)
                rows.append({'column': name, 'value': value, 'kind': kind,
                             'baseline_count': na, 'current_count': nb,
                             'baseline_percent': pa, 'current_percent': pb,
                             'change_pp': pb - pa})

            for value in selected:
                append(str(value), 'category', counts_a.get(value, 0), counts_b.get(value, 0))
            other_a = a - null_a - sum(counts_a.values())
            other_b = b - null_b - sum(counts_b.values())
            if other_a or other_b:
                append('(other categories)', 'other', other_a, other_b)
            if null_a or null_b:
                append('(null)', 'null', null_a, null_b)
        return (pl.DataFrame(rows, schema=_CATEGORICAL),
                pl.DataFrame(skipped, schema=_SKIPPED))

    @property
    def categorical(self) -> pl.DataFrame:
        """Bounded frequency comparisons with an explicit Other remainder."""
        return self._categorical_results[0]

    @property
    def skipped(self) -> pl.DataFrame:
        """Variables omitted from value-level or numerical comparison."""
        return self._categorical_results[1]

    def to_report(self) -> Report:
        """Create a curated, standalone HTML report using aggregated results."""
        report = Report(self.title, subtitle=f'{self.labels[0]} vs {self.labels[1]}')
        report.add_text(
            'Descriptive comparison only. Differences are current minus baseline. '
            'Counts and percentages refer to rows, not necessarily unique patients. '
            'Missingness includes nulls; NaNs remain distinct. Review aggregate '
            'values for disclosure risks before sharing.'
        )
        with report.section('Dataset overview'):
            report.add_table(self.overview, title='Dataset size')
            report.add_table(self.schema_changes, title='Schema Inventory')
            report.add_table(self.missingness, title='Missingness Comparison',
                             caption='Percentage-point change = current minus baseline')
        if self.numeric.height:
            with report.section('Numeric variables'):
                report.add_table(self.numeric, title='Descriptive Numeric Changes',
                                 notes='Numeric calculations exclude NaN and infinity')
        if self.categorical.height:
            with report.section('Categorical variables'):
                report.add_table(self.categorical, title='Category Distribution Changes',
                                 notes='Limited to common categories; other contains the remainder')
        if self.skipped.height:
            with report.section('Omitted Comparisons'):
                report.add_table(self.skipped, title='Skipped variable comparisons')
        return report

    def to_html(self) -> str:
        """Render a complete standalone HTML report as a string."""
        return self.to_report().to_html()

    def write_html(self, path: str | Path) -> Path:
        """Write an offline, printable HTML comparison report."""
        return self.to_report().write_html(path)


def compare(
        baseline: DataInput | DataSource,
        current: DataInput | DataSource,
        *,
        labels: tuple[str, str] = ('Baseline', 'Current'),
        columns: Sequence[str] | None = None,
        exclude: Sequence[str] = (),
        categorical_columns: Sequence[str] = (),
        max_columns: int = 100,
        max_categories: int = 15,
        max_unique_for_frequency: int = 1000,
        title: str = 'Dataset Comparison',
) -> DatasetComparison:
    """Compare two DataFrames, LazyFrames, or parquet datasets descriptively.

    Args:
        baseline: Reference dataset, e.g. an earlier research extract.
        current: Dataset to compare against the baseline.
        labels: Human-readable labels for both datasets.
        columns: Columns to compare; defaults to the union of both schemas.
        exclude: Names to omit from comparison, including sensitive columns.
        categorical_columns: Numeric codes to treat as categorical values.
        max_columns: Maximum number of selected columns.
        max_categories: Maximum number of displayed categories per variable.
        max_unique_for_frequency: Estimated cardinality ceiling for value comparisons.
        title: Title for the standalone HTML report.

    Returns:
        A lazy ``DatasetComparison`` with reusable polars result tables.

    No patient-level join, p-values, or raw record samples are generated.
    """
    return DatasetComparison(
        baseline, current, labels=labels, columns=columns, exclude=exclude,
        categorical_columns=categorical_columns, max_columns=max_columns,
        max_categories=max_categories, max_unique_for_frequency=max_unique_for_frequency,
        title=title,
    )
