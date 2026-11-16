import polarstory as ps
from polarstory.cli import main


def test_inspect_defaults_metadata_only(df, tmp_path):
    path = tmp_path / 'cohort.parquet'
    df.write_parquet(path)
    result = ps.inspect(path)
    assert result.rows is None
    assert result.file_count == 1
    assert result.size_bytes > 0
    assert 'age' in result.to_html()


def test_inspect_count_rows(df, tmp_path):
    path = tmp_path / 'cohort.parquet'
    df.write_parquet(path)
    assert ps.inspect(path, count_rows=True).rows == 6


def test_cli_profile_and_inspect(df, tmp_path, capsys):
    source = tmp_path / 'study.parquet'
    output = tmp_path / 'report.html'
    df.write_parquet(source)
    assert main(['inspect', str(source)]) == 0
    assert 'enctype:' in capsys.readouterr().out
    assert main(['profile', str(source), '--mode', 'quick',
                 '--columns', 'ins_*', '-o', str(output)]) == 0
    html = output.read_text()
    assert 'ins_medicaid' in html
    assert 'enctype —' not in html
