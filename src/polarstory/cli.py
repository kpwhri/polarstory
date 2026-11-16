"""CLI for inspecting, profiling, and regenerating local parquet reports."""

from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from fnmatch import fnmatchcase
from pathlib import Path

from polarstory.config import load_config
from polarstory.inspect import inspect
from polarstory.profile import ProfileOptions, profile, profile_from_spec
from polarstory.report import Report
from polarstory.source import as_source


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='polarstory', description='Profile parquet data and create static HTML reports',
    )
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('profile', help='Generate a static HTML profile')
    p.add_argument('source', help='parquet file, glob, or folder')
    p.add_argument('-o', '--output', type=Path)
    p.add_argument('--config', type=Path)
    p.add_argument('--mode', choices=['quick', 'standard', 'full'])
    p.add_argument('--columns', help='Comma-separated column names or glob patterns')
    p.add_argument('--max-columns', type=int)
    p.add_argument('--open', action='store_true', default=None)
    p.add_argument('--no-open', dest='open', action='store_false')
    p.add_argument('--force', action='store_true', help='Overwrite explicitly named files')
    p.add_argument('--progress', action='store_true', help='Print phase information to stderr')
    p.add_argument('--write-spec', type=Path, help='Save a reusable parquet profile recipe')
    p.add_argument('--no-charts', action='store_true', default=None)
    p.add_argument('--max-categories', type=int)
    p.add_argument('--max-frequency-unique', type=int)
    p.add_argument('--max-groups', type=int)
    p.add_argument('--max-chart-groups', type=int)

    r = commands.add_parser('reproduce', help='Regenerate HTML from a JSON recipe')
    r.add_argument('spec', type=Path)
    r.add_argument('-o', '--output', type=Path)
    r.add_argument('--config', type=Path)
    r.add_argument('--force', action='store_true')
    r.add_argument('--open', action='store_true', default=None)
    r.add_argument('--no-open', dest='open', action='store_false')
    r.add_argument('--progress', action='store_true')

    i = commands.add_parser('inspect', help='Inspect schema and file metadata')
    i.add_argument('source')
    i.add_argument('-o', '--output', type=Path)
    i.add_argument('--config', type=Path)
    i.add_argument('--force', action='store_true')
    i.add_argument('--count-rows', action='store_true')
    i.add_argument('--html', action='store_true', help='Save an HTML inspection beside the source')
    i.add_argument('--open', action='store_true', default=None)
    i.add_argument('--no-open', dest='open', action='store_false')

    c = commands.add_parser('compare', help='Compare two dataset profiles descriptively')
    c.add_argument('baseline', help='Earlier extract or reference dataset')
    c.add_argument('current', help='Newer extract or comparison dataset')
    c.add_argument('-o', '--output', type=Path)
    c.add_argument('--config', type=Path)
    c.add_argument('--columns', help='Comma-separated column names')
    c.add_argument('--exclude', help='Comma-separated columns to omit')
    c.add_argument('--categorical-columns', help='Numeric-coded categorical columns')
    c.add_argument('--max-columns', type=int, default=100)
    c.add_argument('--max-categories', type=int, default=15)
    c.add_argument('--max-frequency-unique', type=int, default=1000)
    c.add_argument('--baseline-label', default='Baseline')
    c.add_argument('--current-label', default='Current')
    c.add_argument('--force', action='store_true')
    c.add_argument('--progress', action='store_true')
    c.add_argument('--open', action='store_true', default=None)
    c.add_argument('--no-open', dest='open', action='store_false')

    d = commands.add_parser('diagnose', help='Create a targeted HTML diagnostic report')
    d.add_argument('source', help='parquet file, glob, or folder')
    d.add_argument('--type', choices=['missingness', 'numeric', 'categorical', 'quality',
                                      'associations'])
    d.add_argument('--choose', action='store_true', help='Choose a diagnostic using a desktop dialog')
    d.add_argument('--config', type=Path)
    d.add_argument('-o', '--output', type=Path)
    d.add_argument('--max-columns', type=int)
    d.add_argument('--force', action='store_true')
    d.add_argument('--progress', action='store_true')
    d.add_argument('--open', action='store_true', default=None)
    d.add_argument('--no-open', dest='open', action='store_false')

    integration = commands.add_parser('integration', help='Manage optional OS integrations')
    targets = integration.add_subparsers(dest='target', required=True)
    windows = targets.add_parser('windows', help='Windows Explorer right-click integration')
    actions = windows.add_subparsers(dest='action', required=True)
    install = actions.add_parser('install')
    install.add_argument('--python', type=Path, help='Interpreter with polarstory installed')
    install.add_argument('--mode', choices=['quick', 'standard', 'full'], default='standard',
                         help='Deprecated; the submenu always includes all profile modes')
    install.add_argument('--config', type=Path)
    actions.add_parser('status')
    actions.add_parser('uninstall')
    return parser


