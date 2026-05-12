from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field


class GitHubSourceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["github"]
    repo: str
    max_pages: int = Field(default=2, ge=1, le=10)
    per_page: int = Field(default=100, ge=1, le=100)


class RSSSourceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["rss"]
    name: str
    url: str
    max_entries: int = Field(default=50, ge=1, le=200)


class FixtureSourceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["fixture"]
    name: str
    path: str


SourceConfig = GitHubSourceConfig | RSSSourceConfig | FixtureSourceConfig


class ResearchConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    days: int = Field(default=30, ge=1, le=3650)
    top_k_themes: int = Field(default=5, ge=1, le=20)
    max_themes: int = Field(default=12, ge=1, le=50)
    evidence_per_theme: int = Field(default=4, ge=1, le=10)
    output_dir: str = "runs"


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = "DevForum Research"
    storage_path: str = "data/devforum.sqlite"
    known_tools_path: str = "data/known_tools.yaml"
    sources: list[SourceConfig]
    research: ResearchConfig = Field(default_factory=ResearchConfig)


def load_config(path: Path) -> AppConfig:
    raw = yaml.safe_load(path.read_text()) or {}
    return AppConfig.model_validate(raw)
