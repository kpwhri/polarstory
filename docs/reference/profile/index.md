# Profiling API

Create profiles from polars dataframes or parquet files, inspect cached summaries, and reuse individual outputs in reports.

Start with [`ps.profile()`](profile.md). Prefer named methods such as [`p.frequency()`](profile-frequency.md) over generic string-based dispatch.

| API | Description |
| --- | --- |
| [`profile`](profile.md) | Create an automatically profiled polars DataFrame/LazyFrame/parquet file |
| [`profile_from_spec`](profile-from-spec.md) | Recompute a parquet profile from a previously saved JSON recipe |
| [`Profile`](profile-class.md) | Defer evaluation and reuse aggregate summaries across profile sections |
| [`ProfileOptions`](profile-options.md) | Options for low-cost univariate profiling and offline HTML output |
| [`VariableProfile`](variable-profile.md) | A cached table and optional static figure for a selected column |
| [`Profile.overview`](profile-overview.md) | Return one-row dataset counts and overall null percentage |
| [`Profile.inventory`](profile-inventory.md) | Column inventory with semantic type, label and null percentage |
| [`Profile.missingness`](profile-missingness.md) | Return per-column null counts and percentages as a polars table |
| [`Profile.alerts`](profile-alerts.md) | Return descriptive data-quality alerts for the selected variables |
| [`Profile.variable`](profile-variable.md) | Return a cached summary and optional chart for one variable |
| [`Profile.item`](profile-item.md) | Get one cached reusable component without building a full profile |
| [`Profile.variable_items`](profile-variable_items.md) | Retrieve the default reusable components for one variable |
| [`Profile.summary`](profile-summary.md) | Return the reusable descriptive table for one variable |
| [`Profile.frequency`](profile-frequency.md) | Return category counts, including for discrete numeric variables |
| [`Profile.histogram`](profile-histogram.md) | Return a numeric histogram as a reusable chart component |
| [`Profile.distribution`](profile-distribution.md) | Return the default static distribution chart for a variable |
| [`Profile.timeline`](profile-timeline.md) | Return a Date/Datetime timeline as a reusable chart component |
| [`Profile.text_length`](profile-text_length.md) | Return a text-length distribution chart |
| [`Profile.category_diagnostics`](profile-category_diagnostics.md) | Return rare-category and dominance statistics for one variable |
| [`Profile.outliers`](profile-outliers.md) | Return an IQR outlier-count table for a numeric variable |
| [`Profile.missingness_chart`](profile-missingness_chart.md) | Return the aggregate missingness chart for selected variables |
| [`Profile.missingness_patterns`](profile-missingness_patterns.md) | Return bounded combinations of null indicators across variables |
| [`Profile.missingness_associations`](profile-missingness_associations.md) | Return pairwise phi coefficients between null indicators |
| [`Profile.missingness_associations_chart`](profile-missingness_associations_chart.md) | Return a static heatmap of missingness phi coefficients |
| [`Profile.uniqueness`](profile-uniqueness.md) | Return approximate distinct counts for selected variables |
| [`Profile.duplicates`](profile-duplicates.md) | Return opt-in exact duplicate-row counts for the source |
| [`Profile.items`](profile-items.md) | All profile components, in deterministic display order |
| [`Profile.show`](profile-show.md) | Preview one variable, or the whole profile when name is omitted |
| [`Profile.explore`](profile-explore.md) | Open the optional notebook explorer or return its controller |
| [`Profile.to_report`](profile-to_report.md) | Group automatic profiling outputs into navigable sections |
| [`Profile.to_html`](profile-to_html.md) | Render the complete static profile as a standalone HTML string |
| [`Profile.write_html`](profile-write_html.md) | Write a standalone, print-friendly HTML profile |
| [`Profile.to_spec`](profile-to_spec.md) | Serializable **recomputable** specification for a parquet profile |
| [`Profile.write_spec`](profile-write_spec.md) | Save a JSON recipe; file paths are relative to the spec directory |
| [`Profile.refresh`](profile-refresh.md) | Build a new profile snapshot with empty calculation caches |
| [`VariableProfile.report_items`](variableprofile-report_items.md) | Reusable summary and distribution components for this variable |
| [`VariableProfile.chart`](variableprofile-chart.md) | Build a static chart only when requested, then reuse it |
| [`VariableProfile.show`](variableprofile-show.md) | Preview this variable in a notebook or a local browser |
