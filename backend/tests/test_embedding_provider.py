"""Unit tests for embedding provider interface, validation, batching, and error handling."""

import math
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest

from backend.app.services.embedding import (
    EmbeddingProviderUnavailableException,
    EmbeddingValidationException,
    IEmbeddingProvider,
    MockEmbeddingProvider,
    OllamaEmbeddingProvider,
    OpenAIEmbeddingProvider,
    get_embedding_provider,
)


class DummyProvider(IEmbeddingProvider):
    @property
    def model_name(self) -> str:
        return "dummy-model"

    @property
    def dimension(self) -> int:
        return 4

    @property
    def is_available(self) -> bool:
        return True

    async def embed_query(self, text: str):
        return [0.1, 0.2, 0.3, 0.4]

    async def embed_batch(self, texts):
        return [[0.1, 0.2, 0.3, 0.4] for _ in texts]


def test_validate_vector_success():
    provider = DummyProvider()
    valid_vec = [1.0, 2.0, 3.0, 4.0]
    validated = provider.validate_vector(valid_vec)
    assert validated == valid_vec


def test_validate_vector_dimension_mismatch():
    provider = DummyProvider()
    with pytest.raises(EmbeddingValidationException, match="Embedding dimension mismatch"):
        provider.validate_vector([1.0, 2.0, 3.0])  # len 3 != 4

    with pytest.raises(EmbeddingValidationException, match="Embedding dimension mismatch"):
        provider.validate_vector([])


def test_validate_vector_nan_rejection():
    provider = DummyProvider()
    with pytest.raises(EmbeddingValidationException, match="Invalid embedding value at index 2"):
        provider.validate_vector([1.0, 2.0, float("nan"), 4.0])


def test_validate_vector_inf_rejection():
    provider = DummyProvider()
    with pytest.raises(EmbeddingValidationException, match="Invalid embedding value at index 1"):
        provider.validate_vector([1.0, float("inf"), 3.0, 4.0])

    with pytest.raises(EmbeddingValidationException, match="Invalid embedding value at index 0"):
        provider.validate_vector([float("-inf"), 2.0, 3.0, 4.0])


def test_openai_provider_availability_checks():
    # Unavailable with None, empty, or placeholder key
    p_none = OpenAIEmbeddingProvider(api_key=None)
    # If settings has placeholder
    assert not OpenAIEmbeddingProvider(api_key="").is_available
    assert not OpenAIEmbeddingProvider(api_key="your_openai_api_key_here").is_available

    # Available with real/dummy key
    p_valid = OpenAIEmbeddingProvider(api_key="sk-real-test-key-1234567890")
    assert p_valid.is_available
    assert p_valid.model_name == "text-embedding-3-small"
    assert p_valid.dimension == 1536


@pytest.mark.asyncio
async def test_openai_provider_raises_when_unavailable():
    provider = OpenAIEmbeddingProvider(api_key="")
    assert not provider.is_available

    with pytest.raises(EmbeddingProviderUnavailableException, match="credentials not configured"):
        await provider.embed_query("test query")

    with pytest.raises(EmbeddingProviderUnavailableException, match="credentials not configured"):
        await provider.embed_batch(["text1", "text2"])


@pytest.mark.asyncio
async def test_openai_provider_empty_batch_returns_empty():
    provider = OpenAIEmbeddingProvider(api_key="sk-test-key")
    result = await provider.embed_batch([])
    assert result == []


