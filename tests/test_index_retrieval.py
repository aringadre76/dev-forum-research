from datetime import UTC, datetime

from devforum_research.index.store import LocalVectorIndex
from devforum_research.models import Document, Theme, ThemeSignals
from devforum_research.research.orchestrator import compile_theme_evidence
from devforum_research.storage import SQLiteStore


def test_local_vector_index_retrieves_semantically_related_document(tmp_path):
    store = SQLiteStore(tmp_path / "research.sqlite")
    documents = [
        Document(
            id="doc-1",
            source_type="rss",
            source="rss:builders",
            url="https://example.com/cache",
            title="Cache invalidation fails in code generation",
            body="Generated clients keep stale workspace outputs.",
            observed_at=datetime(2026, 5, 12, tzinfo=UTC),
        ),
        Document(
            id="doc-2",
            source_type="rss",
            source="rss:builders",
            url="https://example.com/pricing",
            title="Pricing page copy",
            body="A short note about billing copy changes.",
            observed_at=datetime(2026, 5, 12, tzinfo=UTC),
        ),
    ]
    store.upsert_documents(documents)
    index = LocalVectorIndex(store)

    index.index_documents(documents)
    results = index.search("code generation cache invalidation", documents, limit=1)

    assert results[0].document.id == "doc-1"
    assert results[0].score > 0


def test_compile_theme_evidence_uses_vector_retrieval_and_limit(tmp_path):
    store = SQLiteStore(tmp_path / "research.sqlite")
    documents = [
        Document(
            id="doc-1",
            source_type="github_issue",
            source="github:example/evals",
            url="https://github.com/example/evals/issues/1",
            title="Token caps fail during branch evals",
            body="Teams need cost caps and token alerts before eval jobs run.",
            observed_at=datetime(2026, 5, 12, tzinfo=UTC),
        ),
        Document(
            id="doc-2",
            source_type="github_issue",
            source="github:example/evals",
            url="https://github.com/example/evals/issues/2",
            title="Unrelated docs typo",
            body="Small grammar issue.",
            observed_at=datetime(2026, 5, 12, tzinfo=UTC),
        ),
    ]
    store.upsert_documents(documents)
    index = LocalVectorIndex(store)
    index.index_documents(documents)
    theme = Theme(
        label="token caps",
        keywords=["token", "caps"],
        gap_score=5.0,
        signals=ThemeSignals(repeated_phrase_hits=2),
        document_ids=[],
        evidence=[],
    )

    compiled = compile_theme_evidence([theme], documents, index, evidence_per_theme=1)

    assert [e.document_id for e in compiled[0].evidence] == ["doc-1"]
    assert compiled[0].document_ids == ["doc-1"]
