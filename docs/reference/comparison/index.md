# Dataset comparison API

Compare two polars DataFrames, LazyFrames, or parquet datasets using descriptive
statistics. All calculated tables can be reused in curated static reports.

| API | Description |
| --- | --- |
| [`compare`](compare.md) | Create a comparison from two sources |
| [`DatasetComparison`](datasetcomparison.md) | Reusable comparison object |
| [`overview`](overview.md) | Dataset row and column counts |
| [`schema_changes`](schema_changes.md) | Added, removed, and changed dtypes |
| [`missingness`](missingness.md) | Null counts and percentage-point differences |
| [`numeric`](numeric.md) | Numeric summary differences |
| [`categorical`](categorical.md) | Bounded categorical frequency differences |
| [`skipped`](skipped.md) | Category-level comparisons omitted for safeguards |
| [`to_report`](to_report.md) | Create a curated `Report` |
| [`to_html`](to_html.md) | Render complete HTML in memory |
| [`write_html`](write_html.md) | Write an offline HTML report |

See [the comparison guide](../../guides/comparing.md) for practical usage.
