# Testing polarstory

Run the complete test suite from the project root:

```bash
python -m pytest -q
```

## Statistical reference tests

The tests check polarstory against **independent expected results**, not values calculated by polarstory itself.

- **NIST reference datasets:** `test_nist_reference.py` generates NumAcc1–NumAcc4 from published sequences and checks
  their certified means and sample standard deviations. See
  the [NIST Statistical Reference Datasets](https://www.itl.nist.gov/div898/strd/univ/homepage.html).
- **Synthetic healthcare data:** `test_healthcare_reference.py`, `test_association_reference.py`, and
  `test_comparison_reference.py` check frequencies, missingness, outliers, duplicates, correlations, and changes between
  extracts.
- **Cramer's V:** `test_cramers_v.py` checks conventional and bias-corrected results against known contingency tables.

Tests create temporary parquet files as needed, so there are no reference datasets to download. Where appropriate, the
same calculations are checked using DataFrames, LazyFrames, and parquet inputs. Floating-point results use small
tolerances; counts and labels are compared exactly.

To run just the reference tests:

```bash
python -m pytest tests/test_nist_reference.py tests/test_healthcare_reference.py tests/test_association_reference.py tests/test_comparison_reference.py tests/test_cramers_v.py -q
```
