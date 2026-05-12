from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from devforum_research.connectors.base import SourceState
from devforum_research.models import Document


class FixtureConnector:
    def __init__(self, name: str, path: Path) -> None:
        self.name = name
        self.path = path
        self.source_id = f"fixture:{name}"

    def fetch(self, since: datetime | None = None, state: SourceState | None = None) -> list[Document]:
        raw_items = json.loads(self.path.read_text())
        documents = [Document.model_validate(item) for item in raw_items]
        if since:
            return [document for document in documents if document.observed_at >= since]
        return documents
