from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

SourceType = Literal["github_issue", "github_discussion", "rss", "fixture"]


class DocumentMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    thread_id: str | None = None
    author: str | None = None
    reply_count: int = Field(default=0, ge=0)
    resolution_state: Literal["resolved", "unresolved", "unknown"] = "unknown"
    tags: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Document(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    source_type: SourceType
    source: str = Field(min_length=1)
    url: str = Field(min_length=1)
    title: str = Field(min_length=1)
    body: str = ""
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = HttpUrl(value)
        return str(parsed).rstrip("/")

    @property
    def text(self) -> str:
        return f"{self.title}\n\n{self.body}".strip()


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: SourceType
    url: str = Field(min_length=1)
    why_it_matters: str = Field(min_length=1)
    excerpt: str = Field(min_length=1, max_length=1000)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = HttpUrl(value)
        return str(parsed).rstrip("/")


class IdeaBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    one_liner: str = Field(min_length=1)
    target_user: str = Field(min_length=1)
    constraints: list[str]
    pain_hypothesis: str = Field(min_length=1)
    evidence: list[Evidence] = Field(min_length=1)
    why_existing_tools_fail: str = Field(min_length=1)
    mvp_scope_1week: str = Field(min_length=1)
    mvp_scope_4weeks: str = Field(min_length=1)
    differentiation: str = Field(min_length=1)
    risks: list[str]
    validation_plan: list[str] = Field(min_length=1)


class ThemeSignals(BaseModel):
    model_config = ConfigDict(extra="forbid")

    high_reply_unresolved_threads: int = 0
    repeated_phrase_hits: int = 0
    workaround_language_hits: int = 0
    freshness_hits: int = 0


class ThemeEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    source_type: SourceType
    url: str
    title: str
    excerpt: str
    score: float


class Theme(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    keywords: list[str]
    gap_score: float
    signals: ThemeSignals
    document_ids: list[str]
    evidence: list[ThemeEvidence]


class KnownTool(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    category: str
    url: str
    strengths: list[str]
    limitations: list[str]


class ResearchReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    generated_at: datetime
    dry_run: bool
    config_path: str
    document_count: int
    themes: list[Theme]
    ideas: list[IdeaBrief]
    known_tools_considered: list[str]
    limitations: list[str]


def validate_citations(ideas: list[IdeaBrief], allowed_urls: set[str]) -> None:
    normalized = {str(HttpUrl(url)).rstrip("/") for url in allowed_urls}
    for idea in ideas:
        for evidence in idea.evidence:
            if evidence.url not in normalized:
                raise ValueError(
                    f"Citation URL {evidence.url} is not present in ingested documents"
                )
