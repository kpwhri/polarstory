"""Optional notebook previews with an ordinary-browser fallback."""

from __future__ import annotations

import tempfile
import webbrowser
from pathlib import Path


def _in_notebook() -> bool:
    try:
        from IPython import get_ipython
    except ImportError:
        return False
    shell = get_ipython()
    return shell is not None and hasattr(shell, 'kernel')


def show_report(report, *, browser: bool | None = None):
    """Display notebook HTML, or write a temporary offline browser preview.

    `browser=False` always writes a temporary file without opening a browser,
    which is useful in scripts and automated tests.
    """
    if browser is not True and _in_notebook() and browser is None:
        from IPython.display import HTML, display

        display(HTML(report.to_html()))
        return None

    # private temporary directory for preview contents
    directory = Path(tempfile.mkdtemp(prefix='polarstory-preview-'))
    destination = directory / 'preview.html'
    report.write_html(destination)
    if browser is not False:
        webbrowser.open(destination.as_uri())
    return destination
