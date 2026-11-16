"""Per-user Windows cascading context-menu tests."""

import sys
from types import SimpleNamespace

import pytest

from polarstory.integrations import windows


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
