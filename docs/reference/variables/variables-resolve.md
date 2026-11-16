# `Variables.resolve`

<!-- API: polarstory.variables.Variables.resolve -->

::: polarstory.variables.Variables.resolve
    options:
      members: false
      show_root_heading: true
      show_root_full_path: false
      separate_signature: true


## Example

```python
variables = ps.Variables().set('enctype', label='Encounter type')
metadata = variables.resolve(df)
```

[← Variable metadata API](index.md)
