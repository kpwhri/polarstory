"""Independent contingency-table reference results for Cramér's V."""

import polars as pl
import pytest

import polarstory as ps
from polarstory.diagnose import diagnostic_report


def contingency_frame(counts):
    """Expand fixed contingency counts into a synthetic two-column cohort."""
    x, y = [], []
    for i, row in enumerate(counts):
        for j, count in enumerate(row):
            x.extend([f'group_{i}'] * count)
            y.extend([f'outcome_{j}'] * count)
    return pl.DataFrame({'group': x, 'outcome': y})


@pytest.mark.parametrize('source_type', ['dataframe', 'lazyframe', 'parquet'])
@pytest.mark.parametrize('bias_corrected, expected', [
    (False, 0.4),
    (True, 0.3946613431254393),
])
def test_cramers_v_two_by_two_reference(source_type, bias_corrected, expected, tmp_path):
    # reference: 70/30 and 30/70, chi-square 32, n 200
    frame = contingency_frame([[70, 30], [30, 70]])
    if source_type == 'dataframe':
        source = frame
    elif source_type == 'lazyframe':
        source = frame.lazy()
    else:
        path = tmp_path / 'insurance and encounter.parquet'
        frame.write_parquet(path)
        source = path
    result = ps.stats.cramers_v(
        source, 'group', 'outcome', bias_corrected=bias_corrected,
    ).row(0, named=True)
    assert result['n'] == 200
    assert result['n_rows'] == 2
    assert result['n_columns'] == 2
    assert result['cramers_v'] == pytest.approx(expected, abs=1e-12)
    assert result['chi2'] == pytest.approx(32., abs=1e-12)
    assert result['min_expected'] == pytest.approx(50.)
    assert result['small_expected_cells'] == 0
    assert result['small_expected_fraction'] == 0
    assert result['bias_corrected'] is bias_corrected


@pytest.mark.parametrize('bias_corrected, expected', [
    (False, 0.42817441928883765),
    (True, 0.36813898977081155),
])
def test_cramers_v_three_by_two_reference(bias_corrected, expected):
    # reference counts: (12,4), (3,9), (5,7)
    frame = contingency_frame([[12, 4], [3, 9], [5, 7]])
    result = ps.stats.cramers_v(
        frame, 'group', 'outcome', bias_corrected=bias_corrected,
    ).row(0, named=True)
    assert result['n'] == 40
    assert result['n_rows'] == 3
    assert result['n_columns'] == 2
    assert result['chi2'] == pytest.approx(22 / 3, abs=1e-12)
    assert result['cramers_v'] == pytest.approx(expected, abs=1e-12)
    assert result['small_expected_cells'] == 0


def test_cramers_v_independence_and_perfect_association():
    independent = contingency_frame([[25, 25], [25, 25]])
    perfect = contingency_frame([[4, 0], [0, 4]])
    for corrected in (True, False):
        zero = ps.stats.cramers_v(independent, 'group', 'outcome',
                                  bias_corrected=corrected).item(0, 'cramers_v')
        one = ps.stats.cramers_v(perfect, 'group', 'outcome',
                                 bias_corrected=corrected).row(0, named=True)
        assert zero == pytest.approx(0)
        assert one['cramers_v'] == pytest.approx(1)
        assert one['small_expected_cells'] == 4
        assert one['small_expected_fraction'] == 1


def test_cramers_v_symmetric_to_column_order():
    frame = contingency_frame([[12, 4], [3, 9], [5, 7]])
    forward = ps.stats.cramers_v(frame, 'group', 'outcome')['cramers_v'].item()
    reverse = ps.stats.cramers_v(frame, 'outcome', 'group')['cramers_v'].item()
    assert forward == pytest.approx(reverse)


def test_cramers_v_distinguishes_null_from_literal_null_label():
    frame = pl.DataFrame({
        'category': [None, '(null)', '(null)', 'A', 'A'],
        'outcome': ['Y', 'Y', 'N', 'N', 'Y'],
    })
    excluded = ps.stats.cramers_v(frame, 'category', 'outcome').row(0, named=True)
    included = ps.stats.cramers_v(
        frame, 'category', 'outcome', include_null=True,
    ).row(0, named=True)
    assert excluded['n'] == 4
    assert excluded['n_rows'] == 2
    assert included['n'] == 5
    assert included['n_rows'] == 3


def test_cramers_v_omits_nonfinite_float_categories():
    frame = pl.DataFrame({
        'code': [1., 1., 2., 2., float('nan'), float('inf'), None],
        'flag': ['Y', 'N', 'Y', 'N', 'Y', 'N', 'Y'],
    })
    excluded = ps.stats.cramers_v(frame, 'code', 'flag').row(0, named=True)
    included = ps.stats.cramers_v(
        frame, 'code', 'flag', include_null=True,
    ).row(0, named=True)
    assert excluded['n'] == 4
    assert included['n'] == 5
    assert included['n_rows'] == 3


def test_cramers_v_constant_and_empty_are_undefined():
    constant = pl.DataFrame({'category': ['A', 'A'], 'flag': ['Y', 'N']})
    empty = pl.DataFrame(schema={'category': pl.String, 'flag': pl.String})
    result = ps.stats.cramers_v(constant, 'category', 'flag').row(0, named=True)
    assert result['n'] == 2
    assert result['cramers_v'] is None
    result = ps.stats.cramers_v(empty, 'category', 'flag').row(0, named=True)
    assert result['n'] == 0
    assert result['n_rows'] == 0
    assert result['cramers_v'] is None


def test_cramers_v_guards_and_invalid_parameters():
    frame = contingency_frame([[1, 1], [1, 1]])
    with pytest.raises(ValueError, match='column and by'):
        ps.stats.cramers_v(frame, 'group', 'group')
    with pytest.raises(ValueError, match='max_categories'):
        ps.stats.cramers_v(frame, 'group', 'outcome', max_categories=0)
    with pytest.raises(ValueError, match='max_cells'):
        ps.stats.cramers_v(frame, 'group', 'outcome', max_cells=0)
    with pytest.raises(ValueError, match='categories'):
        ps.stats.cramers_v(frame, 'group', 'outcome', max_categories=1)
    with pytest.raises(ValueError, match='cells'):
        ps.stats.cramers_v(frame, 'group', 'outcome', max_cells=3)
    with pytest.raises(ValueError, match='Unknown column'):
        ps.stats.cramers_v(frame, 'missing', 'outcome')
    with pytest.raises(TypeError, match='category-coded'):
        ps.stats.cramers_v(frame.with_columns(
            pl.Series('list', [[1, 2]] * frame.height),
        ), 'list', 'outcome')


def test_diagnostic_report_includes_categorical_associations():
    frame = contingency_frame([[12, 4], [3, 9], [5, 7]])
    report = diagnostic_report(ps.profile(frame, mode='quick'), 'associations')
    assert 'Cramér' in report.to_html()


def test_cramers_v_integer_codes_and_boolean_flags():
    frame = pl.DataFrame({
        'code': [0, 0, 1, 1],
        'flag': [True, True, False, False],
    })
    result = ps.stats.cramers_v(
        frame, 'code', 'flag', bias_corrected=False,
    ).row(0, named=True)
    assert result['cramers_v'] == pytest.approx(1.)
    assert result['n'] == 4
