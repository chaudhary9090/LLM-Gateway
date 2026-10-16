"""Domain exception hierarchy for the LLM Gateway."""

from typing import Any, Dict, Optional


class GatewayException(Exception):
    """Base exception for all LLM Gateway errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "gateway_error",
        is_retryable: bool = False,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.is_retryable = is_retryable
        self.details = details or {}


class AuthenticationError(GatewayException):
    """Raised when client API key is missing or invalid."""

    def __init__(self, message: str = "Invalid or missing Gateway API key"):
        super().__init__(
            message=message,
            status_code=401,
            error_code="invalid_api_key",
            is_retryable=False,
        )


class InvalidRequestError(GatewayException):
    """Raised when request parameters or payload are invalid."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=400,
            error_code="invalid_request_error",
            is_retryable=False,
            details=details,
        )


class ModelNotFoundError(GatewayException):
    """Raised when the requested model or alias cannot be resolved."""

    def __init__(self, model_name: str):
        super().__init__(
            message=f"Model or alias '{model_name}' was not found in catalog.",
            status_code=404,
            error_code="model_not_found",
            is_retryable=False,
            details={"model": model_name},
        )


class ProviderException(GatewayException):
    """Base exception for provider-specific upstream errors."""

    def __init__(
        self,
        provider_name: str,
        message: str,
        status_code: int = 502,
        error_code: str = "provider_error",
        is_retryable: bool = False,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        details["provider"] = provider_name
        super().__init__(
            message=f"Provider '{provider_name}' error: {message}",
            status_code=status_code,
            error_code=error_code,
            is_retryable=is_retryable,
            details=details,
        )
        self.provider_name = provider_name


class ProviderAuthError(ProviderException):
    """Raised when provider rejects credentials (HTTP 401/403). Non-retryable."""

    def __init__(self, provider_name: str, message: str = "Authentication failed at provider"):
        super().__init__(
            provider_name=provider_name,
            message=message,
            status_code=502,
            error_code="provider_auth_error",
            is_retryable=False,
        )


class ProviderRateLimitError(ProviderException):
    """Raised when provider returns HTTP 429. Transient, retryable."""

    def __init__(
        self,
        provider_name: str,
        message: str = "Rate limit exceeded at provider",
        retry_after: Optional[float] = None,
    ):
        details = {}
        if retry_after is not None:
            details["retry_after"] = retry_after
        super().__init__(
            provider_name=provider_name,
            message=message,
            status_code=429,
            error_code="provider_rate_limit",
            is_retryable=True,
            details=details,
        )
        self.retry_after = retry_after


class ProviderTimeoutError(ProviderException):
    """Raised when provider call times out. Transient, retryable."""

    def __init__(self, provider_name: str, message: str = "Provider call timed out"):
        super().__init__(
            provider_name=provider_name,
            message=message,
            status_code=504,
            error_code="provider_timeout",
            is_retryable=True,
        )


class ProviderConnectionError(ProviderException):
    """Raised on network/connection drop to provider. Transient, retryable."""

    def __init__(self, provider_name: str, message: str = "Failed to connect to provider"):
        super().__init__(
            provider_name=provider_name,
            message=message,
            status_code=503,
            error_code="provider_connection_error",
            is_retryable=True,
        )


class ProviderServerError(ProviderException):
    """Raised when provider returns HTTP 5xx. Transient, retryable."""

    def __init__(self, provider_name: str, message: str = "Internal server error from provider"):
        super().__init__(
            provider_name=provider_name,
            message=message,
            status_code=502,
            error_code="provider_server_error",
            is_retryable=True,
        )


class ProviderMalformedResponseError(ProviderException):
    """Raised when provider returns non-JSON or invalid schema. Non-retryable on this provider."""

    def __init__(
        self, provider_name: str, message: str = "Provider returned invalid or malformed response"
    ):
        super().__init__(
            provider_name=provider_name,
            message=message,
            status_code=502,
            error_code="provider_malformed_response",
            is_retryable=False,
        )


class CircuitBreakerOpenError(GatewayException):
    """Raised when attempting to route to a provider whose circuit breaker is OPEN."""

    def __init__(self, provider_name: str, reset_in_seconds: float):
        super().__init__(
            message=f"Circuit breaker for provider '{provider_name}' is OPEN. Retry after {reset_in_seconds:.1f}s.",
            status_code=503,
            error_code="circuit_breaker_open",
            is_retryable=False,
            details={"provider": provider_name, "reset_in_seconds": reset_in_seconds},
        )
        self.provider_name = provider_name
        self.reset_in_seconds = reset_in_seconds


class RequestTimeoutError(GatewayException):
    """Raised when the total end-to-end request budget/deadline expires."""

    def __init__(self, deadline_seconds: float):
        super().__init__(
            message=f"Total request budget of {deadline_seconds:.1f}s exceeded.",
            status_code=504,
            error_code="request_deadline_exceeded",
            is_retryable=False,
        )


class AllProvidersFailedError(GatewayException):
    """Raised when every eligible provider in the fallback chain fails."""

    def __init__(self, attempts: list):
        super().__init__(
            message="All attempted providers in the fallback chain failed.",
            status_code=502,
            error_code="all_providers_failed",
            is_retryable=False,
            details={"attempts": attempts},
        )
        self.attempts = attempts
