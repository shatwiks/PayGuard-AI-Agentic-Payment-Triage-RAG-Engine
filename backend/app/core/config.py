"""Application configuration settings using pydantic-settings."""

from typing import List, Optional, Union
from pydantic import AnyHttpUrl, field_validator
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
    EMBEDDING_BATCH_SIZE: int = 32
    EMBEDDING_TIMEOUT_SECONDS: float = 15.0
    RAG_TOP_K: int = 5
    RETRIEVAL_HYBRID_RRF_K: int = 60
    RETRIEVAL_LEXICAL_WEIGHT: float = 1.0
    RETRIEVAL_SEMANTIC_WEIGHT: float = 1.0

    # Security & Reliability (Phase 6)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 15
    RATE_LIMIT_INVESTIGATIONS_PER_MINUTE: int = 40
    RATE_LIMIT_SEARCH_PER_MINUTE: int = 60
    REQUEST_MAX_BODY_BYTES: int = 1_048_576  # 1 MB
    PROMPT_INJECTION_DEFENSE_ENABLED: bool = True
    INVESTIGATION_IDEMPOTENCY_WINDOW_SECONDS: int = 15

    # CORS

    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)


settings = Settings()
