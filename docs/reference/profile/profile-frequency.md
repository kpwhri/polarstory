# `Profile.frequency`

<!-- API: polarstory.profile.Profile.frequency -->

::: polarstory.profile.Profile.frequency
    options:
      members: false
      show_root_heading: true
      show_root_full_path: false
      separate_signature: true


## Example

```python
p = ps.profile(df)
report.add(p.frequency('enctype'))
```


## Research note

Frequency tables have a high-cardinality safeguard. A numeric identifier is not necessarily a useful categorical variable.


[← Profiling API](index.md)
