"""Abstract base provider adapter."""

from abc import ABC, abstractmethod

from app.api.schemas import ChatCompletionRequest, ChatCompletionResponse


class BaseProvider(ABC):
    """Abstract interface that all LLM provider adapters must implement."""

    def __init__(self, name: str, provider_type: str, enabled: bool = True):
        self.name = name
        self.provider_type = provider_type
        self.enabled = enabled

    @abstractmethod
    async def generate(
        self,
        request: ChatCompletionRequest,
        model: str,
        timeout: float,
    ) -> ChatCompletionResponse:
        """Executes a chat completion request and returns a normalized response."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Checks if the provider endpoint is healthy and reachable."""
        pass

    async def embed(self, texts: list[str], model: str) -> list[list[float]]:
        """Generates embedding vectors for a list of input strings."""
        raise NotImplementedError(f"Provider '{self.name}' does not support embeddings.")
