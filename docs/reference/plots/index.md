# Static plots API

Create static Matplotlib figures for embedding in standalone HTML or printed reports.

These functions return Matplotlib `Figure` objects. The HTML renderer embeds them as SVG.

| API | Description |
| --- | --- |
| [`frequency`](frequency.md) | Horizontal bar chart of the most frequent categorical values |
| [`histogram`](histogram.md) | Aggregate histogram bin counts lazily without collecting raw values |
| [`missingness`](missingness.md) | Compact null percentage chart (not a record-level heat map) |
| [`temporal`](temporal.md) | Counts per month for Date/Datetime columns, keeping output bounded |
| [`text_length`](text_length.md) | Distribution of character lengths, without exporting any text values |
| [`grouped_numeric`](grouped_numeric.md) | Show group medians and interquartile ranges using summary statistics |
| [`grouped_frequency`](grouped_frequency.md) | Plot grouped percentages from a bounded tidy contingency table |
| [`missingness_associations`](missingness_associations.md) | Static phi-correlation heatmap from aggregated missingness statistics |
