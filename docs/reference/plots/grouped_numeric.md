# `plots.grouped_numeric`

<!-- API: polarstory.plots.grouped_numeric -->

::: polarstory.plots.grouped_numeric
    options:
      members: false
      show_root_heading: true
      show_root_full_path: false
      separate_signature: true


## Example

```python
rows = ps.stats.summary(df, ['age'], by='cohort')
figure = ps.plots.grouped_numeric(rows, title='Age by cohort')
```

[← Static plots API](index.md)
