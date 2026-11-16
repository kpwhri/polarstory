# `plots.grouped_frequency`

<!-- API: polarstory.plots.grouped_frequency -->

::: polarstory.plots.grouped_frequency
    options:
      members: false
      show_root_heading: true
      show_root_full_path: false
      separate_signature: true


## Example

```python
rows = ps.stats.crosstab(df, 'enctype', by='cohort')
figure = ps.plots.grouped_frequency(rows, title='Encounters by cohort')
```

[← Static plots API](index.md)
