"""Provider registry for managing and discovering configured adapters."""

from typing import Dict, List, Optional

from app.core.config import Settings
from app.providers.base import BaseProvider
from app.providers.local import LocalProvider
from app.providers.mock import MockProvider
from app.providers.openai_compatible import OpenAICompatibleProvider


class ProviderRegistry:
    """Manages active LLM provider adapters."""

    def __init__(self):
        self._providers: Dict[str, BaseProvider] = {}

    def register(self, provider: BaseProvider) -> None:
        """Registers a provider adapter."""
        self._providers[provider.name] = provider

    def get(self, name: str) -> Optional[BaseProvider]:
        """Retrieves a provider by its identifier."""
        return self._providers.get(name)

    def list_all(self) -> List[BaseProvider]:
        """Returns all registered providers."""
        return list(self._providers.values())

    async def health_check_all(self) -> Dict[str, bool]:
        """Runs health checks on all registered providers."""
        results = {}
        for name, provider in self._providers.items():
            if not provider.enabled:
                results[name] = False
                continue
            try:
                results[name] = await provider.health_check()
            except Exception:
                results[name] = False
        return results


def build_provider_registry(settings: Settings) -> ProviderRegistry:
    """Initializes and configures all provider adapters based on application settings."""
    registry = ProviderRegistry()

    # Register Mock Primary Provider
    mock_primary = MockProvider(
        name="mock-primary",
        enabled=settings.mock_primary_enabled,
        latency_ms=settings.mock_primary_latency_ms,
        failure_rate=settings.mock_primary_failure_rate,
    )
    registry.register(mock_primary)

    # Register Mock Secondary Provider
    mock_secondary = MockProvider(
        name="mock-secondary",
        enabled=settings.mock_secondary_enabled,
        latency_ms=settings.mock_secondary_latency_ms,
        failure_rate=settings.mock_secondary_failure_rate,
    )
    registry.register(mock_secondary)

    # Register Local Provider (Ollama / LM Studio / llama.cpp / vLLM)
    local_provider = LocalProvider(
        name="local",
        base_url=settings.local_base_url,
        default_model=settings.local_models.split(",")[0].strip() if settings.local_models else "llama3.2",
        timeout_seconds=settings.local_timeout_seconds,
        enabled=settings.local_enabled,
    )
    registry.register(local_provider)

    # Register OpenAI Main Provider
    openai_main = OpenAICompatibleProvider(
        name="openai-main",
        base_url=settings.openai_main_base_url,
        api_key=settings.openai_main_api_key,
        default_model=settings.openai_main_default_model,
        timeout_seconds=settings.openai_main_timeout_seconds,
        enabled=settings.openai_main_enabled,
    )
    registry.register(openai_main)

    # Register OpenAI Backup Provider
    openai_backup = OpenAICompatibleProvider(
        name="openai-backup",
        base_url=settings.openai_backup_base_url,
        api_key=settings.openai_backup_api_key,
        default_model=settings.openai_backup_default_model,
        timeout_seconds=settings.openai_backup_timeout_seconds,
        enabled=settings.openai_backup_enabled,
    )
    registry.register(openai_backup)

    return registry
