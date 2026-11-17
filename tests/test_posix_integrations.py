"""Native MacOS and Linux file-manager integration tests."""

import os
import plistlib
import subprocess
import sys
from types import SimpleNamespace

import pytest

from polarstory.integrations import launcher, linux, macos

macos_only = pytest.mark.skipif(sys.platform != 'darwin', reason='MacOS Finder integration')
linux_only = pytest.mark.skipif(not sys.platform.startswith('linux'), reason='Linux file-manager integration')
posix_only = pytest.mark.skipif(
    sys.platform != 'darwin' and not sys.platform.startswith('linux'), reason='MacOS/Linux launcher dialog',
)


@pytest.fixture
def fake_python(tmp_path):
    executable = tmp_path / 'Python environment' / 'bin' / 'python3'
    executable.parent.mkdir(parents=True)
    executable.write_text('#!/bin/sh\nexit 0\n', encoding='utf8')
    executable.chmod(0o755)
    return executable


@pytest.fixture
def fake_macos(monkeypatch, tmp_path):
    root = tmp_path / 'Library' / 'Services'
    monkeypatch.setattr(macos, '_services_dir', lambda: root)
    monkeypatch.setattr(macos, '_require_platform', lambda: None)
    monkeypatch.setattr(macos, '_refresh_services', lambda: None)
    return root


@pytest.fixture
def fake_linux(monkeypatch, tmp_path):
    root = tmp_path / 'share'
    monkeypatch.setattr(linux, '_data_home', lambda: root)
    monkeypatch.setattr(linux, '_require_platform', lambda: None)
    return root


@macos_only
def test_macos_workflows_install_status_and_uninstall(fake_macos, fake_python):
    assert macos.status() is None
    assert macos.uninstall() is False
    assert '5 Finder Quick Actions' in macos.install(python=fake_python)
    assert macos.status().startswith('5/5')
    for action, label in launcher.ACTIONS.items():
        bundle = fake_macos / f'polarstory - {label}.workflow' / 'Contents'
        info = plistlib.loads((bundle / 'Info.plist').read_bytes())
        doc = plistlib.loads((bundle / 'document.wflow').read_bytes())
        assert info['CFBundleIdentifier'].endswith('.' + action)
        assert doc['workflowMetaData']['workflowTypeIdentifier'] == 'com.apple.Automator.servicesMenu'
        assert doc['workflowMetaData']['serviceApplicationBundleID'] == 'com.apple.finder'
        params = doc['actions'][0]['action']['ActionParameters']
        assert params['inputMethod'] == 1
        script = params['COMMAND_STRING']
        assert f'run {action} "$file"' in script
        assert str(fake_python) in script
        assert 'for file in "$@"' in script
    assert macos.uninstall() is True
    assert macos.status() is None


@macos_only
def test_macos_config_and_refuses_unowned_bundle(fake_macos, fake_python, tmp_path):
    config = tmp_path / 'my settings.toml'
    config.write_text('[profile]\n', encoding='utf8')
    macos.install(python=fake_python, config=config)
    script = \
    plistlib.loads((macos._bundle('standard') / 'Contents' / 'document.wflow').read_bytes())['actions'][0]['action'][
        'ActionParameters']['COMMAND_STRING']
    assert '--config ' in script
    assert "'" + str(config) + "'" in script
    not_ours = macos._bundle('quick')
    (not_ours / 'Contents' / 'Info.plist').write_bytes(
        plistlib.dumps({'CFBundleIdentifier': 'org.example.other'}))
    with pytest.raises(FileExistsError, match='Not a polarstory'):
        macos.install(python=fake_python)
    macos.uninstall()
    assert not_ours.exists()
    assert not macos._bundle('standard').exists()


@macos_only
def test_macos_rejects_missing_config(fake_macos, fake_python, tmp_path):
    with pytest.raises(FileNotFoundError):
        macos.install(python=fake_python, config=tmp_path / 'absent.toml')
    assert not fake_macos.exists()


@linux_only
def test_linux_nautilus_install_status_and_cleanup(fake_linux, fake_python):
    assert linux.status(manager='nautilus') is None
    assert '5 Nautilus scripts' in linux.install(manager='nautilus', python=fake_python)
    assert linux.status(manager='nautilus').startswith('5/5')
    for title in launcher.ACTIONS.values():
        file = linux._nautilus_dir() / title
        assert file.stat().st_mode & 0o111
        assert 'polarstory-managed-file-manager-integration' in file.read_text(encoding='utf8')
    assert linux.uninstall(manager='nautilus') is True
    assert not linux._nautilus_dir().exists()
    assert linux.uninstall(manager='nautilus') is False


