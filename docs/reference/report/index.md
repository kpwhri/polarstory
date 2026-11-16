# Reports API

Collect selected tables, static charts, and prose into one offline, print-friendly HTML file.

| API | Description |
| --- | --- |
| [`Report`](report.md) | Ordered static tables, charts and text, independent of input datasets |
| [`ReportItem`](report-item.md) | A small, reusable result and presentation metadata |
| [`Report.section`](report-section.md) | Group subsequent additions under a named heading |
| [`Report.add`](report-add.md) | Insert a component or a complete variable profile |
| [`Report.add_table`](report-add_table.md) | Add an aggregated polars table to the current section |
| [`Report.add_chart`](report-add_chart.md) | Add a static Matplotlib figure to the current section |
| [`Report.add_text`](report-add_text.md) | Add a plain-text paragraph; HTML is escaped on rendering |
| [`Report.add_table1`](report-add_table1.md) | Compute and insert one formatted descriptive Table 1 (no p-values) |
| [`Report.add_profile`](report-add_profile.md) | Append sections from a Profile or a dataframe/path, without raw rows |
| [`Report.remove`](report-remove.md) | Remove an item from any section by its stable ID |
| [`Report.move`](report-move.md) | Reorder an item; `before` can also target another section |
| [`Report.items`](report-items.md) | All items in their current display order |
| [`Report.to_html`](report-to_html.md) | Return a complete offline HTML document as a string |
| [`Report.write_html`](report-write_html.md) | Write a self-contained HTML report, creating directories if needed |
| [`Report.to_spec`](report-to_spec.md) | Return a **recomputable** recipe for a file-backed curated report |
| [`Report.write_spec`](report-write_spec.md) | Write a portable recipe, using source paths relative to the JSON |
| [`Report.from_spec`](report-from_spec.md) | Regenerate a curated report from a JSON recipe and parquet files |
| [`ReportItem.to_html`](reportitem-to_html.md) | Render only this component as a standalone HTML document |
| [`ReportItem.show`](reportitem-show.md) | Preview this component in a notebook or a local browser |
