"""FastAPI dependency injection providers."""

import secrets
from typing import Optional

from fastapi import Header, HTTPException, Request, status

from app.core.config import settings
from app.services.gateway import GatewayService


def verify_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> bool:
    """Validates the client API key if GATEWAY_API_KEY is configured in settings."""
    expected_key = settings.gateway_api_key
    if not expected_key:
        return True  # Auth is disabled in dev / unconfigured mode

    # Check X-API-Key
    if x_api_key and secrets.compare_digest(x_api_key.strip(), expected_key.strip()):
        return True

    # Check Authorization: Bearer <key>
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        if secrets.compare_digest(token, expected_key.strip()):
            return True

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing Gateway API key",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_gateway_service(request: Request) -> GatewayService:
    """Extracts the GatewayService singleton attached to FastAPI app state."""
    return request.app.state.gateway_service
