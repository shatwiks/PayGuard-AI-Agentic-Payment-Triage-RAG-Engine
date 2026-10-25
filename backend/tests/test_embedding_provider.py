"""Unit tests for embedding provider interface, validation, batching, and error handling."""

import math
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest

from backend.app.services.embedding import (
    EmbeddingModelRegistry,
    EmbeddingModelSpec,
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
    # Simulate a 768-dim vector from nomic-embed-text via /api/embed
    mock_resp.json.return_value = {"embeddings": [[0.01] * 768]}
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        vec = await provider.embed_query("test text")
        assert len(vec) == 1536
        assert vec[:768] == [0.01] * 768
        assert vec[768:] == [0.0] * 768


@pytest.mark.asyncio
async def test_ollama_provider_batch_embed_and_ordering():
    provider = OllamaEmbeddingProvider(
        base_url="http://127.0.0.1:11434",
        model="nomic-embed-text",
        dimension=1536,
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "embeddings": [
            [0.1] * 768,
            [0.2] * 768,
            [0.3] * 768,
        ]
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        batch = await provider.embed_batch(["text 1", "text 2", "text 3"])
        assert len(batch) == 3
        assert batch[0][:768] == [0.1] * 768
        assert batch[1][:768] == [0.2] * 768
        assert batch[2][:768] == [0.3] * 768
        assert batch[0][768:] == [0.0] * 768


@pytest.mark.asyncio
async def test_ollama_provider_legacy_fallback():
    provider = OllamaEmbeddingProvider(
        base_url="http://127.0.0.1:11434",
        model="nomic-embed-text",
        dimension=1536,
    )
    # Simulate 404 on /api/embed then 200 on /api/embeddings
    resp_404 = MagicMock()
    resp_404.status_code = 404
    resp_404.text = "404 page not found / endpoint not found"

    resp_legacy = MagicMock()
    resp_legacy.status_code = 200
    resp_legacy.json.return_value = {"embedding": [0.05] * 768}
    resp_legacy.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", side_effect=[resp_404, resp_legacy]):
        vecs = await provider.embed_batch(["legacy prompt"])
        assert len(vecs) == 1
        assert len(vecs[0]) == 1536
        assert vecs[0][:768] == [0.05] * 768


@pytest.mark.asyncio
async def test_ollama_provider_missing_model_error():
    provider = OllamaEmbeddingProvider(
        base_url="http://127.0.0.1:11434",
        model="nonexistent-model",
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.text = '{"error":"model \'nonexistent-model\' not found"}'
    error = httpx.HTTPStatusError("404 Not Found", request=MagicMock(), response=mock_resp)

    with patch("httpx.AsyncClient.post", side_effect=error):
        with pytest.raises(EmbeddingProviderUnavailableException, match="Ollama API error"):
            await provider.embed_query("test query")


def test_embedding_model_registry_resolution():
    """Verify registry resolves standard models and unknown fallbacks correctly."""
    spec_openai = EmbeddingModelRegistry.get_spec("text-embedding-3-small")
    assert spec_openai.native_dimension == 1536
    assert spec_openai.target_dimension == 1536

    spec_nomic = EmbeddingModelRegistry.get_spec("nomic-embed-text:latest")
    assert spec_nomic.native_dimension == 768
    assert spec_nomic.target_dimension == 1536

    spec_minilm = EmbeddingModelRegistry.get_spec("all-minilm")
    assert spec_minilm.native_dimension == 384
    assert spec_minilm.target_dimension == 1536

    # Custom or unknown model
    spec_custom = EmbeddingModelRegistry.get_spec("custom-embedding-model", target_dimension=1024)
    assert spec_custom.native_dimension == 1024
    assert spec_custom.target_dimension == 1024


def test_embedding_model_spec_adaptation_and_padding():
    """Verify automatic zero-padding from native to schema target dimension."""
    spec = EmbeddingModelSpec(
        model_name="test-768",
        native_dimension=768,
        target_dimension=1536,
    )
    raw_vec = [0.05] * 768
    adapted = spec.adapt_vector(raw_vec)
    assert len(adapted) == 1536
    assert adapted[:768] == [0.05] * 768
    assert adapted[768:] == [0.0] * 768

    # Already matching target dimension
    target_vec = [0.01] * 1536
    assert spec.adapt_vector(target_vec) == target_vec


def test_embedding_model_spec_l2_normalization():
    """Verify optional L2 normalization normalizes vector before padding."""
    spec = EmbeddingModelSpec(
        model_name="test-normalized",
        native_dimension=4,
        target_dimension=8,
        normalize_l2=True,
    )
    raw_vec = [3.0, 4.0, 0.0, 0.0]  # norm is 5.0
    adapted = spec.adapt_vector(raw_vec)
    assert len(adapted) == 8
    assert adapted[:4] == [0.6, 0.8, 0.0, 0.0]
    assert adapted[4:] == [0.0, 0.0, 0.0, 0.0]


def test_embedding_model_spec_validation_rejections():
    """Verify rejection of invalid dimensions, empty inputs, NaNs, and Infs."""
    spec = EmbeddingModelSpec(
        model_name="test-spec",
        native_dimension=4,
        target_dimension=8,
    )

    # Empty
    with pytest.raises(EmbeddingValidationException, match="Embedding dimension mismatch"):
        spec.adapt_vector([])

    # Dimension mismatch with both native and target
    with pytest.raises(EmbeddingValidationException, match="expected 8, got 5"):
        spec.adapt_vector([0.1, 0.2, 0.3, 0.4, 0.5])

    # NaN rejection
    with pytest.raises(EmbeddingValidationException, match="Invalid embedding value at index 2"):
        spec.adapt_vector([0.1, 0.2, float("nan"), 0.4])

    # Inf rejection
    with pytest.raises(EmbeddingValidationException, match="Invalid embedding value at index 1"):
        spec.adapt_vector([0.1, float("inf"), 0.3, 0.4])


def test_embedding_model_spec_l2_normalization_at_target_dimension_and_truncation():
    """Verify L2 normalization applies when input equals target_dimension and when truncating."""
    spec_same = EmbeddingModelSpec(
        model_name="test-same-dim-norm",
        native_dimension=4,
        target_dimension=4,
        normalize_l2=True,
    )
    adapted_same = spec_same.adapt_vector([3.0, 4.0, 0.0, 0.0])
    assert adapted_same == [0.6, 0.8, 0.0, 0.0]

    spec_trunc = EmbeddingModelSpec(
        model_name="test-trunc-norm",
        native_dimension=6,
        target_dimension=4,
        normalize_l2=True,
    )
    adapted_trunc = spec_trunc.adapt_vector([3.0, 4.0, 0.0, 0.0, 99.0, 99.0])
    assert adapted_trunc == [0.6, 0.8, 0.0, 0.0]


@pytest.mark.asyncio
async def test_ollama_provider_availability_ttl_cache():
    """Verify OllamaEmbeddingProvider caches availability checks to avoid repeated blocking I/O."""
    OllamaEmbeddingProvider.clear_availability_cache()
    provider = OllamaEmbeddingProvider(base_url="http://127.0.0.1:11499")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("httpx.AsyncClient.get", return_value=mock_resp) as mock_async_get:
        ok1 = await provider.check_availability_async()
        assert ok1 is True
        assert mock_async_get.call_count == 1

    with patch("httpx.Client.get") as mock_sync_get:
        # Should hit TTL cache without making a synchronous HTTP call
        assert provider.is_available is True
        assert mock_sync_get.call_count == 0

    OllamaEmbeddingProvider.clear_availability_cache()
