# polarstory

**Data exploration with polars.**

`polarstory` helps you understand a dataset, investigate individual variables, compare two extracts, and create
standalone
html reports. It works with `polars` DataFrames, LazyFrames, and parquet files.


## Documentation

For guides, examples, and the API reference, visit **[polarstory documentation](https://kpwhri.github.io/polarstory/)**.


## Installation

```bash
pip install polarstory
```

## Getting Started

```python
import polarstory as ps

profile = ps.profile('cohort.parquet')
profile.write_html('cohort_profile.html')
```

Explore particular variables and build a shorter report:

```python
report = ps.Report('Cohort findings')
report.add(profile.summary('age'))
report.add(profile.histogram('age'))
report.add(profile.frequency('enctype'))
report.write_html('findings.html')
```

Compare two datasets:

```python
comparison = ps.compare('cohort_before.parquet', 'cohort_after.parquet')
comparison.write_html('comparison.html')
```

Reports are self-contained html files with static charts. You can open them in a browser, share them with colleagues, or
print them to PDF. `polarstory` also provides command-line tools, a notebook explorer, and optional VS Code and Windows
File Explorer integrations.

> **Working with research data?** Review reports for sensitive information and small cells before sharing. Examples in
> the documentation use synthetic data.

## Development

Run the project's tests with:

```bash
python -m pytest -q
```

The [test guide](tests/README.md) describes the independent statistical reference checks.
