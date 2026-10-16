"""Unit tests for Gateway CLI and Python Client SDK."""

import httpx
import pytest

from app.cli import cmd_doctor
from gateway_client import (
    AsyncGatewayClient,
    AuthError,
    GatewayClient,
    GatewayError,
    RateLimitError,
)
from gateway_client.client import _map_error


def test_doctor_runs_without_crashing(capsys):
    cmd_doctor()
    captured = capsys.readouterr().out
    assert "LLM Gateway" in captured or "DOCTOR" in captured
    assert "Python Version" in captured
    assert "SQLite Persistence" in captured


def test_error_mapping():
    err_429 = _map_error(429, '{"error": {"message": "Rate limit exceeded", "code": "rate_limit_exceeded"}}')
    assert isinstance(err_429, RateLimitError)
    assert err_429.status_code == 429
    assert "Rate limit exceeded" in err_429.message

    err_401 = _map_error(401, '{"error": {"message": "Invalid API key", "code": "invalid_api_key"}}')
    assert isinstance(err_401, AuthError)
    assert err_401.status_code == 401

    err_500 = _map_error(500, '{"error": {"message": "Server failure", "code": "server_error"}}')
    assert isinstance(err_500, GatewayError)
    assert err_500.status_code == 500


def test_sync_gateway_client_mock():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok", "app": "LLM-Gateway"})
        if request.url.path == "/v1/chat/completions":
            return httpx.Response(
                200,
                json={
                    "id": "cmpl-sdk-test",
                    "choices": [{"message": {"role": "assistant", "content": "SDK test response"}}],
                    "usage": {"total_tokens": 15},
                    "cached": False,
                },
            )
        return httpx.Response(404)

    client = GatewayClient(base_url="http://testgateway:8000")
    # Monkeypatch transport on httpx.Client calls
    real_client_init = httpx.Client.__init__

    def fake_client_init(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(mock_handler)
        real_client_init(self, *args, **kwargs)

    httpx.Client.__init__ = fake_client_init
    try:
        health = client.health()
        assert health["status"] == "ok"

        res = client.chat.completions.create(
            model="cheap",
            messages=[{"role": "user", "content": "Ping"}],
        )
        assert res["choices"][0]["message"]["content"] == "SDK test response"
    finally:
        httpx.Client.__init__ = real_client_init


@pytest.mark.asyncio
async def test_async_gateway_client_mock():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/ready":
            return httpx.Response(200, json={"status": "healthy", "offline_mode": True})
        if request.url.path == "/v1/chat/completions":
            return httpx.Response(
                200,
                json={
                    "id": "cmpl-async-sdk",
                    "choices": [{"message": {"role": "assistant", "content": "Async SDK response"}}],
                    "usage": {"total_tokens": 10},
                    "cached": True,
                },
            )
        return httpx.Response(404)

    async_client = AsyncGatewayClient(base_url="http://testgateway:8000")
    real_async_init = httpx.AsyncClient.__init__

    def fake_async_init(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(mock_handler)
        real_async_init(self, *args, **kwargs)

    httpx.AsyncClient.__init__ = fake_async_init
    try:
        ready = await async_client.ready()
        assert ready["status"] == "healthy"
        assert ready["offline_mode"] is True

        res = await async_client.chat.completions.create(
            model="balanced",
            messages=[{"role": "user", "content": "Async ping"}],
        )
        assert res["choices"][0]["message"]["content"] == "Async SDK response"
        assert res["cached"] is True
    finally:
        httpx.AsyncClient.__init__ = real_async_init
