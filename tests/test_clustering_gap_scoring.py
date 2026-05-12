from datetime import UTC, datetime, timedelta

from devforum_research.models import Document, DocumentMetadata
from devforum_research.research.orchestrator import discover_themes


def _doc(
    doc_id: str,
    title: str,
    body: str,
    reply_count: int,
    resolution_state: str,
    days_old: int = 1,
) -> Document:
    observed_at = datetime(2026, 5, 12, tzinfo=UTC) - timedelta(days=days_old)
    return Document(
        id=doc_id,
        source_type="github_issue",
        source="github:acme/tool",
        url=f"https://github.com/acme/tool/issues/{doc_id}",
        title=title,
        body=body,
        observed_at=observed_at,
        metadata=DocumentMetadata(
            thread_id=doc_id,
            reply_count=reply_count,
            resolution_state=resolution_state,
            tags=["bug"],
        ),
    )


def test_discovers_theme_with_gap_score_from_replies_repetition_and_workarounds():
    documents = [
        _doc(
            "1",
            "AI codegen cache invalidation is still broken",
            "The workaround is hacky and cache invalidation fails in monorepos.",
            24,
            "unresolved",
        ),
        _doc(
            "2",
            "Cache invalidation workaround for codegen",
            "We gave up because cache invalidation is still broken during generated builds.",
            9,
            "unresolved",
        ),
        _doc(
            "3",
            "Docs typo in install guide",
            "Small typo in setup docs.",
            1,
            "resolved",
        ),
    ]

    themes = discover_themes(
        documents,
        since=datetime(2026, 5, 1, tzinfo=UTC),
        top_k=2,
        max_themes=4,
    )

    assert themes[0].label == "cache invalidation"
    assert themes[0].gap_score >= 7.0
    assert themes[0].signals.high_reply_unresolved_threads == 2
    assert themes[0].signals.repeated_phrase_hits >= 2
    assert themes[0].signals.workaround_language_hits == 2
    assert [e.document_id for e in themes[0].evidence] == ["1", "2"]
