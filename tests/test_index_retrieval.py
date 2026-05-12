from datetime import UTC, datetime

from devforum_research.index.store import LocalVectorIndex
from devforum_research.models import Document
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
