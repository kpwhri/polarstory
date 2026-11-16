"""Small, fully synthetic healthcare extracts with fixed statistical targets.

The observation sequences and expected results are independent of polarstory.
They deliberately distinguish unknown insurance codes from true null values,
null from floating NaN/infinity, and excess duplicate rows from all rows in
duplicate groups. No real patient information is included.
"""

from collections import Counter
from datetime import date
from math import isclose, isfinite, sqrt
from statistics import mean, stdev

BASELINE = {
    'patient_id': [f'P{i:03}' for i in range(1, 9)],
    'age': [20., 21., 22., 23., 24., 25., 26., 100.],
    'lab_result': [1., 2., 3., 4., None, float('nan'), float('inf'), -float('inf')],
    'ins_medicaid': ['Y', 'N', 'U', 'Y', None, 'N', 'Y', 'U'],
    'enctype': ['ED', 'ED', 'IP', 'IP', 'ED', 'IP', 'ED', 'IP'],
    'flag_a': [None, None, 1, 1, None, 1, 1, 1],
    'flag_b': [None, None, 1, 1, 2, 1, 1, 1],
    'flag_c': [1, 1, None, None, 1, 1, 1, 1],
    'note_text': ['', ' ', 'seen', None, 'discharged', '', '  ', 'seen'],
    'tx_ep_start': [date(2025, 1, d) for d in range(1, 9)],
    'legacy': ['previous'] * 8,
}

CURRENT = {
    'patient_id': [f'P{i:03}' for i in range(1, 11)],
    'age': [20., 20., 21., 22., 23., 24., 25., 26., 27., 100.],
    'lab_result': [1., 2., 3., 4., 5., 6., None, float('nan'), float('inf'), 7.],
    'ins_medicaid': ['Y', 'Y', 'Y', 'N', 'N', 'U', 'U', 'U', None, 'Y'],
    'enctype': ['ED', 'ED', 'IP', 'IP', 'ED', 'IP', 'ED', 'IP', 'ED', 'ED'],
    'flag_a': [None, None, None, None, 1, 1, 1, 1, 1, 1],
    'flag_b': [None, None, 1, None, 1, 1, 1, 1, 1, 1],
    'flag_c': [1] * 10,
    'note_text': ['seen'] * 10,
    'tx_ep_start': [date(2026, 1, d) for d in range(1, 11)],
    'cohort': ['A'] * 6 + ['B'] * 4,
}

DUPLICATE_ROWS = {
    'record_type': [1, 1, 2, 3, 3, 3, 4, 4],
    'enctype': ['ED', 'ED', 'IP', 'OP', 'OP', 'OP', None, None],
}

# fixed targets for these synthetic observations
EXPECTED = {
    'rows': 8,
    'age_mean': 32.625,
    'age_sample_sd': 27.296977854700327,
    'age_q25': 22.,
    'age_q75': 25.,
    'age_outlier_count': 1,
    'lab_finite_count': 4,
    'lab_mean': 2.5,
    'lab_null_count': 1,
    'lab_nan_count': 1,
    'lab_infinite_count': 2,
    'insurance_counts': {'Y': 3, 'N': 2, 'U': 2, None: 1},
    'missingness_patterns': {
        '(none)': 3, 'flag_a, flag_b': 2,
        'flag_c': 2, 'flag_a': 1,
    },
    'phi_a_b': 0.7453559924999299,
    'phi_a_c': -0.4472135954999579,
    'excess_duplicate_rows': 4,
    'duplicate_percent': 50.0,
    'text_empty_count': 2,
    'text_blank_count': 4,
    'text_whitespace_only_count': 2,
}

COMPARISON_EXPECTED = {
    'baseline_rows': 8,
    'current_rows': 10,
    'age_baseline_mean': 32.625,
    'age_current_mean': 30.8,
    'age_mean_change': -1.825,
    'lab_baseline_mean': 2.5,
    'lab_current_mean': 4.0,
    'lab_mean_change': 1.5,
    'insurance_y_baseline_percent': 37.5,
    'insurance_y_current_percent': 40.0,
    'insurance_y_change_pp': 2.5,
    'insurance_u_change_pp': 5.0,
    'insurance_null_change_pp': -2.5,
    'encounter_ed_change_pp': 10.0,
    'flag_a_null_change_pp': 2.5,
    'flag_c_null_change_pp': -25.0,
}

