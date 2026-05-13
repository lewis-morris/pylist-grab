# Repository Guidelines

## Project Structure & Module Organization
Source modules live at the repository root. `cli.py` hosts the command-line entrypoint, `gui.py` launches the desktop workflow, while `downloader.py` contains the download pipeline and metadata helpers. Shared utilities sit in `utils.py`, and logging defaults defined in `logging_config.py` stream to `application.log`. Static imagery and theme resources reside under `assets/`; keep new binaries lightweight and document their use. Place future tests in a top-level `tests/` package that mirrors the module layout.

## Build, Test, and Development Commands
Create a virtual environment (`python -m venv .venv && source .venv/bin/activate`) before installing dependencies (`python -m pip install -r requirements.txt` if present, otherwise install per module imports). Run the CLI locally with `python cli.py -d <output_dir> <playlist_url> [-g <genre>]`. Launch the GUI via `python gui.py`. If you add automated checks, expose them with `make test` or `python -m pytest` and update this section accordingly.

## Coding Style & Naming Conventions
Follow PEP 8 with 4-space indentation and `snake_case` for functions, methods, and variables. Use `PascalCase` only for classes or dataclasses like `SimplePlaylist`. Keep functions focused and prefer early returns. When touching asynchronous or threaded code paths, add concise docstrings explaining side effects. Run a formatter such as `black` and lint with `ruff` or `flake8` before opening a PR; include configuration in `pyproject.toml` if you introduce new tooling.

## Testing Guidelines
Adopt `pytest` for new tests and structure files as `test_<module>.py`. Target playlist validation, metadata tagging, and download flow helpers with unit tests that mock network and filesystem calls. Cover boundary cases: empty playlists, duplicate filenames, and failed artwork fetches. Wire tests into CI once available, and keep coverage high for pure functions in `utils.py` and metadata helpers in `downloader.py`.

## Commit & Pull Request Guidelines
Write commits in the imperative mood (“Add progress bar redraw fix”) and keep subjects under 72 characters. Avoid vague summaries like “changes” that currently appear in history. Squash noise before reviewing. Pull requests should describe motivation, list functional changes, cite related issues, and include screenshots for GUI updates or sample CLI output. Mention new dependencies, update instructions in this guide as needed, and confirm lint/tests have run.
