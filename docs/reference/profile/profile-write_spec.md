# `Profile.write_spec`

<!-- API: polarstory.profile.Profile.write_spec -->

::: polarstory.profile.Profile.write_spec
    options:
      members: false
      show_root_heading: true
      show_root_full_path: false
      separate_signature: true


## Example

```python
p = ps.profile('cohort.parquet')
p.write_spec('cohort.json')
```


## Research note

Recipes refer to data files and recompute statistics; they do not preserve a frozen data snapshot.


[← Profiling API](index.md)