def _matching_columns(source: str, patterns: str | None) -> list[str] | None:
    if patterns is None:
        return None
    selection = [part.strip() for part in patterns.split(',') if part.strip()]
    if not selection:
        raise ValueError('--columns requires at least one column pattern')
    known = as_source(source).schema.names()
    columns = [name for name in known if any(fnmatchcase(name, pat) for pat in selection)]
    if not columns:
        raise ValueError(f'No columns matched: {patterns}')
    return columns


def _value(arg, config: dict, key: str, default):
    return getattr(arg, key, None) if getattr(arg, key, None) is not None else config.get(key, default)


def _destination(explicit: Path | None, default: Path, *, force: bool) -> Path:
    """Avoid silent overwrites; automatic names get numbered suffixes."""
    if explicit is not None:
        output = explicit.expanduser().resolve()
        if output.exists() and not force:
            raise FileExistsError(f'Output exists: {output} (use --force to overwrite)')
        return output
    result = default.expanduser().resolve()
    if not result.exists():
        return result
    for number in range(2, 10000):
        candidate = result.with_name(f'{result.stem}-{number}{result.suffix}')
        if not candidate.exists():
            return candidate
    raise FileExistsError(f'No available filename near {default}')


def _check_spec_destination(path: Path | None, *, force: bool) -> None:
    if path is not None and path.expanduser().exists() and not force:
        raise FileExistsError(f'Specification exists: {path} (use --force to overwrite)')


def _output_dir(config: dict, source: Path) -> Path:
    value = config.get('output_directory')
    if value is None:
        return source.parent
    return Path(value).expanduser().resolve()


def _progress(enabled: bool, message: str) -> None:
    if enabled:
        print(f'polarstory: {message}', file=sys.stderr)


def _open(path: Path, enabled: bool) -> None:
    if enabled:
        webbrowser.open(path.resolve().as_uri())


