"""Application settings using Pydantic Settings."""

from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide configuration loaded from environment variables."""

    # Server configuration
    app_name: str = "LLM-Gateway"
    environment: str = "development"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # Gateway API key for inbound requests (if None or empty, authentication is disabled)
    gateway_api_key: Optional[str] = None

    # CORS Configuration
    cors_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:8000"]
    )

    # Redis Cache Configuration
    cache_enabled: bool = True
    redis_url: str = "redis://localhost:6379/0"
    cache_default_ttl_seconds: int = 3600
    cache_lock_timeout_seconds: float = 10.0
    cache_schema_version: str = "v1"

    # Persistence (Async SQLite)
    database_url: str = "sqlite+aiosqlite:///./gateway.db"

    # Resilience & Timeouts (Seconds)
    request_overall_timeout_seconds: float = 30.0
    provider_timeout_seconds: float = 10.0
    max_retries: int = 3
    retry_min_wait_seconds: float = 0.5
    retry_max_wait_seconds: float = 4.0

    # Circuit Breaker settings
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout_seconds: float = 30.0
    circuit_breaker_half_open_successes: int = 2

    # OpenAI Primary Provider
    openai_main_enabled: bool = False
    openai_main_base_url: str = "https://api.openai.com/v1"
    openai_main_api_key: Optional[str] = None
    openai_main_default_model: str = "gpt-4o-mini"
    openai_main_timeout_seconds: float = 15.0

    # OpenAI Backup Provider (Groq / Together / OpenRouter / vLLM)
    openai_backup_enabled: bool = False
    openai_backup_base_url: str = "https://api.groq.com/openai/v1"
    openai_backup_api_key: Optional[str] = None
    openai_backup_default_model: str = "llama-3.1-8b-instant"
    openai_backup_timeout_seconds: float = 15.0

    # Mock Providers
    mock_primary_enabled: bool = True
    mock_primary_latency_ms: int = 15
    mock_primary_failure_rate: float = 0.0

    mock_secondary_enabled: bool = True
    mock_secondary_latency_ms: int = 25
    mock_secondary_failure_rate: float = 0.0

    # Config file paths
    models_config_path: str = "config/models.yaml"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


# Global settings singleton
settings = Settings()
