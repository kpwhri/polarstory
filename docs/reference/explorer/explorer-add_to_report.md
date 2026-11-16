# `Explorer.add_to_report`

<!-- API: polarstory.explorer.Explorer.add_to_report -->

::: polarstory.explorer.Explorer.add_to_report
    options:
      members: false
      show_root_heading: true
      show_root_full_path: false
      separate_signature: true


## Example

```python
explorer = ps.explore(df, show=False)
explorer.add_to_report('enctype', view='distribution')
explorer.report.write_html('findings.html')
```


[← Variable exploration API](index.md)
