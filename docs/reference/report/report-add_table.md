# `Report.add_table`

<!-- API: polarstory.report.Report.add_table -->

::: polarstory.report.Report.add_table
    options:
      members: false
      show_root_heading: true
      show_root_full_path: false
      separate_signature: true


## Example

```python
table = ps.stats.frequency(df, 'enctype')
report.add_table(table, title='Encounter types')
```


## Research note

Custom tables are not automatically de-identified. Review small cells and identifiers before sharing.


[← Reports API](index.md)
