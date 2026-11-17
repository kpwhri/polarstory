"""Per-user macOS Finder Quick Actions for local Parquet files."""

from __future__ import annotations

import plistlib
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from polarstory.integrations.launcher import ACTIONS, configuration, interpreter

_PREFIX = 'polarstory - '
_BUNDLE_PREFIX = 'org.kpwhri.polarstory.finder.'


def _services_dir() -> Path:
    return Path.home() / 'Library' / 'Services'


def _bundle(action: str) -> Path:
    return _services_dir() / f'{_PREFIX}{ACTIONS[action]}.workflow'


def _document(script: str) -> dict:
    """Generate a single Run Shell Script Automator Quick Action."""
    action_uuid = str(uuid4()).upper()
    return {
        'AMApplicationBuild': '523', 'AMApplicationVersion': '2.10',
        'AMDocumentVersion': '2',
        'actions': [{'action': {
            'AMAccepts': {'Container': 'List', 'Optional': False,
                          'Types': ['com.apple.cocoa.path']},
            'AMActionVersion': '1.0', 'AMApplication': ['Automator'],
            'AMParameterProperties': {'COMMAND_STRING': {}, 'inputMethod': {},
                                      'shell': {}, 'source': {}},
            'AMProvides': {'Container': 'List', 'Types': ['com.apple.cocoa.path']},
            'ActionBundlePath': '/System/Library/Automator/Run Shell Script.action',
            'ActionName': 'Run Shell Script',
            'ActionParameters': {'COMMAND_STRING': script,
                                 'CheckedForUserDefaultShell': True,
                                 'inputMethod': 1, 'shell': '/bin/sh', 'source': ''},
            'BundleIdentifier': 'com.apple.RunShellScript', 'CFBundleVersion': '1.0',
            'CanShowSelectedItemsWhenRun': False, 'CanShowWhenRun': True,
            'Category': ['AMCategoryUtilities'], 'Class Name': 'RunShellScriptAction',
            'InputUUID': str(uuid4()).upper(), 'OutputUUID': str(uuid4()).upper(),
            'UUID': action_uuid, 'UnlocalizedApplications': ['Automator'],
            'arguments': {}, 'isViewVisible': False,
            'nibPath': '/System/Library/Automator/Run Shell Script.action/Contents/Resources/Base.lproj/main.nib',
        }, 'isViewVisible': False}],
        'connectors': {},
        'workflowMetaData': {
            'workflowTypeIdentifier': 'com.apple.Automator.servicesMenu',
            'serviceInputTypeIdentifier': 'com.apple.Automator.fileSystemObject',
            'serviceApplicationBundleID': 'com.apple.finder',
            'serviceApplicationPath': '/System/Library/CoreServices/Finder.app',
            'serviceOutputTypeIdentifier': 'com.apple.Automator.nothing',
        },
    }


def _info(action: str) -> dict:
    label = f'{_PREFIX}{ACTIONS[action]}'
    return {
        'CFBundleIdentifier': _BUNDLE_PREFIX + action,
        'CFBundlePackageType': 'WFLW',
        'CFBundleName': label,
        'NSServices': [{
            'NSMenuItem': {'default': label},
            'NSMessage': 'runWorkflowAsService',
            'NSSendFileTypes': ['public.data', 'public.item'],
        }],
    }


def _script(action: str, python: Path, config: Path | None) -> str:
    command = (f'{shlex.quote(str(python))} -m polarstory.integrations.launcher '
               f'run {action} "$file"')
    if config:
        command += f' --config {shlex.quote(str(config))}'
    return '#!/bin/sh\nfor file in "$@"; do\n    ' + command + '\ndone\n'


def _owned(path: Path, action: str) -> bool:
    if path.is_symlink():
        return False
    try:
        info = plistlib.loads((path / 'Contents' / 'Info.plist').read_bytes())
        return info.get('CFBundleIdentifier') == _BUNDLE_PREFIX + action
    except (OSError, ValueError, TypeError, plistlib.InvalidFileException):
        return False


def _require_platform() -> None:
    if sys.platform != 'darwin':
        raise OSError('Finder integration is only available on macOS')


def install(*, python: str | Path | None = None,
            config: str | Path | None = None) -> str:
    """Install five Finder Quick Actions in the user's Services directory."""
    _require_platform()
    executable, config_file = interpreter(python), configuration(config)
    root = _services_dir()
    for action in ACTIONS:
        destination = _bundle(action)
        if destination.exists() and not _owned(destination, action):
            raise FileExistsError(f'Not a polarstory Quick Action: {destination}')
    root.mkdir(parents=True, exist_ok=True)
    for action in ACTIONS:
        destination = _bundle(action)
        if destination.exists():
            shutil.rmtree(destination)
        contents = destination / 'Contents'
        contents.mkdir(parents=True)
        (contents / 'Info.plist').write_bytes(plistlib.dumps(_info(action)))
        (contents / 'document.wflow').write_bytes(
            plistlib.dumps(_document(_script(action, executable, config_file))))
    _refresh_services()
    return f'Installed {len(ACTIONS)} Finder Quick Actions in {root}'


def status() -> str | None:
    """Show the installed actions owned by polarstory, if any."""
    _require_platform()
    installed = [ACTIONS[action] for action in ACTIONS if _owned(_bundle(action), action)]
    return f'{len(installed)}/{len(ACTIONS)} Finder Quick Actions installed: ' + ', '.join(
        installed) if installed else None


def uninstall() -> bool:
    """Remove only Quick Actions registered by polarstory."""
    _require_platform()
    removed = False
    for action in ACTIONS:
        path = _bundle(action)
        if _owned(path, action):
            shutil.rmtree(path)
            removed = True
    if removed:
        _refresh_services()
    return removed


def _refresh_services() -> None:
    """Ask macOS to refresh its user Services registration, if available."""
    pbs = Path('/System/Library/CoreServices/pbs')
    if pbs.is_file():
        try:
            subprocess.run([str(pbs), '-update'], check=False, timeout=10,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired):
            pass
