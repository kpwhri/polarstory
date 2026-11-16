# Getting started

## Install

For this development release, install from the source checkout in the Python environment used by VS Code:

```powershell
python -m pip install -e .
```

To use the notebook explorer:

```powershell
python -m pip install -e ".[notebook]"
```

The notebook interface is optional. Automatic reports and the CLI do not require it. After publication on PyPI, installation with `python -m pip install polarstory` can be used instead.

## Profile a parquet file

```python
import polarstory as ps

profile = ps.profile('cohort.parquet')
profile.write_html('cohort.profile.html')
```

The file is scanned lazily. Many summaries are aggregations, but some exact operations still require substantial memory. Read [automatic profiling](guides/profiling.md) for modes and cost safeguards.

## Profile an existing dataframe

```python
import polars as pl
import polarstory as ps

df = pl.DataFrame({
    'age': [34, 51, 63, None, 45],
    'enctype': ['ED', 'Inpatient', 'Outpatient', 'ED', 'Outpatient'],
    'ins_medicaid': ['N', 'Y', 'N', 'U', 'Y'],
})

ps.profile(df).write_html('example.html')
```

This is synthetic demonstration data. `U` remains a distinct category rather than automatically becoming null.

## Choose a subset of variables

```python
import polars.selectors as cs

ps.profile(df, columns=['age', 'enctype']).write_html('subset.html')
ps.profile(df, columns=cs.starts_with('ins_')).write_html('insurance.html')
```

## Create a short report for collaborators

```python
p = ps.profile(df)
report = ps.Report('Cohort overview')
report.add(p.summary('age'))
report.add(p.frequency('enctype'))
report.write_html('cohort_summary.html')
```

Open the generated HTML file in a browser, or use **Print → Save as PDF**.

## Next steps

- [Explore variables](guides/explorer.md) in a notebook
- [Healthcare cohort example](examples/cohort.md)
- [API reference](reference/index.md)
