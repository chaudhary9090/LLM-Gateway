"""FastAPI dependency injection providers with multi-key budget & rate limit enforcement."""

import secrets
from typing import Optional

from fastapi import Header, HTTPException, Request, status

from app.core.config import settings
from app.persistence.api_keys import api_key_manager
from app.services.gateway import GatewayService


def verify_api_key(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> bool:
    """Validates the client API key and enforces per-key RPM rate limits and budgets."""
    raw_key = None
    if x_api_key:
        raw_key = x_api_key.strip()
    elif authorization and authorization.lower().startswith("bearer "):
        raw_key = authorization[7:].strip()

    expected_key = settings.gateway_api_key

    # Check registered tenant policies first
    if raw_key:
        policy = api_key_manager.get_policy(raw_key)
        if policy:
            request.state.api_key_policy = policy
            policy.check_and_record_request(requested_model="")
            return True


    # Check global default key
    if expected_key:
        if raw_key and secrets.compare_digest(raw_key, expected_key.strip()):
            return True
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Gateway API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Auth not enforced
    return True


def get_gateway_service(request: Request) -> GatewayService:
    """Extracts the GatewayService singleton attached to FastAPI app state."""
    return request.app.state.gateway_service
