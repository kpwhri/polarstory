"""Generate a deterministic sample report for visual comparison.

Run with the desired polarstory version installed in your environment.
Use --label to distinguish two checkouts with the same package version.
"""

import argparse
import random as rng
import webbrowser
from datetime import datetime
from importlib.metadata import version
from pathlib import Path

import polars as pl
from matplotlib.figure import Figure

import polarstory as ps


def main(label='', n=250, outdir=Path('reports')):
    """Generate, save, and open the sample report."""

    df = pl.DataFrame({
        'patient_id': range(1, n + 1),
        'age': [rng.randint(18, 90) for _ in range(n)],
        'sex_admin': [rng.choice(['F', 'M']) for _ in range(n)],
        'encounter_type': [
            rng.choices(['Outpatient', 'Inpatient', 'Emergency'], weights=[65, 20, 15])[0]
            for _ in range(n)
        ],
        'length_of_stay': [
            None if rng.random() < 0.1 else round(rng.uniform(0, 12), 1)
            for _ in range(n)
        ],
    })

    summary_df = (
        df.group_by('encounter_type')
        .agg(
            count=pl.len(),
            mean_age=pl.col('age').mean(),
            mean_stay=pl.col('length_of_stay').mean(),
        )
        .with_columns(proportion=pl.col('count') / pl.col('count').sum())
        .sort('encounter_type')
    )

    report = ps.Report(
        'Synthetic cohort report',
        subtitle=f'{n} synthetic patients',
    )

    report.add_text(
        'This report uses simulated data, not actual patient records.\n'
        'Plain text test: <strong>not bold</strong> & ordinary text.',
        title='About this report',
    )

    with report.section('DataFrames as Tables'):
        report.add_table(
            summary_df,
            title='Encounter characteristics',
            caption='Aggregated counts and means.',
            notes='Mean length of stay excludes null values.',
            id='native-summary',
        )
        report.add_table(
            df.select('age', 'length_of_stay').describe(),
            title='Numeric summary',
        )

    with report.section('Charts'):
        figure = Figure(figsize=(7, 3))
        ax = figure.subplots()
        ax.hist(df.get_column('age').to_list(), bins=12, edgecolor='white')
        ax.set(xlabel='Age (years)', ylabel='Patients')
        figure.tight_layout()
        report.add_chart(figure, title='Age distribution', caption='Synthetic cohort.')

    # detect new methods without masking rendering errors
    has_gt = callable(getattr(report, 'add_great_table', None))
    has_html = callable(getattr(report, 'add_html', None))

    if has_gt:
        from great_tables import GT

        gt = (
            GT(summary_df)
            .tab_header(title='Encounter characteristics', subtitle='Synthetic cohort')
            .cols_label(
                encounter_type='Encounter type',
                count='Patients',
                mean_age='Mean age',
                mean_stay='Mean stay (days)',
                proportion='Percent',
            )
            .fmt_number(columns='count', decimals=0)
            .fmt_number(columns=['mean_age', 'mean_stay'], decimals=1)
            .fmt_percent(columns='proportion', decimals=1)
            .opt_row_striping()
        )
        with report.section('Great Tables'):
            report.add_great_table(gt, notes='Same data as the native summary table.')
    else:
        print('add_great_table() unavailable; skipping external table.')

    if has_html:
        with report.section('Custom HTML'):
            report.add_html(
                '<div style="padding:12px;border-left:4px solid #388e75;'
                'background:#edf7f2;color:#23443a">'
                '<strong>HTML rendering test</strong>'
                '<p>This is formatted HTML, not escaped text.</p>'
                '</div>',
                title='Custom callout',
                id='html-example',
            )
    else:
        print('add_html() unavailable; skipping custom HTML.')

    ps_version = version('polarstory')
    label = label or f'gt{int(has_gt)}-html{int(has_html)}'
    path = outdir / f'polarstory-{ps_version}-{label}.html'
    path = report.write_html(path).resolve()

    print(f'polarstory {ps_version} | polars {pl.__version__}')
    print(f'Loaded from: {ps.__file__}')
    print(f'Report saved to: {path}')

    webbrowser.open(path.as_uri())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', default=f'{datetime.now().strftime("%Y%m%d_%H%M%S")}',
                        help='Label appended to the report filename, e.g. before or after.')
    parser.add_argument('--n', default=250, type=int, help='Number of samples to generate.')
    parser.add_argument('--outdir', default=Path('reports'), type=Path, help='Output directory.')
    args = parser.parse_args()
    main(label=args.label, n=args.n, outdir=args.outdir)