@pytest.mark.asyncio
async def test_openai_provider_successful_batch_and_ordering():
    provider = OpenAIEmbeddingProvider(
        api_key="sk-test-key",
        dimension=4,
        batch_size=2,
    )

    mock_resp_1 = MagicMock()
    mock_resp_1.status_code = 200
    mock_resp_1.json.return_value = {
        "data": [
            {"index": 1, "embedding": [0.4, 0.5, 0.6, 0.7]},
            {"index": 0, "embedding": [0.0, 0.1, 0.2, 0.3]},
        ]
    }
    mock_resp_1.raise_for_status = MagicMock()

    mock_resp_2 = MagicMock()
    mock_resp_2.status_code = 200
    mock_resp_2.json.return_value = {
        "data": [
            {"index": 0, "embedding": [0.8, 0.9, 1.0, 1.1]},
        ]
    }
    mock_resp_2.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", side_effect=[mock_resp_1, mock_resp_2]) as mock_post:
        texts = ["text0", "text1", "text2"]
        results = await provider.embed_batch(texts)

        assert len(results) == 3
        # Ensure re-ordered correctly according to 'index'
        assert results[0] == [0.0, 0.1, 0.2, 0.3]
        assert results[1] == [0.4, 0.5, 0.6, 0.7]
        assert results[2] == [0.8, 0.9, 1.0, 1.1]
        assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_openai_provider_sanitizes_http_errors_without_exposing_secrets():
    secret_key = "super-secret-sk-12345"
    provider = OpenAIEmbeddingProvider(api_key=secret_key, dimension=4)

    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = '{"error": {"message": "Invalid API key provided"}}'

    http_error = httpx.HTTPStatusError(
        message="Client error '401 Unauthorized'",
        request=MagicMock(),
        response=mock_response,
    )

    with patch("httpx.AsyncClient.post", side_effect=http_error):
        with pytest.raises(EmbeddingProviderUnavailableException) as exc_info:
            await provider.embed_query("test query")

        error_message = str(exc_info.value)
        assert "HTTP 401" in error_message
        assert secret_key not in error_message


@pytest.mark.asyncio
async def test_openai_provider_network_and_timeout_errors():
    provider = OpenAIEmbeddingProvider(api_key="sk-test-key", dimension=4)

    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Read timed out")):
        with pytest.raises(EmbeddingProviderUnavailableException, match="connection failure: TimeoutException"):
            await provider.embed_query("test query")


@pytest.mark.asyncio
async def test_mock_embedding_provider_deterministic():
    provider = MockEmbeddingProvider(dimension=16)
    assert provider.is_available
    assert provider.dimension == 16
    assert provider.model_name == "mock-unit-test-embedding"

    vec1 = await provider.embed_query("payment gateway timeout")
    vec2 = await provider.embed_query("payment gateway timeout")
    vec3 = await provider.embed_query("different query")

    assert vec1 == vec2  # deterministic
    assert len(vec1) == 16
    assert sum(vec1) == 1.0  # single 1.0 hot spot
    assert vec1 != vec3  # different hash


@pytest.mark.asyncio
async def test_mock_embedding_provider_offline():
    provider = MockEmbeddingProvider(available=False)
    assert not provider.is_available
    with pytest.raises(EmbeddingProviderUnavailableException, match="offline"):
        await provider.embed_query("hello")


def test_get_embedding_provider_factory():
    with patch("backend.app.services.embedding.settings.EMBEDDING_PROVIDER", "mock"):
        p_mock = get_embedding_provider()
        assert isinstance(p_mock, MockEmbeddingProvider)

    with patch("backend.app.services.embedding.settings.EMBEDDING_PROVIDER", "openai"):
        p_openai = get_embedding_provider()
        assert isinstance(p_openai, OpenAIEmbeddingProvider)

    with patch("backend.app.services.embedding.settings.EMBEDDING_PROVIDER", "ollama"):
        p_ollama = get_embedding_provider()
        assert isinstance(p_ollama, OllamaEmbeddingProvider)


@pytest.mark.asyncio
async def test_ollama_provider_dimension_padding():
    provider = OllamaEmbeddingProvider(
        base_url="http://127.0.0.1:11434",
        model="nomic-embed-text",
        dimension=1536,
    )
    assert provider.model_name == "nomic-embed-text"
    assert provider.dimension == 1536

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    # Simulate a 768-dim vector from nomic-embed-text
    mock_resp.json.return_value = {"embedding": [0.01] * 768}
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        vec = await provider.embed_query("test text")
        assert len(vec) == 1536
        assert vec[:768] == [0.01] * 768
        assert vec[768:] == [0.0] * 768
