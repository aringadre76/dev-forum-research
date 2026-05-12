from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

from devforum_research.config import (
    AppConfig,
    FixtureSourceConfig,
    GitHubSourceConfig,
    RSSSourceConfig,
)
from devforum_research.connectors.base import SourceConnector, SourceState
from devforum_research.connectors.fixtures import FixtureConnector
from devforum_research.connectors.github import GitHubConnector
from devforum_research.connectors.rss import RSSConnector
from devforum_research.index.store import LocalVectorIndex
from devforum_research.llm.client import LLMClient, build_llm_client
from devforum_research.models import (
    Document,
    KnownTool,
    ResearchReport,
    Theme,
    ThemeEvidence,
    ThemeSignals,
    validate_citations,
)
from devforum_research.storage import SQLiteStore
from devforum_research.text import excerpt, tokenize, top_ngrams

WORKAROUND_RE = re.compile(
    (
        r"\b(hacky|workaround|gave up|still broken|wontfix|won't fix|blocked|stuck|"
        r"fails again|manual step)\b"
    ),
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RunArtifacts:
    run_id: str
    run_dir: Path
    report_json: Path
    report_markdown: Path
    logs_path: Path


class StructuredLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, stage: str, message: str, **fields: object) -> None:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "stage": stage,
            "message": message,
            **fields,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")


def build_connectors(config: AppConfig) -> list[SourceConnector]:
    connectors: list[SourceConnector] = []
    for source in config.sources:
        if isinstance(source, GitHubSourceConfig):
            connectors.append(
                GitHubConnector(
                    repo=source.repo,
                    max_pages=source.max_pages,
                    per_page=source.per_page,
                )
            )
        elif isinstance(source, RSSSourceConfig):
            connectors.append(
                RSSConnector(name=source.name, url=source.url, max_entries=source.max_entries)
            )
        elif isinstance(source, FixtureSourceConfig):
            connectors.append(FixtureConnector(name=source.name, path=Path(source.path)))
        else:
            raise ValueError(f"Unsupported source config: {source}")
    return connectors


def load_known_tools(path: Path) -> list[KnownTool]:
    raw = yaml.safe_load(path.read_text()) or []
    return [KnownTool.model_validate(item) for item in raw]


def discover_themes(
    documents: list[Document],
    since: datetime,
    top_k: int = 5,
    max_themes: int = 12,
) -> list[Theme]:
    recent_documents = [document for document in documents if document.observed_at >= since]
    if not recent_documents:
        return []

    phrases = [
        (phrase, count)
        for phrase, count in top_ngrams(
            [document.text for document in recent_documents], n=2, limit=50
        )
        if count > 1
    ]
    if not phrases:
        token_counts = Counter(
            token for document in recent_documents for token in tokenize(document.text)
        )
        phrases = token_counts.most_common(max_themes)

    themes: list[Theme] = []
    used_labels: set[str] = set()
    for phrase, phrase_count in phrases[:max_themes]:
        matching = [
            document
            for document in recent_documents
            if all(part in tokenize(document.text) for part in phrase.split())
        ]
        if not matching or phrase in used_labels:
            continue
        used_labels.add(phrase)
        theme = _theme_from_documents(phrase, phrase_count, matching)
        themes.append(theme)

    if not themes:
        themes.append(_theme_from_documents("general developer pain", 1, recent_documents))

    return sorted(themes, key=lambda theme: theme.gap_score, reverse=True)[:top_k]


def _theme_from_documents(label: str, phrase_count: int, documents: list[Document]) -> Theme:
    high_reply_unresolved = sum(
        1
        for document in documents
        if document.metadata.reply_count >= 5 and document.metadata.resolution_state == "unresolved"
    )
    workaround_hits = sum(1 for document in documents if WORKAROUND_RE.search(document.text))
    freshness_hits = sum(
        1
        for document in documents
        if document.observed_at >= datetime.now(UTC) - timedelta(days=14)
    )
    signals = ThemeSignals(
        high_reply_unresolved_threads=high_reply_unresolved,
        repeated_phrase_hits=phrase_count,
        workaround_language_hits=workaround_hits,
        freshness_hits=freshness_hits,
    )
    gap_score = round(
        (2.0 * high_reply_unresolved)
        + (1.5 * min(phrase_count, 5))
        + (2.0 * workaround_hits)
        + (0.5 * min(freshness_hits, 4)),
        2,
    )
    ranked = sorted(
        documents,
        key=lambda document: (
            document.metadata.reply_count,
            1 if WORKAROUND_RE.search(document.text) else 0,
            document.observed_at,
        ),
        reverse=True,
    )
    evidence = [
        ThemeEvidence(
            document_id=document.id,
            source_type=document.source_type,
            url=document.url,
            title=document.title,
            excerpt=excerpt(document.body or document.title),
            score=float(document.metadata.reply_count),
        )
        for document in ranked[:5]
    ]
    return Theme(
        label=label,
        keywords=label.split(),
        gap_score=gap_score,
        signals=signals,
        document_ids=[document.id for document in ranked],
        evidence=evidence,
    )


