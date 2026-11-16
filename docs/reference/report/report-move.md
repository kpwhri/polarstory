# `Report.move`

<!-- API: polarstory.report.Report.move -->

::: polarstory.report.Report.move
    options:
      members: false
      show_root_heading: true
      show_root_full_path: false
      separate_signature: true


## Example

```python
first = report.add(p.summary('age'))
second = report.add(p.frequency('enctype'))
report.move(second.id, before=first.id)
```

[← Reports API](index.md)
