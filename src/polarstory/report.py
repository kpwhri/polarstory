"""Self-contained, JavaScript-free HTML reporting and reusable components."""

from __future__ import annotations

import json
import os
import re
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import datetime
from html import escape
from importlib.resources import files
from importlib.metadata import version
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

import polars as pl
from jinja2 import Environment, BaseLoader, select_autoescape
from matplotlib import rc_context
from matplotlib.figure import Figure

if TYPE_CHECKING:
    from polarstory.profile import Profile


@dataclass(frozen=True)
class ReportItem:
    """A small, reusable result and presentation metadata.

    A report assigns an ID on insertion; one item can be reused in several
    reports without changing the original item. `content` is an already
    aggregated table or a Matplotlib figure, not source dataframe rows.
    """

    kind: str
    title: str
    content: pl.DataFrame | Figure | str
    caption: str | None = None
    notes: str | None = None
    id: str | None = None
    recipe: dict | None = field(default=None, repr=False)

    def to_html(self) -> str:
        """Render only this component as a standalone HTML document."""
        report = Report(self.title or 'Preview')
        report.add(self)
        return report.to_html()

    def show(self, *, browser: bool | None = None):
        """Preview this component in a notebook or a local browser."""
        from polarstory.preview import show_report

        report = Report(self.title or 'Preview')
        report.add(self)
        return show_report(report, browser=browser)


@dataclass
class ReportSection:
    title: str
    items: list[ReportItem] = field(default_factory=list)


def _format(value: object) -> str:
    if value is None:
        return '—'
    if isinstance(value, float):
        return f'{value:,.3f}' if abs(value) < 1000 else f'{value:,.2f}'
    if isinstance(value, int):
        return f'{value:,}'
    return str(value)


def _table_html(frame: pl.DataFrame) -> str:
    """Escape both headers and values; do not include the dataframe index."""
    headers = ''.join(f'<th scope="col">{escape(name)}</th>' for name in frame.columns)
    body = []
    for row in frame.iter_rows():
        cells = ''.join(f'<td>{escape(_format(value))}</td>' for value in row)
        body.append(f'<tr>{cells}</tr>')
    return '<div class="table-scroll"><table><thead><tr>' + headers + (
            '</tr></thead><tbody>' + ''.join(body) + '</tbody></table></div>'
    )


def _figure_svg(figure: Figure, *, salt: str = '') -> str:
    """Namespace SVG identifiers for safe embedding in a shared HTML document.

    Matplotlib hashes some element identifiers but reuses glyph identifiers
    across separately rendered SVGs. Embedded charts therefore require
    per-chart identifiers and updated internal references.
    """
    output = StringIO()
    with rc_context({'svg.fonttype': 'path', 'svg.hashsalt': salt}):
        figure.savefig(output, format='svg', bbox_inches='tight')
    svg = output.getvalue()
    start = svg.find('<svg')
    if start < 0:
        raise ValueError('Matplotlib did not produce an SVG')
    svg = svg[start:]
    identifiers = set(re.findall(r'\bid="([^"]+)"', svg))
    prefix = salt or 'polarstory'
    mapped = {value: f'{prefix}-{value}' for value in identifiers}

    svg = re.sub(
        r'\bid="([^"]+)"',
        lambda match: f'id="{mapped[match.group(1)]}"',
        svg,
    )
    svg = re.sub(
        r'((?:xlink:)?href=")#([^"]+)"',
        lambda match: f'{match.group(1)}#{mapped.get(match.group(2), match.group(2))}"',
        svg,
    )
    svg = re.sub(
        r'url\(#([^\)]+)\)',
        lambda match: f'url(#{mapped.get(match.group(1), match.group(1))})',
        svg,
    )
    return svg


