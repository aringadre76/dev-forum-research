from devforum_research.connectors.github import normalize_github_issue
from devforum_research.connectors.rss import normalize_rss_entry


def test_normalizes_github_issue_with_provenance_and_thread_metadata():
    raw_issue = {
        "id": 42,
        "number": 7,
        "title": "Type checker hangs in monorepo",
        "body": "The checker is still broken after splitting packages.",
        "html_url": "https://github.com/acme/tool/issues/7",
        "state": "open",
        "comments": 18,
        "labels": [{"name": "bug"}, {"name": "performance"}],
        "created_at": "2026-05-01T10:00:00Z",
        "updated_at": "2026-05-02T12:30:00Z",
        "closed_at": None,
        "user": {"login": "builder42"},
    }

    document = normalize_github_issue("acme/tool", raw_issue)

    assert document.id == "github_issue:acme/tool:7"
    assert document.source_type == "github_issue"
    assert document.source == "github:acme/tool"
    assert document.url == "https://github.com/acme/tool/issues/7"
    assert document.title == "Type checker hangs in monorepo"
    assert "still broken" in document.body
    assert document.observed_at.isoformat() == "2026-05-02T12:30:00+00:00"
    assert document.metadata.thread_id == "7"
    assert document.metadata.reply_count == 18
    assert document.metadata.resolution_state == "unresolved"
    assert document.metadata.tags == ["bug", "performance"]


def test_normalizes_rss_entry_and_sanitizes_html_description():
    raw_entry = {
        "id": "https://example.com/posts/ai-build-tools",
        "title": "AI build tools need better logs",
        "link": "https://example.com/posts/ai-build-tools",
        "summary": "<p>Users need traces.</p><script>alert('xss')</script>",
        "published": "Tue, 05 May 2026 15:00:00 GMT",
        "tags": [{"term": "devtools"}, {"term": "ai"}],
    }

    document = normalize_rss_entry("builder-feed", raw_entry)

    assert document.id == "rss:builder-feed:https://example.com/posts/ai-build-tools"
    assert document.source_type == "rss"
    assert document.source == "rss:builder-feed"
    assert document.body == "Users need traces."
    assert "script" not in document.body
    assert document.metadata.tags == ["devtools", "ai"]
