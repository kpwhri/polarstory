# `stats.cramers_v`

<!-- API: polarstory.stats.cramers_v -->

::: polarstory.stats.cramers_v
    options:
      members: false
      show_root_heading: true
      show_root_full_path: false
      separate_signature: true

## Example

```python
import polarstory as ps

result = ps.stats.cramers_v(
    df,
    'ins_medicaid',
    'enctype',
    bias_corrected=True,
)
print(result)

report = ps.Report('Categorical associations')
report.add_table(result, title='Insurance and encounter type')
report.write_html('associations.html')
```

## Interpretation

Cramér's V measures **strength**, not direction. The value lies between
0 and 1 when defined. By default, the estimator uses the finite-sample
bias correction proposed by Bergsma (2013). Use
`bias_corrected=False` for the conventional estimate.

Null observations are excluded pairwise by default. If
`include_null=True`, null is a distinct category and is not conflated
with a literal category named `'(null)'`. Floating NaN and infinity are
excluded in either case.

The returned one-row polars DataFrame includes the coefficient, the
complete-case sample size, contingency-table dimensions, chi-square
statistic, and diagnostics for expected cell counts below 5. Values are
**undefined** (`null`) if either variable has fewer than two observed
categories or if the corrected denominator is not positive.

This is a descriptive association measure, not a significance test.
Repeated patient encounters can affect interpretation. A small expected
count is a caution about sparse categories, not a reason to discard
an observed association automatically.

**Note:** SciPy's `association(..., correction=True)` applies a Yates
continuity correction where applicable; it does **not** implement the
Bergsma finite-sample correction used here. For comparisons to SciPy,
use `bias_corrected=False` and `correction=False` in SciPy.

## See also

- [`stats.crosstab`](crosstab.md)
- [`stats.correlations`](correlations.md)
- [Healthcare cohort example](../../examples/cohort.md)

[← Statistics and diagnostics API](index.md)
