.PHONY: dev fmt lint test run-report

dev:
	python3 -m pip install -e '.[dev]'

fmt:
	python3 -m ruff format src tests

lint:
	python3 -m ruff check src tests

test:
	python3 -m pytest -q

run-report:
	python3 -m devforum_research.cli run --config config/example.yaml --dry-run
