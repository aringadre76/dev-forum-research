import json

import httpx

from devforum_research.connectors.github import GitHubConnector, normalize_github_discussion


def _discussion_node(number: int, cursor: str = "cursor-1") -> dict[str, object]:
    return {
        "cursor": cursor,
        "node": {
            "id": "D_kwDOExample",
            "number": number,
            "title": "How do I debug agent tool-call traces?",
            "body": "The workaround is a hacky log export and it is still broken.",
            "url": f"https://github.com/acme/tool/discussions/{number}",
            "createdAt": "2026-05-01T10:00:00Z",
            "updatedAt": "2026-05-03T12:30:00Z",
            "answerChosenAt": None,
            "comments": {"totalCount": 7},
            "category": {"name": "Q&A"},
            "author": {"login": "builder42"},
            "labels": {"nodes": [{"name": "ai"}, {"name": "debugging"}]},
        },
    }


def test_normalizes_github_discussion_with_stable_url_and_metadata():
    document = normalize_github_discussion("acme/tool", _discussion_node(12)["node"])

    assert document.id == "github_discussion:acme/tool:12"
    assert document.source_type == "github_discussion"
    assert document.source == "github:acme/tool"
    assert document.url == "https://github.com/acme/tool/discussions/12"
    assert document.title == "How do I debug agent tool-call traces?"
    assert document.observed_at.isoformat() == "2026-05-03T12:30:00+00:00"
    assert document.metadata.thread_id == "12"
    assert document.metadata.reply_count == 7
    assert document.metadata.resolution_state == "unresolved"
    assert document.metadata.tags == ["Q&A", "ai", "debugging"]


def test_github_connector_fetches_discussions_with_graphql_pagination():
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(
            {
                "url": str(request.url),
                "authorization": request.headers.get("authorization"),
                "body": json.loads(request.content.decode("utf-8")) if request.content else {},
            }
        )
        if str(request.url).startswith("https://api.github.com/repos/acme/tool/issues"):
            return httpx.Response(200, json=[])
        if str(request.url) == "https://api.github.com/graphql":
            after = requests[-1]["body"]["variables"]["after"]
            if after is None:
                return httpx.Response(
                    200,
                    json={
                        "data": {
                            "repository": {
                                "discussions": {
                                    "nodes": [],
                                    "edges": [_discussion_node(12, "cursor-1")],
                                    "pageInfo": {
                                        "hasNextPage": True,
                                        "endCursor": "cursor-1",
                                    },
                                }
                            }
                        }
                    },
                )
            return httpx.Response(
                200,
                json={
                    "data": {
                        "repository": {
                            "discussions": {
                                "nodes": [],
                                "edges": [_discussion_node(13, "cursor-2")],
                                "pageInfo": {
                                    "hasNextPage": False,
                                    "endCursor": "cursor-2",
                                },
                            }
                        }
                    }
                },
            )
        raise AssertionError(f"Unexpected request URL: {request.url}")

    connector = GitHubConnector(
        repo="acme/tool",
        token="test-token",
        include_discussions=True,
        max_discussion_pages=2,
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    )

    documents = connector.fetch()

    assert [document.source_type for document in documents] == [
        "github_discussion",
        "github_discussion",
    ]
    assert [document.metadata.thread_id for document in documents] == ["12", "13"]
    assert requests[0]["authorization"] == "Bearer test-token"
    assert requests[1]["body"]["variables"] == {
        "owner": "acme",
        "name": "tool",
        "first": 50,
        "after": None,
    }
    assert requests[2]["body"]["variables"]["after"] == "cursor-1"
