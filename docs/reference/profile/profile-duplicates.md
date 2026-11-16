# `Profile.duplicates`

<!-- API: polarstory.profile.Profile.duplicates -->

::: polarstory.profile.Profile.duplicates
    options:
      members: false
      show_root_heading: true
      show_root_full_path: false
      separate_signature: true


## Example

```python
p = ps.profile(df, mode='full')
report.add(p.duplicates())
```


## Research note

Repeated records can be valid in longitudinal or encounter-level data. Exact duplicate checks can be expensive.


[← Profiling API](index.md)
