"""Per-user Windows cascading context-menu tests."""

import sys
from types import SimpleNamespace

import pytest

from polarstory.integrations import windows

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='Windows File Explorer integration')


def test_shell_command_quotes_selected_file(tmp_path):
    config = tmp_path / 'polarstory.toml'
    config.write_text('[profile]\nmode = "quick"\n', encoding='utf8')
    result = windows.command(config=config)
    assert '"%1"' in result
    assert '-m polarstory profile' in result
    assert '--mode standard' in result
    assert '--config' in result
    assert '--open' in result
    assert '--choose' in windows.command(action='advanced')
    assert '--html' in windows.command(action='inspect')
    for action in ('quick', 'standard', 'full'):
        assert f'--mode {action}' in windows.command(action=action)
    with pytest.raises(ValueError):
        windows.command(mode='other')


def test_windows_registry_install_remove_does_not_touch_file_associations(monkeypatch):
    entries = {}

    class Key:
        def __init__(self, name):
            self.name = name

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            pass

    def create(root, key, reserved, access):
        entries.setdefault(key, {})
        return Key(key)

    def open_key(root, key):
        if key not in entries:
            raise FileNotFoundError(key)
        return Key(key)

    def set_value(key, name, reserved, typ, data):
        entries[key.name][name] = data

    def query_value(key, name):
        return entries[key.name][name], None

    def delete(root, key):
        if key not in entries:
            raise FileNotFoundError(key)
        if any(name.startswith(key + '\\') for name in entries):
            raise OSError('key has subkeys')
        del entries[key]

    fake = SimpleNamespace(HKEY_CURRENT_USER='HKCU', KEY_SET_VALUE=1, REG_SZ=1,
                           CreateKeyEx=create, OpenKey=open_key,
                           SetValueEx=set_value, QueryValueEx=query_value, DeleteKey=delete)
    monkeypatch.setitem(sys.modules, 'winreg', fake)
    monkeypatch.setattr(windows, 'os', SimpleNamespace(name='nt'))
    assert windows.status() is None
    installed = windows.install()
    assert windows.status() == installed
    base = windows._REGISTRY_PATH
    assert entries[base]['MUIVerb'] == 'polarstory'
    assert entries[base]['SubCommands'] == ''
    assert set(windows._ACTIONS) == {'inspect', 'quick', 'standard', 'full', 'advanced'}
    for action in windows._ACTIONS:
        assert entries[base + rf'\shell\{action}']['MUIVerb']
        assert '"%1"' in entries[base + rf'\shell\{action}\command']['']
    assert windows.uninstall() is True
    assert windows.status() is None
    assert windows.uninstall() is False
    assert not any(k.startswith(base) for k in entries)


def test_windowed_command_uses_pythonw_and_escapes_paths(tmp_path):
    folder = tmp_path / 'Python with spaces'
    folder.mkdir()
    python = folder / 'python.exe'
    pythonw = folder / 'pythonw.exe'
    python.touch()
    pythonw.touch()
    config = tmp_path / 'settings with spaces.toml'
    config.write_text('[profile]\n', encoding='utf8')

    result = windows.command(python=python, config=config,
                             action='advanced', windowed=True)
    assert f'"{pythonw}"' in result
    assert '-m polarstory.integrations.windows run advanced "%1"' in result
    assert f'--config "{config}"' in result
    assert ' -m polarstory diagnose ' not in result


def test_windowed_command_falls_back_to_python(tmp_path):
    python = tmp_path / 'python.exe'
    python.touch()
    result = windows.command(python=python, windowed=True)
    assert result.startswith(str(python) + ' -m polarstory.integrations.windows run standard')
    assert 'pythonw.exe' not in result

    pythonw = tmp_path / 'pythonw.exe'
    pythonw.touch()
    with pytest.raises(FileNotFoundError, match='Configuration file'):
        windows.command(python=python, config=tmp_path / 'missing.toml',
                        windowed=True)


@pytest.mark.parametrize('action, expected', [
    ('inspect', ['inspect', 'example.parquet', '--html', '--open']),
    ('quick', ['profile', 'example.parquet', '--mode', 'quick', '--open']),
    ('standard', ['profile', 'example.parquet', '--mode', 'standard', '--open']),
    ('full', ['profile', 'example.parquet', '--mode', 'full', '--open']),
    ('advanced', ['diagnose', 'example.parquet', '--choose', '--open']),
])
def test_windowed_launcher_calls_existing_cli(monkeypatch, capsys, action, expected):
    invoked = []

    def main(args):
        invoked.append(args)
        print('report generated')
        return 0

    monkeypatch.setitem(sys.modules, 'polarstory.cli', SimpleNamespace(main=main))
    monkeypatch.setattr(windows, '_write_error', lambda *args: pytest.fail('unexpected log'))
    monkeypatch.setattr(windows, '_show_error', lambda *args: pytest.fail('unexpected dialog'))

    assert windows._run_windowed([action, 'example.parquet']) == 0
    assert invoked == [expected]
    assert capsys.readouterr().out == ''
    assert capsys.readouterr().err == ''


