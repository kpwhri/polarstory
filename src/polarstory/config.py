"""Small TOML configuration reader shared by CLI entry points."""

from __future__ import annotations

import tomllib
from pathlib import Path

_PROFILE_FIELDS = {
    'mode': (str, {'quick', 'standard', 'full'}),
    'max_columns': (int, None),
    'max_categories': (int, None),
    'max_groups': (int, None),
    'max_chart_groups': (int, None),
    'max_frequency_unique': (int, None),
    'columns': (str, None),
    'charts': (bool, None),
}
_REPORT_FIELDS = {
    'open': (bool, None),
    'output_directory': (str, None),
}


def load_config(path: str | Path | None = None, *, source: str | Path | None = None) -> dict:
    """Read ``polarstory.toml`` in cwd or next to a source unless explicit.

    Explicit configuration files must exist. The configuration is validated,
    but no file contents other than TOML are read at this stage.
    """
    if path is not None:
        location = Path(path).expanduser().resolve()
        if not location.is_file():
            raise FileNotFoundError(f'Configuration file not found: {location}')
    else:
        candidates = [Path.cwd() / 'polarstory.toml']
        if source is not None:
            candidate = Path(source).expanduser()
            if candidate.is_file():
                candidates.append(candidate.resolve().parent / 'polarstory.toml')
        location = next((p for p in candidates if p.is_file()), None)
        if location is None:
            return {'profile': {}, 'report': {}}
    try:
        with location.open('rb') as handle:
            settings = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f'Invalid TOML configuration {location}: {exc}') from exc
    if not isinstance(settings, dict):
        raise ValueError('Configuration must contain TOML tables')
    unexpected = settings.keys() - {'profile', 'report'}
    if unexpected:
        raise ValueError(f'Unknown configuration sections: {", ".join(sorted(unexpected))}')
    for section, fields in (('profile', _PROFILE_FIELDS), ('report', _REPORT_FIELDS)):
        values = settings.get(section, {})
        if not isinstance(values, dict):
            raise ValueError(f'[{section}] must be a TOML table')
        for name, value in values.items():
            if name not in fields:
                raise ValueError(f'Unknown [{section}] setting: {name}')
            typ, allowed = fields[name]
            if type(value) is not typ or (allowed is not None and value not in allowed):
                raise ValueError(f'Invalid [{section}].{name}: {value!r}')
            if name.startswith('max_') and value <= 0:
                raise ValueError(f'[{section}].{name} must be positive')
    return {
        'profile': settings.get('profile', {}),
        'report': settings.get('report', {}),
    }
