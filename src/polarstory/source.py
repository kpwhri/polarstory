"""Normalize dataframe and local parquet inputs without eagerly loading them."""

from __future__ import annotations

from dataclasses import dataclass
from glob import glob, has_magic
from pathlib import Path
from typing import TypeAlias

import polars as pl

DataInput: TypeAlias = pl.DataFrame | pl.LazyFrame | str | Path


@dataclass(frozen=True)
class DataSource:
    """A reproducible lazy view of a polars frame or local parquet input.

    The source does not pin external file contents. Files should not be
    modified while an inspection/profile is being computed.
    """

    frame: pl.LazyFrame
    label: str
    kind: str
    paths: tuple[Path, ...] = ()
    row_count: int | None = None

    @property
    def schema(self) -> pl.Schema:
        return self.frame.collect_schema()

    @property
    def size_bytes(self) -> int | None:
        if not self.paths:
            return None
        return sum(p.stat().st_size for p in self.paths)


def as_source(data: DataInput | DataSource) -> DataSource:
    """Accept eager/lazy polars frames or a local parquet file, glob, or folder."""
    if isinstance(data, DataSource):
        return data
    if isinstance(data, pl.DataFrame):
        return DataSource(data.lazy(), 'DataFrame', 'dataframe', row_count=data.height)
    if isinstance(data, pl.LazyFrame):
        return DataSource(data, 'LazyFrame', 'lazyframe')
    if not isinstance(data, (str, Path)):
        raise TypeError('Expected a polars DataFrame, LazyFrame, or parquet path')

    raw = str(data)
    if has_magic(raw):
        files = sorted(Path(p).resolve() for p in glob(raw, recursive=True))
    else:
        path = Path(raw).expanduser().resolve()
        if path.is_dir():
            files = sorted(p for p in path.rglob('*.parquet') if p.is_file())
        elif path.is_file():
            files = [path]
        else:
            raise FileNotFoundError(f'No such parquet file or directory: {raw}')

    files = [p for p in files if p.is_file()]
    if not files:
        raise FileNotFoundError(f'No parquet files found: {raw}')
    if any(p.suffix.lower() != '.parquet' for p in files):
        raise ValueError('Only parquet files are supported as file inputs')

    # one scan for cross-file optimization
    # explicit enumeration for predictable folder and glob behavior
    scan_path = str(files[0]) if len(files) == 1 else [str(p) for p in files]
    return DataSource(
        pl.scan_parquet(scan_path),
        label=raw,
        kind='parquet',
        paths=tuple(files),
    )
