# Example: descriptive cohort characteristics (Table 1)

**Question:** How do baseline cohort characteristics differ across two predefined groups?

polarstory can produce a descriptive Table 1 without hypothesis tests or p-values. The same output can be inserted into
a curated HTML report.

## Synthetic example

```python
import polars as pl
import polarstory as ps

df = pl.DataFrame({
    'cohort': ['A', 'A', 'A', 'B', 'B', 'B'],
    'age': [42, 55, 63, 38, 58, 71],
    'sex_admin': ['F', 'M', 'F', 'F', 'M', 'F'],
    'enctype': ['ED', 'Inpatient', 'ED', 'Outpatient', 'ED', 'Inpatient'],
})

report = ps.Report('Cohort characteristics')
report.add_table1(
    df,
    columns=['age', 'sex_admin', 'enctype'],
    by='cohort',
    numeric='median_iqr',
    percent='total',
    include_total=True,
    title='Table 1. Baseline characteristics',
)
report.write_html('table1.html')
```

The table uses `n (%)` for categories and median/IQR for numeric variables. You can use `numeric='mean_sd'` instead. A
useful practice is to document the percentage denominator in the caption or notes.

## Using Great Tables

For more control over the appearance of a descriptive table, use polarstory to calculate the statistics and Great Tables
to format the resulting dataframe. Install the optional library with `pip install great-tables`.

```python
from great_tables import GT

summary = ps.stats.table1(
    df,
    columns=['age', 'sex_admin', 'enctype'],
    by='cohort',
    numeric='median_iqr',
    percent='total',
    include_total=True,
)

table = (
    GT(summary)
    .tab_header(title='Table 1. Baseline characteristics')
    .opt_row_striping()
)

report = ps.Report('Cohort characteristics')
report.add_great_table(table)
report.write_html('table1_formatted.html')
```

Use `Report.add_table1()` for convenient native reporting, or combine `ps.stats.table1()` with Great Tables for
customized presentation. Save the analysis script to reproduce the formatted report; external tables are not supported
by JSON report recipes.

## Important research distinctions

- This is **descriptive** reporting, not a covariate-balance test or causal analysis.
- Rows may represent encounters rather than unique people; verify the observation unit.
- In real patient-level datasets, cells with small counts may require suppression or aggregation according to project
  policy.
- Specify the meaning of coded values (`U`, `N`, `Y`) rather than treating them as interchangeable with missingness.

The `Report.add_table1()` method delegates to the dedicated descriptive Table 1 formatter; the more general
`ps.stats.summary()` returns a tidy descriptive table.

See [Report API](../reference/report/index.md) and [Statistics API](../reference/stats/index.md).