class Report:
    """Ordered static tables, charts and text, independent of input datasets."""

    def __init__(self, title: str = 'Data profile', *, subtitle: str | None = None,
                 max_table_rows: int | None = 2000):
        if max_table_rows is not None and max_table_rows < 1:
            raise ValueError('max_table_rows must be positive or None')
        self.max_table_rows = max_table_rows
        self.title = title
        self.subtitle = subtitle
        self.sections: list[ReportSection] = [ReportSection('Overview')]
        self._active = self.sections[0]
        self._next_id = 1

    @property
    def items(self) -> tuple[ReportItem, ...]:
        """All items in their current display order."""
        return tuple(item for section in self.sections for item in section.items)

    @contextmanager
    def section(self, title: str) -> Iterator[Report]:
        """Group subsequent additions under a named heading."""
        previous = self._active
        current = ReportSection(title)
        self.sections.append(current)
        self._active = current
        try:
            yield self
        finally:
            self._active = previous

    def add(self, item: object) -> ReportItem | tuple[ReportItem, ...]:
        """Insert a component or a complete variable profile.

        A variable profile expands to its summary and optional chart and
        returns a tuple of inserted report components.
        """
        from polarstory.profile import VariableProfile

        if isinstance(item, VariableProfile):
            return tuple(self.add(component) for component in item.report_items())
        if not isinstance(item, ReportItem):
            raise TypeError('add expects a ReportItem or VariableProfile')
        if item.kind not in ('table', 'chart', 'text'):
            raise ValueError(f'Unknown item kind: {item.kind}')
        if item.id is not None:
            if not item.id or not all(c.isalnum() or c in '_-' for c in item.id):
                raise ValueError('ReportItem id must contain only letters, digits, _ or -')
            if any(existing.id == item.id for existing in self.items):
                raise ValueError(f'Duplicate report item id: {item.id}')
            inserted = item
        else:
            existing_ids = {existing.id for existing in self.items}
            while f'item-{self._next_id}' in existing_ids:
                self._next_id += 1
            inserted = replace(item, id=f'item-{self._next_id}')
            self._next_id += 1
        self._active.items.append(inserted)
        return inserted

    def remove(self, item_id: str) -> ReportItem:
        """Remove an item from any section by its stable ID."""
        for section in self.sections:
            for index, item in enumerate(section.items):
                if item.id == item_id:
                    return section.items.pop(index)
        raise KeyError(f'Unknown report item: {item_id}')

    def move(self, item_id: str, *, before: str | None = None) -> None:
        """Reorder an item; `before` can also target another section.

        Without `before`, move the item to the end of its existing section.
        """
        if before == item_id:
            return
        found = next(((section, index) for section in self.sections
                      for index, item in enumerate(section.items) if item.id == item_id), None)
        if found is None:
            raise KeyError(f'Unknown report item: {item_id}')
        if before is None:
            section, index = found
            section.items.append(section.items.pop(index))
            return
        target = next(((section, index) for section in self.sections
                       for index, item in enumerate(section.items) if item.id == before), None)
        if target is None:
            raise KeyError(f'Unknown target report item: {before}')
        source_section, source_index = found
        target_section, _ = target
        item = source_section.items.pop(source_index)
        # resolve target index after removal
        target_index = next(i for i, value in enumerate(target_section.items) if value.id == before)
        target_section.items.insert(target_index, item)

    def add_table(
            self, data: pl.DataFrame | pl.LazyFrame,
            *, title: str, caption: str | None = None, notes: str | None = None,
            id: str | None = None,
    ) -> ReportItem:
        """Add an aggregated polars table to the current section.
        
        Args:
            data: Eager or lazy polars table to include.
            title: Visible table heading.
            caption: Optional caption below the table.
            notes: Optional explanatory notes.
            id: Optional stable component ID.
        
        Returns:
            The added report item.
        
        Raises:
            ValueError: If the table exceeds the configured row limit.
        
        """
        # bound lazy results before collection
        if isinstance(data, pl.LazyFrame):
            data = (data.limit(self.max_table_rows + 1).collect()
                    if self.max_table_rows is not None else data.collect())
        if not isinstance(data, pl.DataFrame):
            raise TypeError('add_table expects a polars DataFrame or LazyFrame')
        if self.max_table_rows is not None and data.height > self.max_table_rows:
            raise ValueError(
                f'Table {title!r} has more than {self.max_table_rows:,} rows; '
                'summarize it before adding, or configure max_table_rows=None'
            )
        return self.add(ReportItem('table', title, data, caption, notes, id))

    def add_chart(
            self, figure: Figure,
            *, title: str, caption: str | None = None, notes: str | None = None,
            id: str | None = None,
    ) -> ReportItem:
        """Add a static Matplotlib figure to the current section.
        
        Args:
            figure: Figure to render as embedded SVG.
            title: Visible chart heading.
            caption: Optional caption.
            notes: Optional explanatory notes.
            id: Optional stable component ID.
        
        Returns:
            The added report item.
        
        """
        if not isinstance(figure, Figure):
            raise TypeError('add_chart expects a Matplotlib Figure')
        return self.add(ReportItem('chart', title, figure, caption, notes, id))

    def add_text(self, text: str, *, title: str = '', id: str | None = None) -> ReportItem:
        """Add a plain-text paragraph; HTML is escaped on rendering."""
        return self.add(ReportItem('text', title, text, id=id,
                                   recipe={'type': 'text', 'title': title, 'content': text}))

    def add_table1(
            self, data: object, columns: list[str] | tuple[str, ...],
            *, title: str = 'Cohort characteristics', by: str | None = None,
            caption: str | None = None, **kwargs,
    ) -> ReportItem:
        """Compute and insert one formatted descriptive Table 1 (no p-values)."""
        from polarstory.stats import table1
        from polarstory.source import as_source
        frame = table1(data, columns, by=by, **kwargs)
        recipe = None
        source = as_source(data)
        if source.kind == 'parquet' and kwargs.get('variables') is None:
            recipe = {
                'type': 'table1', 'sources': [str(path) for path in source.paths],
                'columns': list(columns), 'by': by, 'kwargs': kwargs,
                'title': title, 'caption': caption,
            }
        return self.add(ReportItem(
            'table', title, frame, caption,
            'Descriptive statistics only; no hypothesis tests.', recipe=recipe,
        ))

    def add_profile(self, data: object, *, title: str | None = None, **kwargs) -> Report:
        """Append sections from a Profile or a dataframe/path, without raw rows."""
        from polarstory.profile import Profile, profile

        result = data if isinstance(data, Profile) else profile(data, **kwargs)
        if title is None:
            title = result.title
        with self.section(title):
            for item in result.items():
                self.add(item)
        return self

    def to_spec(self) -> dict:
        """Return a **recomputable** recipe for a file-backed curated report.

        Supported items: profile components from parquet, descriptive Table 1
        from parquet without custom Variables, and plain text. Arbitrary
        dataframe tables or custom figures have no portable JSON recipe;
        this raises rather than silently saving an incomplete specification.
        """
        sections = []
        for section in self.sections:
            entries = []
            for item in section.items:
                if item.recipe is None:
                    raise ValueError(
                        f'Item {item.id} ({item.title}) cannot be regenerated from JSON; '
                        'save the Python script that creates this item instead'
                    )
                entries.append({'id': item.id, 'recipe': deepcopy(item.recipe)})
            sections.append({'title': section.title, 'items': entries})
        return {
            'format': 'polarstory.report/v1', 'title': self.title,
            'subtitle': self.subtitle, 'sections': sections,
        }

    def write_spec(self, path: str | Path) -> Path:
        """Write a portable recipe, using source paths relative to the JSON."""
        destination = Path(path).expanduser().resolve()
        spec = self.to_spec()
        for section in spec['sections']:
            for item in section['items']:
                recipe = item['recipe']
                paths = (recipe['profile']['sources'] if recipe['type'] in ('profile_item', 'explorer_view')
                         else recipe['sources'] if recipe['type'] == 'table1' else None)
                if paths is not None:
                    # rebase absolute source paths relative to the recipe
                    rebased = []
                    for value in paths:
                        try:
                            rebased.append(os.path.relpath(value, destination.parent))
                        # different Windows drives
                        except ValueError:
                            rebased.append(str(value))
                    paths[:] = rebased
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + '\n', encoding='utf8')
        return destination

    @classmethod
    def from_spec(cls, path: str | Path) -> Report:
        """Regenerate a curated report from a JSON recipe and parquet files."""
        from polarstory.profile import _profile_from_definition
        from polarstory.source import DataSource, as_source
        from polarstory.stats import table1

        location = Path(path).expanduser().resolve()
        spec = json.loads(location.read_text(encoding='utf8'))
        if spec.get('format') != 'polarstory.report/v1':
            raise ValueError('Unsupported polarstory report specification')
        result = cls(spec.get('title', 'Report'), subtitle=spec.get('subtitle'))
        result.sections = []
        profile_cache = {}
        for section in spec['sections']:
            group = ReportSection(section['title'])
            result.sections.append(group)
            result._active = group
            for entry in section['items']:
                recipe = entry['recipe']
                kind = recipe['type']
                if kind in ('profile_item', 'explorer_view'):
                    # reuse profiles for components sharing a source
                    key = json.dumps(recipe['profile'], sort_keys=True)
                    if key not in profile_cache:
                        profile_cache[key] = _profile_from_definition(
                            recipe['profile'], base_dir=location.parent,
                        )
                    cached_profile = profile_cache[key]
                    if kind == 'profile_item':
                        item = cached_profile.item(recipe['name'], recipe['kind'])
                    else:
                        from polarstory.explorer import Explorer

                        items = Explorer(cached_profile).preview(
                            recipe['name'], view=recipe['view'],
                            by=recipe.get('by'), bins=recipe.get('bins'),
                            top_n=recipe.get('top_n'),
                            denominator=recipe.get('denominator', 'total'),
                            groups=recipe.get('groups'),
                        )
                        if len(items) != 1:
                            raise ValueError('Explorer recipe must resolve to one component')
                        item = items[0]
                elif kind == 'table1':
                    paths = tuple((location.parent / p).resolve() for p in recipe['sources'])
                    if not paths or any(not p.is_file() for p in paths):
                        raise FileNotFoundError('parquet source missing for Table 1')
                    source = as_source(paths[0]) if len(paths) == 1 else DataSource(
                        pl.scan_parquet([str(p) for p in paths]), 'Saved Table 1',
                        'parquet', paths=paths,
                    )
                    frame = table1(source, recipe['columns'], by=recipe['by'],
                                   **recipe['kwargs'])
                    item = ReportItem('table', recipe['title'], frame,
                                      recipe.get('caption'),
                                      'Descriptive statistics only; no hypothesis tests.',
                                      recipe=recipe)
                elif kind == 'text':
                    item = ReportItem('text', recipe['title'], recipe['content'],
                                      recipe=recipe)
                else:
                    raise ValueError(f'Unsupported report component recipe: {kind}')
                result.add(replace(item, id=entry['id']))
        if not result.sections:
            result.sections = [ReportSection('Overview')]
        result._active = result.sections[0]
        return result

    def _render_sections(self) -> list[dict]:
        """Render report items once for browser and notebook output."""
        render_sections = []
        svg_index = 0
        for index, section in enumerate(self.sections):
            rendered = []
            for item in section.items:
                if item.kind == 'table':
                    html = _table_html(item.content)
                elif item.kind == 'chart':
                    html = _figure_svg(item.content, salt=f'polarstory-{svg_index}')
                    svg_index += 1
                elif item.kind == 'text':
                    html = '<p>' + escape(item.content).replace('\n', '<br>') + '</p>'
                else:
                    raise ValueError(f'Unknown item kind: {item.kind}')
                rendered.append({'item': item, 'html': html})
            if rendered:
                render_sections.append({
                    'id': f'section-{index}', 'title': section.title,
                    'items': rendered,
                })
        return render_sections

    def to_html(self) -> str:
        """Return a complete offline HTML document as a string."""
        template_root = files('polarstory').joinpath('templates')
        template = template_root.joinpath('report.html').read_text(encoding='utf8')
        stylesheet = template_root.joinpath('style.css').read_text(encoding='utf8')
        environment = Environment(loader=BaseLoader(), autoescape=select_autoescape(['html']))
        pl_version = version('polarstory')
        return environment.from_string(template).render(
            title=self.title,
            subtitle=self.subtitle,
            sections=self._render_sections(),
            stylesheet=stylesheet,
            generated_at=datetime.now().astimezone().isoformat(sep=' ', timespec='minutes'),
            version=pl_version,
        )

    def _to_notebook_html(self) -> str:
        """Render a theme-aware fragment without affecting the notebook page."""
        template_root = files('polarstory').joinpath('templates')
        template = template_root.joinpath('notebook.html').read_text(encoding='utf8')
        stylesheet = template_root.joinpath('notebook.css').read_text(encoding='utf8')
        environment = Environment(loader=BaseLoader(), autoescape=select_autoescape(['html']))
        return environment.from_string(template).render(
            title=self.title,
            sections=self._render_sections(),
            stylesheet=stylesheet,
        )

    def write_html(self, path: str | Path) -> Path:
        """Write a self-contained HTML report, creating directories if needed."""
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(self.to_html(), encoding='utf8')
        return destination
