
import httpx

from devforum_research.config import AppConfig
from devforum_research.connectors.stackexchange import (
    StackExchangeConnector,
    normalize_stackexchange_question,
)
from devforum_research.research.orchestrator import build_connectors


def _question(question_id: int, link: str | None = None) -> dict[str, object]:
    return {
        "question_id": question_id,
        "title": "Why do AI agent evals fail only in CI?",
        "body_markdown": "The workaround is a hacky retry loop, but failures are still broken.",
        "link": link or f"https://stackoverflow.com/questions/{question_id}/agent-evals-fail-in-ci",
        "creation_date": 1777639200,
        "last_activity_date": 1777811400,
        "owner": {"display_name": "Builder42"},
        "score": 17,
        "answer_count": 4,
        "is_answered": True,
        "accepted_answer_id": 9001,
        "tags": ["python", "github-actions", "ai"],
    }


def test_normalizes_stackexchange_question_with_metadata_and_stable_url():
    document = normalize_stackexchange_question("stackoverflow", _question(12345))

    assert document.id == "stackexchange_question:stackoverflow:12345"
    assert document.source_type == "stackexchange_question"
    assert document.source == "stackexchange:stackoverflow"
    assert document.url == "https://stackoverflow.com/questions/12345/agent-evals-fail-in-ci"
    assert document.title == "Why do AI agent evals fail only in CI?"
    assert "hacky retry loop" in document.body
    assert document.observed_at.isoformat() == "2026-05-03T12:30:00+00:00"
    assert document.metadata.thread_id == "12345"
    assert document.metadata.author == "Builder42"
    assert document.metadata.reply_count == 4
    assert document.metadata.resolution_state == "resolved"
    assert document.metadata.tags == ["python", "github-actions", "ai"]
    assert document.metadata.score == 17
    assert document.metadata.answer_count == 4
    assert document.metadata.is_answered is True
    assert document.metadata.accepted_answer_id == 9001


def test_stackexchange_connector_fetches_pages_and_obeys_backoff(monkeypatch):
    sleeps: list[float] = []
    requests: list[dict[str, object]] = []
    monkeypatch.setattr("devforum_research.connectors.stackexchange.time.sleep", sleeps.append)

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(dict(request.url.params))
        page = request.url.params["page"]
        if page == "1":
            return httpx.Response(
                200,
                json={
                    "items": [_question(1)],
                    "has_more": True,
                    "backoff": 2,
                },
            )
        return httpx.Response(
            200,
            json={
                "items": [_question(2)],
                "has_more": False,
            },
        )

    connector = StackExchangeConnector(
        site="stackoverflow",
        tagged=["python", "ai"],
        pagesize=1,
        max_pages=2,
        request_interval_seconds=0.25,
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    )

    documents = connector.fetch()

    assert [document.metadata.thread_id for document in documents] == ["1", "2"]
    assert requests[0]["site"] == "stackoverflow"
    assert requests[0]["tagged"] == "python;ai"
    assert requests[0]["filter"] == "withbody"
    assert requests[1]["page"] == "2"
    assert sleeps == [2, 0.25]


def test_stackexchange_config_registers_connector():
    config = AppConfig.model_validate(
        {
            "sources": [
                {
                    "type": "stackexchange",
                    "site": "stackoverflow",
                    "tagged": ["python", "ai"],
                    "pagesize": 10,
                    "max_pages": 1,
                }
            ]
        }
    )

    connectors = build_connectors(config)

    assert len(connectors) == 1
    assert connectors[0].source_id == "stackexchange:stackoverflow:python;ai"
