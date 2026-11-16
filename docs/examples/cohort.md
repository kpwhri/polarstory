# Example: inspect a study cohort

**Question:** What variables are available in a new cohort extract, and how complete are they?

This example uses fabricated patient-level variables. It does not include real patient information.

## Create a small example dataset

```python
from datetime import date
import polars as pl
import polarstory as ps

df = pl.DataFrame({
    'age': [34, 67, 54, 29, 71, 48],
    'sex_admin': ['F', 'M', 'F', 'F', 'M', 'U'],
    'enctype': ['ED', 'Inpatient', 'Outpatient', 'ED', 'Inpatient', 'Outpatient'],
    'ins_medicaid': ['Y', 'N', 'N', 'U', 'Y', 'N'],
    'tx_ep_start': [
        date(2026, 1, 3), date(2026, 1, 8), date(2026, 2, 1),
        date(2026, 2, 3), date(2026, 2, 9), date(2026, 3, 1),
    ],
})
```

## Generate an overview

```python
p = ps.profile(df, title='Synthetic study cohort')
p.write_html('cohort_profile.html')
```

The automatic report includes a dataset overview, missingness information, variable summaries, and static figures.

## Examine a few variables

```python
p.summary('age').show()
p.frequency('enctype').show()
p.timeline('tx_ep_start').show()
```

For an encounter-level dataset, counts represent **encounters** unless explicitly calculated as distinct patients. Label units in the report rather than assuming every row represents a person.

## Share a short report

```python
report = ps.Report('Cohort at a glance')
report.add(p.summary('age'))
report.add(p.frequency('enctype'))
report.add(p.frequency('ins_medicaid'))
report.write_html('cohort_at_a_glance.html')
```

Before distributing a report based on real data, review small counts and rare categories. See [quality and privacy checks](quality.md).

## Categorical associations

For two categorical variables, Cramér's V provides a descriptive
measure of association strength without requiring numerical coding:

```python
association = ps.stats.cramers_v(
    df, 'ins_medicaid', 'enctype',
)
report.add_table(association, title='Insurance and encounter type')
```

Review the contingency table and sample sizes alongside the statistic.
A large association does not establish a causal relationship, and rows may
represent multiple encounters from the same patient.
