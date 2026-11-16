# `Report.section`

<!-- API: polarstory.report.Report.section -->

::: polarstory.report.Report.section
    options:
      members: false
      show_root_heading: true
      show_root_full_path: false
      separate_signature: true


## Example

```python
with report.section('Baseline characteristics'):
    report.add(p.summary('age'))
    report.add(p.histogram('age'))
```


[← Reports API](index.md)
