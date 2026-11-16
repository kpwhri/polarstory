# `ReportItem`

<!-- API: polarstory.report.ReportItem -->

::: polarstory.report.ReportItem
    options:
      members: false
      show_root_heading: true
      show_root_full_path: false
      separate_signature: true


A report item contains an already-aggregated polars table, static Matplotlib figure, or short text. Prefer obtaining it from a `Profile` method rather than constructing one manually.


## Example

```python
item = p.frequency('enctype')
report.add(item)
```

[← Reports API](index.md)
