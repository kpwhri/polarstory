# Command line and desktop integrations

The CLI makes profiling accessible when there is no active Python script. Run it in the same environment where
polarstory is installed.

## Basic commands

```powershell
python -m polarstory inspect cohort.parquet
python -m polarstory inspect cohort.parquet --html --open
python -m polarstory profile cohort.parquet --mode quick --open
python -m polarstory profile cohort.parquet --mode standard --open
python -m polarstory profile cohort.parquet --mode full --open
```

Use `polarstory` in place of `python -m polarstory` when the console command is on your PATH.

Reports receive predictable filenames beside the source by default. Existing output files are not silently replaced;
explicit output filenames require `--force` to overwrite.

## Advanced diagnostics

```powershell
python -m polarstory diagnose cohort.parquet --type missingness --open
python -m polarstory diagnose cohort.parquet --type numeric --open
python -m polarstory diagnose cohort.parquet --type categorical --open
python -m polarstory diagnose cohort.parquet --type quality --open
python -m polarstory diagnose cohort.parquet --type associations --open
```

These commands reuse existing descriptive statistics. They are not hypothesis-testing workflows.

## Limit a report

```powershell
python -m polarstory profile cohort.parquet --mode standard --max-columns 25
python -m polarstory profile cohort.parquet --columns "ins_*,sex_admin"
python -m polarstory profile cohort.parquet -o output/cohort.html
```

CLI `--columns` accepts comma-separated name patterns using shell-style wildcards. Python `profile(columns=...)` also
accepts polars selectors; the two interfaces are not identical.

## VS Code right-click menu

The extension lives in the project's top-level `vscode/` directory, separate from the Python wheel. To test it without
packaging:

1. Open `vscode/` as a VS Code folder.
2. Press **F5** to open an Extension Development Host.
3. In the development host, open a folder containing a `.parquet` file.
4. Select a Python interpreter with polarstory installed.
5. Right-click the file, select **polarstory**, and choose Inspect, Quick, Standard, Full, or Advanced diagnostics.

See `vscode/README.md` in the source repository for development instructions.

## Windows File Explorer

The Windows integration is optional and uses per-user registry entries:

```powershell
python -m polarstory integration windows install
python -m polarstory integration windows status
python -m polarstory integration windows uninstall
```

On Windows 11, the menu may be under **Show more options** (or hold shift while right clicking). Installation registers
the Python executable from the current environment. Reinstall after changing environments or moving that executable.

See also [CLI reference](../reference/cli.md).

## MacOS Finder

Add right-click Quick Actions for profiling Parquet files in Finder.

See [MacOS Finder Integration](macos.md) for installation, usage, and troubleshooting.

## Linux File Managers

Add right-click actions to GNOME Files (Nautilus) or KDE Dolphin.

See [Linux File Manager Integration](linux.md) for installation, usage, and troubleshooting.

## Compare extracts

```powershell
polarstory compare older.parquet newer.parquet --open
```

See [Compare two datasets](comparing.md).
