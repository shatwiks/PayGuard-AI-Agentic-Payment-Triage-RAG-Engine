"""Embedding provider interface and OpenAI-compatible client implementation."""

from abc import ABC, abstractmethod
import math
from typing import List, Optional
import httpx

from backend.app.core.config import settings
from backend.app.core.errors import PayGuardException


class EmbeddingProviderUnavailableException(PayGuardException):
    """Raised when an embedding provider is not configured, unreachable, or has invalid credentials."""
    def __init__(self, message: str = "Embedding provider credentials not configured"):
        super().__init__(
            message=message,
            code="EMBEDDING_PROVIDER_UNAVAILABLE",
            status_code=503,
        )


class EmbeddingValidationException(PayGuardException):
    """Raised when generated embedding vector has invalid dimensions, NaN, or Inf values."""
    def __init__(self, message: str):
        super().__init__(
            message=message,
            code="INVALID_EMBEDDING_VECTOR",
            status_code=422,
        )


class IEmbeddingProvider(ABC):
    """Abstract contract for text embedding generation providers."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Returns the model identifier (e.g. text-embedding-3-small)."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Returns vector dimensionality (e.g. 1536)."""
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Indicates whether credentials and network are configured for live inference."""
        pass

    @abstractmethod
    async def embed_query(self, text: str) -> List[float]:
        """Generates embedding for a single search query."""
        pass

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generates embeddings for a batch of text passages."""
        pass

    def validate_vector(self, vector: List[float]) -> List[float]:
        """Validates that vector matches target dimension and contains valid real numbers."""
        if not vector or len(vector) != self.dimension:
            raise EmbeddingValidationException(
                f"Embedding dimension mismatch: expected {self.dimension}, got {len(vector) if vector else 0}"
            )
        for i, val in enumerate(vector):
            if not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val):
                raise EmbeddingValidationException(
                    f"Invalid embedding value at index {i}: value must be a finite float, got {val}"
                )
        return vector


class OpenAIEmbeddingProvider(IEmbeddingProvider):
    """OpenAI-compatible embedding provider utilizing standard /v1/embeddings endpoint via HTTPX."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        dimension: Optional[int] = None,
        batch_size: Optional[int] = None,
        timeout: Optional[float] = None,
    ):
        self._api_key = api_key if api_key is not None else settings.OPENAI_API_KEY
        self._base_url = (base_url or settings.OPENAI_BASE_URL).rstrip("/")
        self._model = model or settings.EMBEDDING_MODEL
        self._dimension = dimension or settings.EMBEDDING_DIMENSION
        self._batch_size = batch_size or settings.EMBEDDING_BATCH_SIZE
        self._timeout = timeout or settings.EMBEDDING_TIMEOUT_SECONDS

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def is_available(self) -> bool:
        return bool(
            self._api_key
            and self._api_key.strip()
            and not self._api_key.startswith("your_openai")
        )

    async def embed_query(self, text: str) -> List[float]:
        if not text or not text.strip():
            raise EmbeddingValidationException("Cannot generate embedding for empty or blank query text.")
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not self.is_available:
            raise EmbeddingProviderUnavailableException(
                "OpenAI embedding provider credentials not configured (set OPENAI_API_KEY in environment)"
            )

        if not texts:
            return []

        for idx, t in enumerate(texts):
            if not t or not t.strip():
                raise EmbeddingValidationException(
                    f"Cannot generate embedding for empty or blank text at index {idx}."
                )

        all_embeddings: List[List[float]] = []

        # Process in chunks of configured batch_size
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            payload = {
                "input": batch,
                "model": self._model,
            }
            # Only specify dimensions if model supports it (text-embedding-3 series)
            if "text-embedding-3" in self._model:
                payload["dimensions"] = self._dimension

            headers = {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            }

            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(
                        f"{self._base_url}/embeddings",
                        json=payload,
                        headers=headers,
                    )
                    response.raise_for_status()
                    data = response.json()

                if not isinstance(data, dict) or "data" not in data or not isinstance(data["data"], list):
                    raise EmbeddingValidationException(
                        "Embedding provider response missing valid 'data' list."
                    )

                items = data["data"]
                if len(items) != len(batch):
                    raise EmbeddingValidationException(
                        f"Embedding provider returned {len(items)} embeddings for batch of size {len(batch)}."
                    )

                # Extract and order embeddings
                sorted_items = sorted(items, key=lambda x: x.get("index", 0) if isinstance(x, dict) else 0)
                for item in sorted_items:
                    if not isinstance(item, dict) or "embedding" not in item:
                        raise EmbeddingValidationException(
                            "Embedding provider item missing required 'embedding' key."
                        )
                    vec = self.validate_vector(item["embedding"])
                    all_embeddings.append(vec)

            except (EmbeddingValidationException, EmbeddingProviderUnavailableException):
                raise
            except httpx.HTTPStatusError as e:
                # Sanitize error to avoid leaking API key
                status_code = e.response.status_code if e.response else 500
                raise EmbeddingProviderUnavailableException(
                    f"Embedding provider API error (HTTP {status_code}): {e.response.text if e.response else 'Unknown error'}"
                )
            except (httpx.RequestError, httpx.TimeoutException) as e:
                raise EmbeddingProviderUnavailableException(
                    f"Embedding provider network connection failure: {type(e).__name__}"
                )

        return all_embeddings


class MockEmbeddingProvider(IEmbeddingProvider):
    """Controlled mock embedding provider strictly for deterministic unit tests."""

    def __init__(
        self,
        dimension: int = 1536,
        model_name: str = "mock-unit-test-embedding",
        available: bool = True,
        fixed_vector: Optional[List[float]] = None,
    ):
        self._dimension = dimension
        self._model_name = model_name
        self._available = available
        self._fixed_vector = fixed_vector

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def is_available(self) -> bool:
        return self._available

    async def embed_query(self, text: str) -> List[float]:
        if not self._available:
            raise EmbeddingProviderUnavailableException("Mock embedding provider offline")
        if not text or not text.strip():
            raise EmbeddingValidationException("Cannot generate embedding for empty or blank query text.")
        if self._fixed_vector:
            return self.validate_vector(self._fixed_vector)
        # Deterministic unit vector derived from text hash for test reproducibility
        import hashlib
        h = int(hashlib.sha256(text.encode()).hexdigest(), 16)
        vec = [0.0] * self._dimension
        idx = h % self._dimension
        vec[idx] = 1.0
        return self.validate_vector(vec)

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not self._available:
            raise EmbeddingProviderUnavailableException("Mock embedding provider offline")
        if not texts:
            return []
        for idx, t in enumerate(texts):
            if not t or not t.strip():
                raise EmbeddingValidationException(
                    f"Cannot generate embedding for empty or blank text at index {idx}."
                )
        return [await self.embed_query(t) for t in texts]


def get_embedding_provider() -> IEmbeddingProvider:
    """Factory creating the configured embedding provider."""
    provider_type = settings.EMBEDDING_PROVIDER.lower().strip()
    if provider_type == "openai":
        return OpenAIEmbeddingProvider()
    elif provider_type == "mock":
        return MockEmbeddingProvider(available=True)
    else:
        # Default to OpenAICompatible
        return OpenAIEmbeddingProvider()
