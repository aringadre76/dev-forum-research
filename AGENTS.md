# AGENTS.md

## Cursor Cloud specific instructions

This is a Python 3.11+ CLI project. The active codebase lives on the `cursor/devforum-research-mvp-afe7` branch (the `main` branch contains only a placeholder README).

### Quick reference

| Task | Command |
|------|---------|
| Install deps | `python3 -m pip install -e '.[dev]'` |
| Lint | `make lint` |
| Tests | `make test` |
| Run pipeline (no API keys needed) | `make run-report` |
| View latest report | `python3 -m devforum_research.cli latest` |

All commands are documented in the `Makefile` and `README.md`.

### Non-obvious notes

- The installed scripts (pytest, ruff, devforum-research) land in `/home/ubuntu/.local/bin`. Ensure this directory is on `PATH` when running outside of `make` targets (the `Makefile` invokes tools via `python3 -m` so it works regardless).
- The full pipeline runs offline using synthetic fixture data and deterministic hashed embeddings. No `GITHUB_TOKEN` or `OPENAI_API_KEY` is required for `make run-report` (dry-run mode).
- SQLite DB files are created in `data/` at runtime and are gitignored. The `runs/` directory holds timestamped outputs and is also gitignored.
- To enable LLM-powered IdeaBrief generation, set `OPENAI_API_KEY` and run without `--dry-run`.