def _run(args: argparse.Namespace) -> int:
    if args.command == 'integration':
        from polarstory.integrations import windows

        if args.action == 'install':
            print(windows.install(python=args.python, mode=args.mode, config=args.config))
        elif args.action == 'uninstall':
            print('Removed polarstory context menu' if windows.uninstall() else 'Not installed')
        else:
            print(windows.status() or 'Not installed')
        return 0

    settings = load_config(args.config, source=getattr(args, 'source', None))
    defaults = settings['profile']
    report = settings['report']
    if args.command == 'compare':
        from polarstory.comparison import compare

        def split_columns(value):
            return [part.strip() for part in value.split(',') if part.strip()] if value else None

        baseline = Path(args.baseline).expanduser()
        current = Path(args.current).expanduser()
        base_name = baseline.stem if baseline.is_file() else 'baseline'
        current_name = current.stem if current.is_file() else 'current'
        default = (_output_dir(report, current.resolve()) /
                   f'{base_name}-vs-{current_name}.compare.html')
        destination = _destination(args.output, default, force=args.force)
        _progress(args.progress, 'comparing datasets')
        comparison = compare(
            args.baseline, args.current,
            labels=(args.baseline_label, args.current_label),
            columns=split_columns(args.columns),
            exclude=split_columns(args.exclude) or (),
            categorical_columns=split_columns(args.categorical_columns) or (),
            max_columns=args.max_columns, max_categories=args.max_categories,
            max_unique_for_frequency=args.max_frequency_unique,
        )
        path = comparison.write_html(destination)
        print(path.resolve())
        _open(path, _value(args, report, 'open', False))
        return 0

    if args.command == 'inspect':
        result = inspect(args.source, count_rows=args.count_rows)
        if args.output is None and not args.html:
            print(f'Source: {result.source}')
            print(
                f'Files: {result.file_count or "n/a"}; Rows: {result.rows if result.rows is not None else "not counted"}')
            for name, dtype in result.schema.items():
                print(f'  {name}: {dtype}')
        else:
            source = Path(args.source).expanduser()
            default = (_output_dir(report, source.resolve()) /
                       (source.stem + '.inspect.html' if source.is_file()
                        else 'dataset.inspect.html'))
            output = _destination(args.output, default, force=args.force)
            path = result.write_html(output).resolve()
            print(path)
            _open(path, _value(args, report, 'open', False))
        return 0

    if args.command == 'reproduce':
        _progress(args.progress, 'loading recipe')
        data = json.loads(args.spec.read_text(encoding='utf8'))
        result = (Report.from_spec(args.spec) if data.get('format') == 'polarstory.report/v1'
                  else profile_from_spec(args.spec))
        default = _output_dir(report, args.spec.resolve()) / args.spec.with_suffix('.html').name
        destination = _destination(args.output, default, force=args.force)
        _progress(args.progress, 'generating HTML')
        path = result.write_html(destination)
        print(path.resolve())
        _open(path, _value(args, report, 'open', False))
        return 0

    if args.command == 'diagnose':
        from polarstory.diagnose import choose_diagnostic, diagnostic_report

        if args.type is not None and args.choose:
            raise ValueError('Choose either --type or --choose, not both')
        kind = choose_diagnostic() if args.choose else args.type
        if kind is None:
            if args.choose:
                _progress(args.progress, 'diagnostic selection cancelled')
                return 0
            raise ValueError('Specify --type or --choose for advanced diagnostics')
        limit = _value(args, defaults, 'max_columns', 50)
        if limit is not None and limit <= 0:
            raise ValueError('max_columns must be positive')
        source_path = Path(args.source).expanduser()
        name = (source_path.stem if source_path.is_file() else 'dataset')
        default = _output_dir(report, source_path.resolve()) / f'{name}.{kind}.html'
        destination = _destination(args.output, default, force=args.force)
        _progress(args.progress, f'preparing {kind} diagnostics')
        prepared = profile(args.source, mode='standard', max_columns=limit,
                           options=ProfileOptions(
                               charts=defaults.get('charts', True),
                               max_categories=defaults.get('max_categories', 15),
                               max_unique_for_frequency=defaults.get('max_frequency_unique', 1000),
                               max_groups=defaults.get('max_groups', 50),
                               max_chart_groups=defaults.get('max_chart_groups', 20),
                           ))
        result = diagnostic_report(prepared, kind)
        _progress(args.progress, 'generating HTML')
        path = result.write_html(destination)
        print(path.resolve())
        _open(path, _value(args, report, 'open', False))
        return 0

    _progress(args.progress, 'checking source and columns')
    mode = _value(args, defaults, 'mode', 'standard')
    max_columns = _value(args, defaults, 'max_columns', None)
    max_categories = _value(args, defaults, 'max_categories', 15)
    max_frequency_unique = _value(args, defaults, 'max_frequency_unique', 1000)
    max_groups = _value(args, defaults, 'max_groups', 50)
    max_chart_groups = _value(args, defaults, 'max_chart_groups', 20)
    columns = _value(args, defaults, 'columns', None)
    for key, value in (('max_columns', max_columns), ('max_categories', max_categories),
                       ('max_frequency_unique', max_frequency_unique),
                       ('max_groups', max_groups), ('max_chart_groups', max_chart_groups)):
        if value is not None and value <= 0:
            raise ValueError(f'{key} must be positive')
    if args.no_charts:
        charts = False
    else:
        charts = defaults.get('charts', True)
    if columns is not None:
        columns = _matching_columns(args.source, columns)

    source_path = Path(args.source).expanduser()
    if source_path.is_file():
        default_name = source_path.with_suffix('.profile.html').name
    else:
        default_name = source_path.name + '.profile.html'
        if any(char in default_name for char in '*?[]'):
            default_name = 'dataset.profile.html'
    base = _output_dir(report, source_path.resolve())
    destination = _destination(args.output, base / default_name, force=args.force)
    _check_spec_destination(args.write_spec, force=args.force)

    _progress(args.progress, f'profiling ({mode})')
    result = profile(
        args.source, mode=mode, columns=columns, max_columns=max_columns,
        options=ProfileOptions(charts=charts, max_categories=max_categories,
                               max_unique_for_frequency=max_frequency_unique,
                               max_groups=max_groups, max_chart_groups=max_chart_groups),
    )
    path = result.write_html(destination)
    if args.write_spec is not None:
        result.write_spec(args.write_spec)
    print(path.resolve())
    _open(path, _value(args, report, 'open', False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        return _run(args)
    except (OSError, TypeError, ValueError, KeyError, RuntimeError) as exc:
        parser.error(str(exc))
