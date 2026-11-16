"""Table1 tests."""

import polars as pl
import pytest

import polarstory as ps


def test_table1_overall_and_stratified(df):
    table = ps.stats.table1(df, ['age', 'enctype'], by='ins_medicaid')
    assert table.columns[:2] == ['Variable', 'Level']
    assert table.columns[2] == 'Overall (N=6)'
    assert {'N (N=2)', 'Y (N=2)', 'U (N=2)'} <= set(table.columns)
    counts = table.filter(pl.col('Level') == 'Non-missing, n')
    assert counts['Overall (N=6)'].item() == '4'
    dropped = table.filter(pl.col('Level').str.starts_with('Excluded'))
    assert dropped['Overall (N=6)'].item().startswith('2 (')
    ed = table.filter(pl.col('Level') == 'ED')
    assert ed['U (N=2)'].item() == '2 (100.0%)'
    assert ed['N (N=2)'].item() == '0 (0.0%)'


def test_table1_labels_and_percent_denominator(df):
    meta = ps.Variables().set('ins_medicaid', kind='categorical',
                              label='Medicaid', order=['N', 'Y', 'U'],
                              value_labels={'N': 'No', 'Y': 'Yes', 'U': 'Unknown'})
    table = ps.stats.table1(df, ['ins_medicaid'], variables=meta)
    assert table['Variable'][0] == 'Medicaid'
    assert table['Level'].to_list() == ['No', 'Yes', 'Unknown']
    by = ps.stats.table1(df, ['enctype'], by='ins_medicaid',
                         percent='valid', include_total=False)
    ip = by.filter(pl.col('Level') == 'IP')
    assert ip['N (N=2)'].item() == '1 (100.0%)'
    null = by.filter(pl.col('Level') == '(null)')
    assert null['N (N=2)'].item() == '1 (50.0%)'


def test_table1_caps_and_sensitive(df):
    meta = ps.Variables().set('enctype', sensitive=True)
    with pytest.raises(ValueError, match='sensitive'):
        ps.stats.table1(df, ['enctype'], variables=meta)
    with pytest.raises(ValueError, match='Too many strata'):
        ps.stats.table1(df, ['age'], by='ins_medicaid', max_strata=2)
    report = ps.Report('Cohort')
    item = report.add_table1(df, ['age', 'enctype'], by='ins_medicaid')
    assert item.kind == 'table'
    assert 'Cohort characteristics' in report.to_html()


def test_table1_lazy_parquet_parity(df, tmp_path):
    path = tmp_path / 'data.parquet'
    df.write_parquet(path)
    in_memory = ps.stats.table1(df, ['age', 'enctype'], by='ins_medicaid')
    on_disk = ps.stats.table1(path, ['age', 'enctype'], by='ins_medicaid')
    assert in_memory.to_dicts() == on_disk.to_dicts()


def test_table1_null_label_collision():
    df = pl.DataFrame({'kind': ['(null)', None, 'Other categories']})
    rows = ps.stats.table1(df, ['kind'])['Level'].to_list()
    assert '(null) [literal]' in rows
    assert '(null)' in rows
    assert 'Other categories [literal]' in rows


def test_table1_other_categories_has_correct_total():
    df = pl.DataFrame({'label': ['A', 'B', 'C', 'D', 'E', None]})
    table = ps.stats.table1(df, ['label'], max_categories=2)
    other = table.filter(pl.col('Level') == 'Other categories')
    assert other['Overall (N=6)'].item() == '3 (50.0%)'
    assert table.filter(pl.col('Level') == '(null)')['Overall (N=6)'].item() == '1 (16.7%)'
