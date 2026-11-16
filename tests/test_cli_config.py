"""CLI settings, naming, overwriting, and reproducibility tests."""

import json
from pathlib import Path

import pytest

from polarstory.cli import main, _destination
from polarstory.config import load_config


def test_config_validation(tmp_path):
    path = tmp_path / 'polarstory.toml'
    path.write_text('[profile]\nmode = "quick"\nmax_categories = 9\n'
                    '[report]\nopen = false\noutput_directory = "reports"\n',
                    encoding='utf8')
    assert load_config(path)['profile']['max_categories'] == 9
    path.write_text('[profile]\nmax_categories = -1\n', encoding='utf8')
    with pytest.raises(ValueError, match='positive'):
        load_config(path)
    path.write_text('[profile]\nmode = "unexpected"\n', encoding='utf8')
    with pytest.raises(ValueError, match='Invalid'):
        load_config(path)
    path.write_text('[profile]\nunknown = true\n', encoding='utf8')
    with pytest.raises(ValueError, match='Unknown'):
        load_config(path)


def test_config_discovery(tmp_path, monkeypatch):
    source = tmp_path / 'my data.parquet'
    source.touch()
    config = tmp_path / 'polarstory.toml'
    config.write_text('[profile]\nmode = "quick"\n', encoding='utf8')
    monkeypatch.chdir(tmp_path)
    assert load_config(source=source)['profile']['mode'] == 'quick'
    config.unlink()
    assert load_config(source=source) == {'profile': {}, 'report': {}}
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / 'missing.toml')


def test_destination_never_silently_overwrites(tmp_path):
    path = tmp_path / 'test.profile.html'
    path.write_text('previous', encoding='utf8')
    assert _destination(None, path, force=False) == tmp_path / 'test.profile-2.html'
    with pytest.raises(FileExistsError, match='--force'):
        _destination(path, path, force=False)
    assert _destination(path, path, force=True) == path
    assert path.read_text(encoding='utf8') == 'previous'


def test_cli_toml_priority_and_safety(df, tmp_path, capsys):
    source = tmp_path / 'cohort with spaces.parquet'
    df.write_parquet(source)
    config = tmp_path / 'polarstory.toml'
    config.write_text('[profile]\nmode = "quick"\nmax_categories = 3\ncharts = false\n'
                      '[report]\noutput_directory = "reports"\nopen = false\n', encoding='utf8')
    output = tmp_path / 'custom.html'
    assert main(['profile', str(source), '--config', str(config), '-o', str(output)]) == 0
    assert output.is_file()
    with pytest.raises(SystemExit) as exc:
        main(['profile', str(source), '--config', str(config), '-o', str(output)])
    assert exc.value.code == 2
    assert main(['profile', str(source), '--config', str(config), '-o', str(output), '--force']) == 0
    assert output.is_file()
    capsys.readouterr()


def test_cli_default_name_increments(df, tmp_path, monkeypatch, capsys):
    path = tmp_path / 'test.parquet'
    df.write_parquet(path)
    monkeypatch.chdir(tmp_path)
    assert main(['profile', str(path), '--mode', 'quick']) == 0
    first = Path(capsys.readouterr().out.strip())
    assert first.exists()
    assert main(['profile', str(path), '--mode', 'quick']) == 0
    second = Path(capsys.readouterr().out.strip())
    assert second.exists() and first != second
    assert first.read_bytes()


def test_recipe_cli_no_unintended_overwrite(df, tmp_path):
    path = tmp_path / 'test.parquet'
    df.write_parquet(path)
    spec = tmp_path / 'profile.json'
    assert main(['profile', str(path), '--mode', 'quick', '--write-spec', str(spec)]) == 0
    assert json.loads(spec.read_text(encoding='utf8'))['format'] == 'polarstory.profile/v1'
    with pytest.raises(SystemExit) as exc:
        main(['profile', str(path), '--mode', 'quick', '--write-spec', str(spec)])
    assert exc.value.code == 2
    output = tmp_path / 'reproduce.html'
    assert main(['reproduce', str(spec), '-o', str(output)]) == 0
    with pytest.raises(SystemExit):
        main(['reproduce', str(spec), '-o', str(output)])
    assert main(['reproduce', str(spec), '-o', str(output), '--force']) == 0


def test_inspect_html_default_naming(df, tmp_path, capsys):
    source = tmp_path / 'sample file.parquet'
    df.write_parquet(source)
    assert main(['inspect', str(source), '--html', '--no-open']) == 0
    path = Path(capsys.readouterr().out.strip())
    assert path.name == 'sample file.inspect.html'
    assert '<!doctype html>' in path.read_text(encoding='utf8')


@pytest.mark.parametrize('kind', ['missingness', 'numeric', 'categorical',
                                  'quality', 'associations'])
def test_cli_diagnostic_presets(df, tmp_path, capsys, kind):
    source = tmp_path / 'input.parquet'
    df.write_parquet(source)
    assert main(['diagnose', str(source), '--type', kind, '--no-open']) == 0
    path = Path(capsys.readouterr().out.strip())
    assert path.name == f'input.{kind}.html'
    assert '<!doctype html>' in path.read_text(encoding='utf8')
    assert kind.title() in path.read_text(encoding='utf8')


def test_cli_diagnostics_require_selection(df, tmp_path):
    source = tmp_path / 'input.parquet'
    df.write_parquet(source)
    with pytest.raises(SystemExit) as exc:
        main(['diagnose', str(source)])
    assert exc.value.code == 2
