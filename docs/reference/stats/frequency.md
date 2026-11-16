# `stats.frequency`

<!-- API: polarstory.stats.frequency -->

::: polarstory.stats.frequency
    options:
      members: false
      show_root_heading: true
      show_root_full_path: false
      separate_signature: true


## Example

```python
import polarstory as ps

counts = ps.stats.frequency(df, 'enctype', denominator='valid')
```


## Research note

Literal codes such as 'U' remain categories, distinct from polars nulls.


[← Statistics and diagnostics API](index.md)
