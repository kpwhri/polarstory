"""Optional notebook exploration built on reusable static report components."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import replace
from html import escape
from typing import TYPE_CHECKING, Literal, Sequence

import polars as pl

from polarstory import plots, stats
from polarstory.report import Report, ReportItem
from polarstory.variables import Variable

if TYPE_CHECKING:
    from polarstory.source import DataInput, DataSource
    from polarstory.profile import Profile, ProfileOptions
    from polarstory.variables import Variables

View = Literal['all', 'summary', 'distribution', 'frequency', 'missingness', 'outliers']


class Explorer:
    """Select, preview and collect single-variable exploratory summaries.

    Statistics remain in polars. Only aggregated results and static figures
    are passed to the notebook interface. The optional widgets import is
    deferred until `show()` is invoked.
    """

    def __init__(self, profile: Profile, *, report: Report | None = None) -> None:
        self.profile = profile
        self.report = report if report is not None else Report('Selected findings')
        self.widget = None
        self._cache: OrderedDict[tuple, tuple[ReportItem, ...]] = OrderedDict()
        self._group_cache: dict[str, tuple[object, ...]] = {}

    def _group_values(self, by: str) -> list[object]:
        """Return bounded, distinct group values in deterministic order."""
        if by in self._group_cache:
            return list(self._group_cache[by])
        limit = self.profile.options.max_groups
        values = (
            self.profile.source.frame.select(pl.col(by)).unique()
            .limit(limit + 1).collect().get_column(by).to_list()
        )
        if len(values) > limit:
            raise ValueError(
                f'Grouping variable {by!r} has at least {len(values)} groups; '
                f'the summary-table limit is {limit}. Filter the source or ' 'increase ProfileOptions(max_groups=...).'
            )
        ordered = tuple(sorted(values, key=lambda value: (value is not None, str(value))))
        self._group_cache[by] = ordered
        return list(ordered)

    def _chosen_groups(self, by: str, groups: Sequence[object] | None) -> tuple[object, ...]:
        available = self._group_values(by)
        if groups is None:
            return tuple(available)
        chosen = tuple(groups)
        if not chosen:
            raise ValueError('Select at least one group')
        if any(value not in available for value in chosen):
            raise ValueError(f'Selected groups are not present in {by!r}')
        if len(set(chosen)) != len(chosen):
            raise ValueError('Group selections must be unique')
        return chosen

    def _group_frame(self, by: str, groups: tuple[object, ...]) -> pl.LazyFrame:
        selected = [value for value in groups if value is not None]
        predicate = pl.col(by).is_in(selected) if selected else pl.lit(False)
        if None in groups:
            predicate = predicate | pl.col(by).is_null()
        return self.profile.source.frame.filter(predicate)

    def _validate(self, name: str, by: str | None, view: str) -> str:
        if name not in self.profile.columns:
            raise ValueError(f'Variable {name!r} is not selected for this profile')
        if view not in ('all', 'summary', 'distribution', 'frequency', 'missingness', 'outliers'):
            raise ValueError(f'Unknown exploration view: {view}')
        kind = self.profile._kind(name)
        if view == 'outliers' and kind != 'numeric':
            raise ValueError('IQR outlier exploration requires a numeric variable')
        if by is None:
            return kind
        if view == 'outliers':
            raise ValueError('Stratified outlier exploration is not supported')
        if by not in self.profile.columns or by == name:
            raise ValueError('Stratification requires a different, selected variable')
        if self.profile._kind(by) != 'categorical':
            raise ValueError('Stratification requires a categorical grouping variable')
        meta = self.profile.metadata.get(by, Variable())
        if meta.sensitive and not self.profile.options.include_sensitive:
            raise ValueError('Cannot stratify by a sensitive variable')
        if kind not in ('numeric', 'categorical') and view != 'missingness':
            raise ValueError(f'Stratified {kind} summaries are not supported')
        return kind

    def _recipe(self, item: ReportItem, name: str, view: str, *, by: str | None,
                bins: int | None, top_n: int | None, denominator: str,
                groups: tuple[object, ...] | None = None) -> ReportItem:
        if self.profile.source.kind != 'parquet':
            return item
        return replace(item, recipe={
            'type': 'explorer_view', 'profile': self.profile.to_spec(),
            'name': name, 'view': view, 'by': by, 'bins': bins,
            'top_n': top_n, 'denominator': denominator, 'groups': groups,
        })

    def _missingness(self, name: str, by: str | None,
                     groups: tuple[object, ...] | None = None) -> ReportItem:
        label = self.profile.metadata.get(name, Variable()).label or name
        if by is None:
            return ReportItem('table', f'{label} — missingness', self.profile._missing_only(name))
        assert groups is not None
        frame = (
            self._group_frame(by, groups)
            .group_by(by)
            .agg(
                pl.len().alias('rows'),
                pl.col(name).is_null().sum().alias('null_count'),
            )
            .with_columns(
                (pl.col('null_count') / pl.col('rows') * 100).round(2).alias('null_percent'),
            )
            .collect()
            .with_columns(
                pl.col(by).cast(pl.String).fill_null('(null)'),
            )
            .sort(by)
        )
        return ReportItem('table', f'{label} — missingness by {by}', frame)

    def _unstratified(
            self, name: str, view: str, kind: str, *, bins: int | None, top_n: int | None, denominator: str,
    ) -> tuple[ReportItem, ...]:
        profile = self.profile
        meta = profile.metadata.get(name, Variable())
        label = meta.label or name
        suppressed = meta.sensitive and not profile.options.include_sensitive
        if view == 'outliers':
            return (profile.outliers(name),)
        if view == 'missingness':
            return (self._recipe(self._missingness(name, None), name, 'missingness',
                                 by=None, bins=bins, top_n=top_n, denominator=denominator),)
        if view == 'frequency' and kind not in ('numeric', 'categorical'):
            raise ValueError(f'{name} does not support frequency exploration')
        if suppressed and view in ('frequency', 'distribution'):
            raise ValueError(f'Values are suppressed for sensitive column {name}')
        if suppressed:
            return (profile.summary(name),)

        frequency_options = (top_n is not None or denominator != 'total')
        use_frequency = kind == 'categorical' and view in ('all', 'summary', 'frequency', 'distribution')
        use_frequency |= kind == 'numeric' and view == 'frequency'
        if use_frequency and frequency_options:
            cardinality = profile._cardinality(name)
            if cardinality > profile.options.max_unique_for_frequency:
                raise ValueError(f'{name} has too many distinct values for frequency exploration')
            counts = stats.frequency(
                profile.source, name,
                top_n=top_n or profile.options.max_categories,
                include_null=profile.options.include_null,
                denominator=denominator,
            )
            if kind == 'categorical':
                counts = profile._decorate_frequency(counts, meta)
            table = self._recipe(
                ReportItem('table', f'{label} — frequency', counts,
                           caption=f'Percent denominator: {denominator}'),
                name, 'frequency', by=None, bins=bins, top_n=top_n,
                denominator=denominator,
            )
        elif view == 'frequency':
            table = profile.frequency(name)
        else:
            table = profile.summary(name)

        if view == 'summary' or view == 'frequency':
            return (table,)
        if view == 'distribution' and suppressed:
            raise ValueError(f'No distribution available for sensitive column {name}')

        chart = None
        if kind == 'numeric' and bins is not None:
            chart = self._recipe(
                ReportItem('chart', f'{label} — histogram',
                           plots.histogram(profile.source, name, bins=bins, title=label)),
                name, 'distribution', by=None, bins=bins, top_n=top_n,
                denominator=denominator,
            )
        elif kind == 'categorical' and frequency_options:
            chart = self._recipe(
                ReportItem('chart', f'{label} — distribution',
                           plots.frequency(profile.source, name, title=label, counts=table.content)),
                name, 'distribution', by=None, bins=bins, top_n=top_n,
                denominator=denominator,
            )
        else:
            try:
                chart = profile.distribution(name)
            except ValueError:
                if view == 'distribution':
                    raise

        if view == 'distribution':
            if chart is None:
                raise ValueError(f'No distribution available for {name}')
            return (chart,)
        return (table, chart) if chart is not None else (table,)

    def _stratified(
            self, name: str, view: str, kind: str, *, by: str, bins: int | None, top_n: int | None, denominator: str,
            groups: tuple[object, ...],
    ) -> tuple[ReportItem, ...]:
        profile = self.profile
        source = self._group_frame(by, groups)
        meta = profile.metadata.get(name, Variable())
        if meta.sensitive and not profile.options.include_sensitive and view != 'missingness':
            raise ValueError(f'Values are suppressed for sensitive column {name}')
        if view == 'missingness':
            return (self._recipe(self._missingness(name, by, groups), name, view, by=by,
                                 bins=bins, top_n=top_n, denominator=denominator, groups=groups),)
        label = meta.label or name
        group_label = profile.metadata.get(by, Variable()).label or by
        if kind == 'numeric':
            if view == 'frequency':
                raise ValueError('Numeric frequency stratification is not supported; use summary')
            data = stats.summary(source, [name], by=by,
                                 max_categories=profile.options.max_categories,
                                 max_groups=profile.options.max_groups)
            table = self._recipe(ReportItem(
                'table', f'{label} — descriptive statistics by {group_label}', data,
                caption='Descriptive statistics by group; no significance tests',
            ), name, 'summary', by=by, bins=bins, top_n=top_n, denominator=denominator,
                groups=groups)
            if view == 'summary':
                return (table,)
            if len(groups) > profile.options.max_chart_groups:
                if view == 'distribution':
                    raise ValueError(
                        f'{by!r} has {len(groups)} selected groups; chart limit is '
                        f'{profile.options.max_chart_groups}. Select fewer groups or use the table view.'
                    )
                return (table,)
            chart = self._recipe(ReportItem(
                'chart', f'{label} — median and IQR by {group_label}',
                plots.grouped_numeric(data, title=f'{label} by {group_label}'),
                caption='Points are medians; bars span the interquartile range',
            ), name, 'distribution', by=by, bins=bins, top_n=top_n,
                denominator=denominator, groups=groups)
            return (chart,) if view == 'distribution' else (table, chart)
        if profile._cardinality(name) > profile.options.max_unique_for_frequency:
            raise ValueError(f'{name} has too many distinct values for stratification')
        if denominator == 'valid':
            raise ValueError("Stratified denominators are 'group', 'row', or 'total'")
        rows = stats.crosstab(
            source, name, by=by, denominator=denominator,
            include_null=profile.options.include_null,
            max_cells=max(2000, profile.options.max_groups * profile.options.max_categories),
        )
        if top_n is not None:
            # keep only top categories by total count
            counts = rows.group_by('value').agg(pl.sum('count').alias('n')).sort(
                ['n', 'value'], descending=[True, False],
            )
            keep = counts['value'].head(top_n).to_list()
            rows = rows.filter(pl.col('value').is_in(keep))
        if meta.value_labels:
            rows = rows.with_columns(pl.col('value').replace_strict(
                meta.value_labels, default=pl.col('value'),
            ))
        table = self._recipe(ReportItem(
            'table', f'{label} — frequency by {group_label}', rows,
            caption=f'Percent denominator: {denominator}',
        ), name, 'frequency', by=by, bins=bins, top_n=top_n,
            denominator=denominator, groups=groups)
        if view in ('summary', 'frequency'):
            return (table,)
        if len(groups) > profile.options.max_chart_groups:
            if view == 'distribution':
                raise ValueError(
                    f'{by!r} has {len(groups)} selected groups; chart limit is '
                    f'{profile.options.max_chart_groups}. Select fewer groups or use the table view.'
                )
            return (table,)
        chart = self._recipe(ReportItem(
            'chart', f'{label} — distribution by {group_label}',
            plots.grouped_frequency(rows, title=f'{label} by {group_label}',
                                    max_groups=profile.options.max_chart_groups),
            caption=f'Percent denominator: {denominator}',
        ), name, 'distribution', by=by, bins=bins, top_n=top_n,
            denominator=denominator, groups=groups)
        return (chart,) if view == 'distribution' else (table, chart)

    def preview(
            self, name: str, *, view: View = 'all', by: str | None = None, bins: int | None = None,
            top_n: int | None = None, denominator: str = 'total', groups=None,
    ) -> tuple[ReportItem, ...]:
        """Get bounded reusable results for a variable and optional stratum.

        All results are aggregates; no source-row samples enter the browser.
        """
        kind = self._validate(name, by, view)
        if by is None and groups is not None:
            raise ValueError('Group selection requires a grouping variable')
        chosen = self._chosen_groups(by, groups) if by is not None else None
        if bins is not None and not 1 <= bins <= 150:
            raise ValueError('bins must be between 1 and 150')
        if top_n is not None and not 1 <= top_n <= 100:
            raise ValueError('top_n must be between 1 and 100')
        allowed = ('total', 'valid') if by is None else ('group', 'row', 'total')
        if denominator not in allowed:
            raise ValueError(f'Percent denominator must be one of {allowed}')
        key = (name, view, by, bins, top_n, denominator, chosen)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        if by is None:
            result = self._unstratified(name, view, kind, bins=bins, top_n=top_n, denominator=denominator)
        else:
            result = self._stratified(name, view, kind, by=by, bins=bins, top_n=top_n, denominator=denominator,
                                      groups=chosen)
        self._cache[key] = result
        if len(self._cache) > 12:
            self._cache.popitem(last=False)
        return result

    def add_to_report(self, name: str, **kwargs) -> tuple[ReportItem, ...]:
        """Add the current analysis and its exact settings to the report."""
        return tuple(self.report.add(item) for item in self.preview(name, **kwargs))

    def show(self):
        """Display optional ipywidgets controls in a notebook.

        Install `polarstory[notebook]` to enable the interface. The explorer
        retains a Python reference to the profile and never sends raw source
        records to a separate web server.
        """
        try:
            import ipywidgets as widgets
            from IPython.display import HTML, clear_output, display
        except ImportError as exc:
            raise ImportError(
                'The interactive explorer requires polarstory[notebook] '
                '(ipywidgets and IPython)'
            ) from exc
        if not self.profile.columns:
            raise ValueError('No variables selected for exploration')

        titles = [
            (f'{self.profile.metadata.get(name, Variable()).label or name} ({name})'
             if self.profile.metadata.get(name, Variable()).label else name, name)
            for name in self.profile.columns
        ]
        search = widgets.Text(description='Search', placeholder='Filter columns')
        variable = widgets.Dropdown(options=titles, description='Variable')
        by = widgets.Dropdown(options=[('None', None)], description='Group by')
        groups_picker = widgets.SelectMultiple(options=[], description='Groups',
                                               rows=7)
        groups_picker.layout.display = 'none'
        view = widgets.Dropdown(
            options=[('Complete Summary', 'all'),
                     ('Statistics / Table', 'summary'),
                     ('Distribution Chart', 'distribution'),
                     ('Frequency Table', 'frequency'),
                     ('Missingness', 'missingness'),
                     ('IQR Outliers', 'outliers')],
            value='all', description='View',
        )
        bins = widgets.BoundedIntText(value=self.profile.options.histogram_bins, min=1, max=150, description='Bins')
        top_n = widgets.BoundedIntText(value=self.profile.options.max_categories, min=1, max=100, description='Top N')
        denominator = widgets.Dropdown(options=['total', 'valid'], value='total', description='Percent')
        preview_button = widgets.Button(description='Preview', icon='eye')
        add_button = widgets.Button(description='Add to report', icon='plus', button_style='success')
        output = widgets.Output()
        status = widgets.HTML()
        diagnostics = widgets.Dropdown(
            options=[('Missingness Patterns', 'patterns'),
                     ('Missingness Associations', 'associations'),
                     ('Duplicate Rows', 'duplicates'),
                     ('Variable Uniqueness', 'uniqueness')],
            description='Dataset',
        )
        diagnostic_preview = widgets.Button(description='Preview Diagnostic', icon='eye')
        diagnostic_add = widgets.Button(description='Add Diagnostic', icon='plus')
        self.widget = widgets.VBox([
            widgets.HTML('<h3>PolarStory Variable Explorer</h3>'),
            search, variable, by, groups_picker, view,
            widgets.HBox([bins, top_n, denominator]),
            widgets.HBox([preview_button, add_button]),
            widgets.HBox([diagnostics, diagnostic_preview, diagnostic_add]),
            status, output,
        ])

        def search_changed(change):
            phrase = change['new'].casefold().strip()
            matches = [(label, name) for label, name in titles
                       if phrase in label.casefold() or phrase in name.casefold()]
            current = variable.value
            variable.options = matches
            if current in {name for _, name in matches}:
                variable.value = current
            elif matches:
                variable.value = matches[0][1]
            status.value = '' if matches else '<em>No matching variables</em>'

        was_grouped = False

        def controls_changed(change=None):
            nonlocal was_grouped
            selected = variable.value
            if selected is None:
                preview_button.disabled = True
                add_button.disabled = True
                return
            preview_button.disabled = False
            add_button.disabled = False
            kind = self.profile._kind(selected)
            group_options = [('None', None)]
            for name in self.profile.columns:
                if name != selected and self.profile._kind(name) == 'categorical':
                    meta = self.profile.metadata.get(name, Variable())
                    if not meta.sensitive or self.profile.options.include_sensitive:
                        group_options.append((meta.label or name, name))
            previous = by.value
            by.options = group_options
            by.value = previous if previous in {name for _, name in group_options} else None
            bins.layout.display = '' if kind == 'numeric' else 'none'
            top_n.layout.display = '' if kind == 'categorical' else 'none'
            percent_options = ['total', 'valid'] if by.value is None else ['group', 'row', 'total']
            previous_percent = denominator.value
            grouped = by.value is not None
            denominator.options = percent_options
            if grouped and not was_grouped:
                denominator.value = 'group'
            else:
                denominator.value = (previous_percent if previous_percent in percent_options
                                     else percent_options[0])
            was_grouped = grouped
            if grouped:
                try:
                    available = self._group_values(by.value)
                    previous = set(groups_picker.value)
                    groups_picker.options = [(str(v) if v is not None else '(null)', v)
                                             for v in available]
                    # retain selections where possible
                    groups_picker.value = (tuple(v for v in available if v in previous)
                                           if previous else tuple(available))
                    groups_picker.layout.display = ''
                    status.value = (
                        f'<small>{len(available)} groups available; table limit '
                        f'{self.profile.options.max_groups}, chart limit '
                        f'{self.profile.options.max_chart_groups}. '
                        f'Select fewer groups for charts.</small>'
                    )
                except ValueError as exc:
                    groups_picker.options = []
                    groups_picker.layout.display = 'none'
                    status.value = f'<span style="color:#a33">{escape(str(exc))}</span>'
            else:
                groups_picker.options = []
                groups_picker.layout.display = 'none'

        def current_options():
            kind = self.profile._kind(variable.value)
            return {
                'view': view.value,
                'by': by.value,
                'bins': (bins.value
                         if kind == 'numeric' and by.value is None and bins.value != self.profile.options.histogram_bins
                         else None
                         ),
                'top_n': (top_n.value
                          if kind == 'categorical' and top_n.value != self.profile.options.max_categories
                          else None
                          ),
                'denominator': denominator.value,
                'groups': tuple(groups_picker.value) if by.value is not None else None,
            }

        def preview_click(_):
            with output:
                clear_output(wait=True)
                try:
                    items = self.preview(variable.value, **current_options())
                    report = Report(variable.value)
                    for item in items:
                        report.add(item)
                    display(HTML(report.to_html()))
                    status.value = f'<span>Previewing {escape(variable.value)}</span>'
                except (TypeError, ValueError) as exc:
                    status.value = f'<span style="color:#a33">{escape(str(exc))}</span>'

        def add_click(_):
            try:
                self.add_to_report(variable.value, **current_options())
                status.value = f'<span>Added to Report · {len(self.report.items)} items</span>'
            except (TypeError, ValueError) as exc:
                status.value = f'<span style="color:#a33">{escape(str(exc))}</span>'

        def selected_diagnostic():
            return {
                'patterns': self.profile.missingness_patterns,
                'associations': self.profile.missingness_associations,
                'duplicates': self.profile.duplicates,
                'uniqueness': self.profile.uniqueness,
            }[diagnostics.value]()

        def diagnostic_click(add):
            with output:
                if not add:
                    clear_output(wait=True)
                try:
                    item = selected_diagnostic()
                    if add:
                        self.report.add(item)
                        status.value = f'<span>Added to report · {len(self.report.items)} items</span>'
                    else:
                        report = Report(item.title)
                        report.add(item)
                        display(HTML(report.to_html()))
                        status.value = f'<span>Previewing {escape(item.title)}</span>'
                except (TypeError, ValueError) as exc:
                    status.value = f'<span style="color:#a33">{escape(str(exc))}</span>'

        diagnostic_preview.on_click(lambda _: diagnostic_click(False))
        diagnostic_add.on_click(lambda _: diagnostic_click(True))
        search.observe(search_changed, names='value')
        variable.observe(controls_changed, names='value')
        by.observe(controls_changed, names='value')
        preview_button.on_click(preview_click)
        add_button.on_click(add_click)
        controls_changed()
        display(self.widget)
        return self.widget


def explore(
        data: DataInput | DataSource | Profile, *, report: Report | None = None,
        show: bool = True, options: ProfileOptions | None = None,
        variables: Variables | None = None) -> Explorer:
    """Convenience entry point for VS Code Jupyter/Interactive sessions."""
    from polarstory.profile import Profile, profile

    prepared = data if isinstance(data, Profile) else profile(data, options=options, variables=variables)
    explorer = Explorer(prepared, report=report)
    if show:
        explorer.show()
    return explorer
