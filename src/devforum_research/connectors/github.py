from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from devforum_research.connectors.base import SourceState
from devforum_research.models import Document, DocumentMetadata

GITHUB_DISCUSSIONS_QUERY = """
query DevForumResearchDiscussions($owner: String!, $name: String!, $first: Int!, $after: String) {
  repository(owner: $owner, name: $name) {
    discussions(first: $first, after: $after, orderBy: {field: UPDATED_AT, direction: DESC}) {
      edges {
        cursor
        node {
          id
          number
          title
          body
          url
          createdAt
          updatedAt
          answerChosenAt
          comments {
            totalCount
          }
          category {
            name
          }
          author {
            login
          }
          labels(first: 20) {
            nodes {
              name
            }
          }
        }
      }
      pageInfo {
        hasNextPage
        endCursor
      }
    }
  }
}
"""


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


def normalize_github_discussion(repo: str, raw_discussion: dict[str, Any]) -> Document:
    number = str(raw_discussion["number"])
    updated_at = _parse_datetime(raw_discussion.get("updatedAt"))
    created_at = _parse_datetime(raw_discussion.get("createdAt"))
    labels = [
        str(label.get("name"))
        for label in (raw_discussion.get("labels") or {}).get("nodes", [])
        if isinstance(label, dict) and label.get("name")
    ]
    category = raw_discussion.get("category") or {}
    category_name = category.get("name") if isinstance(category, dict) else None
    tags = ([str(category_name)] if category_name else []) + labels
    author = raw_discussion.get("author") or {}
    author_login = author.get("login") if isinstance(author, dict) else None
    comments = raw_discussion.get("comments") or {}
    reply_count = comments.get("totalCount") if isinstance(comments, dict) else 0
    return Document(
        id=f"github_discussion:{repo}:{number}",
        source_type="github_discussion",
        source=f"github:{repo}",
        url=raw_discussion.get("url") or f"https://github.com/{repo}/discussions/{number}",
        title=raw_discussion.get("title") or f"Discussion {number}",
        body=raw_discussion.get("body") or "",
        observed_at=updated_at or created_at or datetime.now(UTC),
        metadata=DocumentMetadata(
            thread_id=number,
            author=author_login,
            reply_count=int(reply_count or 0),
            resolution_state="resolved" if raw_discussion.get("answerChosenAt") else "unresolved",
            tags=tags,
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
        include_discussions: bool = False,
        max_discussion_pages: int = 2,
        discussion_page_size: int = 50,
        base_url: str = "https://api.github.com",
        client_factory: Any | None = None,
    ) -> None:
        self.repo = repo
        self.source_id = f"github:{repo}"
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.per_page = per_page
        self.max_pages = max_pages
        self.include_discussions = include_discussions
        self.max_discussion_pages = max_discussion_pages
        self.discussion_page_size = discussion_page_size
        self.base_url = base_url.rstrip("/")
        self.client_factory = client_factory or (
            lambda: httpx.Client(timeout=30.0, follow_redirects=True)
        )

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
        with self.client_factory() as client:
            while next_url and pages < self.max_pages:
                response = self._get_with_rate_limit_retry(
                    client=client,
                    url=next_url,
                    headers=headers,
                    params=params if pages == 0 else None,
                )
                response.raise_for_status()
                for item in response.json():
                    if "pull_request" not in item:
                        documents.append(normalize_github_issue(self.repo, item))
                next_url = self._next_link(response.headers.get("link"))
                pages += 1
            if self.include_discussions:
                documents.extend(self._fetch_discussions(client, headers))
        return documents

    def _fetch_discussions(
        self,
        client: httpx.Client,
        headers: dict[str, str],
    ) -> list[Document]:
        if not self.token:
            raise ValueError("GITHUB_TOKEN is required when include_discussions is true")
        owner, name = self.repo.split("/", 1)
        after: str | None = None
        pages = 0
        documents: list[Document] = []
        while pages < self.max_discussion_pages:
            response = self._post_with_rate_limit_retry(
                client=client,
                url=f"{self.base_url}/graphql",
                headers=headers,
                json_body={
                    "query": GITHUB_DISCUSSIONS_QUERY,
                    "variables": {
                        "owner": owner,
                        "name": name,
                        "first": self.discussion_page_size,
                        "after": after,
                    },
                },
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("errors"):
                raise RuntimeError(f"GitHub Discussions GraphQL error: {payload['errors']}")
            discussions = (payload.get("data") or {}).get("repository", {}).get("discussions")
            if not discussions:
                return documents
            edges = discussions.get("edges") or []
            for edge in edges:
                node = edge.get("node") if isinstance(edge, dict) else None
                if isinstance(node, dict):
                    documents.append(normalize_github_discussion(self.repo, node))
            page_info = discussions.get("pageInfo") or {}
            pages += 1
            if not page_info.get("hasNextPage"):
                break
            after = page_info.get("endCursor")
        return documents

    def _get_with_rate_limit_retry(
        self,
        client: httpx.Client,
        url: str,
        headers: dict[str, str],
        params: dict[str, str | int] | None,
    ) -> httpx.Response:
        for attempt in range(3):
            response = client.get(url, headers=headers, params=params)
            if not self._is_rate_limited(response) or attempt == 2:
                return response
            reset = response.headers.get("x-ratelimit-reset")
            if reset:
                sleep_for = max(1, int(reset) - int(time.time()) + 1)
                time.sleep(min(sleep_for, 60))
            else:
                time.sleep(2**attempt)
        raise RuntimeError("GitHub rate-limit retry loop exited unexpectedly")

    def _post_with_rate_limit_retry(
        self,
        client: httpx.Client,
        url: str,
        headers: dict[str, str],
        json_body: dict[str, Any],
    ) -> httpx.Response:
        for attempt in range(3):
            response = client.post(url, headers=headers, json=json_body)
            if not self._is_rate_limited(response) or attempt == 2:
                return response
            reset = response.headers.get("x-ratelimit-reset")
            if reset:
                sleep_for = max(1, int(reset) - int(time.time()) + 1)
                time.sleep(min(sleep_for, 60))
            else:
                time.sleep(2**attempt)
        raise RuntimeError("GitHub rate-limit retry loop exited unexpectedly")

    def _is_rate_limited(self, response: httpx.Response) -> bool:
        return (
            response.status_code in {403, 429}
            and response.headers.get("x-ratelimit-remaining") == "0"
        )

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