CORRELATION = {
    'x': [1., 2., 3., 4., None, float('nan'), float('inf')],
    'y': [1., 2., 4., 3., 99., 99., 99.],
    'reverse': [4., 3., 2., 1., None, float('nan'), float('inf')],
}

CORRELATION_EXPECTED = {'n': 4, 'pearson_xy': 0.8, 'spearman_xy': 0.8,
                        'pearson_x_reverse': -1.0, 'spearman_x_reverse': -1.0}


def check_reference_contract() -> None:
    """Verify fixed targets independently using the Python standard library."""
    assert all(len(values) == 8 for values in BASELINE.values())
    assert all(len(values) == 10 for values in CURRENT.values())
    assert mean(BASELINE['age']) == EXPECTED['age_mean']
    assert isclose(stdev(BASELINE['age']), EXPECTED['age_sample_sd'], abs_tol=1e-12)
    sorted_age = sorted(BASELINE['age'])
    # polars default nearest quantile interpolation
    assert sorted_age[2] == EXPECTED['age_q25']
    assert sorted_age[5] == EXPECTED['age_q75']
    iqr = sorted_age[5] - sorted_age[2]
    low, high = sorted_age[2] - 1.5 * iqr, sorted_age[5] + 1.5 * iqr
    assert sum(value < low or value > high for value in sorted_age) == EXPECTED['age_outlier_count']
    assert Counter(BASELINE['ins_medicaid']) == EXPECTED['insurance_counts']
    assert isclose(mean(CURRENT['age']) - mean(BASELINE['age']),
                   COMPARISON_EXPECTED['age_mean_change'], abs_tol=1e-12)
    for column in ('ins_medicaid', 'enctype'):
        assert sum(Counter(BASELINE[column]).values()) == 8
    names = ('flag_a', 'flag_b', 'flag_c')
    patterns = Counter(', '.join(name for name in names if BASELINE[name][i] is None)
                       or '(none)' for i in range(8))
    assert patterns == EXPECTED['missingness_patterns']
    # fixed 2-by-2 missingness table
    # missing counts 3 and 2, overlap 2
    assert isclose((8 * 2 - 3 * 2) / sqrt(3 * 5 * 2 * 6), EXPECTED['phi_a_b'])
    assert isclose((8 * 0 - 3 * 2) / sqrt(3 * 5 * 2 * 6), EXPECTED['phi_a_c'])
    before = Counter(BASELINE['ins_medicaid'])
    after = Counter(CURRENT['ins_medicaid'])
    for category, expected in (('Y', 2.5), ('U', 5.0), (None, -2.5)):
        change = 100 * after[category] / 10 - 100 * before[category] / 8
        assert isclose(change, expected, abs_tol=1e-12)
    ed_change = 100 * Counter(CURRENT['enctype'])['ED'] / 10 - 100 * (4 / 8)
    assert ed_change == COMPARISON_EXPECTED['encounter_ed_change_pp']
    lab = [x for x in BASELINE['lab_result'] if x is not None and isfinite(x)]
    assert len(lab) == EXPECTED['lab_finite_count']
    assert mean(lab) == EXPECTED['lab_mean']
    assert 100 * 4 / 10 - 100 * 3 / 8 == COMPARISON_EXPECTED['flag_a_null_change_pp']
    pairs = list(zip(*DUPLICATE_ROWS.values()))
    assert len(pairs) - len(set(pairs)) == EXPECTED['excess_duplicate_rows']
    assert isclose(CORRELATION_EXPECTED['pearson_xy'], 4 / sqrt(5 * 5))


if __name__ == '__main__':
    check_reference_contract()
    print('Synthetic healthcare reference values verified')
