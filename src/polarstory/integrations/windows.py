"""Per-user cascading File Explorer submenu for local Parquet files."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

_REGISTRY_PATH = r'Software\Classes\SystemFileAssociations\.parquet\shell\polarstory'
_LEGACY_PATH = _REGISTRY_PATH + '.profile'
_ACTIONS = {
    'inspect': 'Inspect metadata',
    'quick': 'Quick profile',
    'standard': 'Standard profile',
    'full': 'Full profile',
    'advanced': 'Advanced diagnostics...',
}


def command(*, python: str | Path | None = None, mode: str = 'standard',
            config: str | Path | None = None, action: str | None = None) -> str:
    """Build a correctly quoted shell command with a selected-file placeholder."""
    requested = action if action is not None else mode
    if requested not in _ACTIONS:
        raise ValueError(f'Invalid polarstory action: {requested}')
    executable = Path(python or sys.executable).expanduser().resolve()
    if not executable.is_file():
        raise FileNotFoundError(f'Python interpreter not found: {executable}')
    if requested == 'inspect':
        verb, args = 'inspect', ['--html', '--open']
    elif requested == 'advanced':
        verb, args = 'diagnose', ['--choose', '--open']
    else:
        verb, args = 'profile', ['--mode', requested, '--open']
    if config is not None:
        config_file = Path(config).expanduser().resolve()
        if not config_file.is_file():
            raise FileNotFoundError(f'Configuration file not found: {config_file}')
        args.extend(['--config', str(config_file)])
    prefix = subprocess.list2cmdline([str(executable), '-m', 'polarstory', verb])
    return prefix + ' "%1" ' + subprocess.list2cmdline(args)


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
    commands = {name: command(python=python, config=config, action=name)
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
