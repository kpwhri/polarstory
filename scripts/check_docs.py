"""Check API identifiers and internal Markdown links without importing polarstory."""

from __future__ import annotations

import ast
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
SRC = ROOT / 'src' / 'polarstory'

REFERENCE = re.compile(r'^::: (polarstory(?:\.\w+)+)', re.MULTILINE)
LINK = re.compile(r'(?<!\!)\[[^\]]*\]\(([^)]+)\)')


def source_object_exists(identifier: str) -> bool:
    parts = identifier.split('.')
    if len(parts) < 3 or parts[0] != 'polarstory':
        return False
    file = SRC / f'{parts[1]}.py'
    if not file.is_file():
        return False
    nodes = ast.parse(file.read_text(encoding='utf8')).body
    for part in parts[2:]:
        object_node = next(
            (item for item in nodes
             if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
             and item.name == part),
            None,
        )
        if object_node is None:
            return False
        nodes = object_node.body if isinstance(object_node, ast.ClassDef) else []
    return True


def check_docs() -> list[str]:
    errors = []
    paths = list(DOCS.rglob('*.md'))
    normalized = [str(path.relative_to(DOCS)).lower() for path in paths]
    if len(normalized) != len(set(normalized)):
        errors.append('documentation filenames collide on case-insensitive file systems')

    symbols = {}
    for path in paths:
        content = path.read_text(encoding='utf8')
        for identifier in REFERENCE.findall(content):
            if not source_object_exists(identifier):
                errors.append(f'{path.relative_to(ROOT)}: unknown API object {identifier}')
            if identifier in symbols:
                errors.append(f'{identifier}: documented on both {symbols[identifier]} and {path}')
            symbols[identifier] = path
        for target in LINK.findall(content):
            target = target.strip().split(' ', 1)[0].strip('"\'')
            if not target or target.startswith(('#', 'mailto:', 'tel:')):
                continue
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc:
                continue
            link_path = (path.parent / unquote(parsed.path)).resolve()
            if not link_path.exists():
                errors.append(f'{path.relative_to(ROOT)}: missing link {target}')
    if len(symbols) < 75:
        errors.append(f'expected per-callable reference pages, found only {len(symbols)}')
    return errors


if __name__ == '__main__':
    problems = check_docs()
    if problems:
        print('\n'.join(problems))
        raise SystemExit(1)
    print('Documentation API references and relative links validated')
