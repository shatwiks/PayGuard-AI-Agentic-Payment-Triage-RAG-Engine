"""Application configuration settings using pydantic-settings."""

from typing import List, Optional, Union
from pydantic import AnyHttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly typed application configuration."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "PayGuard AI: Agentic Payment Triage and RAG Engine"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False
    APP_ENV: str = "development"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./payguard_dev.db"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "payguard_user"
    POSTGRES_PASSWORD: str = "payguard_secure_password"
    POSTGRES_DB: str = "payguard_db"

    # Security & Auth
    SECRET_KEY: str = "dev_secret_key_change_in_production_8f7b2a9e1d4c5e6f"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    MASK_PII_ENABLED: bool = True

    # RAG & Embedding Settings (pgvector + Hybrid Search)
    EMBEDDING_PROVIDER: str = "openai"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536
    EMBEDDING_BATCH_SIZE: int = 16
    EMBEDDING_TIMEOUT_SECONDS: float = 60.0
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"
    OLLAMA_LLM_MODEL: str = "llama3.1:8b"
    LLM_PROVIDER: str = "mock"
    RAG_TOP_K: int = 5
    RETRIEVAL_HYBRID_RRF_K: int = 60
    RETRIEVAL_LEXICAL_WEIGHT: float = 1.0
    RETRIEVAL_SEMANTIC_WEIGHT: float = 1.0

    # Phase 2: Hierarchical Chunking Settings
    CHUNK_PARENT_SIZE: int = 1000
    CHUNK_PARENT_OVERLAP: int = 100
    CHUNK_CHILD_SIZE: int = 200
    CHUNK_CHILD_OVERLAP: int = 30
    CHUNK_TABLE_AWARE_ENABLED: bool = True

    # Security & Reliability (Phase 6)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 15
    RATE_LIMIT_INVESTIGATIONS_PER_MINUTE: int = 40
    RATE_LIMIT_SEARCH_PER_MINUTE: int = 60
    RATE_LIMIT_UPLOAD_PER_MINUTE: int = 15
    REDIS_URL: Optional[str] = None
    RATE_LIMIT_REQUIRE_REDIS: Optional[bool] = None
    TRUSTED_PROXIES: Union[str, List[str]] = [
        "127.0.0.1",
        "::1",
    ]
    REQUEST_MAX_BODY_BYTES: int = 1_048_576  # 1 MB
    UPLOAD_MAX_FILE_SIZE_BYTES: int = 10_485_760  # 10 MB
    UPLOAD_ALLOWED_EXTENSIONS: List[str] = [".pdf", ".txt"]
    UPLOAD_STORAGE_DIR: str = "./storage/uploads"
    PROMPT_INJECTION_DEFENSE_ENABLED: bool = True
    INVESTIGATION_IDEMPOTENCY_WINDOW_SECONDS: int = 15

    # CORS

    BACKEND_CORS_ORIGINS: Union[str, List[str]] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="after")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return [str(i).strip() for i in v]
        raise ValueError(v)

    @field_validator("TRUSTED_PROXIES", mode="after")
    @classmethod
    def assemble_trusted_proxies(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return [str(i).strip() for i in v]
        raise ValueError(v)

    @model_validator(mode="after")
    def validate_production_and_staging_settings(self) -> "Settings":
        env = (self.APP_ENV or "").lower()
        if env in ("production", "staging"):
            insecure_secret = "dev_secret_key_change_in_production_8f7b2a9e1d4c5e6f"
            if not self.SECRET_KEY or self.SECRET_KEY == insecure_secret or len(self.SECRET_KEY) < 32:
                raise ValueError(
                    f"Insecure or missing SECRET_KEY in '{self.APP_ENV}' environment! "
                    "SECRET_KEY must not use default development values and must be at least 32 characters long."
                )
            if self.DEBUG:
                raise ValueError(
                    f"DEBUG cannot be True in '{self.APP_ENV}' environment."
                )
            if "sqlite" in self.DATABASE_URL.lower():
                raise ValueError(
                    f"SQLite database is not permitted in '{self.APP_ENV}' environment. "
                    "A production-grade PostgreSQL database with pgvector is required."
                )
        return self


settings = Settings()
