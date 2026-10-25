"""Embedding provider interface and OpenAI-compatible client implementation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import math
import time
from typing import Dict, List, Optional, Tuple
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


@dataclass
class EmbeddingModelSpec:
    """Formal specification for an embedding model, its native dimension, and projection policy."""
    model_name: str
    native_dimension: int
    target_dimension: int = 1536
    normalize_l2: bool = False
    pad_value: float = 0.0

    def adapt_vector(self, vector: List[float]) -> List[float]:
        """Validates numerical integrity and adapts vector dimension from native to target schema dimension."""
        if not vector or not isinstance(vector, (list, tuple)):
            raise EmbeddingValidationException(
                f"Embedding dimension mismatch: expected {self.target_dimension}, got {len(vector) if vector else 0}"
            )

        for i, val in enumerate(vector):
            if not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val):
                raise EmbeddingValidationException(
                    f"Invalid embedding value at index {i}: value must be a finite float, got {val}"
                )

        n = len(vector)
        # Exact match with target schema dimension
        if n == self.target_dimension:
            vec = list(vector)
            if self.normalize_l2:
                norm = math.sqrt(sum(x * x for x in vec))
                if norm > 1e-12:
                    vec = [x / norm for x in vec]
            return vec

        # Matches native dimension and can be zero-padded or Matryoshka-truncated to target_dimension
        if n == self.native_dimension:
            vec = list(vector)
            if self.native_dimension < self.target_dimension:
                if self.normalize_l2:
                    norm = math.sqrt(sum(x * x for x in vec))
                    if norm > 1e-12:
                        vec = [x / norm for x in vec]
                return vec + [self.pad_value] * (self.target_dimension - self.native_dimension)
            elif self.native_dimension > self.target_dimension:
                truncated = vec[: self.target_dimension]
                if self.normalize_l2:
                    norm = math.sqrt(sum(x * x for x in truncated))
                    if norm > 1e-12:
                        truncated = [x / norm for x in truncated]
                return truncated

        raise EmbeddingValidationException(
            f"Embedding dimension mismatch: expected {self.target_dimension}, got {n}"
        )


class EmbeddingModelRegistry:
    """Registry of known embedding model specifications and dimension projection policies."""

    _registry: Dict[str, EmbeddingModelSpec] = {
        "text-embedding-3-small": EmbeddingModelSpec(
            model_name="text-embedding-3-small",
            native_dimension=1536,
            target_dimension=1536,
        ),
        "text-embedding-3-large": EmbeddingModelSpec(
            model_name="text-embedding-3-large",
            native_dimension=1536,
            target_dimension=1536,
        ),
        "text-embedding-ada-002": EmbeddingModelSpec(
            model_name="text-embedding-ada-002",
            native_dimension=1536,
            target_dimension=1536,
        ),
        "nomic-embed-text": EmbeddingModelSpec(
            model_name="nomic-embed-text",
            native_dimension=768,
            target_dimension=1536,
        ),
        "all-minilm": EmbeddingModelSpec(
            model_name="all-minilm",
            native_dimension=384,
            target_dimension=1536,
        ),
        "mock-unit-test-embedding": EmbeddingModelSpec(
            model_name="mock-unit-test-embedding",
            native_dimension=1536,
            target_dimension=1536,
        ),
    }

    @classmethod
    def register(cls, spec: EmbeddingModelSpec) -> None:
        """Register or override an embedding model specification."""
        cls._registry[spec.model_name.lower().strip()] = spec

    @classmethod
    def get_spec(cls, model_name: str, target_dimension: Optional[int] = None) -> EmbeddingModelSpec:
        """Resolve model specification by model identifier or normalized alias."""
        clean_name = (model_name or "").lower().strip()
        spec = cls._registry.get(clean_name)
        if not spec:
            for key, registered_spec in cls._registry.items():
                if clean_name.startswith(key) or key in clean_name:
                    spec = registered_spec
                    break

        target_dim = target_dimension or (spec.target_dimension if spec else 1536)
        if spec:
            if spec.target_dimension != target_dim:
                return EmbeddingModelSpec(
                    model_name=spec.model_name,
                    native_dimension=spec.native_dimension,
                    target_dimension=target_dim,
                    normalize_l2=spec.normalize_l2,
                    pad_value=spec.pad_value,
                )
            return spec

        return EmbeddingModelSpec(
            model_name=model_name,
            native_dimension=target_dim,
            target_dimension=target_dim,
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

    @property
    def spec(self) -> EmbeddingModelSpec:
        """Returns the model specification governing dimension projection and validation."""
        if not hasattr(self, "_spec") or self._spec is None:
            self._spec = EmbeddingModelRegistry.get_spec(self.model_name, self.dimension)
        return self._spec

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
        return self.spec.adapt_vector(vector)


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
        self._spec = EmbeddingModelRegistry.get_spec(self._model, self._dimension)

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
        self._spec = EmbeddingModelRegistry.get_spec(self._model_name, self._dimension)

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


class OllamaEmbeddingProvider(IEmbeddingProvider):
    """Native Ollama embedding provider supporting open models like nomic-embed-text."""

    _AVAILABILITY_TTL_SECONDS: float = 30.0
    _availability_cache: Dict[str, Tuple[float, bool]] = {}

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        dimension: Optional[int] = None,
        batch_size: Optional[int] = None,
        timeout: Optional[float] = None,
    ):
        self._base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self._model = model or settings.OLLAMA_EMBED_MODEL
        self._dimension = dimension or settings.EMBEDDING_DIMENSION
        self._batch_size = batch_size or settings.EMBEDDING_BATCH_SIZE
        self._timeout = timeout or settings.EMBEDDING_TIMEOUT_SECONDS
        self._spec = EmbeddingModelRegistry.get_spec(self._model, self._dimension)

    @classmethod
    def clear_availability_cache(cls) -> None:
        """Clears cached Ollama server availability probes."""
        cls._availability_cache.clear()

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def is_available(self) -> bool:
        now = time.monotonic()
        cached = self._availability_cache.get(self._base_url)
        if cached is not None and (now - cached[0]) < self._AVAILABILITY_TTL_SECONDS:
            return cached[1]

        try:
            with httpx.Client(timeout=1.5) as client:
                resp = client.get(f"{self._base_url}/api/version")
                ok = resp.status_code == 200
                self._availability_cache[self._base_url] = (now, ok)
                return ok
        except Exception:
            self._availability_cache[self._base_url] = (now, False)
            return False

    async def check_availability_async(self) -> bool:
        """Non-blocking async availability check with TTL caching."""
        now = time.monotonic()
        cached = self._availability_cache.get(self._base_url)
        if cached is not None and (now - cached[0]) < self._AVAILABILITY_TTL_SECONDS:
            return cached[1]

        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                resp = await client.get(f"{self._base_url}/api/version")
                ok = resp.status_code == 200
                self._availability_cache[self._base_url] = (now, ok)
                return ok
        except Exception:
            self._availability_cache[self._base_url] = (now, False)
            return False

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        for idx, t in enumerate(texts):
            if not t or not t.strip():
                raise EmbeddingValidationException(
                    f"Cannot generate embedding for empty or blank text at index {idx}."
                )

        all_embeddings: List[List[float]] = []
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                for i in range(0, len(texts), self._batch_size):
                    batch = texts[i : i + self._batch_size]
                    # Modern Ollama batch embedding endpoint (/api/embed)
                    resp = await client.post(
                        f"{self._base_url}/api/embed",
                        json={"model": self._model, "input": batch},
                    )
                    if resp.status_code == 404 and "endpoint not found" in resp.text.lower():
                        # Legacy fallback for older Ollama versions (< 0.1.44)
                        return await self._legacy_embed_batch(client, texts)

                    resp.raise_for_status()
                    data = resp.json()
                    raw_list = data.get("embeddings", [])
                    if not raw_list or len(raw_list) != len(batch):
                        raise EmbeddingProviderUnavailableException(
                            f"Ollama /api/embed returned {len(raw_list)} embeddings for {len(batch)} input texts."
                        )

                    for raw_vec in raw_list:
                        validated = self.validate_vector(raw_vec)
                        all_embeddings.append(validated)
                return all_embeddings
            except (EmbeddingValidationException, EmbeddingProviderUnavailableException):
                raise
            except httpx.HTTPStatusError as e:
                raise EmbeddingProviderUnavailableException(f"Ollama API error: {e}")
            except Exception as e:
                raise EmbeddingProviderUnavailableException(f"Ollama connection error: {e}")

    async def _legacy_embed_batch(self, client: httpx.AsyncClient, texts: List[str]) -> List[List[float]]:
        """Serial fallback for older Ollama endpoints that only support /api/embeddings."""
        results: List[List[float]] = []
        for text in texts:
            resp = await client.post(
                f"{self._base_url}/api/embeddings",
                json={"model": self._model, "prompt": text},
            )
            resp.raise_for_status()
            data = resp.json()
            raw_vec = data.get("embedding", [])
            results.append(self.validate_vector(raw_vec))
        return results

    async def embed_query(self, text: str) -> List[float]:
        if not text or not text.strip():
            raise EmbeddingValidationException("Cannot generate embedding for empty or blank query text.")
        res = await self.embed_batch([text])
        return res[0]


def get_embedding_provider() -> IEmbeddingProvider:
    """Factory creating the configured embedding provider."""
    provider_type = settings.EMBEDDING_PROVIDER.lower().strip()
    if provider_type == "ollama":
        return OllamaEmbeddingProvider()
    elif provider_type == "mock":
        return MockEmbeddingProvider(available=True)
    elif provider_type == "openai":
        return OpenAIEmbeddingProvider()
    else:
        # Default to OpenAICompatible
        return OpenAIEmbeddingProvider()

