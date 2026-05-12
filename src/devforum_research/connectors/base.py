from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from devforum_research.models import Document


@dataclass(frozen=True)
class SourceState:
    source_id: str
    cursor: str | None = None


class SourceConnector(Protocol):
    source_id: str

    def fetch(
        self, since: datetime | None = None, state: SourceState | None = None
    ) -> list[Document]:
        raise NotImplementedError
