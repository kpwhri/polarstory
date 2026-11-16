# Automatic profiling

`ps.profile()` computes descriptive summaries for selected variables and makes them available as reusable report components.

## Modes

| Mode | Includes | When to use |
| --- | --- | --- |
| `quick` | Counts, descriptive summaries, frequencies, missingness | First look at unfamiliar data |
| `standard` | Quick profile plus static charts | General exploration and sharing |
| `full` | Standard plus additional missingness, duplicates, outliers, uniqueness and categorical diagnostics | Deliberate, deeper review |

```python
import polarstory as ps

ps.profile('cohort.parquet', mode='quick').write_html('quick.html')
ps.profile('cohort.parquet', mode='full').write_html('full.html')
```

**Performance:** `full` can be substantially more expensive, particularly for wide or high-cardinality datasets. A lazy parquet scan does not guarantee bounded memory for every calculation.

## Limit the columns

```python
import polars.selectors as cs

p = ps.profile(
    'cohort.parquet',
    columns=cs.starts_with('ins_'),
    max_columns=15,
)
```

You can also pass `columns=['sex_admin', 'enctype']` or `exclude=cs.starts_with('note_')`.

## Adjust the output

```python
options = ps.ProfileOptions(
    max_categories=15,
    histogram_bins=25,
    charts=True,
    max_unique_for_frequency=1000,
)

p = ps.profile('cohort.parquet', options=options)
p.write_html('cohort.html')
```

The profile object delays and caches several calculations. `p.refresh()` creates a new snapshot with empty caches; it does **not** preserve a frozen copy of a changing source file.

## Understand missing and unknown values

- polars `null` values are reported as missing.
- Floating `NaN` and infinities are distinguished where supported.
- Literal codes such as `'U'` or `'Unknown'` remain categories until you define your own meaning for them.
- Percent denominators are stated on the relevant frequency tables.

## Reuse profile results

```python
p = ps.profile('cohort.parquet')

age_table = p.summary('age')
age_chart = p.histogram('age')
encounter_counts = p.frequency('enctype')

report = ps.Report('Selected findings')
report.add(age_table)
report.add(age_chart)
report.add(encounter_counts)
report.write_html('findings.html')
```

See [Profile API](../reference/profile/index.md) for all named methods.
