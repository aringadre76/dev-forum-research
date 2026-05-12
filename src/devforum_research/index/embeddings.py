from __future__ import annotations

import hashlib
import math
import os
from typing import Protocol

import httpx

from devforum_research.config import EmbeddingConfig
from devforum_research.text import tokenize


class EmbeddingModel(Protocol):
    mode: str
    model_name: str

    def embed(self, text: str) -> list[float]:
        raise NotImplementedError

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class HashingEmbeddingModel:
    mode = "local"
    model_name = "hashing"

    def __init__(self, dimensions: int = 128) -> None:
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in tokenize(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]


class HostedEmbeddingModel:
    mode = "hosted"

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        base_url: str = "https://api.openai.com/v1",
        api_key: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.model = model
        self.model_name = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for hosted embedding mode")
        self.client = client or httpx.Client(timeout=60.0)

    def embed(self, text: str) -> list[float]:
        return self.embed_many([text])[0]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self.client.post(
            f"{self.base_url}/embeddings",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={"model": self.model, "input": texts},
        )
        response.raise_for_status()
        data = sorted(response.json()["data"], key=lambda item: item["index"])
        return [_normalize_vector(item["embedding"]) for item in data]


def _normalize_vector(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def build_embedding_model(config: EmbeddingConfig) -> EmbeddingModel:
    if config.mode == "local":
        return HashingEmbeddingModel(dimensions=config.dimensions)
    if config.mode == "hosted":
        return HostedEmbeddingModel(model=config.model, base_url=config.base_url)
    raise ValueError(f"Unsupported embedding mode: {config.mode}")


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True))
