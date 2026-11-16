# `Report.add_chart`

<!-- API: polarstory.report.Report.add_chart -->

::: polarstory.report.Report.add_chart
    options:
      members: false
      show_root_heading: true
      show_root_full_path: false
      separate_signature: true


## Example

```python
figure = ps.plots.histogram(df, 'age')
report.add_chart(figure, title='Age distribution')
```


## Research note

Only aggregated plots should be shared when observations are sensitive.


[← Reports API](index.md)
