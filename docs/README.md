## Building the Documentation

Run these commands from the **project root** (the directory containing `mkdocs.yml`).

```bash
python -m pip install -r docs/requirements.txt
python scripts/check_docs.py
python -m mkdocs serve
```

Open **http://127.0.0.1:8000/** to preview the site. MkDocs updates it as you edit the documentation.

To check and build the static site:

```bash
python -m mkdocs build --strict
```

The generated html is written to `site/`.

For publishing, a GitHub workflow is available at: `.github/workflows/build_docs.yml`.