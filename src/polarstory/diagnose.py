"""Small, curated diagnostic reports composed from existing polars analyses."""

from __future__ import annotations

from itertools import combinations

import polars as pl

from polarstory import stats
from polarstory.profile import Profile
from polarstory.report import Report
from polarstory.variables import Variable

DIAGNOSTIC_TYPES = ('missingness', 'numeric', 'categorical', 'quality', 'associations')


def choose_diagnostic() -> str | None:
    """Ask for one diagnostic using the standard-library desktop dialog."""
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError as exc:
        raise RuntimeError('Advanced diagnostics selection requires tkinter') from exc

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise RuntimeError('A desktop session is required for the diagnostics dialog') from exc
    root.title('polarstory · Advanced Diagnostics')
    root.resizable(False, False)
    selection = tk.StringVar(value=DIAGNOSTIC_TYPES[0])
    chosen: list[str] = []
    content = ttk.Frame(root, padding=16)
    content.pack(fill='both', expand=True)
    ttk.Label(content, text='Choose a diagnostic report:').pack(anchor='w', pady=(0, 8))
    for name in DIAGNOSTIC_TYPES:
        ttk.Radiobutton(content, text=name.replace('_', ' ').title(),
                        variable=selection, value=name).pack(anchor='w', pady=2)

    def confirm():
        chosen.append(selection.get())
        root.destroy()

    ttk.Button(content, text='Generate Report', command=confirm).pack(pady=(12, 0))
    root.protocol('WM_DELETE_WINDOW', root.destroy)
    root.mainloop()
    return chosen[0] if chosen else None


def diagnostic_report(profile: Profile, kind: str) -> Report:
    """Build a bounded diagnostic report without exporting raw observations."""
    if kind not in DIAGNOSTIC_TYPES:
        raise ValueError(f'Unknown Diagnostic: {kind}')
    report = Report(f'{kind.replace("_", " ").title()} · {profile.title}')
    report.add(profile.item('@overview'))
    if kind == 'missingness':
        report.add(profile.item('@missingness'))
        if profile.options.charts and profile.columns:
            report.add(profile.missingness_chart())
        if len(profile.columns) > profile.options.max_missingness_columns:
            report.add_text(
                f'Selected {len(profile.columns)} variables; missingness patterns are '
                f'limited to {profile.options.max_missingness_columns}. '
                'Use --max-columns to limit the analysis.',
                title='Diagnostics Limited',
            )
        else:
            report.add(profile.missingness_patterns())
            report.add(profile.missingness_associations())
            if profile.options.charts:
                report.add(profile.missingness_associations_chart())
    elif kind in ('numeric', 'categorical'):
        selected = [name for name in profile.columns if profile._kind(name) == kind
                    and (profile.options.include_sensitive or
                         not profile.metadata.get(name, Variable()).sensitive)]
        if not selected:
            report.add_text(f'No {kind} variables selected for profiling.')
        for name in selected:
            with report.section(profile.metadata.get(name, Variable()).label or name):
                report.add(profile.summary(name))
                if profile.options.charts:
                    try:
                        report.add(profile.distribution(name))
                    except ValueError:
                        pass
                if kind == 'numeric':
                    report.add(profile.outliers(name))
                elif profile._cardinality(name) <= profile.options.max_unique_for_frequency:
                    report.add(profile.category_diagnostics(name))
    elif kind == 'quality':
        report.add(profile.item('@missingness'))
        if profile.options.alerts and profile.alerts:
            report.add(profile.item('@alerts'))
        else:
            report.add_text('No configured quality alerts were triggered.')
        if profile._can_check_duplicates():
            report.add(profile.duplicates())
        else:
            report.add_text('Duplicate analysis skipped because of schema or column limits.')
        report.add(profile.uniqueness())
    elif kind == 'associations':
        numeric = [name for name in profile.columns if profile._kind(name) == 'numeric'
                   and (profile.options.include_sensitive or
                        not profile.metadata.get(name, Variable()).sensitive)]
        if len(numeric) > 12:
            report.add_text(
                f'{len(numeric)} numeric variables selected; association results are limited to the first 12.')
        if len(numeric) >= 2:
            report.add_table(
                stats.correlations(
                    profile.source,
                    columns=numeric[:12],
                    method='spearman',
                    max_columns=12
                ),
                title='Spearman Correlations',
                caption='Descriptive associations; not hypothesis tests',
            )
        else:
            report.add_text('At least two numeric variables are needed for correlation analysis.')

        categorical = [
            name for name in profile.columns
            if profile._kind(name) == 'categorical'
               and (profile.options.include_sensitive or not profile.metadata.get(name, Variable()).sensitive)
        ]
        max_categorical = 8
        if len(categorical) > max_categorical:
            report.add_text(
                f'{len(categorical)} categorical variables selected; '
                f'only the first {max_categorical} are compared.',
                title='Categorical Association Limit',
            )
        rows = []
        skipped = []
        for left, right in combinations(categorical[:max_categorical], 2):
            try:
                result = stats.cramers_v(
                    profile.source, left, right, bias_corrected=True,
                    max_categories=profile.options.max_groups,
                ).row(0, named=True)
            except (ValueError, TypeError) as exc:
                skipped.append(f'{left} × {right}: {exc}')
            else:
                rows.append(result)
        if rows:
            report.add_table(
                pl.DataFrame(rows).select(
                    'column', 'by', 'n', 'n_rows', 'n_columns',
                    'cramers_v', 'small_expected_fraction',
                ),
                title='Categorical Associations (Cramér\'s V)',
                caption='Bias-corrected; pairwise complete observations; descriptive only',
            )
        elif len(categorical) < 2:
            report.add_text('At least two categorical variables are needed for Cramér\'s V.')
        if skipped:
            report.add_text(
                'Some categorical pairs were excluded by the cardinality or type limits: '
                + '; '.join(skipped),
                title='Categorical Associations Skipped',
            )
    return report
