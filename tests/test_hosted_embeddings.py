import json

import httpx
import pytest

from devforum_research.config import AppConfig
from devforum_research.index.embeddings import HostedEmbeddingModel, build_embedding_model


def test_hosted_embedding_model_batches_inputs_with_openai_compatible_api(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(
            {
                "url": str(request.url),
                "authorization": request.headers.get("authorization"),
                "body": json.loads(request.content.decode("utf-8")),
            }
        )
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 0, "embedding": [3.0, 4.0]},
                    {"index": 1, "embedding": [0.0, 2.0]},
                ]
            },
        )

    model = HostedEmbeddingModel(
        model="text-embedding-test",
        base_url="https://embeddings.example/v1",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    vectors = model.embed_many(["first document", "second document"])

    assert vectors == [[0.6, 0.8], [0.0, 1.0]]
    assert requests == [
        {
            "url": "https://embeddings.example/v1/embeddings",
            "authorization": "Bearer test-key",
            "body": {
                "model": "text-embedding-test",
                "input": ["first document", "second document"],
            },
        }
    ]


def test_hosted_embedding_model_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        HostedEmbeddingModel(model="text-embedding-test")


def test_build_embedding_model_uses_configured_hosted_mode(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    config = AppConfig.model_validate(
        {
            "sources": [
                {"type": "fixture", "name": "fixture", "path": "tests/fixtures/documents.json"}
            ],
            "embedding": {
                "mode": "hosted",
                "model": "text-embedding-test",
                "base_url": "https://embeddings.example/v1",
            },
        }
    )

    model = build_embedding_model(config.embedding)

    assert isinstance(model, HostedEmbeddingModel)
    assert model.model == "text-embedding-test"
