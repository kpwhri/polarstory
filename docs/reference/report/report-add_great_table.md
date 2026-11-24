# `Report.add_great_table`

<!-- API: polarstory.report.Report.add_great_table -->

::: polarstory.report.Report.add_great_table
    options:
      members: false
      show_root_heading: true
      show_root_full_path: false
      separate_signature: true


## Installation

Great Tables is optional; install it separately:

```bash
pip install great-tables
```

## Example

```python
import polars as pl
from great_tables import GT

frequency = pl.DataFrame({'enctype': ['ED', 'Inpatient'], 'count': [1200, 350]})
table = (
    GT(frequency)
    .tab_header(title='Encounter types')
    .fmt_number(columns='count', decimals=0)
)
report.add_great_table(table)
```

Optional report-level metadata can also be supplied:

```python
report.add_great_table(
    table,
    title='Encounter counts',
    caption='Table 1. Encounter types.',
    notes='Counts represent encounters, not unique patients.',
    id='encounters',
)
```

## Notes

Great Tables renders the table using `as_raw_html()`; polarstory inserts the resulting HTML fragment. Configure formatting through Great Tables. The native `Report.max_table_rows` limit does not apply to external tables.

Static tables are recommended for offline and printable reports. Interactive tables and external resources may introduce dependencies. Use trusted content and check small cells and identifiers before sharing.

Great Tables components cannot be regenerated from JSON report recipes. Retain the Python script that creates the table.

See the [Great Tables documentation](https://posit-dev.github.io/great-tables/) for formatting options, or [`Report.add_html()`](report-add_html.md) for arbitrary HTML fragments.

[← Reports API](index.md)
