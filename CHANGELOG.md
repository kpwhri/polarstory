# Changelog

Notable changes to `polarstory` are recorded here, following [Keep a Changelog](https://keepachangelog.com/)
and [Semantic Versioning](https://semver.org/).

The versions below outline the intended release series. Release dates and version links will be added when published.

## [Unreleased]

### Added

- Don't open a window when right-click launching in Windows, attempt error handling if fails (e.g., non-parquet file)

## [1.2.0] - 2026-11-16

### Added

- Right-click Windows integration for parquet files + tests
- Generated documentation with mkdocs

## [1.1.0] - 2026-11-16

### Added

- Integrate the VS Code polarstory extension into this repo (exclude from wheel)

## [1.0.0] - 2026-11-16

### Added

- polars dataset profiling, variable exploration, and descriptive statistics
- Standalone html reports with tables and charts
- Dataset comparison, data-quality diagnostics, and cli

[Unreleased]: https://github.com/kpwhri/polarstory/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/kpwhri/polarstory/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/kpwhri/polarstory/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/kpwhri/polarstory/releases/tag/v1.0.0