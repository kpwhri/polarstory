# MacOS Finder Integration

Polarstory can add **Quick Actions** to Finder so you can profile a Parquet file without opening a terminal. This integration is optional and installs only for your macOS user account.

## Install

Install polarstory in the Python environment you want to use, then run:

```bash
pip install polarstory
polarstory integration macos install
```

The installer creates five Finder actions: **Inspect Metadata**, **Quick Profile**, **Standard Profile**, **Full Profile**, and **Advanced Diagnostics**.

Right-click a local `.parquet` file in Finder and select **Quick Actions → polarstory - Standard Profile**, or choose another action. Reports open in your browser when complete. Advanced Diagnostics lets you choose a diagnostic.

If the actions do not appear, check Finder's **Quick Actions** settings and enable the polarstory actions. They may also appear under the **Services** menu, depending on your macOS version and Finder configuration.

## Check or remove the integration

```bash
polarstory integration macos status
polarstory integration macos uninstall
```

The actions use the Python interpreter that was active when you installed them. If you move or replace that environment, run `polarstory integration macos install` again.

To use a different installed Python interpreter or a configuration file, supply `--python /path/to/python` or `--config /path/to/polarstory.toml` during installation.

## If something goes wrong

The actions run without a Terminal window. Failures produce a MacOS alert and are logged at:

```text
~/Library/Logs/polarstory/integration.log
```

For more detail, run the corresponding [CLI command](cli.md) in Terminal. For configuration options, see the [CLI reference](../reference/cli.md#configuration-example).
