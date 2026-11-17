"""Per-user cascading File Explorer submenu for local Parquet files."""

from __future__ import annotations

import argparse
import io
import os
import subprocess
import sys
import tempfile
import traceback
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path

_REGISTRY_PATH = r'Software\Classes\SystemFileAssociations\.parquet\shell\polarstory'
_LEGACY_PATH = _REGISTRY_PATH + '.profile'
_ACTIONS = {
    'inspect': 'Inspect Metadata',
    'quick': 'Quick Profile',
    'standard': 'Standard Profile',
    'full': 'Full Profile',
    'advanced': 'Advanced Diagnostics...',
}


def _pythonw(executable: Path) -> Path:
    """Prefer pythonw.exe, falling back to the selected Python interpreter."""
    if executable.name.lower() == 'pythonw.exe':
        return executable
    windowed = executable.with_name('pythonw.exe')
    if windowed.is_file():
        return windowed
    return executable


def _action_args(action: str, source: str, config: str | Path | None = None) -> list[str]:
    """Translate Explorer actions into the existing polarstory CLI options."""
    if action not in _ACTIONS:
        raise ValueError(f'Invalid polarstory action: {action}')
    if action == 'inspect':
        args = ['inspect', source, '--html', '--open']
    elif action == 'advanced':
        args = ['diagnose', source, '--choose', '--open']
    else:
        args = ['profile', source, '--mode', action, '--open']
    if config is not None:
        args.extend(['--config', str(config)])
    return args


def command(*, python: str | Path | None = None, mode: str = 'standard',
            config: str | Path | None = None, action: str | None = None,
            windowed: bool = False) -> str:
    """Build a quoted Explorer command; windowed mode includes error reporting.

    The console form remains available for troubleshooting. ``install()``
    registers the windowed form on Windows.
    """
    requested = action if action is not None else mode
    if requested not in _ACTIONS:
        raise ValueError(f'Invalid polarstory action: {requested}')
    executable = Path(python or sys.executable).expanduser().resolve()
    if not executable.is_file():
        raise FileNotFoundError(f'Python interpreter not found: {executable}')
    config_file = None
    if config is not None:
        config_file = Path(config).expanduser().resolve()
        if not config_file.is_file():
            raise FileNotFoundError(f'Configuration file not found: {config_file}')

    if windowed:
        prefix = subprocess.list2cmdline([
            str(_pythonw(executable)), '-m', 'polarstory.integrations.windows',
            'run', requested,
        ])
        suffix = ['--config', str(config_file)] if config_file else []
        return prefix + ' "%1"' + (' ' + subprocess.list2cmdline(suffix) if suffix else '')

    args = _action_args(requested, '%1', config_file)
    prefix = subprocess.list2cmdline([str(executable), '-m', 'polarstory', args[0]])
    # preserve the selected-file placeholder for Explorer substitution
    return prefix + ' "%1" ' + subprocess.list2cmdline(args[2:])


def _error_log() -> Path:
    """Keep integration errors in the user's local profile, not beside data."""
    candidates = [os.environ.get('LOCALAPPDATA'), tempfile.gettempdir()]
    for root in candidates:
        if not root:
            continue
        try:
            directory = Path(root) / 'polarstory'
            directory.mkdir(parents=True, exist_ok=True)
            return directory / 'windows.log'
        except OSError:
            continue
    raise OSError('Unable to create a polarstory error-log directory')


def _write_error(action: str, source: str, details: str) -> Path | None:
    """Append a diagnostic record, limiting growth of repeated failure logs."""
    try:
        path = _error_log()
        if path.exists() and path.stat().st_size > 1024 * 1024:
            try:
                path.replace(path.with_suffix('.previous.log'))
            except OSError:
                pass
        with path.open('a', encoding='utf8') as file:
            stamp = datetime.now().astimezone().isoformat(timespec='seconds')
            file.write(f'\n[{stamp}] {action}: {source}\n{details.rstrip()}\n')
        return path
    except OSError:
        return None


def _show_error(message: str, log_path: Path | None) -> None:
    """Show a visible error whether or not a console is available."""
    details = f'\n\nDetails: {log_path}' if log_path is not None else (
        '\n\nThe error log could not be written.'
    )
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            None, f'polarstory could not complete the operation.\n\n{message}{details}',
            'polarstory', 0x10,
        )
    except Exception:
        # message boxes can fail in noninteractive Windows sessions
        pass


