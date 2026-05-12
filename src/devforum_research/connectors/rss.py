from __future__ import annotations

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser

from devforum_research.connectors.base import SourceState
from devforum_research.models import Document, DocumentMetadata
from devforum_research.text import sanitize_html


def _parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    parsed = parsedate_to_datetime(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def normalize_rss_entry(feed_name: str, raw_entry: dict[str, Any]) -> Document:
    entry_id = str(raw_entry.get("id") or raw_entry.get("guid") or raw_entry.get("link"))
    link = str(raw_entry.get("link") or entry_id)
    summary = raw_entry.get("summary") or raw_entry.get("description") or raw_entry.get("content", "")
    if isinstance(summary, list) and summary:
        summary = summary[0].get("value", "")
    tags = [
        str(tag.get("term"))
        for tag in raw_entry.get("tags", [])
        if isinstance(tag, dict) and tag.get("term")
    ]
    published = _parse_datetime(
        raw_entry.get("published") or raw_entry.get("updated") or raw_entry.get("created")
    )
    return Document(
        id=f"rss:{feed_name}:{entry_id}",
        source_type="rss",
        source=f"rss:{feed_name}",
        url=link,
        title=str(raw_entry.get("title") or "Untitled RSS entry"),
        body=sanitize_html(str(summary)),
        observed_at=published,
        metadata=DocumentMetadata(
            thread_id=entry_id,
            reply_count=0,
            resolution_state="unknown",
            tags=tags,
            created_at=published,
            updated_at=published,
        ),
    )


class RSSConnector:
    def __init__(self, name: str, url: str, max_entries: int = 50) -> None:
        self.name = name
        self.url = url
        self.max_entries = max_entries
        self.source_id = f"rss:{name}"

    def fetch(self, since: datetime | None = None, state: SourceState | None = None) -> list[Document]:
        feed = feedparser.parse(self.url)
        documents = [
            normalize_rss_entry(self.name, entry)
            for entry in feed.entries[: self.max_entries]
        ]
        if since:
            return [document for document in documents if document.observed_at >= since]
        return documents
