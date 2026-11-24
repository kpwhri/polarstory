# Save and Reproduce Reports

A saved recipe records how to regenerate results from a parquet source. It does **not** contain the underlying rows or a
frozen copy of the source file.

## Automatic Profile Recipe

```python
import polarstory as ps

p = ps.profile('cohort.parquet', mode='standard')
p.write_html('cohort.html')
p.write_spec('cohort.json')

# later: compute a new report from the saved configuration
ps.profile_from_spec('cohort.json').write_html('cohort_updated.html')
```

## Curated Report Recipe

```python
p = ps.profile('cohort.parquet')
report = ps.Report('Selected findings')
report.add(p.summary('age'))
report.add(p.frequency('enctype'))
report.write_spec('selected.json')

ps.Report.from_spec('selected.json').write_html('selected_updated.html')
```

Recomputable report recipes support file-backed profile components, descriptive Table 1 results from parquet without
custom variable metadata, and plain text.

Custom polars tables, externally created figures, great tables, and raw html components have no recomputable recipe. A
report containing one of these components raises an error when saved as a json recipe. Retain the Python script that
builds the report and save the rendered output with `Report.write_html()`.

## Command Line Regeneration

```powershell
python -m polarstory reproduce selected.json --open
```

Source paths in recipes are interpreted relative to the recipe location where supported. Moving a recipe without its
referenced data can break regeneration. Source files should remain stable while a profile is calculated.

For audit trails, keep the data-extract version, analysis code, and recipe together. Treat generated HTML as an output
artifact, not a substitute for the input data or analysis script.