def _run_windowed(argv: list[str]) -> int:
    """Run an Explorer action quietly, recording and displaying failures."""
    stdout = io.StringIO()
    stderr = io.StringIO()
    action = 'unknown action'
    source = 'unknown file'
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            parser = argparse.ArgumentParser(prog='polarstory (Windows Explorer)')
            parser.add_argument('action', choices=tuple(_ACTIONS))
            parser.add_argument('source')
            parser.add_argument('--config', type=Path)
            args = parser.parse_args(argv)
            action, source = args.action, args.source
            from polarstory.cli import main
            status = main(_action_args(action, source, args.config))
            if status not in (None, 0):
                raise RuntimeError(f'polarstory exited with code {status}')
        return 0
    except SystemExit as exc:
        if exc.code in (None, 0):
            return 0
        details = stderr.getvalue().strip() or f'Exit code: {exc.code}'
        summary = details.splitlines()[-1]
    except Exception as exc:
        details = stderr.getvalue() + traceback.format_exc()
        summary = str(exc) or type(exc).__name__

    path = _write_error(action, source, details)
    _show_error(summary[-500:], path)
    return 1


def _delete_key(winreg, path: str) -> bool:
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
        return True
    except FileNotFoundError:
        return False


def _remove_legacy(winreg) -> None:
    _delete_key(winreg, _LEGACY_PATH + r'\command')
    _delete_key(winreg, _LEGACY_PATH)


def install(*, python: str | Path | None = None, mode: str = 'standard',
            config: str | Path | None = None) -> str:
    """Install the per-user classic submenu without changing file associations."""
    if os.name != 'nt':
        raise OSError('Windows File Explorer integration is only available on Windows')
    import winreg

    if mode not in ('quick', 'standard', 'full'):
        raise ValueError(f'Invalid profile mode: {mode}')
    # prefer pythonw on Windows, but fall back to python.exe
    commands = {name: command(python=python, config=config, action=name,
                              windowed=(sys.platform == 'win32'))
                for name in _ACTIONS}
    _remove_legacy(winreg)
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _REGISTRY_PATH, 0,
                            winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, 'MUIVerb', 0, winreg.REG_SZ, 'polarstory')
        # empty SubCommands allows local nested shell subverbs
        winreg.SetValueEx(key, 'SubCommands', 0, winreg.REG_SZ, '')
    for name, title in _ACTIONS.items():
        node = _REGISTRY_PATH + rf'\shell\{name}'
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, node, 0,
                                winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, 'MUIVerb', 0, winreg.REG_SZ, title)
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, node + r'\command', 0,
                                winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, '', 0, winreg.REG_SZ, commands[name])
    return commands['standard']


def status() -> str | None:
    """Return the registered standard-profile command, if installed."""
    if os.name != 'nt':
        raise OSError('Windows integration is only available on Windows')
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            _REGISTRY_PATH + r'\shell\standard\command') as key:
            return winreg.QueryValueEx(key, '')[0]
    except FileNotFoundError:
        return None


def uninstall() -> bool:
    """Remove only polarstory's per-user menu and previous single verb."""
    if os.name != 'nt':
        raise OSError('Windows integration is only available on Windows')
    import winreg

    removed = False
    for name in reversed(tuple(_ACTIONS)):
        base = _REGISTRY_PATH + rf'\shell\{name}'
        removed = _delete_key(winreg, base + r'\command') or removed
        removed = _delete_key(winreg, base) or removed
    removed = _delete_key(winreg, _REGISTRY_PATH + r'\shell') or removed
    removed = _delete_key(winreg, _REGISTRY_PATH) or removed
    legacy_present = _legacy_exists(winreg)
    _remove_legacy(winreg)
    return removed or legacy_present


def _legacy_exists(winreg) -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _LEGACY_PATH):
            return True
    except FileNotFoundError:
        return False


if __name__ == '__main__':
    # Explorer calls: pythonw.exe or python.exe -m polarstory.integrations.windows run ...
    if len(sys.argv) > 1 and sys.argv[1] == 'run':
        raise SystemExit(_run_windowed(sys.argv[2:]))
    raise SystemExit('Expected: run ACTION FILE [--config PATH]')
