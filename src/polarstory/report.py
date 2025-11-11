import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, Union
import polars as pl


def _slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r'[^\w\-]+', '-', text)
    text = re.sub(r'-{2,}', '-', text)
    return text.strip('-') or 'item'


def _ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def _pl_to_markdown_table(df, align_first_col_left: bool = True, formatters: dict[str | int, callable] = None) -> str:
    """
    Render a Polars DataFrame (or any object exposing .columns and .rows()) to GitHub-style Markdown.
    """
    headers = list(df.columns)
    rows = df.rows() if hasattr(df, 'rows') else []
    default_formatters = {
        'percent': lambda x: f'{x:,.2f}%',
        'percent100': lambda x: f'{100 * x:,.2f}%',
        'round': lambda x: f'{x:,.2f}',
        'round_int': lambda x: f'{x:,}',
    }
    dtypes = {col: str(df[col].dtype) for col in df.columns}
    formatters = formatters or dict()
    formatters = {k: default_formatters.get(v, v) for k, v in formatters.items()}
    header_line = '| ' + ' | '.join(str(h) for h in headers) + ' |'
    aligns = []  # row alignment
    for i in range(len(headers)):
        if i == 0 and align_first_col_left:
            aligns.append(':--')
        else:
            aligns.append('--:')
    sep_line = '| ' + ' | '.join(aligns) + ' |'
    lines = [header_line, sep_line]

    for i, row in enumerate(rows):
        curr_line = []
        for j, (value, colname) in enumerate(zip(row, headers)):
            if value is None:
                curr_line.append('')
            else:  # check for special formatting
                if colname in formatters:
                    curr_line.append(formatters[colname](value))
                elif j in formatters:
                    curr_line.append(formatters[j](value))
                elif dtypes[colname].startswith('Int') or dtypes[colname].startswith('UInt'):
                    curr_line.append(default_formatters['round_int'](value))
                elif dtypes[colname].startswith('Float'):
                    curr_line.append(default_formatters['round'](value))
                else:
                    curr_line.append(str(value))

        lines.append('| ' + ' | '.join(curr_line) + ' |')
    return '\n'.join(lines)


def _detect_mpl_figure(obj):
    """Returns a matplotlib.figure.Figure if obj is a Figure or Axes, else None"""
    try:
        import matplotlib.figure as mplfig
        import matplotlib.axes as mplaxes
    except Exception:
        return None
    if isinstance(obj, mplfig.Figure):
        return obj
    if isinstance(obj, mplaxes.Axes):
        return obj.figure
    return None


def _save_plotly_figure(fig, out_path: Path, width: Optional[int] = None, height: Optional[int] = None,
                        scale: float = 2.0):
    """Save a plotly figure"""
    try:
        import plotly.io as pio
    except Exception as e:
        raise RuntimeError('Plotly is not installed. Please install plotly and kaleido for static image export.') from e
    # Requires kaleido installed
    try:
        img_bytes = pio.to_image(fig, format='png', width=width, height=height, scale=scale)
    except Exception as e:
        raise RuntimeError(
            'Failed to export Plotly figure. Ensure "kaleido" is installed (pip install -U kaleido).') from e
    out_path.write_bytes(img_bytes)


