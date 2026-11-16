"""Numerical-accuracy regression tests using NIST's certified StRD datasets.

The input sequences below follow NIST's published NumAcc1-NumAcc4 dataset
constructions. Expected mean and sample standard deviation are independent
certified values, not values calculated by polarstory.

Sources:
    https://www.itl.nist.gov/div898/strd/univ/homepage.html
    https://www.itl.nist.gov/div898/strd/univ/addinfo/numacc1.html
    https://www.itl.nist.gov/div898/strd/univ/addinfo/numacc2.html
    https://www.itl.nist.gov/div898/strd/univ/addinfo/numacc3.html
    https://www.itl.nist.gov/div898/strd/univ/addinfo/numacc4.html
    https://www.itl.nist.gov/div898/strd/univ/certvalues/numacc1.html
    https://www.itl.nist.gov/div898/strd/univ/certvalues/numacc2.html
    https://www.itl.nist.gov/div898/strd/univ/certvalues/numacc3.html
    https://www.itl.nist.gov/div898/strd/univ/certvalues/numacc4.html
"""

from dataclasses import dataclass

import polars as pl
import pytest

import polarstory as ps


@dataclass(frozen=True)
class NISTCase:
    """Published input construction and certified summary statistics."""

    name: str
    first: int | float
    low: int | float
    high: int | float
    count: int
    mean: float
    sample_sd: float
    mean_abs_tol: float
    sd_abs_tol: float

    def values(self) -> list[int | float]:
        """Reproduce the exact published observation order locally."""
        if self.count == 3:
            return [self.first, self.low, self.high]
        return [self.first] + [v for _ in range(500) for v in (self.low, self.high)]


CASES = (
    NISTCase('NumAcc1', 10_000_002, 10_000_001, 10_000_003,
             3, 10_000_002, 1.0, 1e-7, 1e-9),
    NISTCase('NumAcc2', 1.2, 1.1, 1.3,
             1001, 1.2, 0.1, 1e-10, 1e-9),
    NISTCase('NumAcc3', 1_000_000.2, 1_000_000.1, 1_000_000.3,
             1001, 1_000_000.2, 0.1, 1e-8, 1e-8),
    NISTCase('NumAcc4', 10_000_000.2, 10_000_000.1, 10_000_000.3,
             1001, 10_000_000.2, 0.1, 1e-7, 1e-8),
)


@pytest.fixture(params=CASES, ids=lambda case: case.name.lower())
def nist_case(request):
    """Generate each NIST reference dataset without checked-in binary files."""
    case = request.param
    values = case.values()
    assert len(values) == case.count
    return case, pl.DataFrame({'value': values})


@pytest.mark.parametrize('source_kind', ['dataframe', 'lazyframe', 'parquet'])
def test_nist_certified_numeric(nist_case, source_kind, tmp_path):
    """Validate sample SD and mean against NIST for all supported inputs."""
    case, frame = nist_case
    if source_kind == 'dataframe':
        data = frame
    elif source_kind == 'lazyframe':
        data = frame.lazy()
    else:
        path = tmp_path / f'{case.name}.parquet'
        frame.write_parquet(path)
        data = path

    result = ps.stats.numeric(data, 'value').row(0, named=True)

    assert result['rows'] == case.count
    assert result['finite_count'] == case.count
    assert result['null_count'] == 0
    assert result['mean'] == pytest.approx(case.mean, rel=0, abs=case.mean_abs_tol)
    assert result['std'] == pytest.approx(case.sample_sd, rel=0, abs=case.sd_abs_tol)


def test_nist_automatic_profile(nist_case):
    """Ensure automatic profiles reuse the same certified summary metrics."""
    case, frame = nist_case
    profile = ps.profile(frame.lazy(), columns=['value'], mode='quick')
    result = profile.variable('value').table.row(0, named=True)

    assert result['rows'] == case.count
    assert result['mean'] == pytest.approx(case.mean, rel=0, abs=case.mean_abs_tol)
    assert result['std'] == pytest.approx(case.sample_sd, rel=0, abs=case.sd_abs_tol)


@pytest.mark.parametrize('source_kind', ['dataframe', 'parquet'])
def test_nist_certified_dataset_comparison(source_kind, tmp_path):
    """Compare two NIST cases against their independently certified values."""
    before = pl.DataFrame({'value': CASES[1].values()})
    after = pl.DataFrame({'value': CASES[3].values()})
    if source_kind == 'parquet':
        before_path = tmp_path / 'numacc2.parquet'
        after_path = tmp_path / 'numacc4.parquet'
        before.write_parquet(before_path)
        after.write_parquet(after_path)
        before, after = before_path, after_path

    rows = ps.compare(before, after).numeric.to_dicts()
    result = {(row['column'], row['metric']): row for row in rows}
    mean = result['value', 'mean']
    sd = result['value', 'std']

    assert mean['baseline'] == pytest.approx(1.2, rel=0, abs=1e-10)
    assert mean['current'] == pytest.approx(10_000_000.2, rel=0, abs=1e-7)
    assert mean['difference'] == pytest.approx(9_999_999.0, rel=0, abs=1e-7)
    assert sd['baseline'] == pytest.approx(0.1, rel=0, abs=1e-9)
    assert sd['current'] == pytest.approx(0.1, rel=0, abs=1e-8)
    assert sd['difference'] == pytest.approx(0, rel=0, abs=1e-8)
