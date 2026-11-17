"""Per-user GNOME Files (Nautilus) and KDE Dolphin context-menu entries."""

from __future__ import annotations

import os
import shlex
import shutil
import sys
from pathlib import Path

from polarstory.integrations.launcher import ACTIONS, configuration, interpreter

_MANAGERS = ('nautilus', 'dolphin')
_MARKER = 'polarstory-managed-file-manager-integration'


def _data_home() -> Path:
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')).expanduser()


def _nautilus_dir() -> Path:
    return _data_home() / 'nautilus' / 'scripts' / 'polarstory'


def _dolphin_file() -> Path:
    return _data_home() / 'kio' / 'servicemenus' / 'polarstory.desktop'


def _manager(manager: str) -> str:
    if manager in _MANAGERS:
        return manager
    if manager != 'auto':
        raise ValueError(f'Unknown Linux file manager: {manager}')
    desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
    if 'kde' in desktop or 'plasma' in desktop:
        return 'dolphin'
    if any(name in desktop for name in ('gnome', 'unity', 'budgie')):
        return 'nautilus'
    found = [name for name in _MANAGERS if shutil.which(name)]
    if len(found) == 1:
        return found[0]
    raise ValueError('Cannot identify a supported file manager; use --manager nautilus or dolphin')


def _script(action: str, python: Path, config: Path | None) -> str:
    args = (f'{shlex.quote(str(python))} -m polarstory.integrations.launcher '
            f'run {action} "$file"')
    if config:
        args += f' --config {shlex.quote(str(config))}'
    return (f'#!/bin/sh\n# {_MARKER}\n'
            'if [ "$#" -gt 0 ]; then\n'
            '    for file in "$@"; do\n'
            f'        {args}\n'
            '    done\n'
            'elif [ -n "${NAUTILUS_SCRIPT_SELECTED_FILE_PATHS:-}" ]; then\n'
            '    printf "%s\\n" "$NAUTILUS_SCRIPT_SELECTED_FILE_PATHS" | while IFS= read -r file; do\n'
            '        [ -n "$file" ] || continue\n'
            f'        {args}\n'
            '    done\n'
            'fi\n')


def _exec_quote(value: str) -> str:
    """Quote a single executable/argument for the desktop-entry Exec grammar."""
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$') + '"'


def _desktop(python: Path, config: Path | None) -> str:
    parts = [
        '[Desktop Entry]', 'Type=Service',
        f'X-polarstory-Marker={_MARKER}',
        'MimeType=all/allfiles;application/octet-stream;application/vnd.apache.parquet;',
        'X-KDE-Submenu=polarstory',
        'Actions=' + ';'.join(ACTIONS) + ';',
        '',
    ]
    for action, title in ACTIONS.items():
        cmd = f'{_exec_quote(str(python))} -m polarstory.integrations.launcher run {action} %f'
        if config:
            cmd += ' --config ' + _exec_quote(str(config))
        parts.extend([f'[Desktop Action {action}]', f'Name={title}', f'Exec={cmd}', ''])
    return '\n'.join(parts)


def _owned(path: Path) -> bool:
    if path.is_symlink():
        return False
    try:
        with path.open('r', encoding='utf8', errors='replace') as file:
            return _MARKER in file.read(300)
    except OSError:
        return False


def _require_platform() -> None:
    if not sys.platform.startswith('linux'):
        raise OSError('Linux file-manager integration is only available on Linux')


def install(*, manager: str = 'auto', python: str | Path | None = None,
            config: str | Path | None = None) -> str:
    """Install per-user Nautilus scripts or Dolphin service menu."""
    _require_platform()
    selected = _manager(manager)
    executable, config_file = interpreter(python), configuration(config)
    if selected == 'dolphin':
        file = _dolphin_file()
        if file.exists() and not _owned(file):
            raise FileExistsError(f'Not a polarstory service menu: {file}')
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(_desktop(executable, config_file), encoding='utf8')
        file.chmod(0o755)
        return f'Installed Dolphin service menu: {file}'
    root = _nautilus_dir()
    for action, title in ACTIONS.items():
        file = root / title
        if file.exists() and not _owned(file):
            raise FileExistsError(f'Not a polarstory script: {file}')
    root.mkdir(parents=True, exist_ok=True)
    for action, title in ACTIONS.items():
        file = root / title
        file.write_text(_script(action, executable, config_file), encoding='utf8')
        file.chmod(0o755)
    return f'Installed {len(ACTIONS)} Nautilus scripts in {root}'


def status(*, manager: str = 'auto') -> str | None:
    """Report installed file-manager actions for the selected manager."""
    _require_platform()
    selected = _manager(manager)
    if selected == 'dolphin':
        return str(_dolphin_file()) if _owned(_dolphin_file()) else None
    found = [name for name in ACTIONS.values() if _owned(_nautilus_dir() / name)]
    return f'{len(found)}/{len(ACTIONS)} Nautilus scripts installed: ' + ', '.join(found) if found else None


def uninstall(*, manager: str = 'auto') -> bool:
    """Remove only polarstory-managed scripts and service menus."""
    _require_platform()
    selected = _manager(manager)
    if selected == 'dolphin':
        path = _dolphin_file()
        if _owned(path):
            path.unlink()
            return True
        return False
    removed = False
    for title in ACTIONS.values():
        file = _nautilus_dir() / title
        if _owned(file):
            file.unlink()
            removed = True
    if _nautilus_dir().is_dir() and not any(_nautilus_dir().iterdir()):
        _nautilus_dir().rmdir()
    return removed
