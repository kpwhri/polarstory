# `ProfileOptions`

<!-- API: polarstory.profile.ProfileOptions -->

::: polarstory.profile.ProfileOptions
    options:
      members: false
      show_root_heading: true
      show_root_full_path: false
      separate_signature: true


## Common settings

| Option | Default | Description |
| --- | ---: | --- |
| `max_categories` | `15` | Displayed categorical levels |
| `max_groups` | `50` | Maximum distinct groups in tables |
| `max_chart_groups` | `20` | Maximum groups in charts |
| `histogram_bins` | `20` | Histogram bins |
| `max_unique_for_frequency` | `1000` | Guard on frequency-cardinality analysis |
| `include_sensitive` | `False` | Explicit opt-in for sensitive-value display |
| `include_missingness_diagnostics` | `False` | Optional full-data missingness analysis |
| `include_duplicates` | `False` | Optional exact duplicate checks |
| `batch_size` | `24` | Columns per metrics batch |

For the complete defaults and types, refer to the automatically generated class definition above.


## Example

```python
import polarstory as ps

options = ps.ProfileOptions(max_categories=15, max_groups=50, max_chart_groups=20)
p = ps.profile(df, options=options)
```


## Research note

Increasing group or category limits can make reports slower and charts harder to read. The 50-group table and 20-group chart limits are independent.


[← Profiling API](index.md)
