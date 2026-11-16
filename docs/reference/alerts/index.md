# Quality alerts API

Inspect and reuse descriptive quality-alert records; a warning does not imply an invalid clinical record.

| API | Description |
| --- | --- |
| [`Alert`](alert.md) | API definition and return type |
| [`scan`](scan.md) | Check missingness; optionally compute expensive exact cardinalities |
| [`to_frame`](to_frame.md) | Convert a sequence of structured quality alerts to a polars DataFrame |
| [`from_missingness`](from_missingness.md) | Create missingness alerts from previously computed aggregate counts |
| [`from_metrics`](from_metrics.md) | Infer descriptive warnings without triggering additional scans |
| [`from_frequency`](from_frequency.md) | Identify categorical dominance from an existing frequency table |
