# Statistics and diagnostics API

Reuse descriptive statistics as polars DataFrames, including Table 1 and opt-in dataset diagnostics.

These functions return polars DataFrames. `table1` is also available as `ps.stats.table1`. Functions from `polarstory.diagnostics` are opt-in and may require costly scans.

| API | Description |
| --- | --- |
| [`overview`](overview.md) | Dataset-level record count, column count, and null cell count |
| [`missingness`](missingness.md) | One row per variable; null and NaN are deliberately not conflated |
| [`frequency`](frequency.md) | Top frequency categories, an optional null row, and an Other remainder |
| [`numeric`](numeric.md) | One-row numeric summary with null and floating NaN counts separated |
| [`temporal`](temporal.md) | One-row summary for Date/Datetime/Time/Duration columns |
| [`text`](text.md) | Profile text length and emptiness without exporting example strings |
| [`crosstab`](crosstab.md) | Tidy two-way counts/percentages, with explicit denominator semantics |
| [`summary`](summary.md) | Tidy descriptive summaries, with grouped numeric metrics in one query |
| [`cramers_v`](cramers_v.md) | Bias-corrected or ordinary association between two categorical variables |
| [`correlations`](correlations.md) | Pairwise numeric correlations in tidy form (opt-in; never in quick mode) |
| [`outliers`](outliers.md) | Count IQR-rule outliers among finite observations of one numeric column |
| [`categorical_diagnostics`](categorical_diagnostics.md) | Bounded rare-category and imbalance statistics, without category values |
| [`table1`](table1.md) | Return a wide, formatted descriptive Table 1 |
| [`missingness_patterns`](missingness_patterns.md) | Most frequent missingness combinations, with a remainder row |
| [`missingness_associations`](missingness_associations.md) | Pairwise phi coefficients between binary missingness indicators |
| [`duplicates`](duplicates.md) | Exact excess duplicate rows, including the first row in each group once |
| [`uniqueness`](uniqueness.md) | Distinct *non-null* values and ratios, exact or approximate |