@linux_only
def test_linux_nautilus_shell_handles_spaces_and_selections(fake_linux, tmp_path, monkeypatch):
    args_file = tmp_path / 'invocations.txt'
    python = tmp_path / 'Python folder' / 'python3'
    python.parent.mkdir()
    python.write_text('#!/bin/sh\nprintf "%s\\n" "$@" >> "$ARGS_FILE"\n', encoding='utf8')
    python.chmod(0o755)
    linux.install(manager='nautilus', python=python)
    script = linux._nautilus_dir() / 'Standard Profile'
    one = tmp_path / 'first name.parquet'
    two = tmp_path / 'second; name.parquet'
    monkeypatch.setenv('ARGS_FILE', str(args_file))
    env = dict(os.environ, NAUTILUS_SCRIPT_SELECTED_FILE_PATHS=f'{one}\n{two}')
    subprocess.run(['/bin/sh', str(script)], check=True, env=env)
    lines = args_file.read_text(encoding='utf8').splitlines()
    assert lines.count(str(one)) == 1
    assert lines.count(str(two)) == 1
    assert lines.count('run') == 2
    assert lines.count('standard') == 2
    args_file.unlink()
    subprocess.run(['/bin/sh', str(script), str(two)], check=True, env=env)
    assert args_file.read_text(encoding='utf8').splitlines().count(str(two)) == 1


@linux_only
def test_linux_dolphin_desktop_entry(fake_linux, fake_python, tmp_path):
    config = tmp_path / 'custom settings.toml'
    config.write_text('[profile]\n', encoding='utf8')
    assert linux.status(manager='dolphin') is None
    linux.install(manager='dolphin', python=fake_python, config=config)
    file = linux._dolphin_file()
    content = file.read_text(encoding='utf8')
    assert file.stat().st_mode & 0o111
    assert 'Type=Service' in content
    assert 'X-KDE-Submenu=polarstory' in content
    for action in launcher.ACTIONS:
        assert f'[Desktop Action {action}]' in content
        assert f'run {action} %f' in content
    assert '"' + str(fake_python) + '"' in content
    assert '"' + str(config) + '"' in content
    assert linux.status(manager='dolphin') == str(file)
    assert linux.uninstall(manager='dolphin') is True
    assert linux.uninstall(manager='dolphin') is False


@linux_only
def test_linux_manager_detection(fake_linux, monkeypatch):
    monkeypatch.setenv('XDG_CURRENT_DESKTOP', 'KDE')
    assert linux._manager('auto') == 'dolphin'
    monkeypatch.setenv('XDG_CURRENT_DESKTOP', 'GNOME:GNOME')
    assert linux._manager('auto') == 'nautilus'
    monkeypatch.setenv('XDG_CURRENT_DESKTOP', '')
    monkeypatch.setattr(linux.shutil, 'which', lambda name: None)
    with pytest.raises(ValueError, match='--manager'):
        linux._manager('auto')
    with pytest.raises(ValueError, match='Unknown'):
        linux._manager('thunar')


@linux_only
def test_linux_does_not_remove_user_script(fake_linux, fake_python):
    linux.install(manager='nautilus', python=fake_python)
    user_file = linux._nautilus_dir() / 'My own helper'
    user_file.write_text('echo hello', encoding='utf8')
    assert linux.uninstall(manager='nautilus')
    assert user_file.exists()
    assert linux._nautilus_dir().exists()


@pytest.mark.parametrize('action,argv', [
    ('inspect', ['inspect', '--html', '--open']),
    ('quick', ['profile', '--mode', 'quick', '--open']),
    ('standard', ['profile', '--mode', 'standard', '--open']),
    ('full', ['profile', '--mode', 'full', '--open']),
    ('advanced', ['diagnose', '--choose', '--open']),
])
def test_launcher_invokes_cli_quietly(monkeypatch, tmp_path, capsys, action, argv):
    source = tmp_path / 'study cohort.parquet'
    source.touch()
    called = []
    monkeypatch.setitem(sys.modules, 'polarstory.cli', SimpleNamespace(
        main=lambda arguments: called.append(arguments) or 0))
    monkeypatch.setattr(launcher, '_write_error', lambda *args: pytest.fail('unexpected log'))
    monkeypatch.setattr(launcher, '_show_error', lambda *args: pytest.fail('unexpected alert'))
    assert launcher.run(action, str(source)) == 0
    assert called and called[0][0] == argv[0]
    assert called[0][1] == str(source)
    assert called[0][2:] == argv[1:]
    assert capsys.readouterr().out == ''


