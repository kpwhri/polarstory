# `ps.profile`

::: polarstory.profile.profile
    options:
      members: false
      show_root_heading: true
      show_root_full_path: false
      separate_signature: true

## Example

```python
import polarstory as ps

p = ps.profile('cohort.parquet', mode='standard')
p.write_html('cohort.html')
```

[← Profiling API](index.md)