def test_windowed_launcher_passes_config_to_cli(monkeypatch, tmp_path):
    invoked = []
    monkeypatch.setitem(sys.modules, 'polarstory.cli', SimpleNamespace(
        main=lambda args: invoked.append(args) or 0,
    ))
    monkeypatch.setattr(windows, '_write_error', lambda *args: pytest.fail('unexpected log'))
    config = tmp_path / 'my settings.toml'
    assert windows._run_windowed(['standard', 'source.parquet',
                                  '--config', str(config)]) == 0
    assert invoked == [['profile', 'source.parquet', '--mode', 'standard',
                        '--open', '--config', str(config)]]


@pytest.mark.parametrize('kind', ['return-code', 'exception', 'invalid-arguments'])
def test_windowed_launcher_reports_failures(monkeypatch, tmp_path, kind):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    dialogs = []
    monkeypatch.setattr(windows, '_show_error', lambda msg, path: dialogs.append((msg, path)))

    def main(args):
        if kind == 'return-code':
            print('diagnostic details', file=sys.stderr)
            return 3
        raise ValueError('invalid source')

    monkeypatch.setitem(sys.modules, 'polarstory.cli', SimpleNamespace(main=main))
    args = ['not-an-action', 'example.parquet'] if kind == 'invalid-arguments' else [
        'standard', 'example.parquet',
    ]
    assert windows._run_windowed(args) == 1

    log = tmp_path / 'polarstory' / 'windows.log'
    assert log.exists()
    content = log.read_text(encoding='utf8')
    if kind == 'return-code':
        assert 'diagnostic details' in content
        assert 'exited with code 3' in content
    elif kind == 'exception':
        assert 'ValueError: invalid source' in content
        assert 'Traceback' in content
    else:
        assert 'invalid choice' in content
    assert len(dialogs) == 1
    assert dialogs[0][1] == log
    assert dialogs[0][0]


def test_window_error_log_rotates_when_large(monkeypatch, tmp_path):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    folder = tmp_path / 'polarstory'
    folder.mkdir()
    log = folder / 'windows.log'
    log.write_text('x' * (1024 * 1024 + 1), encoding='utf8')

    assert windows._write_error('standard', 'sample.parquet', 'sample error') == log
    assert (folder / 'windows.previous.log').exists()
    assert 'sample error' in log.read_text(encoding='utf8')
    assert log.stat().st_size < 1024 * 1024


def test_registry_install_uses_windowed_launcher(monkeypatch, tmp_path):
    registry = {}

    class Key:
        def __init__(self, name):
            self.name = name

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    def create(root, key, reserved, access):
        registry.setdefault(key, {})
        return Key(key)

    def set_value(key, name, reserved, type_id, value):
        registry[key.name][name] = value

    def delete(root, key):
        if key not in registry:
            raise FileNotFoundError(key)
        del registry[key]

    fake_winreg = SimpleNamespace(
        HKEY_CURRENT_USER='HKCU', KEY_SET_VALUE=1, REG_SZ=1,
        CreateKeyEx=create, SetValueEx=set_value, DeleteKey=delete,
    )
    monkeypatch.setitem(sys.modules, 'winreg', fake_winreg)
    monkeypatch.setattr(windows, 'os', SimpleNamespace(name='nt'))
    monkeypatch.setattr(windows.sys, 'platform', 'win32')

    python = tmp_path / 'python.exe'
    pythonw = tmp_path / 'pythonw.exe'
    python.touch()
    pythonw.touch()
    result = windows.install(python=python)

    assert 'pythonw.exe' in result
    for action in windows._ACTIONS:
        key = windows._REGISTRY_PATH + rf'\shell\{action}\command'
        assert 'pythonw.exe' in registry[key]['']
        assert '-m polarstory.integrations.windows run ' + action in registry[key]['']
        assert '"%1"' in registry[key]['']

    pythonw.unlink()
    fallback = windows.install(python=python)
    assert 'python.exe' in fallback
    assert 'pythonw.exe' not in fallback
    for action in windows._ACTIONS:
        key = windows._REGISTRY_PATH + rf'\shell\{action}\command'
        assert 'python.exe' in registry[key]['']
        assert 'pythonw.exe' not in registry[key]['']
