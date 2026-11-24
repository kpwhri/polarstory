# `Report.add_html`

<!-- API: polarstory.report.Report.add_html -->

::: polarstory.report.Report.add_html
    options:
      members: false
      show_root_heading: true
      show_root_full_path: false
      separate_signature: true


## Example

```python
report.add_html(
    '<p>Results are <strong>preliminary</strong>.</p>',
    title='Interpretation',
)
```

HTML fragments are inserted without escaping, sanitization, or modification. Only include trusted HTML. Use [`Report.add_text()`](report-add_text.md) for ordinary text that should be escaped.

External HTML may bring its own styles, scripts, or resource dependencies. The caller is responsible for internal HTML identifiers and resource availability. HTML components cannot be regenerated from JSON report recipes.

[← Reports API](index.md)