@pytest.mark.parametrize('kind', ['exception', 'exit', 'nonzero', 'invalid'])
def test_launcher_logs_and_alerts_on_failure(monkeypatch, tmp_path, kind):
    source = tmp_path / 'cohort.parquet'
    source.touch()
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path / 'state'))
    log = tmp_path / 'state' / 'polarstory' / 'integration.log'
    log.parent.mkdir(parents=True)
    monkeypatch.setattr(launcher, 'error_log', lambda: log)
    alerts = []
    monkeypatch.setattr(launcher, '_show_error', lambda message, path: alerts.append((message, path)))

    def main(arguments):
        if kind == 'exception':
            raise ValueError('dataset is invalid')
        if kind == 'exit':
            print('invalid CLI options', file=sys.stderr)
            raise SystemExit(2)
        return 4

    monkeypatch.setitem(sys.modules, 'polarstory.cli', SimpleNamespace(main=main))
    target = str(tmp_path / 'bad.txt') if kind == 'invalid' else str(source)
    assert launcher.run('standard', target) == 1
    assert log.exists()
    content = log.read_text(encoding='utf8')
    assert 'standard:' in content
    if kind == 'exception':
        assert 'ValueError: dataset is invalid' in content
        assert 'Traceback' in content
    if kind == 'exit':
        assert 'invalid CLI options' in content
    assert len(alerts) == 1 and alerts[0][1] == log


def test_launcher_rotates_large_log(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
    path = tmp_path / 'polarstory' / 'integration.log'
    path.parent.mkdir(parents=True)
    monkeypatch.setattr(launcher, 'error_log', lambda: path)
    path.write_bytes(b'x' * (1024 * 1024 + 1))
    assert launcher._write_error('quick', 'x.parquet', 'bad') == path
    assert path.with_suffix('.previous.log').exists()
    assert 'bad' in path.read_text(encoding='utf8')


@posix_only
def test_launcher_builds_error_dialog_without_shell(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher.shutil, 'which', lambda name: '/usr/bin/zenity' if name == 'zenity' else None)
    calls = []
    monkeypatch.setattr(launcher.subprocess, 'run', lambda args, **kwargs: calls.append((args, kwargs)))
    launcher._show_error('bad input; rm -rf /', tmp_path / 'integration.log')
    if sys.platform == 'darwin':
        assert calls[0][0][0] == '/usr/bin/osascript'
    else:
        assert calls[0][0][0] == 'zenity'
    assert calls[0][1]['check'] is False
    assert all('shell' not in args for args, _ in calls)


@pytest.mark.parametrize('args,target,action,manager', [
    pytest.param(['integration', 'macos', 'install'], 'macos', 'install', None,
                 marks=macos_only),
    pytest.param(['integration', 'macos', 'status'], 'macos', 'status', None,
                 marks=macos_only),
    pytest.param(['integration', 'linux', 'install', '--manager', 'nautilus'],
                 'linux', 'install', 'nautilus', marks=linux_only),
    pytest.param(['integration', 'linux', 'uninstall', '--manager', 'dolphin'],
                 'linux', 'uninstall', 'dolphin', marks=linux_only),
])
def test_cli_dispatch_for_platform_integrations(monkeypatch, capsys, args,
                                                target, action, manager):
    from polarstory import cli

    called = []
    module = {'linux': linux, 'macos': macos}[target]
    monkeypatch.setattr(module, action, lambda **kwargs: called.append(kwargs) or 'ok')
    assert cli.main(args) == 0
    assert called
    if manager:
        assert called[0]['manager'] == manager
    assert capsys.readouterr().out.strip() == ('ok' if action != 'uninstall' else 'Removed polarstory integration')


@linux_only
def test_cli_auto_selects_linux_integration(monkeypatch, capsys):
    from polarstory import cli

    called = []
    monkeypatch.setattr('platform.system', lambda: 'Linux')
    monkeypatch.setattr(linux, 'install', lambda **kwargs: called.append(kwargs) or 'linux installed')
    assert cli.main(['integration', 'install', '--manager', 'dolphin']) == 0
    assert called[0]['manager'] == 'dolphin'
    assert capsys.readouterr().out.strip() == 'linux installed'
