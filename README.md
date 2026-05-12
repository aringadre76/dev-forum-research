# DevForum Research

DevForum Research is an MVP CLI for evidence-backed devtools and AI-devtools opportunity research.
It ingests configured public sources, normalizes documents with provenance, indexes them locally,
scores recurring pain themes, and writes dated Markdown and JSON reports.

The default example uses a tiny synthetic fixture dataset so the full pipeline runs without secrets.
GitHub Issues and RSS or Atom feeds are available as source connectors.

## Compliance stance

- API-first ingestion. GitHub data is read through the GitHub REST API.
- RSS and Atom feeds are consumed through feed URLs configured by the user.
- No prohibited scraping is implemented.
- If future HTTP fetching is added beyond official APIs and feeds, it should respect robots.txt and source terms.
- RSS descriptions are sanitized before storage to remove unsafe HTML.
- Tokens and API keys are read from environment variables and must not be committed.

## Architecture

- `SourceConnector` is the extension interface for ingestion.
- `Document` is the unified schema for GitHub Issues, RSS entries, and fixtures.
- `SQLiteStore` persists documents, source cursors, and local vectors.
- `HashingEmbeddingModel` provides deterministic local embeddings for MVP use.
- `LocalVectorIndex` combines vector similarity with a small keyword overlap boost.
- `ResearchOrchestrator` runs ingest, index, theme discovery, gap scoring, evidence compilation, optional LLM idea generation, and artifact writing.
- `LLMClient` is the provider abstraction. The included implementation is OpenAI-compatible.

SQLite plus deterministic hashed embeddings were chosen because they keep the MVP local, reproducible,
and runnable without paid embedding credentials. The limitation is that retrieval is less semantic than
hosted embedding models or a dedicated vector database.

## Setup

```bash
python3 -m pip install -e '.[dev]'
```

Copy the example environment file if you plan to use GitHub or LLM mode:

```bash
cp .env.example .env
```

Environment variables:

- `GITHUB_TOKEN`: Optional for GitHub API ingestion, recommended for rate limits.
- `OPENAI_API_KEY`: Enables IdeaBrief generation when not using dry-run mode.
- `OPENAI_BASE_URL`: Optional OpenAI-compatible endpoint.
- `OPENAI_MODEL`: Optional model name, defaults to `gpt-4o-mini`.

## Commands

Run tests:

```bash
make test
```

Run lint:

```bash
make lint
```

Format code:

```bash
make fmt
```

Run the fixture report in deterministic dry-run mode:

```bash
make run-report
```

Run directly:

```bash
python3 -m devforum_research.cli run --config config/example.yaml --dry-run
```

View the latest Markdown report:

```bash
python3 -m devforum_research.cli latest
```

Enable LLM IdeaBrief generation:

```bash
OPENAI_API_KEY=your_key python3 -m devforum_research.cli run --config config/example.yaml
```

## Source configuration

Edit `config/example.yaml` or create another YAML file:

```yaml
name: DevForum Research
storage_path: data/devforum.sqlite
known_tools_path: data/known_tools.yaml
sources:
  - type: github
    repo: owner/repo
    max_pages: 2
    per_page: 100
  - type: rss
    name: example-feed
    url: https://example.com/feed.xml
    max_entries: 50
research:
  days: 30
  top_k_themes: 5
  max_themes: 12
  evidence_per_theme: 4
  output_dir: runs
```

## Outputs

Each run writes artifacts to `runs/<timestamp>/`:

- `logs.jsonl`: Structured stage logs.
- `documents.json`: Normalized documents used in the run.
- `themes.json`: Theme and gap scoring details.
- `report.json`: Validated report object.
- `report.md`: Markdown export.

A checked-in sample report is available at `examples/sample_report.md`.

## Gap scoring signals

The MVP implements these scoring signals:

1. High-reply unresolved threads, using GitHub issue state and reply count where available.
2. Repeated two-word phrases across documents.
3. Workaround language such as `hacky`, `workaround`, `gave up`, `still broken`, `wontfix`, `blocked`, and `manual step`.
4. Freshness boost for recent documents.

These are prioritization heuristics. They identify themes worth investigating, not validated demand.

## Known tools knowledge base

`data/known_tools.yaml` contains seed entries across devtools and AI-devtools. LLM mode includes this file in
the prompt and asks the model to compare ideas against relevant tools by name.

## LLM behavior

When `OPENAI_API_KEY` is missing or `--dry-run` is used, the pipeline skips IdeaBrief generation and writes
themes plus evidence excerpts. When LLM mode is enabled:

- Responses are parsed into the required `IdeaBrief` schema with Pydantic.
- JSON parse or schema failure is retried once.
- Every evidence URL must match an ingested document URL.
- The model is instructed not to invent URLs.

## Tests

The test suite covers:

- GitHub and RSS document normalization.
- RSS HTML sanitization.
- IdeaBrief schema validation.
- Citation enforcement.
- Local vector retrieval.
- Golden-style clustering and gap scoring on synthetic data.

## Extension points

To add a new source:

1. Implement `SourceConnector` from `src/devforum_research/connectors/base.py`.
2. Normalize data into `Document`.
3. Add a source config model in `src/devforum_research/config.py`.
4. Register the connector in `build_connectors`.
5. Add normalization tests and fixture coverage.

## Limitations

- GitHub Discussions are not implemented yet, though the schema allows a future `github_discussion` source type.
- Stack Exchange tags are not implemented in this MVP.
- The local embedding model is deterministic and cheap, but not deeply semantic.
- RSS sources often lack thread metadata, reply counts, or resolution state.
- The fixture report is synthetic and intended for pipeline verification.
- Novelty detection is heuristic and should be paired with interviews and landing-page validation.
