from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from devforum_research.connectors.base import SourceState
from devforum_research.models import Document


class SQLiteStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.initialize()

    def initialize(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                source TEXT NOT NULL,
                url TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                document_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_documents_observed_at ON documents(observed_at);
            CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source);
            CREATE TABLE IF NOT EXISTS source_state (
                source_id TEXT PRIMARY KEY,
                cursor TEXT,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS embeddings (
                document_id TEXT PRIMARY KEY,
                vector_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
            );
            """
        )
        self.connection.commit()

    def upsert_documents(self, documents: list[Document]) -> None:
        rows = [
            (
                document.id,
                document.source_type,
                document.source,
                document.url,
                document.title,
                document.body,
                document.observed_at.isoformat(),
                document.metadata.model_dump_json(),
                document.model_dump_json(),
            )
            for document in documents
        ]
        self.connection.executemany(
            """
            INSERT INTO documents (
                id, source_type, source, url, title, body, observed_at, metadata_json, document_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                source_type = excluded.source_type,
                source = excluded.source,
                url = excluded.url,
                title = excluded.title,
                body = excluded.body,
                observed_at = excluded.observed_at,
                metadata_json = excluded.metadata_json,
                document_json = excluded.document_json
            """,
            rows,
        )
        self.connection.commit()

    def list_documents(self, since: datetime | None = None) -> list[Document]:
        if since:
            rows = self.connection.execute(
                (
                    "SELECT document_json FROM documents "
                    "WHERE observed_at >= ? ORDER BY observed_at DESC"
                ),
                (since.isoformat(),),
            ).fetchall()
        else:
            rows = self.connection.execute(
                "SELECT document_json FROM documents ORDER BY observed_at DESC"
            ).fetchall()
        return [Document.model_validate_json(row["document_json"]) for row in rows]

    def save_embedding(self, document_id: str, vector: list[float]) -> None:
        self.connection.execute(
            """
            INSERT INTO embeddings (document_id, vector_json, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(document_id) DO UPDATE SET
                vector_json = excluded.vector_json,
                updated_at = excluded.updated_at
            """,
            (document_id, json.dumps(vector)),
        )
        self.connection.commit()

    def load_embeddings(self) -> dict[str, list[float]]:
        rows = self.connection.execute("SELECT document_id, vector_json FROM embeddings").fetchall()
        return {row["document_id"]: json.loads(row["vector_json"]) for row in rows}

    def get_source_state(self, source_id: str) -> SourceState | None:
        row = self.connection.execute(
            "SELECT source_id, cursor FROM source_state WHERE source_id = ?",
            (source_id,),
        ).fetchone()
        if not row:
            return None
        return SourceState(source_id=row["source_id"], cursor=row["cursor"])

    def set_source_state(self, state: SourceState) -> None:
        self.connection.execute(
            """
            INSERT INTO source_state (source_id, cursor, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(source_id) DO UPDATE SET
                cursor = excluded.cursor,
                updated_at = excluded.updated_at
            """,
            (state.source_id, state.cursor),
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()
