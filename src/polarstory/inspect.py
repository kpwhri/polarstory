"""Fast schema inspection for eager/lazy frames and parquet files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl

from polarstory.source import DataInput, as_source
from polarstory.report import Report


@dataclass
class Inspection:
    source: str
    kind: str
    schema: pl.Schema
    rows: int | None
    file_count: int | None
    size_bytes: int | None

    def to_report(self) -> Report:
        """Convert the metadata inspection into a small static report."""
        report = Report(f'Inspection: {self.source}')
        report.add_table(pl.DataFrame([{
            'source': self.source,
            'kind': self.kind,
            'rows': self.rows,
            'files': self.file_count,
            'size_bytes': self.size_bytes,
        }]), title='Source details')
        report.add_table(pl.DataFrame(
            [{'column': col, 'dtype': str(dtype)} for col, dtype in self.schema.items()],
            schema={'column': pl.String, 'dtype': pl.String},
        ), title='Schema')
        return report

    def to_html(self) -> str:
        """Return an HTML string displaying inspected file metadata."""
        return self.to_report().to_html()

    def write_html(self, path: str | Path) -> Path:
        """Save the metadata inspection as a standalone HTML file.
        
        Args:
            path: Output HTML path.
        
        Returns:
            Path to the written file.
        
        """
        return self.to_report().write_html(path)


def inspect(data: DataInput, *, count_rows: bool = False) -> Inspection:
    """Inspect schema and source size without reading column data by default.

    count_rows=True performs a lazy count query, which may be optimized using
    parquet metadata, but is not guaranteed to avoid scanning data.
    """
    source = as_source(data)
    rows = source.row_count
    if count_rows and rows is None:
        rows = source.frame.select(pl.len()).collect().item()
    return Inspection(
        source=source.label,
        kind=source.kind,
        schema=source.schema,
        rows=rows,
        file_count=len(source.paths) if source.paths else None,
        size_bytes=source.size_bytes,
    )
