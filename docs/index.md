# polarstory

**Explore polars datasets and share clear, static html reports.**

polarstory helps researchers inspect a dataframe or parquet dataset, review its variables, and select tables and figures
for a project report. Its reports use ordinary html tables and embedded SVG figures, with no JavaScript required.

## Start here

| I want to…                          | Read                                    |
|-------------------------------------|-----------------------------------------|
| Generate a complete profile         | [Getting started](getting-started.md)   |
| Understand one variable             | [Explore variables](guides/explorer.md) |
| Assemble selected results           | [Build a report](guides/reports.md)     |
| Profile a file without Python code  | [CLI and integrations](guides/cli.md)   |
| Review healthcare research examples | [Cohort overview](examples/cohort.md)   |
| Find a function or parameter        | [API reference](reference/index.md)     |

## Three core workflows

### Automatic profiling

```python
import polarstory as ps

ps.profile('cohort.parquet').write_html('cohort.html')
```

### Explore individual variables

```python
p = ps.profile('cohort.parquet')
p.show('age')

# optional interactive explorer in a VS Code notebook
p.explore()
```

### Share selected findings

```python
report = ps.Report('Cohort summary')
report.add(p.histogram('age'))
report.add(p.frequency('enctype'))
report.write_html('team_summary.html')
```
