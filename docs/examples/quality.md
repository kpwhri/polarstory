# Example: quality checks and safe sharing

**Question:** Is a research extract suitable for exploratory review, and which summaries need careful interpretation?

polarstory provides diagnostics, not an automated judgment that a dataset is clinically valid or safe to publish.

## Inspect quality indicators

```python
import polars as pl
import polarstory as ps

df = pl.DataFrame({
    'study_id': ['s01', 's02', 's03', 's04', 's05'],
    'age': [25, 37, 37, 82, 82],
    'enctype': ['ED', 'ED', 'ED', 'Inpatient', 'ED'],
    'ins_medicaid': ['Y', 'N', None, 'N', 'U'],
})

variables = (
    ps.Variables()
    .set('study_id', kind='identifier', sensitive=True)
    .set('ins_medicaid', kind='categorical',
         value_labels={'Y': 'Yes', 'N': 'No', 'U': 'Unknown'})
)

p = ps.profile(df, variables=variables, mode='full')
p.write_html('quality_review.html')
```

## Targeted diagnostics

```python
report = ps.Report('Data-quality review')
report.add(p.uniqueness())
report.add(p.duplicates())
report.add(p.outliers('age'))
report.write_html('quality_diagnostics.html')
```

Here `duplicates()` counts exact excess duplicate rows. In clinical data, repeated encounters and visits may be legitimate; duplicate rows do not automatically indicate erroneous records.

## Review before sharing

- Identify columns that contain PHI or other confidential data; do not rely only on automatic identifier-name heuristics.
- Review low-frequency categories and combinations of subgroup variables.
- Confirm that identifiers are not included in explicitly added custom tables.
- Keep reports and underlying files on approved storage and follow your project's disclosure rules.
- Do not interpret descriptive outlier flags as diagnoses or recording errors without additional review.

The package's `sensitive=True` metadata restricts automatic output; it does not constitute a complete disclosure-control mechanism.
