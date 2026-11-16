# Build a curated report

A `Report` collects reusable tables, charts, profile components, and short narrative text into one standalone HTML file.

## Combine outputs

```python
import polarstory as ps

p = ps.profile('cohort.parquet')
report = ps.Report('Cohort exploration', subtitle='Descriptive results')

with report.section('Demographics'):
    report.add(p.summary('age'))
    report.add(p.histogram('age'))

with report.section('Encounter types'):
    report.add(p.frequency('enctype'))

report.write_html('cohort_report.html')
```

## Add a complete variable profile

```python
report = ps.Report('Selected variables')
report.add(p.variable('age'))
report.write_html('variables.html')
```

`p.variable(name)` is a `VariableProfile`; `Report.add()` expands it into its available summary and chart components.

## Add your own polars summary

```python
frequency = ps.stats.frequency('cohort.parquet', 'enctype')
report.add_table(frequency, title='Encounter type',
                 notes='Counts are of encounters, not distinct patients.')
```

`Report.add_table()` accepts eager or lazy polars tables. The default output limit is 2,000 rows to avoid silently generating enormous reports. `Report.add_chart()` accepts a Matplotlib figure.

## Organize and preview

```python
report.add_text('Results are descriptive, not inferential.')
report.to_html()             # complete HTML as a string
report.write_html('study.html')
```

`ReportItem.show()` previews a single result. `Report.remove(item_id)` and `Report.move(item_id, before=...)` edit the ordering of collected results.

## Printing and sharing

Reports embed SVG figures and use print CSS. Open the HTML in a browser and use **Print → Save as PDF** when a PDF is needed. No JavaScript or server is required to view a saved report.

**Disclosure caution:** Small aggregate cells, unusual categories, and individual-level plots can still disclose information. The library does not guarantee safe sharing of protected health information.
