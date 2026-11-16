import polars as pl

import polarstory as ps


def test_escapes_html_in_tables_and_text(tmp_path):
    report = ps.Report('<bad title>')
    report.add_table(pl.DataFrame({'<column>': ['<script>alert(1)</script>']}), title='<heading>')
    report.add_text('<img src=x onerror=alert(1)>')
    path = report.write_html(tmp_path / 'report.html')
    html = path.read_text()
    assert '&lt;bad title&gt;' in html
    assert '&lt;script&gt;' in html
    assert '<script>' not in html
    assert '&lt;img src=x onerror=alert(1)&gt;' in html
    assert '@media print' in html


def test_report_sections_and_chart(df):
    report = ps.Report('Study')
    with report.section('Findings'):
        report.add_table(ps.stats.frequency(df, 'enctype'), title='Encounter types')
        report.add_chart(ps.plots.frequency(df, 'enctype'), title='Encounter chart')
    html = report.to_html()
    assert 'Findings' in html
    assert '<svg' in html
    assert '<script' not in html


def test_add_profile(df):
    report = ps.Report('Combined')
    report.add_profile(df, columns=['ins_medicaid'], mode='quick', title='Insurance')
    assert 'Insurance' in report.to_html()


def test_report_generated_at_uses_local_timezone():
    from datetime import datetime, timedelta, timezone
    from unittest.mock import patch

    pacific = timezone(timedelta(hours=-8))
    generated_at = datetime(2026, 11, 11, 14, 30, tzinfo=pacific)
    with patch('polarstory.report.datetime') as clock:
        clock.now.return_value.astimezone.return_value = generated_at
        html = ps.Report('Local timestamp').to_html()
        clock.now.assert_called_once_with()
        clock.now.return_value.astimezone.assert_called_once_with()

    assert 'Generated 2026-11-11 14:30-08:00' in html
    assert 'Generated 2026-11-11 22:30 UTC' not in html
