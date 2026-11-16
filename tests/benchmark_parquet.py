"""Optional local performance benchmark for file-backed profiling.

Run from an editable installation:

    python tests/benchmark_parquet.py --rows 200000 --columns 32

This reports elapsed wall time and source/report sizes. It intentionally does
not claim to measure polars' native Rust heap usage.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

import polars as pl

import polarstory as ps


def run(rows: int, columns: int, mode: str) -> None:
    if rows < 1 or columns < 1:
        raise ValueError('rows and columns must be positive')

    with TemporaryDirectory(prefix='polarstory-benchmark-') as directory:
        source = Path(directory) / 'dataset.parquet'
        report = Path(directory) / 'profile.html'
        data = pl.DataFrame({
            f'variable_{i}': [(index + i) % (20 if i % 2 == 0 else 1000)
                              for index in range(rows)]
            for i in range(columns)
        })
        data.write_parquet(source)
        del data

        started = perf_counter()
        ps.profile(source, mode=mode).write_html(report)
        elapsed = perf_counter() - started

        print(f'Rows: {rows:,}')
        print(f'Columns: {columns:,}')
        print(f'Mode: {mode}')
        print(f'parquet: {source.stat().st_size:,} bytes')
        print(f'HTML: {report.stat().st_size:,} bytes')
        print(f'Elapsed: {elapsed:.2f} seconds')
        print('Peak native memory: not measured')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Benchmark polarstory parquet profiling')
    parser.add_argument('--rows', type=int, default=200000)
    parser.add_argument('--columns', type=int, default=32)
    parser.add_argument('--mode', choices=['quick', 'standard'], default='quick')
    arguments = parser.parse_args()
    run(arguments.rows, arguments.columns, arguments.mode)
