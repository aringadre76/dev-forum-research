from __future__ import annotations

from dataclasses import dataclass

from devforum_research.index.embeddings import (
    EmbeddingModel,
    HashingEmbeddingModel,
    cosine_similarity,
)
from devforum_research.models import Document
from devforum_research.storage import SQLiteStore
from devforum_research.text import tokenize


@dataclass(frozen=True)
class SearchResult:
    document: Document
    score: float


class LocalVectorIndex:
    def __init__(
        self,
        store: SQLiteStore,
        embedding_model: EmbeddingModel | None = None,
    ) -> None:
        self.store = store
        self.embedding_model = embedding_model or HashingEmbeddingModel()

    def index_documents(self, documents: list[Document]) -> int:
        vectors = self.embedding_model.embed_many([document.text for document in documents])
        for document, vector in zip(documents, vectors, strict=True):
            self.store.save_embedding(document.id, vector)
        return len(vectors)

    def search(self, query: str, documents: list[Document], limit: int = 5) -> list[SearchResult]:
        query_vector = self.embedding_model.embed(query)
        embeddings = self.store.load_embeddings()
        query_terms = set(tokenize(query))
        results: list[SearchResult] = []
        for document in documents:
            vector_score = cosine_similarity(query_vector, embeddings.get(document.id, []))
            document_terms = set(tokenize(document.text))
            keyword_score = len(query_terms & document_terms) / max(1, len(query_terms))
            score = (0.75 * vector_score) + (0.25 * keyword_score)
            results.append(SearchResult(document=document, score=score))
        return sorted(results, key=lambda result: result.score, reverse=True)[:limit]
