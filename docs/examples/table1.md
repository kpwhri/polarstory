# Example: descriptive cohort characteristics (Table 1)

**Question:** How do baseline cohort characteristics differ across two predefined groups?

polarstory can produce a descriptive Table 1 without hypothesis tests or p-values. The same output can be inserted into a curated HTML report.

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

The table uses `n (%)` for categories and median/IQR for numeric variables. You can use `numeric='mean_sd'` instead. A useful practice is to document the percentage denominator in the caption or notes.

## Important research distinctions

- This is **descriptive** reporting, not a covariate-balance test or causal analysis.
- Rows may represent encounters rather than unique people; verify the observation unit.
- In real patient-level datasets, cells with small counts may require suppression or aggregation according to project policy.
- Specify the meaning of coded values (`U`, `N`, `Y`) rather than treating them as interchangeable with missingness.

The `Report.add_table1()` method delegates to the dedicated descriptive Table 1 formatter; the more general `ps.stats.summary()` returns a tidy descriptive table.

See [Report API](../reference/report/index.md) and [Statistics API](../reference/stats/index.md).
