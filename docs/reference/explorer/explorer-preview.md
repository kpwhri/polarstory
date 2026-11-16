# `Explorer.preview`

<!-- API: polarstory.explorer.Explorer.preview -->

::: polarstory.explorer.Explorer.preview
    options:
      members: false
      show_root_heading: true
      show_root_full_path: false
      separate_signature: true


## Example

```python
explorer = ps.explore(df, show=False)
summary = explorer.preview('age', by='facility', view='summary')
```


## Research note

Grouping supports 50 levels in summary tables by default, but only 20 in grouped charts. Choose a smaller group subset for charts.


[← Variable exploration API](index.md)
