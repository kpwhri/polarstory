# Building the Documentation

Polarstory's documentation is built with MkDocs. Run the commands below from the project root (where `mkdocs.yml` lives).

## Preview locally

```powershell
python -m pip install -r docs/requirements.txt
python -m mkdocs serve
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) to view the site. MkDocs updates the preview as you edit pages.

## Check the build

```powershell
python scripts/check_docs.py
python -m mkdocs build --strict
```

The built site is written to `site/`. You don't need to commit that folder.

## Publish to GitHub Pages

In the repository's **Settings → Pages**, select **GitHub Actions** as the build source. To publish manually, open **Actions → Documentation → Run workflow**. The workflow builds the site and deploys it to GitHub Pages.

## Update the API reference

API signatures and descriptions come from Python docstrings. Edit the docstring in `src/polarstory/`, then update the relevant example in `docs/reference/` if needed. Run the checks above before publishing.