class ResearchOrchestrator:
    def __init__(
        self,
        config: AppConfig,
        config_path: Path,
        store: SQLiteStore,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.config = config
        self.config_path = config_path
        self.store = store
        self.index = LocalVectorIndex(store)
        self.llm_client = llm_client if llm_client is not None else build_llm_client()

    def run(self, dry_run: bool = False) -> RunArtifacts:
        run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        run_dir = Path(self.config.research.output_dir) / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        logger = StructuredLogger(run_dir / "logs.jsonl")
        since = datetime.now(UTC) - timedelta(days=self.config.research.days)

        logger.log("ingest", "starting ingestion", source_count=len(self.config.sources))
        connectors = build_connectors(self.config)
        ingested: list[Document] = []
        for connector in connectors:
            state = self.store.get_source_state(connector.source_id)
            documents = connector.fetch(since=since, state=state)
            self.store.upsert_documents(documents)
            ingested.extend(documents)
            self.store.set_source_state(state or SourceState(source_id=connector.source_id))
            logger.log(
                "ingest",
                "source ingested",
                source_id=connector.source_id,
                document_count=len(documents),
            )

        documents = self.store.list_documents(since=since)
        logger.log("index", "indexing documents", document_count=len(documents))
        self.index.index_documents(documents)

        logger.log("theme_discovery", "discovering themes")
        themes = discover_themes(
            documents,
            since=since,
            top_k=self.config.research.top_k_themes,
            max_themes=self.config.research.max_themes,
        )
        logger.log("gap_detection", "scored themes", theme_count=len(themes))

        known_tools = load_known_tools(Path(self.config.known_tools_path))
        allowed_urls = {document.url for document in documents}
        ideas = []
        is_dry_run = dry_run or self.llm_client is None
        if is_dry_run:
            logger.log("idea_generation", "dry run active, skipping LLM idea generation")
        else:
            logger.log("idea_generation", "generating ideas with LLM")
            ideas = self.llm_client.generate_ideas(
                themes=themes,
                known_tools=known_tools,
                allowed_urls=allowed_urls,
            )
            validate_citations(ideas, allowed_urls)

        report = ResearchReport(
            run_id=run_id,
            generated_at=datetime.now(UTC),
            dry_run=is_dry_run,
            config_path=str(self.config_path),
            document_count=len(documents),
            themes=themes,
            ideas=ideas,
            known_tools_considered=[tool.name for tool in known_tools],
            limitations=[
                (
                    "SQLite hashed embeddings are deterministic and local, "
                    "but less semantic than hosted embeddings."
                ),
                "RSS entries do not expose accepted answers, so resolution state is unknown.",
                "Gap scores are heuristics intended to prioritize review, not prove market demand.",
            ],
        )

        documents_path = run_dir / "documents.json"
        themes_path = run_dir / "themes.json"
        report_json = run_dir / "report.json"
        report_markdown = run_dir / "report.md"
        documents_path.write_text(
            json.dumps([document.model_dump(mode="json") for document in documents], indent=2),
            encoding="utf-8",
        )
        themes_path.write_text(
            json.dumps([theme.model_dump(mode="json") for theme in themes], indent=2),
            encoding="utf-8",
        )
        report_json.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        report_markdown.write_text(render_markdown_report(report), encoding="utf-8")
        logger.log("artifacts", "saved run artifacts", run_dir=str(run_dir))
        return RunArtifacts(
            run_id=run_id,
            run_dir=run_dir,
            report_json=report_json,
            report_markdown=report_markdown,
            logs_path=run_dir / "logs.jsonl",
        )


def render_markdown_report(report: ResearchReport) -> str:
    lines = [
        f"# DevForum Research Report {report.run_id}",
        "",
        f"Generated at: {report.generated_at.isoformat()}",
        f"Dry run: {str(report.dry_run).lower()}",
        f"Documents indexed: {report.document_count}",
        "",
        "## Themes",
        "",
    ]
    for index, theme in enumerate(report.themes, start=1):
        lines.extend(
            [
                f"### {index}. {theme.label}",
                "",
                f"Gap score: {theme.gap_score}",
                (
                    "Signals: "
                    f"{theme.signals.high_reply_unresolved_threads} unresolved high-reply threads, "
                    f"{theme.signals.repeated_phrase_hits} repeated phrase hits, "
                    f"{theme.signals.workaround_language_hits} workaround-language hits"
                ),
                "",
            ]
        )
        for evidence in theme.evidence:
            lines.append(
                f"- [{evidence.title}]({evidence.url}) ({evidence.source_type}): {evidence.excerpt}"
            )
        lines.append("")

    if report.ideas:
        lines.extend(["## Idea briefs", ""])
        for index, idea in enumerate(report.ideas, start=1):
            lines.extend(
                [
                    f"### {index}. {idea.title}",
                    "",
                    idea.one_liner,
                    "",
                    f"Target user: {idea.target_user}",
                    f"Pain hypothesis: {idea.pain_hypothesis}",
                    f"Why existing tools fail: {idea.why_existing_tools_fail}",
                    f"One-week MVP: {idea.mvp_scope_1week}",
                    f"Four-week MVP: {idea.mvp_scope_4weeks}",
                    f"Differentiation: {idea.differentiation}",
                    "",
                    "Evidence:",
                ]
            )
            for evidence in idea.evidence:
                lines.append(
                    f"- [{evidence.source_type}]({evidence.url}): "
                    f"{evidence.excerpt} {evidence.why_it_matters}"
                )
            lines.extend(["", "Validation plan:"])
            for step in idea.validation_plan:
                lines.append(f"- {step}")
            lines.append("")
    else:
        lines.extend(
            [
                "## Idea briefs",
                "",
                (
                    "No IdeaBrief objects were generated because LLM mode is disabled. "
                    "Set OPENAI_API_KEY, optionally OPENAI_BASE_URL and OPENAI_MODEL, then rerun "
                    "without --dry-run."
                ),
                "",
            ]
        )

    lines.extend(["## Known limitations", ""])
    for limitation in report.limitations:
        lines.append(f"- {limitation}")
    lines.append("")
    return "\n".join(lines)
