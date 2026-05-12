from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

import httpx

from devforum_research.connectors.base import SourceState
from devforum_research.models import Document, DocumentMetadata
from devforum_research.text import sanitize_html


def _from_unix_timestamp(value: int | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value, tz=UTC)


def normalize_stackexchange_question(site: str, raw_question: dict[str, Any]) -> Document:
    question_id = str(raw_question["question_id"])
    created_at = _from_unix_timestamp(raw_question.get("creation_date"))
    updated_at = _from_unix_timestamp(raw_question.get("last_activity_date"))
    owner = raw_question.get("owner") or {}
    author = owner.get("display_name") if isinstance(owner, dict) else None
    answer_count = int(raw_question.get("answer_count") or 0)
    is_answered = bool(raw_question.get("is_answered"))
    accepted_answer_id = raw_question.get("accepted_answer_id")
    return Document(
        id=f"stackexchange_question:{site}:{question_id}",
        source_type="stackexchange_question",
        source=f"stackexchange:{site}",
        url=raw_question["link"],
        title=sanitize_html(raw_question.get("title") or f"Question {question_id}"),
        body=raw_question.get("body_markdown") or sanitize_html(raw_question.get("body") or ""),
        observed_at=updated_at or created_at or datetime.now(UTC),
        metadata=DocumentMetadata(
            thread_id=question_id,
            author=author,
            reply_count=answer_count,
            resolution_state="resolved" if accepted_answer_id else "unresolved",
            tags=[str(tag) for tag in raw_question.get("tags", [])],
            created_at=created_at,
            updated_at=updated_at,
            score=int(raw_question.get("score") or 0),
            answer_count=answer_count,
            is_answered=is_answered,
            accepted_answer_id=accepted_answer_id,
        ),
    )


class StackExchangeConnector:
    def __init__(
        self,
        site: str = "stackoverflow",
        tagged: list[str] | None = None,
        pagesize: int = 25,
        max_pages: int = 2,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        request_interval_seconds: float = 0.5,
        base_url: str = "https://api.stackexchange.com/2.3",
        client_factory: Any | None = None,
    ) -> None:
        self.site = site
        self.tagged = tagged or []
        self.pagesize = pagesize
        self.max_pages = max_pages
        self.from_date = from_date
        self.to_date = to_date
        self.request_interval_seconds = request_interval_seconds
        self.base_url = base_url.rstrip("/")
        tag_key = ";".join(self.tagged) if self.tagged else "all"
        self.source_id = f"stackexchange:{site}:{tag_key}"
        self.client_factory = client_factory or (lambda: httpx.Client(timeout=30.0))

    def fetch(
        self, since: datetime | None = None, state: SourceState | None = None
    ) -> list[Document]:
        documents: list[Document] = []
        from_date = self.from_date or since
        params: dict[str, str | int] = {
            "site": self.site,
            "pagesize": self.pagesize,
            "order": "desc",
            "sort": "activity",
            "filter": "withbody",
        }
        if self.tagged:
            params["tagged"] = ";".join(self.tagged)
        if from_date:
            params["fromdate"] = int(from_date.astimezone(UTC).timestamp())
        if self.to_date:
            params["todate"] = int(self.to_date.astimezone(UTC).timestamp())

        with self.client_factory() as client:
            for page in range(1, self.max_pages + 1):
                response = client.get(
                    f"{self.base_url}/questions",
                    params={**params, "page": page},
                )
                response.raise_for_status()
                payload = response.json()
                documents.extend(
                    normalize_stackexchange_question(self.site, item)
                    for item in payload.get("items", [])
                )
                backoff = payload.get("backoff")
                if backoff:
                    time.sleep(float(backoff))
                if not payload.get("has_more"):
                    break
                if self.request_interval_seconds:
                    time.sleep(self.request_interval_seconds)
        return documents
