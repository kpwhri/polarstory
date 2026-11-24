# Linux File Manager Integration

Polarstory can add right-click actions for Parquet files in **GNOME Files (Nautilus)** and **KDE Dolphin**. The integration is optional and installs only for your Linux user account.

## Install

Install polarstory in the Python environment you want to use:

```bash
pip install polarstory
```

Then choose your file manager:

```bash
# GNOME Files / Nautilus
polarstory integration linux install --manager nautilus

# KDE Dolphin
polarstory integration linux install --manager dolphin
```

You can also run `polarstory integration install` to detect a supported desktop automatically. If detection fails, specify `--manager nautilus` or `--manager dolphin`.

## Use the actions

- **Nautilus:** Right-click a local `.parquet` file and select **Scripts → polarstory**, then choose an action.
- **Dolphin:** Right-click a local `.parquet` file and open the **polarstory** submenu.

Both integrations provide **Inspect Metadata**, **Quick Profile**, **Standard Profile**, **Full Profile**, and **Advanced Diagnostics**. Completed reports open in your browser. Advanced Diagnostics lets you choose a diagnostic.

If a menu entry doesn't appear immediately, close and reopen the file manager.

## Check or remove the integration

```bash
polarstory integration linux status --manager nautilus
polarstory integration linux uninstall --manager nautilus

polarstory integration linux status --manager dolphin
polarstory integration linux uninstall --manager dolphin
```

The actions use the Python interpreter from installation time. Reinstall after moving or replacing the environment. Installation also accepts `--python /path/to/python` and `--config /path/to/polarstory.toml`.

## If something goes wrong

The actions do not open a terminal. Failures are logged at:

```text
~/.local/state/polarstory/integration.log
```

If `XDG_STATE_HOME` is set, the log is stored under `$XDG_STATE_HOME/polarstory/` instead. A graphical error dialog appears when **Zenity** or **KDialog** is available; otherwise, inspect the log or run the corresponding [CLI command](cli.md) in a terminal.

For configuration options, see the [CLI reference](../reference/cli.md#configuration-example).