@dataclass
class Report:
    title: str = 'Report'
    author: Optional[str] = None
    created: datetime = field(default_factory=datetime.now)
    out_dir: Union[str, Path] = 'report_out'
    md_filename: str = 'report.md'
    assets_dirname: str = 'assets'
    gfm: bool = True  # github-flavored markdown
    _parts: list[str] = field(default_factory=list, init=False)
    _image_counter: int = field(default=0, init=False)

    def __post_init__(self):
        self.out_dir = _ensure_dir(Path(self.out_dir))
        self.assets_dir = _ensure_dir(self.out_dir / self.assets_dirname)

        self.add_heading(self.title, level=1)
        meta = [f'Generated: {self.created:%Y-%m-%d %H:%M}']
        if self.author:
            meta.append(f'Author: {self.author}')
        self.add_paragraph(' | '.join(meta))

    # REPORT COMPONENTS
    def add_heading(self, text: str, level: int = 2) -> 'Report':
        level = max(1, min(level, 6))
        self._parts.append(f'{'#' * level} {text}')
        return self

    def add_paragraph(self, text: str) -> 'Report':
        self._parts.append(str(text))
        return self

    def add_markdown(self, md: str) -> 'Report':
        self._parts.append(md.rstrip())
        return self

    def add_table(self, name: str, table, align_first_col_left: bool = True) -> 'Report':
        if pl is not None and isinstance(table, pl.DataFrame):
            md_table = _pl_to_markdown_table(table, align_first_col_left=align_first_col_left)
        else:
            # Fallback: try to treat 'table' as having .columns and .rows()
            if not hasattr(table, 'columns') or not hasattr(table, 'rows'):
                raise TypeError('table must be a polars.DataFrame or an object exposing .columns and .rows().')
            md_table = _pl_to_markdown_table(table, align_first_col_left=align_first_col_left)

        self.add_heading(name, level=3)
        self.add_markdown(md_table)
        return self

    def add_image(self, image_path: Union[str, Path], caption: Optional[str] = None,
                  width: Optional[str] = None) -> "Report":
        """
        Embed an existing image file. width can be like '80%' or '400px'.
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f'Image not found: {image_path}')

        # Copy into assets for portability
        ext = image_path.suffix.lower()
        safe_name = f"{_slugify(image_path.stem)}{ext}"
        dest = self.assets_dir / safe_name
        if image_path.resolve() != dest.resolve():
            shutil.copyfile(image_path, dest)

        attr = ''
        if width:
            # Pandoc attribute syntax
            attr = f'{{ width="{width}" }}'
        cap = f'\n\n{caption}' if caption else ''
        self._parts.append(f'![{image_path.stem}]({self.assets_dirname}/{safe_name}){attr}{cap}')
        return self

    def add_plot(self, fig, caption: Optional[str] = None, width: Optional[str] = None, dpi: int = 150,
                 size: Optional[tuple[int, int]] = None) -> "Report":
        """
        Add a Matplotlib or Plotly figure as a rasterized image.
        - For Matplotlib: supports Figure or Axes; uses dpi for resolution.
        - For Plotly: requires kaleido installed.
        size: optional pixel (width, height) for Plotly export.
        """
        self._image_counter += 1
        filename = f'figure-{self._image_counter:03d}.png'
        out_path = self.assets_dir / filename

        mpl_fig = _detect_mpl_figure(fig)
        if mpl_fig is not None:
            mpl_fig.savefig(out_path, dpi=dpi, bbox_inches='tight')
        else:
            try:  # try plotly
                w, h = (size if size else (800, 500))
                _save_plotly_figure(fig, out_path, width=w, height=h, scale=2.0)
            except Exception as e:
                raise TypeError('Unsupported figure type. Provide a Matplotlib figure/axes or a Plotly figure.') from e

        attr = f'{{ width="{width}" }}' if width else ''
        self._parts.append(f'![Figure {self._image_counter}]({self.assets_dirname}/{filename}){attr}' + (
            f'\n\n{caption}' if caption else ''))
        return self

    @property
    def md_path(self) -> Path:
        return self.out_dir / self.md_filename

    def to_markdown(self) -> str:
        content = []
        for i, part in enumerate(self._parts):
            part = part.rstrip()
            content.append(part)
            # Ensure a single blank line between parts
            if i < len(self._parts) - 1:
                content.append('')
        return '\n'.join(content)

    def save_markdown(self) -> Path:
        self.md_path.write_text(self.to_markdown() + '\n', encoding='utf8')
        return self.md_path

    def _pick_pdf_engine(self) -> Optional[str]:
        # try engines that don't require full LaTeX first
        for engine in ('wkhtmltopdf', 'weasyprint', 'xelatex', 'pdflatex'):
            if shutil.which(engine):
                return engine
        return None

    def compile(self, output: Optional[Union[str, Path]] = None, to: Optional[str] = None,
                pdf_engine: Optional[str] = None, extra_args: Optional[Iterable[str]] = None,
                open_after=False, print_command_only=False, wsl_mount: str = None) -> Path:
        """
        Compile the Markdown to PDF/DOCX/HTML using Pandoc.
        - output: file path; extension decides the format (e.g., .pdf, .docx, .html).
                  If not provided, uses title + extension inferred from 'to' or defaults to .pdf.
        - to: 'pdf' | 'docx' | 'html' (optional if output has an extension).
        - pdf_engine: override auto-detected engine (e.g., 'wkhtmltopdf', 'xelatex').
        - extra_args: additional Pandoc args as an iterable.
        - open_after: open the resulting file after compilation (OS default handler).
        - print_command_only: instead of running, just print the command so it can be used in, e.g., wsl.
        - wsl_mount: print command only, but do it for WSL (assmes on Windows) using specified mount (e.g., 'mnt')
        """
        if wsl_mount:
            print_command_only = True
            if wsl_mount is True:
                wsl_mount = 'mnt'
        if shutil.which('pandoc') is None and not print_command_only:
            raise RuntimeError('Pandoc is not installed or not on PATH. Install from https://pandoc.org/install.html')

        md_path = self.save_markdown()

        # Determine format/extension
        if output is None:
            base = _slugify(self.title) or 'report'
            ext = '.pdf' if (to is None or to.lower() == 'pdf') else f'.{to.lower()}'
            output = self.out_dir / f'{base}{ext}'
        output = Path(output)
        if to is None:
            to = output.suffix.lstrip('.').lower()
        elif output.suffix.lower() != f'.{to}':
            # Normalize output path to requested format
            output = output.with_suffix(f'.{to}')

        # Build Pandoc command
        cmd = ['pandoc', '-s', '--from', 'gfm', wsl_str(md_path, wsl_mount), '-o', wsl_str(output, wsl_mount)]
        # Resource path so images are found
        cmd += ['--resource-path', wsl_str(self.assets_dir, wsl_mount)]
        # Metadata
        cmd += ['-M', f'title={self.title}', '-M', f'author={self.author or ''}', '-M',
                f'date={self.created:%Y-%m-%d %H:%M}']

        if to == 'pdf':
            engine = pdf_engine or self._pick_pdf_engine()
            if engine is None and not print_command_only:
                raise RuntimeError(
                    'No PDF engine found. Install one of: wkhtmltopdf, weasyprint, or a LaTeX engine (xelatex/pdflatex).'
                )
            cmd += ['--pdf-engine', engine]

        if extra_args:
            cmd += list(extra_args)

        if print_command_only:
            print(' '.join(cmd))
        else:  # run pandoc
            subprocess.run(cmd, check=True)

            if open_after:
                try:
                    if os.name == 'nt':
                        os.startfile(str(output))  # type: ignore[attr-defined]
                    elif os.name == 'posix':
                        subprocess.Popen(['xdg-open', str(output)])
                    else:
                        subprocess.Popen(['open', str(output)])
                except Exception:
                    pass

        return output


def wsl_str(path: Path, mnt='mnt'):
    if mnt:
        path = str(path.resolve())
        drive = path[0].lower()
        path_no_drive = path[2:].replace('\\', '/')
        return f'/{mnt}/{drive}{path_no_drive}'
    else:
        return str(path)
