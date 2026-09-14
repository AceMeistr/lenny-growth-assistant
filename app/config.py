"""
Global application settings and environment variable parsing.
"""

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Immutable application settings validated via Pydantic."""
    
    app_env: str = Field(default="development", alias="APP_ENV")
    app_port: int = Field(default=8000, alias="APP_PORT")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Database configuration (Postgres with pgvector or SQLite fallback)
    database_url: str = Field(
        default="sqlite:///./data/lenny.db",
        alias="DATABASE_URL"
    )

    # LLM Provider configuration ('anthropic' or 'ollama')
    llm_provider: str = Field(default="ollama", alias="LLM_PROVIDER")
    llm_model: str = Field(default="phi3", alias="LLM_MODEL")
    anthropic_model: str = Field(default="claude-3-5-sonnet-20241022", alias="ANTHROPIC_MODEL")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")

    # Ollama settings
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="phi3", alias="OLLAMA_MODEL")
    ollama_embed_model: str = Field(default="phi3", alias="OLLAMA_EMBED_MODEL")

    # Resilience & Fallback
    llm_fallback_to_local: bool = Field(default=True, alias="LLM_FALLBACK_TO_LOCAL")
    request_timeout_seconds: int = Field(default=60, alias="REQUEST_TIMEOUT_SECONDS")

    # RAG / Retrieval parameters
    similarity_threshold: float = Field(default=0.90, alias="SIMILARITY_THRESHOLD")
    retrieval_top_k: int = Field(default=6, alias="RETRIEVAL_TOP_K")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


# Singleton settings instance
settings = Settings()
