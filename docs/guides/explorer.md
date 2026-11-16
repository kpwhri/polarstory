# Explore individual variables

The optional explorer works with an existing polars dataset in VS Code's Jupyter notebook or Python Interactive Window. It reuses the same tables and static charts as automatic profiles.

## Launch the explorer

Install the optional notebook dependencies, then:

```python
import polarstory as ps

p = ps.profile('cohort.parquet')
report = ps.Report('Selected findings')

explorer = p.explore(report=report)
```

Choose a variable, select an appropriate view, and use **Add to Report** to save that output. Export the report whenever you are ready:

```python
report.write_html('findings.html')
```

## Quick previews without widgets

```python
p.show('age')
p.histogram('age').show()
p.frequency('enctype').show()
```

`show()` previews in a notebook or local browser as appropriate. The underlying output is ordinary HTML and SVG.

## Stratify by a categorical variable

```python
explorer = p.explore(show=False)

# the complete summary may include up to 50 groups by default
summary = explorer.preview(
    'age', by='facility', view='summary',
)

# choose a smaller subset for a readable chart
chart = explorer.preview(
    'age', by='facility', view='distribution',
    groups=['Clinic A', 'Clinic B'],
)
```

**Group defaults:** `max_groups=50` for summary tables and `max_chart_groups=20` for charts. Use `ProfileOptions` to change either limit. A grouping variable with 33 values is permitted in a summary table, but a 33-group plot is usually difficult to read.

## Add a configured result programmatically

```python
explorer.add_to_report(
    'age', by='facility', view='summary',
    groups=['Clinic A', 'Clinic B'],
)

explorer.report.write_html('facility_summary.html')
```

Only aggregated results should be sent to the report. Review combinations of group sizes and sensitive variables before sharing.
