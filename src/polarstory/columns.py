"""Column resolution and basic dtype classification."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, TypeAlias

import polars as pl

from polarstory.source import DataSource

ColumnSelection: TypeAlias = str | Sequence[str] | Any  # any polars selector


def select_columns(
        source: DataSource,
        columns: ColumnSelection | None = None,
        exclude: ColumnSelection | None = None,
        max_columns: int | None = None,
) -> tuple[str, ...]:
    if max_columns is not None and max_columns < 1:
        raise ValueError('max_columns must be at least 1')
    selected = (
        source.frame.select(columns).collect_schema().names()
        if columns is not None
        else source.schema.names()
    )
    if exclude is not None:
        omitted = set(source.frame.select(exclude).collect_schema().names())
        selected = [name for name in selected if name not in omitted]
    if max_columns is not None:
        selected = selected[:max_columns]
    return tuple(selected)


def dtype_kind(dtype: pl.DataType) -> str:
    """Classify a physical dtype for default profiling; not semantic inference."""
    if dtype.is_numeric():
        return 'numeric'
    if dtype.is_temporal():
        return 'temporal'
    if dtype == pl.Boolean:
        return 'categorical'
    if dtype.base_type() in (pl.String, pl.Categorical, pl.Enum):
        return 'categorical'
    return 'other'
