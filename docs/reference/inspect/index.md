# File inspection API

Inspect parquet schema and file information without constructing a complete statistical profile.

| API | Description |
| --- | --- |
| [`inspect`](inspect.md) | Inspect schema and source size without reading column data by default |
| [`Inspection`](inspection.md) | API definition and return type |
| [`Inspection.to_report`](inspection-to_report.md) | Convert the metadata inspection into a small static report |
| [`Inspection.to_html`](inspection-to_html.md) | Return an HTML string displaying inspected file metadata |
| [`Inspection.write_html`](inspection-write_html.md) | Save the metadata inspection as a standalone HTML file |
