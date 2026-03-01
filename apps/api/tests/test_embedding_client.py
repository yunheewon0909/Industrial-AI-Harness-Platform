import httpx
import pytest

from api.services.rag.embedding_client import EmbeddingClientError, OllamaEmbeddingClient


class _FakeResponse:
    def __init__(self, payload: dict[str, object], *, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("POST", "http://localhost:11434/v1/embeddings")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("request failed", request=request, response=response)

    def json(self) -> dict[str, object]:
        return self._payload


def test_ollama_embedding_client_parses_vectors(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_post(url: str, *, json: dict[str, object], timeout: float) -> _FakeResponse:
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse(
            {
                "data": [
                    {"embedding": [1, 2, 3]},
                    {"embedding": [4.5, 5.0, 6.25]},
                ]
            }
        )

    monkeypatch.setattr("api.services.rag.embedding_client.httpx.post", fake_post)

    client = OllamaEmbeddingClient(
        base_url="http://localhost:11434/v1",
        model="nomic-embed-text",
        timeout_seconds=12,
    )
    vectors = client.embed_texts(["first", "second"])

    assert vectors == [[1.0, 2.0, 3.0], [4.5, 5.0, 6.25]]
    assert captured["url"] == "http://localhost:11434/v1/embeddings"
    assert captured["json"] == {
        "model": "nomic-embed-text",
        "input": ["first", "second"],
    }
    assert captured["timeout"] == 12


def test_ollama_embedding_client_rejects_payload_size_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(url: str, *, json: dict[str, object], timeout: float) -> _FakeResponse:
        del url, json, timeout
        return _FakeResponse({"data": [{"embedding": [1, 2, 3]}]})

    monkeypatch.setattr("api.services.rag.embedding_client.httpx.post", fake_post)

    client = OllamaEmbeddingClient(
        base_url="http://localhost:11434/v1",
        model="nomic-embed-text",
    )

    with pytest.raises(EmbeddingClientError, match="expected 2 vectors"):
        client.embed_texts(["first", "second"])
