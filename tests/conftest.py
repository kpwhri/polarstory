from datetime import date

import polars as pl
import pytest


@pytest.fixture
def df():
    return pl.DataFrame({
        'enctype': ['ED', 'IP', 'ED', None, 'OP', 'ED'],
        'ins_medicaid': ['Y', 'N', 'U', 'N', 'Y', 'U'],
        'age': [12., 40., 41., None, 30., float('nan')],
        'tx_ep_start': [
            date(2025, 1, 1),
            date(2025, 1, 2),
            None,
            date(2025, 1, 1),
            date(2025, 1, 3),
            date(2025, 1, 4)
        ],
    })
