# API reference

Each public function or method has its **own reference page**. Signatures and docstrings come from the Python source; each page can include a short research example. Start with a workflow guide if you want a complete analysis.

| API area | Main entry points |
| --- | --- |
| [Automatic profiling](profile/index.md) | `ps.profile()`, `Profile`, `ProfileOptions` |
| [Variable exploration](explorer/index.md) | `ps.explore()`, `Explorer.preview()` |
| [Curated reports](report/index.md) | `Report`, `Report.add()`, `Report.write_html()` |
| [Statistics and diagnostics](stats/index.md) | `ps.stats.frequency()`, `stats.table1()`, missingness diagnostics |
| [Static plots](plots/index.md) | `ps.plots.histogram()`, `ps.plots.frequency()` |
| [Variable metadata](variables/index.md) | `Variables`, `Variables.set()`, `Variable` |
| [Dataset comparison](comparison/index.md) | `ps.compare()`, `DatasetComparison` |
| [parquet inspection](inspect/index.md) | `ps.inspect()`, `Inspection` |
| [Quality alerts](alerts/index.md) | `Alert`, alert helpers |
| [CLI commands](cli.md) | Inspect, profile, diagnose, reproduce, integrations |

## Conventions

- **Inputs:** polars DataFrame, LazyFrame, or supported local parquet source, unless the method specifies otherwise
- **Tables:** polars DataFrames containing descriptive results
- **Charts:** Static Matplotlib figures, rendered as SVG in HTML reports
- **Report components:** `ReportItem` objects can be added with `Report.add()`
- **Privacy:** Aggregates may still disclose small cells or identifying categories; review outputs before sharing

Examples assume `import polarstory as ps` and an existing polars dataframe named `df`, unless the snippet shows a file path.

Signatures are generated from source using mkdocstrings. This makes documentation updates follow changes to Python functions without retyping parameters. See [documentation maintenance](../documentation.md).
