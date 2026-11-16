# Compare two datasets

Use `ps.compare()` to describe differences between two research extracts. It accepts
polars DataFrames, LazyFrames, or local parquet paths. No patient-level join is
performed, and there are no p-values or distributional significance tests.

```python
import polarstory as ps

comparison = ps.compare(
    'cohort_earlier.parquet',
    'cohort_recent.parquet',
    labels=('Earlier extract', 'Recent extract'),
)

comparison.write_html('cohort_comparison.html')
```

The offline HTML report contains:

- record and column counts
- added, removed, and changed column types
- null counts, percentages, and percentage-point changes
- means, medians, sample standard deviations, and other numeric metrics
- bounded categorical frequency changes, including unknown (`U`) and null categories

## Use individual results

Every result is an ordinary polars DataFrame, so it can be examined or
added to another report.

```python
comparison = ps.compare(before, after)
comparison.schema_changes
comparison.missingness
comparison.numeric
comparison.categorical
comparison.skipped

report = ps.Report('Study update')
report.add_table(comparison.missingness, title='Missingness by extract')
report.write_html('study_update.html')
```

For numeric-coded categories, explicitly identify those columns:

```python
comparison = ps.compare(
    before,
    after,
    categorical_columns=['insurance_code'],
    exclude=['patient_name', 'medical_record_number'],
)
```

## Large datasets and disclosure

Numeric summaries operate on lazy sources, but exact frequency grouping
may still use significant memory. The comparison limits the number of
columns and categories, skips identifier-like column values, and excludes
high-cardinality categorical variables. It does **not** make aggregate
outputs automatically safe to share; small cells and rare categories may
still disclose sensitive information.

Rows represent records, **not necessarily unique patients**. A relative
change in row count may reflect encounter volume, not cohort size.

## Command line

```powershell
polarstory compare cohort_earlier.parquet cohort_recent.parquet --open
polarstory compare cohort_earlier.parquet cohort_recent.parquet -o reports/changes.html
polarstory compare cohort_earlier.parquet cohort_recent.parquet --columns age,sex_admin,enctype
```

By default, percent changes are shown in **percentage points**. A missingness
change from 10% to 20% is +10 percentage points, not +10% relative.

See [Dataset comparison API](../reference/comparison/index.md).
