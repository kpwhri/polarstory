"""Known correlation and missingness-phi reference values."""

import polars as pl
import pytest

import polarstory as ps
from reference_healthcare import BASELINE, CORRELATION, CORRELATION_EXPECTED, EXPECTED


@pytest.mark.parametrize('method', ['pearson', 'spearman'])
@pytest.mark.parametrize('source_kind', ['dataframe', 'lazyframe', 'parquet'])
def test_known_pairwise_correlations(method, source_kind, tmp_path):
    frame = pl.DataFrame(CORRELATION)
    if source_kind == 'dataframe':
        data = frame
    elif source_kind == 'lazyframe':
        data = frame.lazy()
    else:
        path = tmp_path / 'pairwise.parquet'
        frame.write_parquet(path)
        data = path
    rows = ps.stats.correlations(
        data, columns=['x', 'y', 'reverse'], method=method,
    ).to_dicts()
    values = {(r['left'], r['right']): r for r in rows}
    assert values['x', 'y']['n'] == CORRELATION_EXPECTED['n']
    assert values['x', 'y']['correlation'] == pytest.approx(
        CORRELATION_EXPECTED[f'{method}_xy'], abs=1e-12,
    )
    assert values['x', 'reverse']['n'] == CORRELATION_EXPECTED['n']
    assert values['x', 'reverse']['correlation'] == pytest.approx(-1., abs=1e-12)


@pytest.mark.parametrize('source_kind', ['dataframe', 'parquet'])
def test_nontrivial_missingness_phi(source_kind, tmp_path):
    frame = pl.DataFrame(BASELINE)
    if source_kind == 'parquet':
        path = tmp_path / 'missingness.parquet'
        frame.write_parquet(path)
        data = path
    else:
        data = frame
    records = ps.stats.missingness_associations(
        data, columns=['flag_a', 'flag_b', 'flag_c'],
    ).to_dicts()
    by_pair = {(r['left'], r['right']): r for r in records}
    assert by_pair['flag_a', 'flag_b']['rows'] == 8
    assert by_pair['flag_a', 'flag_b']['both_missing'] == 2
    assert by_pair['flag_a', 'flag_b']['phi'] == pytest.approx(
        EXPECTED['phi_a_b'], abs=1e-12,
    )
    assert by_pair['flag_a', 'flag_c']['both_missing'] == 0
    assert by_pair['flag_a', 'flag_c']['phi'] == pytest.approx(
        EXPECTED['phi_a_c'], abs=1e-12,
    )


def test_spearman_with_tied_ranks():
    """Average ranks must be used for tied observations."""
    frame = pl.DataFrame({'x': [1., 1., 2., 3.], 'y': [1., 2., 2., 3.]})
    row = ps.stats.correlations(frame, columns=['x', 'y'], method='spearman').row(
        0, named=True,
    )
    assert row['n'] == 4
    assert row['correlation'] == pytest.approx(5 / 6, abs=1e-12)
