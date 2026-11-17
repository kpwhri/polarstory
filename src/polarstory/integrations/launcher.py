"""Quiet POSIX file-manager launcher with local error logging and native alerts."""

from __future__ import annotations

import argparse
import io
import os
import shutil
import subprocess
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path

ACTIONS = {
    'inspect': 'Inspect Metadata',
    'quick': 'Quick Profile',
    'standard': 'Standard Profile',
    'full': 'Full Profile',
    'advanced': 'Advanced Diagnostics',
}


def action_args(action: str, source: str, config: str | Path | None = None) -> list[str]:
    """Translate a file-manager action into a polarstory CLI invocation."""
    if action not in ACTIONS:
        raise ValueError(f'Unknown polarstory action: {action}')
    if action == 'inspect':
        args = ['inspect', source, '--html', '--open']
    elif action == 'advanced':
        args = ['diagnose', source, '--choose', '--open']
    else:
        args = ['profile', source, '--mode', action, '--open']
    if config is not None:
        args.extend(['--config', str(config)])
    return args


def interpreter(python: str | Path | None = None) -> Path:
    """Require an existing executable for a user-installed file-manager action."""
    executable = Path(python or sys.executable).expanduser().resolve()
    if not executable.is_file():
        raise FileNotFoundError(f'Python interpreter not found: {executable}')
    return executable


def configuration(config: str | Path | None = None) -> Path | None:
    """Validate and resolve an optional shared configuration path."""
    if config is None:
        return None
    path = Path(config).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f'Configuration file not found: {path}')
    return path


def error_log(platform: str | None = None) -> Path:
    """Keep errors in a user-local directory, never beside research datasets."""
    selected = platform or sys.platform
    if selected == 'darwin':
        directory = Path.home() / 'Library' / 'Logs' / 'polarstory'
    else:
        state = os.environ.get('XDG_STATE_HOME')
        directory = (Path(state).expanduser() if state else Path.home() / '.local' / 'state') / 'polarstory'
    directory.mkdir(parents=True, exist_ok=True)
    return directory / 'integration.log'


def _write_error(action: str, source: str, details: str) -> Path | None:
    try:
        path = error_log()
        if path.exists() and path.stat().st_size > 1024 * 1024:
            path.replace(path.with_suffix('.previous.log'))
        with path.open('a', encoding='utf8') as file:
            stamp = datetime.now().astimezone().isoformat(timespec='seconds')
            file.write(f'\n[{stamp}] {action}: {source}\n{details.rstrip()}\n')
        return path
    except OSError:
        return None


def _show_error(message: str, log_path: Path | None) -> None:
    """Display an OS-native alert without relying on a terminal window."""
    suffix = f'\n\nSee: {log_path}' if log_path else '\n\nUnable to write an error log.'
    description = f'polarstory could not complete the operation.\n\n{message}{suffix}'
    try:
        if sys.platform == 'darwin':
            subprocess.run([
                '/usr/bin/osascript', '-e', 'on run argv',
                '-e', 'display alert "polarstory" message (item 1 of argv) as critical',
                '-e', 'end run', description,
            ], check=False, timeout=20, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
        elif shutil.which('zenity'):
            subprocess.run(['zenity', '--error', '--title=polarstory',
                            f'--text={description}'], check=False, timeout=20,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif shutil.which('kdialog'):
            subprocess.run(['kdialog', '--error', description, '--title', 'polarstory'],
                           check=False, timeout=20, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        else:
            print(description, file=sys.stderr)
    except (OSError, subprocess.TimeoutExpired):
        print(description, file=sys.stderr)


def run(action: str, source: str, config: str | Path | None = None) -> int:
    """Run a selected Parquet action quietly; log and display any failure."""
    stdout, stderr = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            if action not in ACTIONS:
                raise ValueError(f'Unknown polarstory action: {action}')
            path = Path(source).expanduser()
            if not path.is_file() or path.suffix.lower() != '.parquet':
                raise ValueError('Select an existing local .parquet file')
            from polarstory.cli import main
            status = main(action_args(action, str(path), config))
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='polarstory file-manager launcher')
    parser.add_argument('operation', choices=['run'])
    parser.add_argument('action', choices=tuple(ACTIONS))
    parser.add_argument('source')
    parser.add_argument('--config', type=Path)
    args = parser.parse_args(argv)
    return run(args.action, args.source, args.config)


if __name__ == '__main__':
    raise SystemExit(main())
