# CLI reference

Run the CLI with `polarstory` or `python -m polarstory` in an environment where the package is installed.

## Commands

| Command                                         | Purpose                                     |
|-------------------------------------------------|---------------------------------------------|
| `inspect SOURCE`                                | Inspect parquet schema and file metadata    |
| `profile SOURCE`                                | Create an automatic HTML report             |
| `diagnose SOURCE`                               | Generate a selected diagnostic report       |
| `reproduce RECIPE.json`                         | Regenerate a supported saved report         |
| `integration windows install`                   | Register optional per-user Explorer submenu |
| `integration windows status`                    | Show integration status                     |
| `integration windows uninstall`                 | Remove integration                          |
| `integration macos install`                     | Install Finder Quick Actions                |
| `integration macos status`                      | Check Finder integration                    |
| `integration macos uninstall`                   | Remove Finder Quick Actions                 |
| `integration linux install --manager MANAGER`   | Install Nautilus or Dolphin actions         |
| `integration linux status --manager MANAGER`    | Check Linux integration                     |
| `integration linux uninstall --manager MANAGER` | Remove Linux integration                    |

For setup instructions, see the [macOS Finder guide](../guides/macos.md) or [Linux file manager guide](../guides/linux.md).

## `profile` flags

| Flag                           | Description                                |
|--------------------------------|--------------------------------------------|
| `--mode quick\|standard\|full` | Select profiling depth                     |
| `--columns 'ins_*,sex_admin'`  | Comma-separated column name patterns       |
| `--max-columns N`              | Limit profiled columns                     |
| `--max-categories N`           | Categories in frequency tables             |
| `--max-frequency-unique N`     | Frequency cardinality guard                |
| `--max-groups N`               | Grouped table limit                        |
| `--max-chart-groups N`         | Grouped plot limit                         |
| `--no-charts`                  | Disable plot generation                    |
| `--write-spec PATH`            | Save profile regeneration recipe           |
| `--config PATH`                | Read explicit TOML configuration           |
| `-o, --output PATH`            | Select report destination                  |
| `--open` / `--no-open`         | Control browser opening                    |
| `--force`                      | Allow overwrite of explicitly named output |
| `--progress`                   | Print phase messages to stderr             |

## `inspect` flags

`--count-rows`, `--html`, `--open`, `--config`, `-o/--output`, and `--force`.

## `diagnose` flags

`--type missingness|numeric|categorical|quality|associations`, or `--choose` for a desktop selection dialog; also
`--max-columns`, `--config`, `-o/--output`, `--open`, `--force`, and `--progress`.

## `reproduce` flags

`--config`, `-o/--output`, `--open`, `--force`, and `--progress`.

## Configuration Example

```toml
[profile]
mode = 'standard'
max_columns = 50
max_categories = 15
max_groups = 50
max_chart_groups = 20

[report]
open = false
output_directory = 'reports'
```

Save as `polarstory.toml` or provide `--config`. Explicit CLI flags take precedence over TOML values, which take
precedence over built-in defaults. See [CLI usage](../guides/cli.md).

## Dataset Comparison

```powershell
polarstory compare older.parquet newer.parquet --open
```

See [Comparison API](comparison/index.md).
