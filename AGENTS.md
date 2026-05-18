# AGENTS.md

## Cursor Cloud specific instructions

This is a Python CLI project (no web frontend, no Docker, no external services).

### Quick reference

- **Install deps**: `python3 -m pip install -e '.[dev]'`
- **Lint**: `make lint`
- **Test**: `make test` (15 offline tests, all use mocks/fixtures, no API keys needed)
- **Run the app**: `make run-report` (fixture data, dry-run, no API keys needed)
- **View latest report**: `python3 -m devforum_research.cli latest`

All Makefile targets and CLI usage are documented in `README.md`.

### Non-obvious notes

- The `runs/` directory is generated output and is not checked in. The `data/` directory holds the SQLite DB created at runtime. Both can be safely deleted to reset state.
- The example config (`config/example.yaml`) uses fixture data and `as_of` date pinning, so dry-run output is deterministic and date-stable regardless of when it is executed.
- `GITHUB_TOKEN` and `OPENAI_API_KEY` are only needed for live GitHub/LLM source connectors, not for tests or the fixture report.
- `ruff` is used for both linting (`ruff check`) and formatting (`ruff format`). The `make lint` target only runs `check`; run `make fmt` before committing if you modify Python files.
