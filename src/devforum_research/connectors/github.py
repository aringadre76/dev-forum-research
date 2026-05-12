from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from devforum_research.connectors.base import SourceState
from devforum_research.models import Document, DocumentMetadata


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value).astimezone(UTC)


def _resolution_state(raw_issue: dict[str, Any]) -> str:
    labels = {
        str(label.get("name", "")).lower()
        for label in raw_issue.get("labels", [])
        if isinstance(label, dict)
    }
    if raw_issue.get("state") == "closed" and "wontfix" not in labels:
        return "resolved"
    return "unresolved"


def normalize_github_issue(repo: str, raw_issue: dict[str, Any]) -> Document:
    number = str(raw_issue["number"])
    updated_at = _parse_datetime(raw_issue.get("updated_at"))
    created_at = _parse_datetime(raw_issue.get("created_at"))
    labels = [
        str(label.get("name"))
        for label in raw_issue.get("labels", [])
        if isinstance(label, dict) and label.get("name")
    ]
    user = raw_issue.get("user") or {}
    author = user.get("login") if isinstance(user, dict) else None
    return Document(
        id=f"github_issue:{repo}:{number}",
        source_type="github_issue",
        source=f"github:{repo}",
        url=raw_issue["html_url"],
        title=raw_issue.get("title") or f"Issue {number}",
        body=raw_issue.get("body") or "",
        observed_at=updated_at or created_at or datetime.now(UTC),
        metadata=DocumentMetadata(
            thread_id=number,
            author=author,
            reply_count=int(raw_issue.get("comments") or 0),
            resolution_state=_resolution_state(raw_issue),
            tags=labels,
            created_at=created_at,
            updated_at=updated_at,
        ),
    )


class GitHubConnector:
    def __init__(
        self,
        repo: str,
        token: str | None = None,
        per_page: int = 100,
        max_pages: int = 2,
        base_url: str = "https://api.github.com",
    ) -> None:
        self.repo = repo
        self.source_id = f"github:{repo}"
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.per_page = per_page
        self.max_pages = max_pages
        self.base_url = base_url.rstrip("/")

    def fetch(
        self, since: datetime | None = None, state: SourceState | None = None
    ) -> list[Document]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        params: dict[str, str | int] = {
            "state": "all",
            "sort": "updated",
            "direction": "desc",
            "per_page": self.per_page,
        }
        if since:
            params["since"] = since.astimezone(UTC).isoformat().replace("+00:00", "Z")

        documents: list[Document] = []
        next_url: str | None = f"{self.base_url}/repos/{self.repo}/issues"
        pages = 0
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            while next_url and pages < self.max_pages:
                response = client.get(
                    next_url,
                    headers=headers,
                    params=params if pages == 0 else None,
                )
                self._handle_rate_limit(response)
                response.raise_for_status()
                for item in response.json():
                    if "pull_request" not in item:
                        documents.append(normalize_github_issue(self.repo, item))
                next_url = self._next_link(response.headers.get("link"))
                pages += 1
        return documents

    def _handle_rate_limit(self, response: httpx.Response) -> None:
        if response.status_code not in {403, 429}:
            return
        remaining = response.headers.get("x-ratelimit-remaining")
        reset = response.headers.get("x-ratelimit-reset")
        if remaining == "0" and reset:
            sleep_for = max(1, int(reset) - int(time.time()) + 1)
            time.sleep(min(sleep_for, 60))

    def _next_link(self, link_header: str | None) -> str | None:
        if not link_header:
            return None
        for part in link_header.split(","):
            url_part, _, rel_part = part.strip().partition(";")
            if 'rel="next"' in rel_part:
                return url_part.strip()[1:-1]
        return None


def parse_http_date(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = parsedate_to_datetime(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
