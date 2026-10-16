"""API Key Management with Sliding-Window Rate Limiting and Daily Budgets."""

import hashlib
import time
from typing import Dict, List, Optional

from app.core.exceptions import GatewayException


class RateLimitExceededError(GatewayException):
    """Raised when rate limit (RPM) or daily budget is exceeded."""

    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(
            message=message,
            status_code=429,
            error_code="rate_limit_exceeded",
            is_retryable=False,
            details={"retry_after": retry_after},
        )
        self.retry_after = retry_after


class ApiKeyPolicy:
    """Policy definition for a tenant or API key."""

    def __init__(
        self,
        name: str,
        rate_limit_rpm: int = 60,
        daily_token_budget: int = 0,  # 0 = unlimited
        daily_cost_budget: float = 0.0,  # 0.0 = unlimited
        allowed_models: Optional[List[str]] = None,
    ):
        self.name = name
        self.rate_limit_rpm = rate_limit_rpm
        self.daily_token_budget = daily_token_budget
        self.daily_cost_budget = daily_cost_budget
        self.allowed_models = allowed_models or []

        # State tracking
        self.request_timestamps: List[float] = []
        self.daily_tokens_used: int = 0
        self.daily_cost_used: float = 0.0
        self.current_day: int = int(time.time() // 86400)

    def _reset_if_new_day(self):
        day = int(time.time() // 86400)
        if day != self.current_day:
            self.daily_tokens_used = 0
            self.daily_cost_used = 0.0
            self.current_day = day

    def check_and_record_request(self, requested_model: str) -> None:
        """Enforces RPM and model authorization before request executes."""
        self._reset_if_new_day()

        # Check model whitelist
        if self.allowed_models and requested_model not in self.allowed_models:
            raise GatewayException(
                message=f"Model '{requested_model}' is not allowed for this API key. Allowed: {self.allowed_models}",
                status_code=403,
                error_code="model_not_allowed",
                is_retryable=False,
            )

        # Check RPM sliding window
        now = time.time()
        self.request_timestamps = [t for t in self.request_timestamps if now - t < 60.0]

        if self.rate_limit_rpm > 0 and len(self.request_timestamps) >= self.rate_limit_rpm:
            oldest = self.request_timestamps[0]
            retry_after = max(1, int(60.0 - (now - oldest)))
            raise RateLimitExceededError(
                message=f"Rate limit of {self.rate_limit_rpm} requests per minute exceeded.",
                retry_after=retry_after,
            )

        # Check daily token budget
        if self.daily_token_budget > 0 and self.daily_tokens_used >= self.daily_token_budget:
            raise RateLimitExceededError(
                message=f"Daily token budget of {self.daily_token_budget} tokens reached.",
                retry_after=3600,
            )

        # Check daily cost budget
        if self.daily_cost_budget > 0.0 and self.daily_cost_used >= self.daily_cost_budget:
            raise RateLimitExceededError(
                message=f"Daily cost budget of ${self.daily_cost_budget:.2f} reached.",
                retry_after=3600,
            )

        self.request_timestamps.append(now)

    def record_usage(self, tokens: int, cost_usd: float) -> None:
        """Updates daily token and cost consumption."""
        self._reset_if_new_day()
        self.daily_tokens_used += tokens
        self.daily_cost_used += cost_usd


class ApiKeyManager:
    """Manages active tenant API keys and policies."""

    def __init__(self):
        self._policies: Dict[str, ApiKeyPolicy] = {}

    def register_key(self, api_key: str, policy: ApiKeyPolicy) -> None:
        """Registers an API key with its policy."""
        key_hash = hashlib.sha256(api_key.strip().encode("utf-8")).hexdigest()
        self._policies[key_hash] = policy

    def get_policy(self, api_key: str) -> Optional[ApiKeyPolicy]:
        """Looks up policy by API key."""
        key_hash = hashlib.sha256(api_key.strip().encode("utf-8")).hexdigest()
        return self._policies.get(key_hash)


# Global singleton
api_key_manager = ApiKeyManager()
# Seed standard gateway policies
api_key_manager.register_key("gw-prod-key-1", ApiKeyPolicy(name="Production Tier", rate_limit_rpm=600))
api_key_manager.register_key("gw-free-tier", ApiKeyPolicy(name="Free Tier", rate_limit_rpm=10, daily_token_budget=10000))
api_key_manager.register_key("gw-test-rpm", ApiKeyPolicy(name="Test Low RPM", rate_limit_rpm=3))

