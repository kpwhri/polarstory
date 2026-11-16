# `alerts.from_missingness`

<!-- API: polarstory.alerts.from_missingness -->

::: polarstory.alerts.from_missingness
    options:
      members: false
      show_root_heading: true
      show_root_full_path: false
      separate_signature: true


## Example

```python
missing = ps.stats.missingness(df)
alerts = ps.alerts.from_missingness(missing, rows=df.height)
```

[← Quality alerts API](index.md)
