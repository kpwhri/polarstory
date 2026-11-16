# `stats.table1`

<!-- API: polarstory.table1.table1 -->

::: polarstory.table1.table1
    options:
      members: false
      show_root_heading: true
      show_root_full_path: false
      separate_signature: true


## Example

```python
table = ps.stats.table1(
    df, ['age', 'sex_admin', 'enctype'],
    by='cohort', numeric='median_iqr',
)
```


## Research note

The output is descriptive, without hypothesis tests or p-values; review small-cell counts.


[← Statistics and diagnostics API](index.md)
