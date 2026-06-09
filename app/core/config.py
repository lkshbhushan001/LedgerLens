"""Application configuration via Pydantic Settings."""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """All application settings loaded from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    APP_NAME: str = "Financial RAG API"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # --- Security ---
    SECRET_KEY: str = Field(..., min_length=32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ALGORITHM: str = "HS256"

    # --- Qdrant ---
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION: str = "financial_documents"

    # --- Embeddings ---
    EMBEDDING_MODEL: str = "BAAI/bge-large-en-v1.5"
    EMBEDDING_DEVICE: str = "cpu"

    # --- LLM ---
    GROQ_API_KEY: str
    ROUTER_MODEL: str = "llama-3.3-70b-versatile"
    SYNTHESIS_MODEL: str = "llama-3.2-90b-vision-preview"
    VISION_MODEL: str = "llama-3.2-90b-vision-preview"
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 2048

    # --- LlamaParse ---
    LLAMA_CLOUD_API_KEY: str | None = None

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Reranker ---
    RERANKER_MODEL: str = "BAAI/bge-reranker-large"

    # --- OTel ---
    OTEL_SERVICE_NAME: str = "financial-rag"
    OTEL_EXPORTER_OTLP_ENDPOINT: str | None = None

    @field_validator("EMBEDDING_DEVICE", mode="before")
    @classmethod
    def _validate_device(cls, v: str) -> str:
        allowed = {"cpu", "cuda", "mps"}
        if v not in allowed:
            raise ValueError(f"EMBEDDING_DEVICE must be one of {allowed}")
        return v

    @field_validator("ENVIRONMENT")
    @classmethod
    def _validate_env(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of {allowed}")
        return v


settings = Settings()
