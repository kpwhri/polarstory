# Example: investigate missing data

**Question:** Do insurance variables and other cohort fields tend to be missing together?

An overall percent missing per column is useful but may hide patterns. polarstory can summarize common combinations of missing columns and their pairwise associations.

## Synthetic example

```python
import polars as pl
import polarstory as ps

df = pl.DataFrame({
    'age': [44, 51, 35, 68, 59, 42],
    'ins_medicaid': ['Y', None, 'N', None, 'U', 'N'],
    'ins_commercial': ['N', None, 'Y', None, 'N', 'Y'],
    'enctype': ['ED', 'ED', 'Outpatient', 'Inpatient', 'ED', 'Outpatient'],
})

p = ps.profile(df)
report = ps.Report('Missing-data assessment')
report.add(p.missingness_patterns())
report.add(p.missingness_associations())
report.add(p.missingness_associations_chart())
report.write_html('missingness.html')
```

## Interpretation

The missingness-pattern table identifies combinations of missing fields. The association output uses phi coefficients between binary missingness indicators; an undefined coefficient can occur when an indicator is constant.

`'U'` in this example is a recorded **unknown category**. It is not the same as a polars null. Transform it into null only if that matches your data dictionary and analysis plan.

## Large datasets

Missingness-pattern analysis grows more expensive with the number of columns. Use a selected subset and the `max_missingness_columns` option when preparing a targeted review:

```python
p = ps.profile(
    df,
    columns=['ins_medicaid', 'ins_commercial'],
    options=ps.ProfileOptions(max_missingness_columns=12),
)
```

Missingness associations are descriptive. They do not by themselves establish that values are missing at random or not at random.
