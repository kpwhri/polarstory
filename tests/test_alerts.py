"""Data quality and alert tests."""

import polars as pl
import pytest

import polarstory as ps


def test_alerts(df):
    data = df.with_columns(pl.lit(None).cast(pl.String).alias('all_missing'))
    result = ps.alerts.scan(data, columns=('all_missing', 'ins_medicaid'))
    assert ('all_missing', 'all_null') in {(a.column, a.code) for a in result}
    assert not any(a.column == 'ins_medicaid' for a in result)
    assert ps.alerts.to_frame(result).height == len(result)


def test_alerts_invalid_threshold(df):
    with pytest.raises(ValueError):
        ps.alerts.scan(df, missing_threshold=1.1)


def test_profile_alerts_in_report(df):
    result = ps.profile(df, mode='quick', options=ps.ProfileOptions(missing_threshold=0.1))
    assert any(item.title == 'Data Quality Alerts' for item in result.items())
    assert '<script' not in result.to_html()
