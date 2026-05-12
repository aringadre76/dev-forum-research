from __future__ import annotations

import json
import os
from typing import Protocol

import httpx
from pydantic import TypeAdapter, ValidationError

from devforum_research.models import IdeaBrief, KnownTool, Theme, validate_citations


class LLMClient(Protocol):
    def generate_ideas(
        self,
        themes: list[Theme],
        known_tools: list[KnownTool],
        allowed_urls: set[str],
        count: int = 8,
    ) -> list[IdeaBrief]:
        raise NotImplementedError


class OpenAICompatibleClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.base_url = (
            base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        ).rstrip("/")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for LLM mode")

    def generate_ideas(
        self,
        themes: list[Theme],
        known_tools: list[KnownTool],
        allowed_urls: set[str],
        count: int = 8,
    ) -> list[IdeaBrief]:
        adapter = TypeAdapter(list[IdeaBrief])
        prompt = self._prompt(themes, known_tools, allowed_urls, count)
        last_error: Exception | None = None
        for _ in range(2):
            content = self._complete(prompt)
            try:
                ideas = adapter.validate_json(content)
                validate_citations(ideas, allowed_urls)
                return ideas
            except (ValidationError, ValueError, json.JSONDecodeError) as exc:
                last_error = exc
                prompt += (
                    "\n\nPrevious response failed validation. "
                    "Return only valid JSON matching the schema. "
                    f"Validation error: {exc}"
                )
        raise ValueError(f"LLM failed to return valid IdeaBrief JSON: {last_error}")

    def _complete(self, prompt: str) -> str:
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You generate evidence-backed developer product ideas. "
                            "Return only JSON with an ideas array. Do not invent URLs."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=90.0,
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        if isinstance(parsed, dict) and "ideas" in parsed:
            return json.dumps(parsed["ideas"])
        return content

    def _prompt(
        self,
        themes: list[Theme],
        known_tools: list[KnownTool],
        allowed_urls: set[str],
        count: int,
    ) -> str:
        theme_payload = [theme.model_dump(mode="json") for theme in themes]
        tools_payload = [tool.model_dump(mode="json") for tool in known_tools]
        return json.dumps(
            {
                "task": "Generate 5 to 12 IdeaBrief objects for DevForum Research.",
                "count": count,
                "schema": {
                    "title": "string",
                    "one_liner": "string",
                    "target_user": "string",
                    "constraints": ["string"],
                    "pain_hypothesis": "string",
                    "evidence": [
                        {
                            "source_type": (
                                "github_issue|github_discussion|rss|fixture|stackexchange_question"
                            ),
                            "url": "string",
                            "why_it_matters": "string",
                            "excerpt": "string",
                        }
                    ],
                    "why_existing_tools_fail": "string",
                    "mvp_scope_1week": "string",
                    "mvp_scope_4weeks": "string",
                    "differentiation": "string",
                    "risks": ["string"],
                    "validation_plan": ["string"],
                },
                "rules": [
                    "Return JSON object with a top-level ideas array.",
                    "Only cite allowed_urls.",
                    "Use short evidence excerpts from provided theme evidence.",
                    "Compare against known tools by name when relevant.",
                    "Make every pain_hypothesis falsifiable.",
                ],
                "allowed_urls": sorted(allowed_urls),
                "themes": theme_payload,
                "known_tools": tools_payload,
            },
            indent=2,
        )


def build_llm_client() -> LLMClient | None:
    if not os.getenv("OPENAI_API_KEY"):
        return None
    return OpenAICompatibleClient()
